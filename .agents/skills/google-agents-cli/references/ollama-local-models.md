---
title: "Ollama Local Models"
description: "Hosting and running local open-source models with Ollama and LiteLLM in ADK"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - ollama
  - local-models
  - ollama-chat
  - offline
  - models
---

# ADK Ollama Yerel Model Entegrasyonu

Kaynak: `https://adk.dev/agents/models/ollama/index.md`  
Destek: Python v0.1.0+ (`LiteLlm`)

---

## 1. Kritik Yapılandırma Kuralları

> [!WARNING]
> Sağlayıcı adı olarak `ollama` değil, mutlaka **`ollama_chat`** kullanılmalıdır. Aksi halde sonsuz araç döngüleri ve bağlam kaybı yaşanır.

> [!IMPORTANT]
> `OLLAMA_API_BASE` ortam değişkeni tanımlanmalıdır (LiteLLM dahili çağrılarda parametre yerine bu değişkene bakar):
> ```bash
> export OLLAMA_API_BASE="http://localhost:11434"
> ```

---

## 2. Kullanım Örnekleri

### A. `ollama_chat` ile Standart Kullanım
```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    name="local_agent",
    model=LiteLlm(model="ollama_chat/gemma3:latest"),
    instruction="You are a helpful local assistant.",
    tools=[local_tool],
)
```

### B. `openai` Uyumluluk Modu ile Kullanım
```python
# export OPENAI_API_BASE="http://localhost:11434/v1"
# export OPENAI_API_KEY="anything"

root_agent = Agent(
    name="local_agent",
    model=LiteLlm(model="openai/mistral-small3.1"),
    instruction="You are a helpful local assistant.",
    tools=[local_tool],
)
```

---

## 3. Araç Desteği ve Hata Ayıklama
- **Araç Yeteneğini Doğrulama:** `ollama show <model>` komutunda `Capabilities: tools` olmalıdır.
- **Hata Ayıklama (Debug):** `import litellm; litellm._turn_on_debug()` ile giden ham HTTP istekleri incelenebilir.
