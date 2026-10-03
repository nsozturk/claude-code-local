---
title: Installation & Requirements
description: Prerequisites and setup instructions for running Claude Code on local models.
---

## Prerequisites

- **macOS** with Apple Silicon (M1/M2/M3/M4 recommended for unified memory acceleration).
- [**Claude Code**](https://docs.claude.com/en/docs/claude-code) CLI installed and available on your system `PATH`.
- [**Ollama**](https://ollama.com) running locally (`http://127.0.0.1:11434`).
- **Python 3.10+** (Standard library only; zero external `pip` dependencies).

## Installation

Clone the repository to your local machine:

```bash
git clone https://github.com/nsozturk/claude-code-local.git
cd claude-code-local
```

### Adding to PATH

To make the `ccl` command available anywhere, add the `bin/` directory to your shell configuration (`~/.zshrc` or `~/.bashrc`):

```bash
export PATH="$HOME/path-to/claude-code-local/bin:$PATH"
```

Then reload your shell:

```bash
source ~/.zshrc
```

Verify that the CLI is accessible:

```bash
ccl --help
```
