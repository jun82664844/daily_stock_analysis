from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SOURCE_NAME = "anthropics/financial-services"
ACCEPTED_SOURCE_COMMIT = "4aa51ed3d379731f8f9beff498d749580372699c"
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "external" / "anthropic-financial-services"
BOUNDARY_ZH = "仅提供资讯和数据，不构成投资建议、交易指令、目标价或收益预测。"
BOUNDARY_EN = "Information and data only; no investment advice, trade instruction, target price, or return forecast."

WORKFLOW_SPECS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "company_snapshot",
        "title_zh": "公司与估值概览",
        "title_en": "Company and valuation snapshot",
        "purpose_zh": "汇总当前行情、规模和公开估值字段，供进一步查阅。",
        "purpose_en": "Summarize current quote, scale, and disclosed valuation fields for further review.",
        "reference": "plugins/vertical-plugins/financial-analysis/skills/comps-analysis/SKILL.md",
        "required": ("current_price", "market_cap", "pe_ratio"),
    },
    {
        "id": "earnings_review",
        "title_zh": "经营数据复盘",
        "title_en": "Operating data review",
        "purpose_zh": "整理收入、利润及其公开增长字段，不生成结论性推荐。",
        "purpose_en": "Organize revenue, profit, and disclosed growth fields without a recommendation.",
        "reference": "plugins/vertical-plugins/equity-research/skills/earnings-analysis/SKILL.md",
        "required": ("revenue", "net_profit", "revenue_growth", "earnings_growth"),
    },
    {
        "id": "sector_overview",
        "title_zh": "行业与板块概览",
        "title_en": "Sector and industry overview",
        "purpose_zh": "展示公司所属板块和行业，作为横向比较入口。",
        "purpose_en": "Show sector and industry as an entry point for factual peer comparison.",
        "reference": "plugins/vertical-plugins/equity-research/skills/sector-overview/SKILL.md",
        "required": ("sector", "industry"),
    },
    {
        "id": "catalyst_calendar",
        "title_zh": "公开事件日历",
        "title_en": "Public event calendar",
        "purpose_zh": "汇总已有公告和公开事件条目；缺少来源时明确显示待补充。",
        "purpose_en": "List available filings and public events, with explicit missing-source states.",
        "reference": "plugins/vertical-plugins/equity-research/skills/catalyst-calendar/SKILL.md",
        "required": ("events",),
    },
)

FACT_LABELS: Dict[str, Tuple[str, str]] = {
    "current_price": ("最新价格", "Latest price"),
    "change_percent": ("涨跌幅", "Price change"),
    "volume": ("成交量", "Volume"),
    "amount": ("成交额", "Trading value"),
    "market_cap": ("总市值", "Market cap"),
    "pe_ratio": ("市盈率", "P/E ratio"),
    "pb_ratio": ("市净率", "P/B ratio"),
    "revenue": ("营业收入", "Revenue"),
    "net_profit": ("净利润", "Net profit"),
    "revenue_growth": ("收入增长率", "Revenue growth"),
    "earnings_growth": ("利润增长率", "Earnings growth"),
    "sector": ("板块", "Sector"),
    "industry": ("行业", "Industry"),
}


