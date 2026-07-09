# =============================================================================
# tracked_call.py
# Wraps Anthropic API calls with per-call cost attribution metadata.
# This is the observability foundation for chargeback and unit economics.
#
# Project : Token Cost Anatomy
# Author  : Shannon Eldridge-Kuehn
# Blog    : https://shankuehn.io
# Created : 2026-07-09
# Version : 1.0.0
# License : MIT
# =============================================================================
#
# WHAT THIS DOES
#   Tags every API call with team and use_case, logs a CallRecord with full
#   token breakdown and estimated cost, and exposes summarize_costs() for
#   rollup reporting. Wire emit() into your observability platform of choice.
#
# FINOPS MATURITY PATH
#   1. API key governance        - one key per team; know who owns what
#   2. Observability (this file) - log cost + attribution per call
#   3. Model right-sizing        - route cheaper models where quality allows
#   4. Chargeback / showback     - bill teams from call_log data
#
# USAGE
#   from token_cost_anatomy.tracked_call import tracked_call, summarize_costs
#
#   result = tracked_call(
#       messages=[{"role": "user", "content": "Summarize this cost report..."}],
#       team="platform-engineering",
#       use_case="cost-anomaly-detection",
#   )
#
#   Run the smoke test:
#   export ANTHROPIC_API_KEY=your_key_here
#   python -m token_cost_anatomy.tracked_call
#
# WIRING INTO OTEL (replace emit() below)
#   from opentelemetry import trace
#   tracer = trace.get_tracer(__name__)
#
#   def emit(record: CallRecord) -> None:
#       with tracer.start_as_current_span("llm.call") as span:
#           span.set_attribute("llm.team",          record.team)
#           span.set_attribute("llm.use_case",       record.use_case)
#           span.set_attribute("llm.model",          record.model)
#           span.set_attribute("llm.cost_usd",       record.estimated_cost_usd)
#           span.set_attribute("llm.input_tokens",   record.input_tokens)
#           span.set_attribute("llm.output_tokens",  record.output_tokens)
#           span.set_attribute("llm.cache_hit",      record.cache_read_tokens)
#           span.set_attribute("llm.latency_ms",     record.latency_ms)
# =============================================================================

import os
import time
from dataclasses import dataclass, asdict
from typing import Optional

import anthropic

from .pricing import cost_of


@dataclass
class CallRecord:
    """
    Single Anthropic API call with full cost attribution.
    Serialize with dataclasses.asdict(record) before shipping to your sink.
    """
    timestamp: float            # Unix epoch at call start
    model: str
    team: str                   # Cost center or team owner
    use_case: str               # What this call is for
    input_tokens: int           # Fresh (non-cached) input tokens
    output_tokens: int
    cache_read_tokens: int      # Served from cache (90% cheaper)
    cache_write_tokens: int     # Written to cache (one-time cost)
    estimated_cost_usd: float
    latency_ms: float


# Module-level log - replace with a real sink in production
call_log: list[CallRecord] = []


def emit(record: CallRecord) -> None:
    """
    Ship a CallRecord to your observability platform.
    Replace the print() with your preferred sink (OTel, Azure Monitor, Datadog).
    See the WIRING INTO OTEL comment at the top of this file.
    """
    print(
        f"[{record.team}/{record.use_case}] "
        f"${record.estimated_cost_usd:.6f} | "
        f"model={record.model} | "
        f"in={record.input_tokens} out={record.output_tokens} "
        f"cache_hit={record.cache_read_tokens} cache_write={record.cache_write_tokens} | "
        f"latency={record.latency_ms:.0f}ms"
    )


def tracked_call(
    messages: list[dict],
    system: Optional[list[dict]] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    team: str = "unknown",
    use_case: str = "unknown",
) -> str:
    """
    Wraps an Anthropic API call with cost tracking and attribution.

    Args:
        messages:   Conversation messages list.
        system:     Optional system prompt blocks. Include cache_control
                    here to combine caching with attribution tracking.
        model:      Anthropic model ID.
        max_tokens: Hard ceiling on output tokens.
        team:       Team or cost center for chargeback attribution.
        use_case:   Purpose of this call for unit economics analysis.

    Returns:
        Model text response as a string.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or [],
        messages=messages,
    )
    latency_ms = (time.time() - start) * 1000

    usage = response.usage
    cache_read  = getattr(usage, "cache_read_input_tokens", 0)
    cache_write = getattr(usage, "cache_creation_input_tokens", 0)

    estimated_cost = cost_of(
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )

    record = CallRecord(
        timestamp=start,
        model=model,
        team=team,
        use_case=use_case,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        estimated_cost_usd=estimated_cost,
        latency_ms=latency_ms,
    )

    call_log.append(record)
    emit(record)
    return response.content[0].text


def summarize_costs(log: list[CallRecord] | None = None) -> dict:
    """
    Aggregates call records into a cost summary grouped by team and use_case.

    Args:
        log: List of CallRecords. Defaults to the module-level call_log.

    Returns:
        Dict with total_usd and a by_team breakdown.
    """
    records = log or call_log
    if not records:
        return {"total_usd": 0.0, "by_team": {}}

    summary: dict = {"total_usd": 0.0, "by_team": {}}

    for r in records:
        summary["total_usd"] = round(summary["total_usd"] + r.estimated_cost_usd, 8)
        team_bucket = summary["by_team"].setdefault(
            r.team, {"total_usd": 0.0, "by_use_case": {}}
        )
        team_bucket["total_usd"] = round(
            team_bucket["total_usd"] + r.estimated_cost_usd, 8
        )
        uc_bucket = team_bucket["by_use_case"].setdefault(
            r.use_case, {"calls": 0, "total_usd": 0.0}
        )
        uc_bucket["calls"] += 1
        uc_bucket["total_usd"] = round(
            uc_bucket["total_usd"] + r.estimated_cost_usd, 8
        )

    return summary


if __name__ == "__main__":
    import json

    print("Making two tracked calls...\n")

    tracked_call(
        messages=[{"role": "user", "content": "Summarize cost anomalies for sub-prod-1234."}],
        team="platform-engineering",
        use_case="cost-anomaly-detection",
    )

    tracked_call(
        messages=[{"role": "user", "content": "Which idle VMs should we shut down first?"}],
        model="claude-haiku-4-5",
        team="platform-engineering",
        use_case="rightsizing-recommendations",
    )

    print("\nCost Summary:")
    print(json.dumps(summarize_costs(), indent=2))
