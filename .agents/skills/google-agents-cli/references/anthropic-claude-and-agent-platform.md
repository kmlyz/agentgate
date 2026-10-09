---
title: "Anthropic Claude & Agent Platform"
description: "Orchestrating Anthropic Claude models natively on Vertex AI and direct API with adaptive thinking"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - anthropic
  - claude
  - vertex-ai
  - adaptive-thinking
  - models
---

# Google ADK Anthropic Claude ve Agent Platform Modelleri Rehberi

Kaynaklar:  
- `https://adk.dev/agents/models/anthropic/index.md`  
- `https://adk.dev/agents/models/agent-platform/index.md`  
Destek: Python v0.1.0+, Java v0.2.0+

---

## 1. Python ile Claude Modelleri Kullanımı

ADK Python içinde Anthropic Claude modelleri iki ana yolla çalıştırılabilir:

### Yol A: Google Cloud Agent Platform (Vertex AI) - Önerilen Kurumsal Yöntem
Google Cloud üzerinde yönetilen Claude modellerine doğrudan kurumsal kimlik ve faturalandırma ile erişilir.

1. **Bağımlılık:**
   ```powershell
   pip install "anthropic[vertex]"
   ```
2. **Ortam Değişkenleri:**
   ```text
   GOOGLE_GENAI_USE_ENTERPRISE=True
   GOOGLE_CLOUD_PROJECT=proje-id
   GOOGLE_CLOUD_LOCATION=us-east5  # Claude destekli Vertex bölgesi
   ```
   Ayrıca Application Default Credentials (ADC) doğrulanmış olmalıdır (`gcloud auth application-default login`).

3. **Otomatik Kayıt Defteri Çözümlemesi (Registry Routing):**
   ADK'nın dahili kayıt defteri `claude-3-*` ve `claude-*-4*` kalıplarındaki model isimlerini otomatik olarak `Claude` bağdaştırıcısına yönlendirir:

```python
from google.adk.agents import LlmAgent
from google.genai import types

claude_agent = LlmAgent(
    name="claude_vertex_agent",
    model="claude-3-sonnet@20240229",  # veya claude-3-7-sonnet
    instruction="You are a senior analyst powered by Anthropic Claude on Vertex AI.",
    generate_content_config=types.GenerateContentConfig(max_output_tokens=4096),
    tools=[analysis_tool],
)
```

> [!NOTE]
> İsmi bu şablonlara uymayan özel bir Claude uç noktası için `google.adk.models.Claude` sınıfı açıkça örneklenebilir:
> `LlmAgent(model=Claude(model="custom-claude-endpoint"), ...)`

---

### Yol B: Adaptif Düşünme (Adaptive Thinking - ADK Python v1.34.0+)
Yeni Claude modelleri, sabit token bütçesi yerine muhakeme derinliğini kendi ayarlayan **adaptif düşünme** desteğine sahiptir:

> [!WARNING]
> Standart Gemini parametresi olan `thinking_config.thinking_level`, Claude modellerinde **desteklenmez** (doğrulama hatası verir).  
> Bunun yerine `AnthropicGenerateContentConfig(effort=...)` kullanılmalıdır.

```python
from google.adk.agents import LlmAgent
from google.adk.models import AnthropicGenerateContentConfig

reasoning_agent = LlmAgent(
    name="claude_reasoner",
    model="claude-sonnet-4@20250514",
    instruction="Solve complex algorithmic and architectural problems.",
    generate_content_config=AnthropicGenerateContentConfig(
        # Desteklenen seviyeler: "low", "medium", "high", "xhigh", "max"
        effort="high",
    ),
)
```

---

### Yol C: Doğrudan Anthropic API (LiteLLM ile)
Doğrudan Anthropic API anahtarı kullanılarak `LiteLlm` bağdaştırıcısı üzerinden çalıştırma:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

direct_claude_agent = LlmAgent(
    name="direct_claude_agent",
    model=LiteLlm(
        model="anthropic/claude-3-7-sonnet-20250219",
        api_key="sk-ant-...",
    ),
    instruction="Assist user with general inquiries.",
)
```

---

## 2. Java ile Claude Modelleri Kullanımı

Java ADK'da `com.google.adk.models.Claude` sınıfı hem doğrudan Anthropic API hem de Vertex AI arka ucu (`VertexBackend`) için kullanılır:

### Vertex AI Agent Platform ile:
```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.vertex.backends.VertexBackend;
import com.google.adk.agents.LlmAgent;
import com.google.adk.models.Claude;
import com.google.auth.oauth2.GoogleCredentials;

AnthropicClient anthropicClient = AnthropicOkHttpClient.builder()
    .backend(
        VertexBackend.builder()
            .region("us-east5")
            .project("proje-id")
            .googleCredentials(GoogleCredentials.getApplicationDefault())
            .build())
    .build();

LlmAgent claudeAgent = LlmAgent.builder()
    .model(new Claude("claude-3-7-sonnet", anthropicClient))
    .name("claude_java_agent")
    .instruction("You are an assistant powered by Claude on Vertex AI.")
    .build();
```

---

## 3. Agent Platform MaaS Açık Modeller (Meta Llama 4 Scout)

Google Cloud Agent Platform Model-as-a-Service (MaaS) havuzundaki açık kaynaklı modeller `LiteLlm` ile doğrudan çağrılabilir:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

llama_agent = LlmAgent(
    name="llama4_agent",
    model=LiteLlm(
        model="vertex_ai/meta/llama-4-scout-17b-16e-instruct-maas"
    ),
    instruction="You are a helpful assistant powered by Meta Llama 4 Scout on Vertex AI.",
)
```
