---
title: "Apigee AI Gateway"
description: "Governing model traffic with Model Armor, rate limiting, and semantic caching via Apigee"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - apigee
  - ai-gateway
  - governance
  - security
  - models
---

# Apigee AI Gateway Modelleri ve Yönetişim Rehberi

Kaynak: `https://adk.dev/agents/models/apigee/index.md`  
Destek: Python v1.18.0+, Java v0.4.0+

---

## 1. Temel Yetenekler
Apigee proxy üzerinden model çağrısı yaparak kurumsal güvenlik politikaları uygulanır:
- **Model Armor:** Tehdit koruması ve güvenlik filtreleri.
- **Trafik Yönetimi:** İstek (Rate) ve belirteç (Token) sınırlama.
- **Semantik Önbellek (Semantic Caching):** Tekrar eden sorgularda maliyet ve süre optimizasyonu.
- **İzleme & Denetim:** Detaylı telemetri ve günlükleme.

---

## 2. `ApigeeLlm` ile Gemini & Agent Platform
Gemini API ve Agent Platform trafiğini Apigee proxy üzerinden geçirmek için:

```python
from google.adk.agents import LlmAgent
from google.adk.models.apigee_llm import ApigeeLlm

governed_model = ApigeeLlm(
    model="apigee/gemini-flash-latest",
    proxy_url="https://your-apigee-proxy.com/v1",
    custom_headers={"X-API-Key": "your-key"},
)

agent = LlmAgent(
    name="governed_agent",
    model=governed_model,
    instruction="You are an assistant governed by Apigee policies.",
)
```

---

## 3. `CompletionsHTTPClient` ile OpenAI Uyumlu Uç Noktalar
Apigee üzerinden standart `/chat/completions` rotalarına istek atmak için:

```python
from google.adk.models.apigee_llm import CompletionsHTTPClient
from google.adk.models.llm_request import LlmRequest
from google.genai import types

client = CompletionsHTTPClient(
    base_url="https://your-apigee-proxy.com/v1",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    retry_options=types.HttpRetryOptions(initial_delay=1.0, attempts=3),
)
```
