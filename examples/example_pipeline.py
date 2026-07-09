# =============================================================================
# example_pipeline.py
# End-to-end cost governance pipeline combining all four modules.
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
#   Simulates a nightly cost governance job that:
#     1. Extracts structured cost signals from resource inventory (mocked here)
#     2. Routes a heavier model for extraction, a cheaper one for summaries
#     3. Logs every call with team + use_case attribution via tracked_call
#     4. Prints a cost rollup at the end
#
#   Replace the RESOURCE_PAYLOADS list with live API calls to Azure Resource
#   Graph, AWS Cost Explorer, or GCP Asset Inventory in production.
#
# USAGE
#   export ANTHROPIC_API_KEY=your_key_here
#   cd token-cost-anatomy
#   python examples/example_pipeline.py
# =============================================================================

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from token_cost_anatomy.tracked_call import tracked_call, summarize_costs
from token_cost_anatomy.structured_output import extract_cost_signals


RESOURCE_PAYLOADS = [
    {
        "subscription": "sub-prod-1234",
        "data": """
            12x Standard_D8s_v3 VMs, avg CPU 3%, running 24/7, no stop schedule
            4x Premium SSD P30 disks unattached for 47 days
            Azure OpenAI dedicated endpoint: 0 requests in last 14 days
            Monthly spend: $28,400 vs $19,200 prior month (+47%)
            Tags: None applied on any resource
        """,
    },
    {
        "subscription": "sub-dev-5678",
        "data": """
            3x GPU NC6 VMs used for ML training, idle 9 days
            Storage account with LRS redundancy on DR-designated data
            Monthly spend: $4,100 vs $4,050 prior month (+1.2%)
            Tags: environment=dev, team=ml-platform
        """,
    },
]


def run():
    print("=" * 60)
    print("  Token Cost Anatomy - Example Pipeline")
    print("  Author: Shannon Eldridge-Kuehn | shankuehn.io")
    print("=" * 60)
    print()

    findings = []

    for payload in RESOURCE_PAYLOADS:
        sub = payload["subscription"]
        print(f"Analyzing: {sub}")

        try:
            # Sonnet for signal extraction - needs reasoning quality
            signal = extract_cost_signals(payload["data"], model="claude-sonnet-4-6")
            findings.append({"subscription": sub, "signal": signal})
            print(f"  Anomaly  : {signal.anomaly_detected}")
            print(f"  Severity : {signal.severity}")
            print(f"  Driver   : {signal.primary_driver}")
            print(f"  Fix      : {signal.recommended_action}")
            print(f"  Waste    : ${signal.estimated_monthly_waste_usd:,.2f}/mo")
            print()
        except Exception as exc:
            print(f"  ERROR: {exc}\n")

    # Haiku for summary - cheaper model, simpler task
    finding_lines = "\n".join(
        f"- {f['subscription']}: {f['signal'].primary_driver} "
        f"(${f['signal'].estimated_monthly_waste_usd:,.0f}/mo waste)"
        for f in findings
        if f.get("signal")
    )

    print("Generating executive summary (Haiku - lower cost for simple task)...\n")
    summary = tracked_call(
        messages=[
            {
                "role": "user",
                "content": (
                    "Write a 3-sentence executive summary of these cloud cost findings "
                    f"for a CTO audience:\n\n{finding_lines}"
                ),
            }
        ],
        model="claude-haiku-4-5",
        max_tokens=256,
        team="finops-platform",
        use_case="executive-summary",
    )

    print("Executive Summary:")
    print(summary)
    print()

    print("=" * 60)
    print("  Cost Attribution Rollup")
    print("=" * 60)
    print(json.dumps(summarize_costs(), indent=2))


if __name__ == "__main__":
    run()
