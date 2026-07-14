# =============================================================================
# structured_output.py
# Constrains output tokens by requesting a JSON schema instead of prose.
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
#   Instead of asking for a narrative analysis (verbose, expensive), this
#   pattern asks for a compact JSON object with a fixed schema. Reducing
#   average output from 2,000 to 800 tokens saves $0.003 per call.
#   At 10M calls/month that is $30K annually from a two-hour change.
#
# WHEN TO USE IT
#   - Any downstream step that only needs structured data, not prose
#   - Pipelines where the response is parsed programmatically
#   - Classification, extraction, scoring, and routing tasks
#
# WHEN TO SKIP IT
#   - User-facing responses where humans read the output directly
#   - Tasks where the explanation is as important as the answer
#
# USAGE
#   export ANTHROPIC_API_KEY=your_key_here
#   python -m token_cost_anatomy.structured_output
# =============================================================================

import anthropic
import json
import os
from dataclasses import dataclass


@dataclass
class CostSignal:
    """Parsed cost signal returned by extract_cost_signals()."""
    anomaly_detected: bool
    severity: str                       # "low" | "medium" | "high"
    primary_driver: str
    recommended_action: str
    estimated_monthly_waste_usd: float


def extract_cost_signals(
    raw_resource_data: str,
    model: str = "claude-sonnet-4-6",
) -> CostSignal:
    """
    Sends resource inventory data to Claude and returns a compact cost signal.

    Args:
        raw_resource_data: JSON or plain-text resource inventory dump.
        model:             Anthropic model to use.

    Returns:
        CostSignal dataclass.

    Raises:
        json.JSONDecodeError: If the model returns malformed JSON.
        ValueError:           If severity contains an unexpected value.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=model,
        max_tokens=512,  # hard ceiling - tune to your schema's realistic max
        system="""You are a cloud cost signal extractor.

Respond ONLY with a valid JSON object matching this exact schema.
No preamble, no explanation, no markdown fences. Raw JSON only.

{
  "anomaly_detected": <boolean>,
  "severity": "<low|medium|high>",
  "primary_driver": "<one sentence describing the top cost driver>",
  "recommended_action": "<one sentence describing the highest-impact fix>",
  "estimated_monthly_waste_usd": <number>
}""",
        messages=[
            {
                "role": "user",
                "content": f"Analyze this resource data:\n\n{raw_resource_data}",
            }
        ],
    )

    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"Model returned malformed JSON. Raw response was: {raw}",
            exc.doc,
            exc.pos,
        )

    valid_severities = {"low", "medium", "high"}
    if data.get("severity") not in valid_severities:
        raise ValueError(
            f"Unexpected severity '{data.get('severity')}'. "
            f"Expected one of {valid_severities}."
        )

    return CostSignal(
        anomaly_detected=bool(data["anomaly_detected"]),
        severity=data["severity"],
        primary_driver=data["primary_driver"],
        recommended_action=data["recommended_action"],
        estimated_monthly_waste_usd=float(data["estimated_monthly_waste_usd"]),
    )


if __name__ == "__main__":
    sample = """
    Subscription: sub-prod-1234
    Resources:
      - 12x Standard_D8s_v3 VMs, avg CPU 3%, running 24/7
      - 4x Premium SSD P30 disks unattached for 47 days
      - Azure OpenAI endpoint: 0 requests in last 14 days, dedicated capacity
    Tags: None applied on any resource
    Monthly spend: $28,400 vs $19,200 prior month (+47%)
    """

    signal = extract_cost_signals(sample)
    print(f"Anomaly   : {signal.anomaly_detected}")
    print(f"Severity  : {signal.severity}")
    print(f"Driver    : {signal.primary_driver}")
    print(f"Fix       : {signal.recommended_action}")
    print(f"Est. waste: ${signal.estimated_monthly_waste_usd:,.2f}/mo")