class FinancialResearchWorkflowService:
    def __init__(self, *, source_root: Optional[Path] = None) -> None:
        configured = str(os.getenv("DSA_FINANCIAL_SERVICES_ROOT", "")).strip()
        self.source_root = Path(source_root or configured or DEFAULT_SOURCE_ROOT).resolve()

    def source_diagnostics(self) -> Dict[str, Any]:
        workflows = [
            {
                "id": spec["id"],
                "source_reference": spec["reference"],
                "available": (self.source_root / spec["reference"]).is_file(),
            }
            for spec in WORKFLOW_SPECS
        ]
        license_path = self.source_root / "LICENSE"
        license_name = "unavailable"
        try:
            if "apache license" in license_path.read_text(encoding="utf-8", errors="ignore").lower():
                license_name = "Apache-2.0"
        except OSError:
            pass
        commit = self._read_git_commit()
        commit_verified = commit == ACCEPTED_SOURCE_COMMIT
        installed = (
            bool(workflows)
            and all(item["available"] for item in workflows)
            and license_name == "Apache-2.0"
            and commit_verified
        )
        return {
            "installed": installed,
            "source_name": SOURCE_NAME,
            "source_root_name": self.source_root.name,
            "license": license_name,
            "commit": commit,
            "accepted_commit": ACCEPTED_SOURCE_COMMIT,
            "commit_verified": commit_verified,
            "external_code_executed": False,
            "connectors_enabled": False,
            "workflows": workflows,
        }

    def build_research_workflows(self, snapshot: Any) -> Dict[str, Any]:
        payload = self._plain_dict(snapshot)
        quote = self._plain_dict(payload.get("quote"))
        profile = self._plain_dict(payload.get("profile"))
        intelligence = self._plain_dict(payload.get("intelligence"))
        source = self.source_diagnostics()
        market = str(payload.get("market") or "unknown").lower()
        currency = self._text(quote.get("currency") or profile.get("currency")) or self._market_currency(market)

        common_facts = self._facts_from_fields(
            quote,
            ("current_price", "change_percent", "volume", "amount"),
            source=str(quote.get("source") or "quote_unavailable"),
            freshness=str(quote.get("freshness") or "unavailable"),
            as_of=self._text(quote.get("update_time")),
            market=market,
            currency=currency,
        )
        profile_facts = self._facts_from_fields(
            profile,
            (
                "market_cap",
                "pe_ratio",
                "pb_ratio",
                "revenue",
                "net_profit",
                "revenue_growth",
                "earnings_growth",
                "sector",
                "industry",
            ),
            source=str(profile.get("source") or "profile_unavailable"),
            freshness=str(profile.get("freshness") or "unavailable"),
            as_of=None,
            market=market,
            currency=currency,
        )
        facts_by_code = {fact["code"]: fact for fact in (*common_facts, *profile_facts)}
        event_facts = self._event_facts(intelligence)

        workflow_payloads: List[Dict[str, Any]] = []
        for spec in WORKFLOW_SPECS:
            workflow_id = str(spec["id"])
            if workflow_id == "company_snapshot":
                facts = self._select_facts(
                    facts_by_code,
                    ("current_price", "change_percent", "market_cap", "pe_ratio", "pb_ratio", "volume", "amount"),
                )
            elif workflow_id == "earnings_review":
                facts = self._select_facts(
                    facts_by_code,
                    ("revenue", "net_profit", "revenue_growth", "earnings_growth"),
                )
            elif workflow_id == "sector_overview":
                facts = self._select_facts(facts_by_code, ("sector", "industry", "market_cap"))
            else:
                facts = [fact for fact in event_facts if self._verified_event_fact(fact)]

            required = tuple(str(item) for item in spec["required"])
            available_codes = {fact["code"] for fact in facts}
            missing = [code for code in required if code not in available_codes]
            if workflow_id == "catalyst_calendar" and facts:
                missing = []
            source_available = next(
                (source["installed"] and item["available"] for item in source["workflows"] if item["id"] == workflow_id),
                False,
            )
            workflow_payloads.append(
                {
                    "id": workflow_id,
                    "title_zh": spec["title_zh"],
                    "title_en": spec["title_en"],
                    "purpose_zh": spec["purpose_zh"],
                    "purpose_en": spec["purpose_en"],
                    "status": "available" if source_available and not missing else "partial",
                    "source_reference": spec["reference"],
                    "facts": facts,
                    "missing_data": missing,
                    "ai_used": False,
                    "public_search_used": False,
                }
            )

        return {
            "stock_code": str(payload.get("stock_code") or ""),
            "stock_name": self._text(payload.get("stock_name")),
            "market": str(payload.get("market") or "unknown"),
            "generated_at": self._text(quote.get("update_time")),
            "mode": "deterministic_no_ai",
            "ai_used": False,
            "public_search_used": False,
            "source": source,
            "workflows": workflow_payloads,
            "boundary_zh": BOUNDARY_ZH,
            "boundary_en": BOUNDARY_EN,
        }

    def _read_git_commit(self) -> Optional[str]:
        git_dir = self.source_root / ".git"
        try:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not head.startswith("ref:"):
            return head or None
        ref = head.split(":", 1)[1].strip()
        try:
            return (git_dir / ref).read_text(encoding="utf-8").strip() or None
        except OSError:
            try:
                packed = (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines()
            except OSError:
                return None
            for line in packed:
                if line and not line.startswith(("#", "^")):
                    commit, _, packed_ref = line.partition(" ")
                    if packed_ref == ref:
                        return commit
        return None

    @staticmethod
    def _plain_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else {}
        return {}

    @classmethod
    def _facts_from_fields(
        cls,
        values: Dict[str, Any],
        fields: Sequence[str],
        *,
        source: str,
        freshness: str,
        as_of: Optional[str],
        market: str,
        currency: Optional[str],
    ) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        for code in fields:
            value = values.get(code)
            if value is None or value == "":
                continue
            label_zh, label_en = FACT_LABELS[code]
            facts.append(
                {
                    "code": code,
                    "label_zh": label_zh,
                    "label_en": label_en,
                    "value": value,
                    "unit": cls._fact_unit(code, market),
                    "currency": currency if code in {"current_price", "amount", "market_cap", "revenue", "net_profit"} else None,
                    "source": source,
                    "freshness": freshness,
                    "as_of": as_of,
                }
            )
        return facts

    @classmethod
    def _event_facts(cls, intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        news_center = cls._plain_dict(intelligence.get("news_center"))
        items = news_center.get("items") if isinstance(news_center.get("items"), list) else []
        facts: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(items[:8]):
            item = cls._plain_dict(raw_item)
            title = cls._text(item.get("title"))
            if not title:
                continue
            category = re.sub(r"[^a-z0-9_]+", "_", str(item.get("category") or "public_event").lower()).strip("_")
            facts.append(
                {
                    "code": f"event:{category or index + 1}",
                    "label_zh": "公开事件",
                    "label_en": "Public event",
                    "value": title,
                    "detail": cls._text(item.get("summary")),
                    "unit": "event",
                    "currency": None,
                    "source": str(item.get("source") or "event_source_unavailable"),
                    "freshness": str(item.get("status") or "unavailable"),
                    "as_of": cls._text(item.get("updated_at")),
                }
            )
        return facts

    @staticmethod
    def _verified_event_fact(fact: Dict[str, Any]) -> bool:
        placeholder_sources = {"no_ai_news_center_rules", "yfinance_profile", "profile_cache"}
        unusable_states = {"degraded", "missing", "unavailable", "stale"}
        verified_categories = {
            "announcement",
            "announcements",
            "corporate_action",
            "dividend",
            "earnings",
            "event",
            "filing",
            "filings",
            "news",
        }
        category = str(fact.get("code") or "").partition(":")[2]
        return (
            category in verified_categories
            and
            str(fact.get("source") or "") not in placeholder_sources
            and str(fact.get("freshness") or "").lower() not in unusable_states
        )

    @staticmethod
    def _market_currency(market: str) -> Optional[str]:
        return {
            "us": "USD",
            "cn": "CNY",
            "hk": "HKD",
            "crypto": "USD",
        }.get(market)

    @staticmethod
    def _fact_unit(code: str, market: str) -> str:
        if code in {"current_price", "amount", "market_cap", "revenue", "net_profit"}:
            return "currency"
        if code == "volume":
            return "units" if market == "crypto" else "shares"
        if code in {"change_percent", "revenue_growth", "earnings_growth"}:
            return "percent"
        if code in {"pe_ratio", "pb_ratio"}:
            return "ratio"
        return "text"

    @staticmethod
    def _select_facts(values: Dict[str, Dict[str, Any]], codes: Iterable[str]) -> List[Dict[str, Any]]:
        return [values[code] for code in codes if code in values]

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None
