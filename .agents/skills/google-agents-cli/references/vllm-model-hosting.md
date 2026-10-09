---
title: "vLLM Model Hosting"
description: "Serving OpenAI-compatible open models with vLLM and connecting via LiteLLM"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - vllm
  - self-hosted
  - cloud-run
  - tool-choice
  - models
---

# ADK vLLM Model Barındırma ve Dağıtım Rehberi

Kaynak: `https://adk.dev/agents/models/vllm/index.md`  
Destek: Python v0.1.0+ (`LiteLlm`)

---

## 1. vLLM Sunucu Gereksinimleri
ADK araçlarının (tools/function calling) vLLM üzerinde çalışabilmesi için sunucu başlatılırken şu bayraklar açılmalıdır:
- `--enable-auto-tool-choice`: Otomatik araç seçimi.
- `--tool-call-parser <parser_name>`: Modelin mimarisine uygun araç ayrıştırıcısı (örn. `hermes`, `mistral`, `llama3_json`).

---

## 2. ADK Entegrasyonu (Python `LiteLlm`)

Cloud Run veya GKE üzerinde barındırılan vLLM uç noktasına bağlanma:

```python
import subprocess
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Cloud Run IAM Bearer token alma (gerekirse):
try:
    token = subprocess.check_output(
        ["gcloud", "auth", "print-identity-token", "-q"]
    ).decode().strip()
    headers = {"Authorization": f"Bearer {token}"}
except Exception:
    headers = None

agent_vllm = LlmAgent(
    name="vllm_agent",
    model=LiteLlm(
        model="hosted_vllm/google/gemma-4-E4B-it",
        api_base="https://your-vllm-endpoint.run.app/v1",
        extra_headers=headers,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": True},
            "skip_special_tokens": False,  # Kritik: False olmalı
        },
    ),
    instruction="You are a helpful assistant running on a self-hosted vLLM endpoint.",
    tools=[custom_tool],
)
```
