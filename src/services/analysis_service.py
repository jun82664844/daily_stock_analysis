# -*- coding: utf-8 -*-
"""
===================================
分析服务层
===================================

职责：
1. 封装股票分析逻辑
2. 调用 analyzer 和 pipeline 执行分析
3. 保存分析结果到数据库
"""

import logging
import copy
import os
import uuid
from typing import Optional, Dict, Any, Callable, List

from src.repositories.analysis_repo import AnalysisRepository
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.market_phase_summary import extract_market_phase_summary
from src.schemas.decision_action import build_action_fields
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    build_run_diagnostic_summary,
    get_current_diagnostic_context,
    reset_run_diagnostic_context,
)

logger = logging.getLogger(__name__)


_FAST_DISABLED_SEARCH_KEY_FIELDS = (
    "bocha_api_keys",
    "tavily_api_keys",
    "anspire_api_keys",
    "brave_api_keys",
    "serpapi_keys",
    "minimax_api_keys",
    "searxng_base_urls",
)


def _normalize_analysis_depth(value: Optional[str]) -> str:
    normalized = (value or "fast").strip().lower()
    return "deep" if normalized == "deep" else "fast"


def _with_request_analysis_depth(config: Any, analysis_depth: Optional[str]) -> tuple[Any, Dict[str, Any]]:
    """Return a request-scoped config/pipeline override for fast analysis."""
    if _normalize_analysis_depth(analysis_depth) != "fast":
        return config, {}

    scoped_config = copy.copy(config)
    for field_name in (
        "daily_market_context_enabled",
        "enable_fundamental_pipeline",
        "enable_chip_distribution",
        "searxng_public_instances_enabled",
        "prefetch_realtime_quotes",
    ):
        setattr(scoped_config, field_name, False)

    for field_name in _FAST_DISABLED_SEARCH_KEY_FIELDS:
        if hasattr(scoped_config, field_name):
            setattr(scoped_config, field_name, [])
    if hasattr(scoped_config, "social_sentiment_api_key"):
        setattr(scoped_config, "social_sentiment_api_key", "")

    return scoped_config, {
        "daily_market_context_enabled": False,
        "daily_market_context_allow_generate": False,
    }


