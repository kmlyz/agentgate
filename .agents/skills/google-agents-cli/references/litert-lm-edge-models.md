---
title: "LiteRT-LM On-Device Models"
description: "Running local language models on CPU and edge devices using LiteRT-LM in Python and Kotlin"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - litert-lm
  - edge-ai
  - on-device
  - cpu
  - gemma
  - models
---

# ADK LiteRT-LM Uç Cihaz (On-Device) Model Rehberi

Kaynak: `https://adk.dev/agents/models/litert-lm/index.md`  
Destek: Python v0.1.0+, Kotlin v0.4.0+  
Amaç: Harici GPU/TPU gerektirmeden yerel CPU/Edge cihazlarda açık modelleri (Gemma vb.) çalıştırma.

---

## 1. Python Entegrasyonu

LiteRT-LM sunucusu (`lit` CLI) modelleri yerel HTTP servisi olarak sunar:

```bash
# Model indirme ve sunucuyu başlatma:
lit pull gemma3n-e2b
lit serve --port 8001 --verbose
```

ADK içinde standart `Gemini` adaptörüne `base_url` verilerek bağlanılır:

```python
from google.adk.agents import Agent
from google.adk.models import Gemini

agent = Agent(
    name="edge_agent",
    model=Gemini(
        model="gemma3n-e2b",
        base_url="http://localhost:8001",
    ),
    instruction="You are an on-device local assistant.",
    tools=[local_tool],
)
```

---

## 2. Kotlin Entegrasyonu

Bağımlılıklar (`build.gradle.kts`):
```kotlin
implementation("com.google.adk:google-adk-kotlin-core:1.3.0")
implementation("com.google.adk:google-adk-kotlin-litertlm:1.3.0")
implementation("com.google.ai.edge.litertlm:litertlm-jvm:0.13.1")
```

Ajan Tanımı:
```kotlin
val model = LiteRtLmModel.create(
    EngineConfig(
        modelPath = System.getenv("LITERT_LM_MODEL_PATH"),
        backend = Backend.CPU() // veya Backend.GPU()
    )
)

val agent = LlmAgent(
    name = "edge_agent",
    model = model,
    instruction = Instruction("You are an on-device assistant."),
)
```
