# -*- coding: utf-8 -*-
"""Canonical market-data provenance, arbitration, and record deduplication."""

from __future__ import annotations

import copy
import json
import math
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_FRESHNESS_ORDER = {
    "fresh": 0,
    "cached": 1,
    "stale": 2,
    "unavailable": 3,
}
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
}


class MarketDataContractService:
    """Keep one observable fact contract while feature modules reuse it."""

    resolution_strategy = "freshness_then_priority_then_observed_at"

    def arbitrate_fact(
        self,
        *,
        domain: str,
        field: str,
        candidates: Iterable[Mapping[str, Any]],
        source_priority: Sequence[str] = (),
    ) -> Dict[str, Any]:
        usable = [dict(item) for item in candidates if self._has_value(item.get("value"))]
        if not usable:
            return {
                "domain": domain,
                "field": field,
                "value": None,
                "source": "unavailable",
                "freshness": "unavailable",
                "observed_at": None,
                "conflict": False,
                "resolution": self.resolution_strategy,
                "candidate_count": 0,
            }

        priorities = {str(source): index for index, source in enumerate(source_priority)}
        usable.sort(
            key=lambda item: (
                _FRESHNESS_ORDER.get(str(item.get("freshness") or "unavailable").lower(), 3),
                priorities.get(str(item.get("source") or ""), len(priorities) + 1),
                -self._timestamp(item.get("observed_at")),
            )
        )
        selected = usable[0]
        conflict = any(
            not self._values_equivalent(selected.get("value"), item.get("value"))
            for item in usable[1:]
        )
        return {
            "domain": domain,
            "field": field,
            "value": selected.get("value"),
            "source": str(selected.get("source") or "unavailable"),
            "freshness": self._freshness(selected.get("freshness")),
            "observed_at": selected.get("observed_at"),
            "conflict": conflict,
            "resolution": self.resolution_strategy,
            "candidate_count": len(usable),
        }

    def deduplicate_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> tuple[list[Dict[str, Any]], Dict[str, int]]:
        items = [dict(item) for item in records if isinstance(item, Mapping)]
        result: list[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            identity = self._record_identity(item)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(item)
        return result, {
            "input_count": len(items),
            "output_count": len(result),
            "removed_count": len(items) - len(result),
        }

    def deduplicate_snapshot_intelligence(
        self,
        intelligence: Optional[Mapping[str, Any]],
    ) -> tuple[Dict[str, Any], Dict[str, int]]:
        payload = copy.deepcopy(dict(intelligence or {}))
        totals = {"input_count": 0, "output_count": 0, "removed_count": 0}

        def deduplicate(container: Dict[str, Any], key: str) -> None:
            records = container.get(key)
            if not isinstance(records, list):
                return
            deduped, metrics = self.deduplicate_records(records)
            container[key] = deduped
            for metric, value in metrics.items():
                totals[metric] += value

        deduplicate(payload, "items")
        news_center = payload.get("news_center")
        if isinstance(news_center, dict):
            deduplicate(news_center, "items")
        for enrichment_key in ("a_share_enrichment", "global_equity_enrichment"):
            enrichment = payload.get(enrichment_key)
            if not isinstance(enrichment, dict):
                continue
            for channel in enrichment.get("channels") or []:
                if isinstance(channel, dict):
                    deduplicate(channel, "items")
        return payload, totals

    def build_snapshot_contract(
        self,
        *,
        symbol: str,
        market: str,
        source_priority: Mapping[str, Sequence[str]],
        quote: Optional[Mapping[str, Any]],
        history: Optional[Mapping[str, Any]],
        profile: Optional[Mapping[str, Any]],
        diagnostics: Optional[Mapping[str, Any]] = None,
        deduplication: Optional[Mapping[str, int]] = None,
        conflicts: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> Dict[str, Any]:
        domains = {
            "quote": dict(quote or {}),
            "history": dict(history or {}),
            "profile": dict(profile or {}),
        }
        diagnostics_payload = dict(diagnostics or {})
        cache_states = diagnostics_payload.get("cache") or {}
        selected_sources: Dict[str, Dict[str, Any]] = {}
        field_provenance: Dict[str, str] = {}

        for domain, payload in domains.items():
            source = str(payload.get("source") or "unavailable")
            freshness = self._freshness(payload.get("freshness"))
            observed_at = self._observed_at(domain, payload)
            priorities = tuple(source_priority.get(domain) or ())
            selected_sources[domain] = {
                "source": source,
                "freshness": freshness,
                "observed_at": observed_at,
                "priority": priorities.index(source) if source in priorities else None,
                "cache_state": cache_states.get(domain),
            }
            if domain == "history":
                if payload.get("data"):
                    field_provenance["history.daily_bars"] = source
                continue
            for field, value in payload.items():
                if field in {"source", "freshness", "update_time", "observed_at"}:
                    continue
                if self._has_value(value):
                    field_provenance[f"{domain}.{field}"] = source

        conflict_items = [dict(item) for item in conflicts or []]
        return {
            "contract_version": "v1",
            "symbol": symbol,
            "market": market,
            "policy": {
                "strategy": self.resolution_strategy,
                "no_averaging": True,
                "facts_and_models_separated": True,
            },
            "selected_sources": selected_sources,
            "field_provenance": field_provenance,
            "conflicts": conflict_items,
            "deduplication": {
                "input_count": int((deduplication or {}).get("input_count", 0)),
                "output_count": int((deduplication or {}).get("output_count", 0)),
                "removed_count": int((deduplication or {}).get("removed_count", 0)),
            },
            "informational_only": True,
            "ai_used": False,
        }

    @staticmethod
    def _has_value(value: Any) -> bool:
        return value is not None and value != ""

    @staticmethod
    def _freshness(value: Any) -> str:
        normalized = str(value or "unavailable").lower()
        return normalized if normalized in _FRESHNESS_ORDER else "unavailable"

    @staticmethod
    def _timestamp(value: Any) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _values_equivalent(left: Any, right: Any) -> bool:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=1e-8)
        return str(left).strip() == str(right).strip()

    def _record_identity(self, item: Mapping[str, Any]) -> str:
        url = item.get("url") or item.get("link") or item.get("official_url")
        if url:
            return f"url:{self._canonical_url(str(url))}"
        source_id = item.get("id") or item.get("event_id") or item.get("accession_number")
        if source_id:
            return f"id:{str(source_id).strip().lower()}"
        title = str(item.get("title") or item.get("label") or item.get("summary") or "").strip().lower()
        observed = str(item.get("published_at") or item.get("updated_at") or item.get("as_of") or "").strip()
        source = str(item.get("source") or item.get("publisher") or "").strip().lower()
        value = ""
        if "value" in item:
            try:
                value = json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                value = str(item.get("value"))
        return f"text:{title}|{observed}|{source}|{value}"

    @staticmethod
    def _canonical_url(value: str) -> str:
        parts = urlsplit(value.strip())
        query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_KEYS
        ]
        query.sort()
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))

    @staticmethod
    def _observed_at(domain: str, payload: Mapping[str, Any]) -> Any:
        if domain == "quote":
            return payload.get("update_time") or payload.get("observed_at")
        if domain == "history":
            rows = payload.get("data") or []
            if rows and isinstance(rows[-1], Mapping):
                return rows[-1].get("date") or rows[-1].get("timestamp")
        return payload.get("updated_at") or payload.get("as_of") or payload.get("observed_at")
