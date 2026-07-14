# -*- coding: utf-8 -*-
"""
===================================
股票数据接口
===================================

职责：
1. POST /api/v1/stocks/extract-from-image 从图片提取股票代码
2. POST /api/v1/stocks/parse-import 解析 CSV/Excel/剪贴板
3. GET /api/v1/stocks/{code}/quote 实时行情接口
4. GET /api/v1/stocks/{code}/history 历史行情接口
"""

import logging
import os
from typing import Optional
import re

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Depends

from api.deps import get_system_config_service

from api.v1.schemas.basic_query import (
    BasicMarketSourceOpsResponse,
    BasicMarketSourceRecoveryRequest,
    BasicMarketSourceRecoveryResponse,
    BasicPrewarmRequest,
    BasicPrewarmResponse,
    BasicStockSnapshot,
    FinancialResearchWorkflowResponse,
    KronosForecastResponse,
)
from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
)
from api.v1.schemas.history import WatchlistRequest, WatchlistResponse
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService
from src.services.basic_query_service import BasicQueryService
from src.services.a_share_enrichment_service import AShareEnrichmentService
from src.services.kronos_forecast_service import KronosForecastService
from src.services.financial_research_workflow_service import FinancialResearchWorkflowService
from src.services.global_equity_enrichment_service import GlobalEquityEnrichmentService
from src.services.market_source_ops import build_market_source_ops_snapshot, recover_market_sources
from src.services.stock_code_utils import normalize_crypto_symbol
from src.services.system_config_service import SystemConfigService
from src.auth import COOKIE_NAME, verify_session
from src.platform_accounts import PlatformIdentity, platform_identity_from_request
from src.platform_rate_limit import check_platform_rate_limit
from data_provider.base import normalize_stock_code

logger = logging.getLogger(__name__)

router = APIRouter()

# 须在 /{stock_code} 路由之前定义
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


def _global_equity_enrichment_service_from_env() -> Optional[GlobalEquityEnrichmentService]:
    enabled = str(os.getenv("GLOBAL_EQUITY_ENRICHMENT_ENABLED", "false")).strip().lower()
    return GlobalEquityEnrichmentService() if enabled in {"1", "true", "yes", "on"} else None


def _read_watchlist_codes(service: SystemConfigService) -> list:
    """Read STOCK_LIST codes as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    stock_list_str = ""
    for item in config_data.get("items", []):
        if item.get("key") == "STOCK_LIST":
            stock_list_str = str(item.get("value", ""))
            break
    return [c.strip() for c in stock_list_str.split(",") if c.strip()]


def _write_watchlist_codes(service: SystemConfigService, codes: list) -> None:
    """Persist stock codes to STOCK_LIST as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    config_version = config_data.get("config_version", "")
    service.update(
        config_version=config_version,
        items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
        mask_token="******",
        reload_now=True,
    )


# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    """Validate stock code format and return canonical form.

    Raises HTTPException(400) if the code does not match supported formats.
    """
    stripped = code.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "股票代码不能为空"},
        )
    crypto_symbol = normalize_crypto_symbol(stripped)
    if crypto_symbol is not None:
        return crypto_symbol
    if not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_stock_code",
                "message": f"'{stripped}' 不是合法的股票代码格式",
            },
        )
    return normalize_stock_code(stripped)


def _require_stock_admin_identity(request: Request) -> PlatformIdentity:
    admin_cookie = request.cookies.get(COOKIE_NAME)
    if admin_cookie and verify_session(admin_cookie):
        return PlatformIdentity(
            user_id=None,
            email="admin",
            role="admin",
            plan="enterprise",
            is_admin=True,
        )

    identity = platform_identity_from_request(request)
    if identity is None or not identity.is_admin:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Admin role required"})
    return identity


def _watchlist_match_key(code: str) -> str:
    """Return the equivalence key used for watchlist add/remove matching."""
    normalized = normalize_stock_code(code.strip())
    if re.fullmatch(r"\d{5}", normalized):
        return f"HK{normalized}"
    return normalized.upper()


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "提取的股票代码"},
        400: {"description": "图片无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从图片提取股票代码",
    description="上传截图/图片，通过 Vision LLM 提取股票代码。支持 JPEG、PNG、WebP、GIF，最大 5MB。",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="图片文件（表单字段名 file）"),
    include_raw: bool = Query(False, description="是否在结果中包含原始 LLM 响应"),
) -> ExtractFromImageResponse:
    """
    从上传的图片中提取股票代码（使用 Vision LLM）。

    表单字段请使用 file 上传图片。优先级：Gemini / Anthropic / OpenAI（首个可用）。
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file 上传图片"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"不支持的类型: {content_type}。允许: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # 先读取限定大小，再检查是否还有剩余（语义清晰：超出则拒绝）
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"图片超过 {MAX_SIZE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"读取上传文件失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "读取上传文件失败"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"图片提取失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "图片提取失败"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "解析结果"},
        400: {"description": "未提供数据或解析失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析 CSV/Excel/剪贴板",
    description="上传 CSV/Excel 文件或粘贴文本，自动解析股票代码。文件上限 2MB，文本上限 100KB。",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    解析 CSV/Excel 文件或剪贴板文本。

    - multipart/form-data + file: 上传文件
    - application/json + {"text": "..."}: 粘贴文本
    - 优先使用 file，若同时提供则忽略 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON 解析失败: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供 text，请使用 {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "读取文件失败"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "请使用 multipart/form-data 上传文件，或 application/json 提交 {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "当前自选队列"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取自选队列",
    description="返回当前 STOCK_LIST 配置中的所有股票代码。",
)
def get_watchlist(
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        codes = _read_watchlist_codes(service)
        return WatchlistResponse(stock_codes=codes, message=f"当前自选 {len(codes)} 只股票")
    except Exception as e:
        logger.error(f"获取自选队列失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取自选队列失败: {str(e)}"},
        )


@router.post(
    "/watchlist/add",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已加入自选"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="加入自选队列",
    description="将指定股票代码加入 STOCK_LIST。",
)
def add_to_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        if _watchlist_match_key(validated) not in existing_keys:
            codes.append(request.stock_code.strip())
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"已加入 {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加入自选失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"加入自选失败: {str(e)}"},
        )


