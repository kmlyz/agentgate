---
title: "Gemma Models & MCP Toolset"
description: "Gemma 4/3 architectures, vLLM self-hosting, and remote Model Context Protocol integration"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - gemma
  - vllm
  - model-context-protocol
  - models
---

# Google Gemma Modelleri ve MCP Araç Entegrasyon Rehberi

Kaynak: `https://adk.dev/agents/models/google-gemma/index.md`  
Destek: Python v0.1.0+, Java  
Ortamlar: Google AI Studio, Google Cloud Agent Platform / Model Garden, GKE, Cloud Run (vLLM)

---

## 1. Gemma 4 vs Gemma 3 Mimari Ayrımı

Google'ın açık ağırlıklı (open-weights) Gemma modelleri ADK içinde sürümlerine göre farklı adaptör sınıfları gerektirir:

### Gemma 4
- **Özellikler:** Yerel fonksiyon/araç çağırma (Tool Calling) ve Yapılandırılmış Çıktı (Structured Output) desteği mevcuttur.
- **Kullanım:** Doğrudan ADK'nın standart `Gemini` adaptörü ile kullanılır:
  ```python
  from google.adk.agents import LlmAgent
  from google.adk.models import Gemini

  agent = LlmAgent(
      name="gemma_agent",
      model=Gemini(model="gemma-4-31b-it"),
      instruction="You are a helpful assistant.",
      tools=[get_weather],
  )
  ```

### Gemma 3
- **Özellikler:** Model seviyesinde yerel fonksiyon çağırma veya sistem talimatı (system instruction) desteği **yoktur**.
- **Çözüm Sınıfları:** ADK'nın bu eksikliği prompt seviyesinde çözen özel sınıfları kullanılır:
  - Gemini API için: `Gemma(model="gemma-3-27b-it")` (`from google.adk.models import Gemma`)
  - Ollama için: `Gemma3Ollama()` (`litellm>=1.84` bağımlılığı gerektirir).

---

## 2. vLLM / Self-Hosted Dağıtım (Cloud Run / GKE)

Kendi altyapınızda (GKE, Cloud Run veya yerel sunucularda) vLLM ile barındırılan Gemma modellerine bağlanmak için `LiteLlm` bağdaştırıcısı kullanılır:

> [!IMPORTANT]
> **vLLM Yapılandırma Kuralları:**
> 1. `skip_special_tokens`: Araç çağırma ve düşünme (thinking) belirteçlerinin kaybolmaması için **mutlaka `False`** olmalıdır.
> 2. `enable_thinking`: Modelin muhakeme (reasoning) yeteneğini açmak için `chat_template_kwargs` altında `True` verilir.
> 3. **Kimlik Doğrulama:** Uç nokta Cloud Run üzerinde korunuyorsa `gcloud auth print-identity-token` çıktısı `Bearer` token olarak `extra_headers` içerisine eklenmelidir.

```python
import subprocess
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Cloud Run için kimlik belirteci (identity token) alma:
try:
    token = subprocess.check_output(
        ["gcloud", "auth", "print-identity-token", "-q"]
    ).decode().strip()
    headers = {"Authorization": f"Bearer {token}"}
except Exception:
    headers = None

vllm_agent = LlmAgent(
    name="vllm_gemma_agent",
    model=LiteLlm(
        model="hosted_vllm/gemma-4-31b-it",
        api_base="https://your-vllm-endpoint.run.app/v1",
        extra_headers=headers,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": True  # Akıl yürütme açık
            },
            "skip_special_tokens": False,  # Kritik: False olmalı
        },
    ),
    instruction="Analyze technical logs and diagnose issues.",
    tools=[diagnose_tool],
)
```

---

## 3. Model Context Protocol (MCP) StreamableHTTP Entegrasyonu

ADK, uzaktaki Model Context Protocol (MCP) sunucularını doğrudan ajan araç seti (`tools`) olarak entegre edebilir.

### Örnek: Google Maps MCP Sunucusu Entegrasyonu
- **MCP Sunucu Uç Noktası:** `https://mapstools.googleapis.com/mcp`
- **Sınıflar:** `McpToolset` ve `StreamableHTTPConnectionParams`

```python
import os
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

maps_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mapstools.googleapis.com/mcp",
        headers={"X-Goog-Api-Key": os.getenv("MAPS_API_KEY")},
    )
)

tour_agent = LlmAgent(
    name="city_tour_agent",
    model=Gemini(model="gemma-4-31b-it"),
    instruction=(
        "You are an expert guide. Search places and compute walking routes "
        "using available MCP tools. Always use exact place_id or lat_lng."
    ),
    tools=[maps_toolset],
)
```

Bu desen sayesinde üçüncü taraf veya kurumsal MCP sunucuları (veritabanı MCP, GitHub MCP, Maps MCP vb.) herhangi bir ara kodlama olmadan doğrudan ADK ajanının yetenek havuzuna katılır.
