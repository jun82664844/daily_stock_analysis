# -*- coding: utf-8 -*-
"""
TechnicalAgent — technical & price analysis specialist.

Responsible for:
- Fetching realtime quotes and historical K-line data
- Running technical indicators (trend, MA, volume, pattern)
- Producing a structured opinion on trend/momentum/support-resistance
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion, StageResult
from src.agent.runner import serialize_tool_result, try_parse_json

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    agent_name = "technical"
    max_steps = 6
    tool_names = [
        "get_realtime_quote",
        "get_daily_history",
        "analyze_trend",
        "calculate_ma",
        "get_volume_analysis",
        "analyze_pattern",
        "get_chip_distribution",
        "get_analysis_context",
    ]

    def run(
        self,
        ctx: AgentContext,
        progress_callback: Optional[Callable[[Dict[str, object]], None]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> StageResult:
        prefetch_log = self._prefetch_technical_context(ctx, progress_callback)
        result = super().run(
            ctx,
            progress_callback=progress_callback,
            timeout_seconds=timeout_seconds,
        )
        if prefetch_log:
            result.meta["tool_calls_log"] = prefetch_log + (
                result.meta.get("tool_calls_log") or []
            )
            result.tool_calls_count += len(prefetch_log)
        return result

    def _prefetch_technical_context(
        self,
        ctx: AgentContext,
        progress_callback: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> list[dict]:
        if not ctx.stock_code:
            return []

        stock_code = ctx.stock_code
        tasks = [
            ("realtime_quote", "get_realtime_quote", {"stock_code": stock_code}),
            ("daily_history", "get_daily_history", {"stock_code": stock_code, "days": 45}),
            ("trend_result", "analyze_trend", {"stock_code": stock_code}),
            ("ma_result", "calculate_ma", {"stock_code": stock_code, "periods": "5,10,20,60", "days": 120}),
        ]
        if self._looks_like_a_share(stock_code):
            tasks.append(("chip_distribution", "get_chip_distribution", {"stock_code": stock_code}))

        logs: list[dict] = []
        realtime_quote: Optional[dict] = (
            ctx.get_data("realtime_quote")
            if isinstance(ctx.get_data("realtime_quote"), dict)
            else None
        )
        for data_key, tool_name, arguments in tasks:
            if ctx.get_data(data_key) is not None:
                continue
            tool_def = self.tool_registry.get(tool_name)
            if tool_def is None:
                continue

            if progress_callback:
                progress_callback({"type": "tool_start", "step": 0, "tool": tool_name})

            t0 = time.time()
            success = True
            try:
                payload = self.tool_registry.execute(tool_name, **arguments)
                if data_key == "daily_history":
                    payload = self._compact_daily_history(payload)
                if data_key == "realtime_quote" and isinstance(payload, dict):
                    realtime_quote = payload
                elif data_key in {"trend_result", "ma_result"}:
                    payload = self._align_price_to_realtime(payload, realtime_quote)
            except Exception as exc:
                success = False
                payload = {"error": str(exc)}
                logger.warning("[TechnicalAgent] prefetch tool '%s' failed: %s", tool_name, exc)

            ctx.set_data(data_key, payload)
            result_str = serialize_tool_result(payload)
            duration = round(time.time() - t0, 2)
            logs.append({
                "step": 0,
                "tool": tool_name,
                "arguments": arguments,
                "success": success and not (isinstance(payload, dict) and payload.get("error")),
                "duration": duration,
                "result_length": len(result_str),
                "prefetched": True,
            })
            if progress_callback:
                progress_callback({
                    "type": "tool_done",
                    "step": 0,
                    "tool": tool_name,
                    "success": logs[-1]["success"],
                    "duration": duration,
                })

        return logs

    @staticmethod
    def _align_price_to_realtime(payload: object, realtime_quote: Optional[dict]) -> object:
        if not isinstance(payload, dict) or not isinstance(realtime_quote, dict):
            return payload
        price = realtime_quote.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            return payload

        original_price = payload.get("current_price")
        payload = dict(payload)
        payload["current_price"] = round(float(price), 4)
        payload["current_price_source"] = "realtime_quote.price"
        payload["indicator_price_source"] = "daily_history_last_close"
        if original_price not in (None, price):
            payload["indicator_original_current_price"] = original_price
            payload["price_alignment_note"] = (
                "Realtime quote overrides stale/previous daily close for current price. "
                "Technical indicators may still be calculated from the latest completed daily bar."
            )

        for key in ("ma5", "ma10", "ma20", "ma30", "ma60", "ma120", "ma250"):
            ma_value = payload.get(key)
            if isinstance(ma_value, (int, float)) and ma_value:
                payload[f"bias_{key}"] = round((float(price) - float(ma_value)) / float(ma_value) * 100, 2)

        ma_block = payload.get("ma")
        if isinstance(ma_block, dict):
            ma_block = dict(ma_block)
            for ma_key, ma_info in list(ma_block.items()):
                if not isinstance(ma_info, dict):
                    continue
                ma_value = ma_info.get("value")
                if not isinstance(ma_value, (int, float)) or not ma_value:
                    continue
                patched = dict(ma_info)
                patched["bias_pct"] = round((float(price) - float(ma_value)) / float(ma_value) * 100, 2)
                patched["price_above"] = float(price) > float(ma_value)
                ma_block[ma_key] = patched
            payload["ma"] = ma_block
            ma_values = [v for v in ma_block.values() if isinstance(v, dict) and v.get("value") is not None]
            if ma_values:
                above_count = sum(1 for v in ma_values if v.get("price_above"))
                payload["above_ma_count"] = above_count
                payload["total_ma_count"] = len(ma_values)

        return payload

    @staticmethod
    def _compact_daily_history(payload: object) -> object:
        if not isinstance(payload, dict):
            return payload
        rows = payload.get("data")
        if not isinstance(rows, list):
            return payload

        keep_keys = (
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "ma5",
            "ma10",
            "ma20",
        )
        compact_rows = []
        for row in rows[-20:]:
            if isinstance(row, dict):
                compact_rows.append({k: row.get(k) for k in keep_keys if k in row})
        compact = {
            "code": payload.get("code"),
            "source": payload.get("source"),
            "actual_records": payload.get("actual_records"),
            "shown_records": len(compact_rows),
            "data": compact_rows,
        }
        if payload.get("error"):
            compact["error"] = payload.get("error")
        return compact

    @staticmethod
    def _looks_like_a_share(stock_code: str) -> bool:
        code = (stock_code or "").strip().upper()
        if code.startswith(("SH", "SZ", "BJ")):
            return True
        return code.isdigit() and len(code) == 6

    def system_prompt(self, ctx: AgentContext) -> str:
        skills = ""
        if self.skill_instructions:
            skills = f"\n## Active Trading Skills\n\n{self.skill_instructions}\n"
        baseline = ""
        if self.technical_skill_policy:
            baseline = f"\n{self.technical_skill_policy}\n"

        return f"""\