class AnalysisService:
    """
    分析服务
    
    封装股票分析相关的业务逻辑
    """
    
    def __init__(self):
        """初始化分析服务"""
        self.repo = AnalysisRepository()
        self.last_error: Optional[str] = None
    
    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        skills: Optional[List[str]] = None,
        analysis_phase: str = "auto",
        analysis_depth: str = "fast",
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_language: Optional[str] = None,
        platform_user_id: Optional[int] = None,
        api_key_mode: str = "platform",
    ) -> Optional[Dict[str, Any]]:
        """
        执行股票分析
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型 (simple/detailed)
            force_refresh: 是否强制刷新
            query_id: 查询 ID（可选）
            send_notification: 是否发送通知（API 触发默认发送）
            analysis_phase: 请求的分析阶段覆盖（auto/premarket/intraday/postmarket）
            
        Returns:
            分析结果字典，包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - report: 分析报告
        """
        try:
            self.last_error = None
            local_model_ticket = None
            # 导入分析相关模块
            from src.config import get_config
            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType
            
            # 生成 query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            effective_trace_id = trace_id or query_id
            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=effective_trace_id,
                    query_id=query_id,
                    stock_code=stock_code,
                    trigger_source=query_source or "api",
                )
            
            # 获取配置
            config = get_config()
            normalized_api_key_mode = (api_key_mode or "platform").lower()
            if normalized_api_key_mode == "local":
                from src.llm.local_model_router import get_default_local_model_router
                from src.services.ollama_runtime_service import get_ollama_runtime_service

                local_model_ticket = get_default_local_model_router().try_acquire()
                if not local_model_ticket.acquired:
                    self.last_error = local_model_ticket.reason
                    logger.warning("本地模型不可用: %s", local_model_ticket.reason)
                    return None
                local_runtime = get_ollama_runtime_service()
                local_status = local_runtime.get_status()
                local_reason = local_runtime.readiness_reason(
                    analysis_depth,
                    status=local_status,
                )
                if local_reason != "ready":
                    self.last_error = local_reason
                    logger.warning("Local model preflight failed: %s", local_reason)
                    return None
                config = local_runtime.configure_analysis(
                    config,
                    analysis_depth=analysis_depth,
                )
            elif platform_user_id and normalized_api_key_mode == "user":
                from src.platform_accounts import PlatformAccountService

                config = PlatformAccountService().apply_user_llm_config(
                    config,
                    platform_user_id,
                    mode=api_key_mode,
                )
            config, pipeline_overrides = _with_request_analysis_depth(config, analysis_depth)
            normalized_report_language = normalize_report_language(report_language, default="")
            if normalized_report_language:
                config = copy.copy(config)
                config.report_language = normalized_report_language
            
            # 创建分析流水线
            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                trace_id=effective_trace_id,
                query_source=query_source or "api",
                progress_callback=progress_callback,
                analysis_skills=skills,
                analysis_phase=analysis_phase,
                portfolio_context=portfolio_context,
                platform_user_id=platform_user_id,
                **pipeline_overrides,
            )
            
            # 确定报告类型 (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)
            
            # 执行分析
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
            )
            
            if result is None:
                logger.warning(f"分析股票 {stock_code} 返回空结果")
                self.last_error = self.last_error or f"分析股票 {stock_code} 返回空结果"
                return None

            if not getattr(result, "success", True):
                self.last_error = getattr(result, "error_message", None) or f"分析股票 {stock_code} 失败"
                logger.warning(f"分析股票 {stock_code} 未成功完成: {self.last_error}")
                return None
            
            # 构建响应
            return self._build_analysis_response(
                result,
                query_id,
                report_type=rt.value,
                informational_only=normalized_api_key_mode == "local",
            )
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"分析股票 {stock_code} 失败: {e}", exc_info=True)
            return None
        finally:
            if locals().get("local_model_ticket") is not None:
                try:
                    locals()["local_model_ticket"].release()
                except Exception:
                    pass
            reset_run_diagnostic_context(locals().get("diag_token"))
    
    def _build_analysis_response(
        self, 
        result: Any, 
        query_id: str,
        report_type: str = "detailed",
        informational_only: bool = False,
    ) -> Dict[str, Any]:
        """
        构建分析响应
        
        Args:
            result: AnalysisResult 对象
            query_id: 查询 ID
            report_type: 归一化后的报告类型
            
        Returns:
            格式化的响应字典
        """
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        if informational_only:
            from src.core.pipeline import StockAnalysisPipeline

            StockAnalysisPipeline._apply_information_only_boundary(result)

        # 获取狙击点位
        sniper_points = {}
        if hasattr(result, 'get_sniper_points'):
            sniper_points = result.get_sniper_points() or {}
        
        # 计算情绪标签
        if informational_only:
            sniper_points = {}
        sentiment_label = get_sentiment_label(result.sentiment_score, report_language)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        action_fields = build_action_fields(
            operation_advice=getattr(result, "operation_advice", None),
            explicit_action=getattr(result, "action", None),
            report_type=report_type,
            report_language=report_language,
        )
        if informational_only:
            action_fields = {
                "action": None,
                "action_label": getattr(result, "action_label", None),
            }
        diagnostic_context = get_current_diagnostic_context()
        trace_id = diagnostic_context.trace_id if diagnostic_context is not None else query_id
        diagnostic_snapshot = diagnostic_context.snapshot() if diagnostic_context is not None else None
        diagnostic_context_snapshot = getattr(result, "diagnostic_context_snapshot", None)
        market_phase_summary = extract_market_phase_summary(diagnostic_context_snapshot)
        if isinstance(diagnostic_context_snapshot, dict):
            context_snapshot = dict(diagnostic_context_snapshot)
            if diagnostic_snapshot is not None:
                context_snapshot["diagnostics"] = diagnostic_snapshot
        elif diagnostic_snapshot is not None:
            context_snapshot = {"diagnostics": diagnostic_snapshot}
        else:
            context_snapshot = None
        diagnostic_summary = build_run_diagnostic_summary(
            context_snapshot=context_snapshot,
            raw_result=result.to_dict() if hasattr(result, "to_dict") else None,
            report_saved=True,
            query_id=query_id,
            stock_code=result.code,
        )
        
        # 构建报告结构
        report = {
            "meta": {
                "query_id": query_id,
                "trace_id": trace_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
                "market_phase_summary": market_phase_summary,
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "action": action_fields["action"],
                "action_label": action_fields["action_label"],
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
            }
        }
        
        return {
            "query_id": query_id,
            "trace_id": trace_id,
            "stock_code": result.code,
            "stock_name": stock_name,
            "report": report,
            "diagnostic_summary": diagnostic_summary,
        }
