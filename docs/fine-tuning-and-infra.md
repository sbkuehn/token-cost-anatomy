# Fine-tuning and Inference Infrastructure Notes

> Author: Shannon Eldridge-Kuehn | Cloudy Musings | shankuehn.io

This document covers the two token cost buckets without dedicated source files
in this repo: fine-tuning tokens (12%) and inference infrastructure (10%).

---

## Fine-tuning Tokens (12%)

Fine-tuning costs are bursty and high-visibility. They get approved once,
shipped, and forgotten until the inference tail starts compounding.

### Before You Fine-tune, Ask This

Do you actually need fine-tuning, or will one of these get you there?

- **Few-shot prompting** - 5 to 10 examples in the system prompt
- **RAG** - retrieval-augmented generation with a vector DB
- **Prompt engineering** - structured instructions and output constraints

Fine-tuning is the right call for consistent formatting, style adherence,
and highly domain-specific tasks where in-context examples fall short.
It is not the right call for most knowledge retrieval problems.

### LoRA and PEFT Adapters

Instead of full model re-training, use parameter-efficient fine-tuning:

- [Hugging Face PEFT](https://huggingface.co/docs/peft/en/index)
- LoRA (Low-Rank Adaptation)
- QLoRA (quantized LoRA for lower memory requirements)

Pattern: fine-tune a shared base model once, attach lightweight adapters
per use case. Multiple teams share the base, each owns their adapter.

### The Inference Tail Problem

Training costs are one-time and visible.
Inference costs on a fine-tuned model are continuous.

A model trained for $20K might generate $8K per month in inference costs
that nobody forecasted. Run this before approving a training run:

```
Annual inference cost = (calls/month x avg_tokens x price_per_token) x 12
```

---

## Inference Infrastructure (10%)

### The Idle Endpoint Problem

Teams provision GPU endpoints, ship the feature, and never right-size.
The endpoint runs 24/7 regardless of actual call volume.

### Recommended Approach by Workload Type

| Pattern | Recommendation |
|---------|----------------|
| Bursty, unpredictable | Serverless / pay-per-request |
| Steady, high volume | Reserved capacity after 90 days of baseline data |
| Batch, non-real-time | Spot / preemptible with queue |
| Internal tooling | Shared endpoint with routing layer |

### Managed Endpoint Options

- **Azure AI Foundry** - serverless inference with auto-scaling
- **AWS Bedrock** - on-demand and provisioned throughput tiers
- **Vertex AI** - dedicated and shared GPU endpoints

Start serverless. Move to reserved capacity only once you have 90 days
of stable call volume data to justify the commitment.

### ARM Migration

Graviton on AWS, Ampere on Azure: 10-20% cost reduction, zero model changes.
Not exciting. Genuinely works. Run it as a quarterly check on any dedicated
compute you own.

---

## Pricing References

Verify before budgeting. These change:

- Anthropic: https://www.anthropic.com/pricing
- AWS Bedrock: https://aws.amazon.com/bedrock/pricing/
- Azure AI Foundry: https://azure.microsoft.com/en-us/pricing/details/ai-foundry/
- Vertex AI: https://cloud.google.com/vertex-ai/pricing
- Voyage AI (embeddings): https://www.voyageai.com/pricing
