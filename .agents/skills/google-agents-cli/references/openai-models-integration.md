---
title: "OpenAI Models Integration"
description: "Connecting OpenAI models via LiteLLM in Python and the native openaimodel package in Go"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - openai
  - gpt-4o
  - openaimodel
  - go
  - models
---

# ADK OpenAI Modelleri ve Uç Noktaları Rehberi

Kaynak: `https://adk.dev/agents/models/openai/index.md`  
Destek: Python (LiteLLM), Go v2.1.0+ (`openaimodel`)

---

## 1. Python Entegrasyonu (`LiteLlm`)
Python ortamında OpenAI modellerine ve uyumlu sunuculara `LiteLlm` bağdaştırıcısı ile erişilir:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

agent = LlmAgent(
    name="openai_agent",
    model=LiteLlm(
        model="openai/gpt-4o",
        api_key="sk-...",
    ),
    instruction="You are a helpful assistant powered by OpenAI.",
)
```

---

## 2. Go Entegrasyonu (`openaimodel`)

ADK Go, yerel `google.golang.org/adk/v2/model/openaimodel` paketiyle doğrudan destek sunar:

### A. Responses API (Varsayılan - `/v1/responses`)
```go
import (
    "context"
    "github.com/openai/openai-go/v3"
    "google.golang.org/adk/v2/agent/llmagent"
    "google.golang.org/adk/v2/model/openaimodel"
)

llm, _ := openaimodel.NewModel(context.Background(), openai.ChatModelGPT4oMini, &openaimodel.ClientConfig{})
agent, _ := llmagent.New(llmagent.Config{
    Name:        "openai_agent",
    Model:       llm,
    Instruction: "You are a helpful assistant.",
})
```

### B. Chat Completions API & Yerel Uç Noktalar (Ollama, vLLM)
Ollama veya üçüncü taraf OpenAI uyumlu sunucular için `APIChatCompletions` ve `BaseURL` kullanılır:

```go
llm, _ := openaimodel.NewModel(context.Background(), openai.ChatModelGPT4oMini, &openaimodel.ClientConfig{
    APIKey:  "key",
    BaseURL: "http://localhost:11434/v1",
    API:     openaimodel.APIChatCompletions,
})
```

---

## 3. Özellikler ve Kısıtlamalar
- **Desteklenenler:** Metin üretimi, fonksiyon/araç çağırma, JSON Schema strict-mode çıktı, akıl yürütme modelleri (o-serisi token muhasebesi).
- **Kısıtlamalar:** Salt metin (multimodal desteklenmez), yalnızca fonksiyon araçları (Google Search gibi yerleşik araçlar çalışmaz).