You are a **Technical Analysis Agent** specialising in Chinese A-shares, \
Hong Kong stocks, and US equities.

Your task: perform a thorough technical analysis of the given stock and \
output a structured JSON opinion.

## Workflow (execute stages in order)
1. Fetch realtime quote + daily history (if not already provided)
2. Run trend analysis (MA alignment, MACD, RSI)
3. Analyse volume and chip distribution
4. Identify chart patterns

## Mandatory Tool Use
- If the conversation does not include pre-fetched `realtime_quote`, call
  `get_realtime_quote` before producing the final JSON.
- If the conversation does not include pre-fetched `daily_history`, call
  `get_daily_history` before producing the final JSON.
- Use `analyze_trend` and `calculate_ma` after market data is available.
- If a tool fails or returns unsupported data, still finish the JSON, but
  explicitly reflect that limitation in `reasoning`.

## Price Accuracy Rules
- Treat `realtime_quote.price` as the only source for the current price.
- Do not call a previous daily close, high, resistance, or MA-derived price
  "current price".
- If technical indicators include `indicator_original_current_price` or
  `price_alignment_note`, explain that indicators are based on the latest
  completed daily bar while current price comes from realtime quote.

{baseline}
{skills}
## Output Format
Return **only** a JSON object (no markdown fences):
{{
  "signal": "strong_buy|buy|hold|sell|strong_sell",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence summary",
  "key_levels": {{
    "support": <float>,
    "resistance": <float>,
    "stop_loss": <float>
  }},
  "trend_score": 0-100,
  "ma_alignment": "bullish|neutral|bearish",
  "volume_status": "heavy|normal|light",
  "pattern": "<detected pattern or none>"
}}
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [f"Perform technical analysis on stock **{ctx.stock_code}**"]
        if ctx.stock_name:
            parts[0] += f" ({ctx.stock_name})"
        parts.append("Use your tools to fetch any missing data, then output the JSON opinion.")
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """Parse the JSON opinion from the LLM response."""
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[TechnicalAgent] failed to parse opinion JSON")
            return None

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=parsed.get("signal", "hold"),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            key_levels={
                k: float(v) for k, v in parsed.get("key_levels", {}).items()
                if isinstance(v, (int, float))
            },
            raw_data=parsed,
        )

