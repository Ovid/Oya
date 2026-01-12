# Product Overview

Oya is a local-first, editable wiki generator for codebases that creates comprehensive documentation from your code and allows you to correct AI mistakes.

## Core Concept

Unlike traditional AI documentation tools, Oya is **editable and trustworthy**:
- Generates DeepWiki-style documentation (overview, architecture, workflows, directories, files)
- Allows human corrections through in-UI markdown notes
- Treats corrections as ground truth for future generations
- Stores all artifacts in `.oyawiki/` within your repository

## Key Features

- **Evidence-Gated Q&A**: Ask questions with answers backed by citations
- **Human Corrections**: Add notes to fix AI mistakes; corrections override AI inference
- **Local-First**: All data stays in your repo, fully committable to git
- **Multi-Provider LLM**: Works with OpenAI, Anthropic, Google, or local Ollama
- **Docker-Only**: Entire system runs via Docker Compose

## Target Users

Developers who need trustworthy, editable documentation for their codebases that integrates with their git workflow and can be corrected when AI gets things wrong.

## Status

Currently in ALPHA - not suitable for production use.