---
title: Importing Models
description: How to import models from LM Studio, Hugging Face GGUF, or Ollama.
---

## Importing from LM Studio

If you have downloaded GGUF models in LM Studio (`~/.cache/lm-studio/models`), you can import them into `ccl` with a single command:

```bash
ccl --import-lm-studio
```

This scans your LM Studio cache, registers each model with Ollama, and automatically adds `-ctx128k` variants.

## Importing GGUF Files

To import any standalone GGUF file:

```bash
ccl --import-gguf /path/to/model.gguf --name my-model
```

## Pulling from Ollama

Pull any model using the standard Ollama CLI:

```bash
ollama pull qwen2.5-coder:14b
```

Then synchronize model definitions:

```bash
ccl --sync
```
