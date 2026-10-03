---
title: Recommended Models & Benchmarks
description: Tested models, context requirements, and performance characteristics.
---

## Verified Models for Claude Code

| Model | Parameters | Context Tested | Recommended VRAM | Speed (M-series) |
|---|---|---|---|---|
| `qwen2.5-coder:32b` | 32B | 128k | 36GB+ | ~28 t/s |
| `qwen2.5-coder:14b` | 14B | 128k | 18GB+ | ~45 t/s |
| `deepseek-coder-v2:16b` | 16B (MoE) | 128k | 18GB+ | ~40 t/s |
| `command-r:35b` | 35B | 128k | 36GB+ | ~25 t/s |
| `llama-3.1:8b` | 8B | 128k | 12GB+ | ~65 t/s |

## Key Recommendations

1. **Context Window**: Claude Code requires a minimum of 64k tokens for complex repositories, with 128k strongly recommended. Ensure your model is imported with `-ctx128k`.
2. **Apple Silicon Hardware**:
   - **18GB - 24GB Unified RAM**: Best suited for 8B-14B models.
   - **36GB - 48GB Unified RAM**: Ideal for 32B models.
   - **64GB - 128GB Unified RAM**: Can comfortably run 70B quantized or 32B FP16 models.
