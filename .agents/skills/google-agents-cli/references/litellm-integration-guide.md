---
title: "LiteLLM Integration Guide"
description: "Connecting 100+ LLM providers, Windows UTF-8 configuration, and Anthropic thinking blocks"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - litellm
  - multi-model
  - windows-encoding
  - thinking-blocks
  - models
---

# ADK LiteLLM Çoklu Model Entegrasyon Rehberi

Kaynak: `https://adk.dev/agents/models/litellm/index.md`  
Destek: Python v0.1.0+ (`litellm>=1.84`)

---

## 1. Kritik Güvenlik ve Sistem Ayarları

> [!CAUTION]
> **Güvenlik Gereksinimi:** Güvenlik açığı nedeniyle `litellm>=1.84` zorunludur.

> [!IMPORTANT]
> **Windows UTF-8 Kuralı:** Windows üzerinde `UnicodeDecodeError` hatasını önlemek için UTF-8 modu zorunlu kılınmalıdır:
> ```powershell
> $env:PYTHONUTF8 = "1"
> [System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', [System.EnvironmentVariableTarget]::User)
> ```

---

## 2. Kullanım Formatı (`LiteLlm`)

Format: `LiteLlm(model="<provider>/<model_name>")`

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# OpenAI modeli (OPENAI_API_KEY gerektirir)
openai_agent = LlmAgent(
    name="openai_agent",
    model=LiteLlm(model="openai/gpt-4o"),
    instruction="You are a helpful assistant.",
)

# Doğrudan Anthropic Claude (ANTHROPIC_API_KEY gerektirir)
claude_agent = LlmAgent(
    name="claude_agent",
    model=LiteLlm(model="anthropic/claude-3-7-sonnet-20250219"),
    instruction="You are a reasoning assistant.",
)
```

---

## 3. Anthropic Düşünme Blokları (Thinking Blocks)
ADK Python v1.28.0+, `LiteLlm` üzerinden Claude 3.7+ modelleri çağrıldığında akıl yürütme bloklarını (`thinking_blocks`) ve imzalarını otomatik olarak yakalar ve çok turlu konuşmalarda tekrar modele iletir. Geliştiricinin ek bir durum yönetimi yapmasına gerek yoktur.