@router.post(
    "/watchlist/remove",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已从自选删除"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从自选队列删除",
    description="从 STOCK_LIST 中移除指定股票代码。",
)
def remove_from_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        requested_key = _watchlist_match_key(validated)
        if requested_key in existing_keys:
            idx = existing_keys.index(requested_key)
            codes.pop(idx)
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"已移除 {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从自选删除失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"从自选删除失败: {str(e)}"},
        )


@router.post(
    "/prewarm",
    response_model=BasicPrewarmResponse,
    responses={
        200: {"description": "No-AI local prewarm summary"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="Prewarm no-AI market data cache",
    description="Prewarm deterministic market data snapshots without invoking AI.",
)
def prewarm_basic_stock_snapshots(request: BasicPrewarmRequest) -> BasicPrewarmResponse:
    """Prewarm a small local cache for quick snapshots without invoking AI."""
    try:
        symbols = request.symbols or ["600519", "AAPL", "HK00700", "BTC-USD"]
        normalized = [_validate_and_normalize_stock_code(symbol) for symbol in symbols]
        summary = BasicQueryService().prewarm_snapshots(normalized)
        return BasicPrewarmResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("No-AI market prewarm failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"No-AI market prewarm failed: {str(e)}"},
        )


@router.get(
    "/sources/health",
    response_model=BasicMarketSourceOpsResponse,
    responses={
        200: {"description": "Local no-AI market source health and priority summary"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Local market source health",
    description="Read-only local diagnostics for quick-query source priority, cooldown, latency, and cache mode. Does not invoke AI.",
)
def get_market_source_health() -> BasicMarketSourceOpsResponse:
    """Return local quick-query source diagnostics without fetching live market data."""
    try:
        return BasicMarketSourceOpsResponse.model_validate(build_market_source_ops_snapshot())
    except Exception as e:
        logger.error("Local market source health failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Local market source health failed: {str(e)}"},
        )


@router.post(
    "/sources/recovery",
    response_model=BasicMarketSourceRecoveryResponse,
    responses={
        200: {"description": "Admin-only local source-health recovery summary"},
        403: {"description": "Admin role required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Recover local market sources",
    description="Admin-only local recovery for quick-query source cooldown state. Optionally prewarms no-AI snapshots and never invokes AI.",
)
def recover_market_source_health(
    request: BasicMarketSourceRecoveryRequest,
    _identity: PlatformIdentity = Depends(_require_stock_admin_identity),
) -> BasicMarketSourceRecoveryResponse:
    """Reset local source-health cooldown state without deleting user data."""
    try:
        normalized_symbols = [_validate_and_normalize_stock_code(symbol) for symbol in request.symbols]
        summary = recover_market_sources(
            market=request.market,
            sources=request.sources,
            symbols=normalized_symbols,
            prewarm=request.prewarm,
        )
        return BasicMarketSourceRecoveryResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Local market source recovery failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Local market source recovery failed: {str(e)}"},
        )


@router.get(
    "/{stock_code}/kronos-forecast",
    response_model=KronosForecastResponse,
    responses={
        200: {"description": "Local Kronos sandbox forecast or explicit fallback"},
        401: {"description": "Login required for real Kronos model run"},
        403: {"description": "Premium plan required for real Kronos model run"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Local Kronos forecast sandbox",
    description=(
        "Return a local Kronos model sandbox forecast when enabled and available; otherwise return an explicit "
        "local-rules fallback without AI or public search."
    ),
)
def get_kronos_forecast(
    request: Request,
    stock_code: str,
    lookback: int = Query(120, ge=5, le=512, description="Historical K-line bars for Kronos or fallback rules."),
    horizon: int = Query(5, ge=1, le=30, description="Future K-line bars to forecast."),
    require_model: bool = Query(False, description="Require a real Kronos model run instead of fallback status."),
) -> KronosForecastResponse:
    """Return a local Kronos sandbox payload with explicit fallback status."""
    try:
        normalized = _validate_and_normalize_stock_code(stock_code)
        identity = platform_identity_from_request(request)
        if require_model and identity is None:
            raise HTTPException(
                status_code=401,
                detail={"error": "login_required", "message": "Login is required to run the Kronos model sandbox."},
            )
        if require_model and identity and not (identity.is_admin or identity.plan in {"pro", "premium", "enterprise"}):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "premium_required",
                    "message": "A pro or higher plan is required to run the Kronos model sandbox.",
                },
            )
        allow_model = bool(
            require_model
            and identity
            and (identity.is_admin or identity.plan in {"pro", "premium", "enterprise"})
        )
        forecast = KronosForecastService().forecast(
            normalized,
            lookback=lookback,
            horizon=horizon,
            allow_model=allow_model,
        )
        if require_model and not forecast.get("kronos_model_used"):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "model_unavailable",
                    "message": "Kronos model is not available locally; fallback preview was not returned because require_model=true.",
                    "missing_dependencies": forecast.get("missing_dependencies", []),
                },
            )
        return KronosForecastResponse.model_validate(forecast)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Local Kronos forecast failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Local Kronos forecast failed: {str(e)}"},
        )


@router.get(
    "/{stock_code}/research-workflows",
    response_model=FinancialResearchWorkflowResponse,
    responses={
        200: {"description": "No-AI financial research workflows"},
        400: {"description": "Invalid stock code", "model": ErrorResponse},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get information-only financial research workflows",
    description=(
        "Build four deterministic research checklists from the existing DSA stock snapshot. "
        "The route does not execute external agents, connectors, public search, or AI."
    ),
)
def get_financial_research_workflows(
    stock_code: str,
    refresh: bool = Query(False, description="Refresh the existing no-AI stock snapshot before building workflows."),
) -> FinancialResearchWorkflowResponse:
    """Return allowlisted financial research workflows for anonymous and logged-in users."""
    try:
        normalized = _validate_and_normalize_stock_code(stock_code)
        snapshot = BasicQueryService(
            global_equity_enrichment_service=_global_equity_enrichment_service_from_env(),
        ).get_snapshot(normalized, force_refresh=refresh)
        payload = FinancialResearchWorkflowService().build_research_workflows(snapshot)
        return FinancialResearchWorkflowResponse.model_validate(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Financial research workflow build failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "Financial research workflow build failed."},
        )


@router.get(
    "/{stock_code}/snapshot",
    response_model=BasicStockSnapshot,
    responses={
        200: {"description": "No-AI stock snapshot"},
        400: {"description": "参数错误", "model": ErrorResponse},
        429: {"description": "查询过于频繁，请按 retry_after_seconds 稍后重试"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取 No-AI 股票快照",
    description="返回行情、均线、成交量等基础数据，不调用 AI 模型。",
)
def get_basic_stock_snapshot(
    request: Request,
    stock_code: str,
    refresh: bool = Query(False, description="Force a deterministic no-AI market data refresh and update local cache."),
    a_share_source_mode: str = Query(
        "poc",
        pattern="^(poc|a_stock_data|off)$",
        description="A-share enrichment source mode for this no-AI snapshot.",
    ),
) -> BasicStockSnapshot:
    """Return a fast stock snapshot without invoking an AI model."""
    try:
        identity = platform_identity_from_request(request)
        limited = check_platform_rate_limit(
            request,
            "basic_snapshot",
            user_id=int(identity.user_id) if identity and identity.user_id is not None else None,
        )
        if limited is not None:
            return limited
        normalized = _validate_and_normalize_stock_code(stock_code)
        a_share_enrichment_service = AShareEnrichmentService(source_mode=a_share_source_mode)
        snapshot = BasicQueryService(
            a_share_enrichment_service=a_share_enrichment_service,
            global_equity_enrichment_service=_global_equity_enrichment_service_from_env(),
        ).get_snapshot(
            normalized,
            force_refresh=refresh,
        )
        return BasicStockSnapshot.model_validate(snapshot)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("No-AI stock snapshot failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"No-AI 股票快照失败: {str(e)}"},
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    获取股票实时行情
    
    获取指定股票的最新行情数据
    
    Args:
        stock_code: 股票代码（如 600519、00700、AAPL）
        
    Returns:
        StockQuote: 实时行情数据
        
    Raises:
        HTTPException: 404 - 股票不存在
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"未找到股票 {stock_code} 的行情数据"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取实时行情失败: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "历史行情数据"},
        422: {"description": "不支持的周期参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票历史行情",
    description="获取指定股票的历史 K 线数据"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K 线周期", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="获取天数")
) -> StockHistoryResponse:
    """
    获取股票历史行情
    
    获取指定股票的历史 K 线数据
    
    Args:
        stock_code: 股票代码
        period: K 线周期 (daily/weekly/monthly)
        days: 获取天数
        
    Returns:
        StockHistoryResponse: 历史行情数据
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # 转换为响应模型
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            source=result.get("source"),
            data=data
        )
    
    except ValueError as e:
        # period 参数不支持的错误（如 weekly/monthly）
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"获取历史行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取历史行情失败: {str(e)}"
            }
        )
