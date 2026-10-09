---
title: "Agent Platform Hosted Models"
description: "Deploying and routing Model Garden, fine-tuned, and MaaS models on Google Cloud Agent Platform"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - vertex-ai
  - agent-platform
  - endpoints
  - model-garden
  - maas
  - models
---

# Google Cloud Agent Platform Barındırılan Modeller (Hosted & Fine-Tuned)

Kaynak: `https://adk.dev/agents/models/agent-platform/index.md`  
Destek: Python v0.2.0+, Java v0.1.0+  
Altyapı: Google Cloud Vertex AI / Agent Platform Endpoints & Model Garden

---

## 1. Endpoint Kaynak Adı Biçimi (Resource Name)

Google Cloud Agent Platform üzerinde dağıtılmış (Model Garden veya ince ayarlı / fine-tuned) tüm modeller kurumsal bir **Endpoint Kaynak Adı** ile temsil edilir:

```text
projects/PROJECT_ID/locations/LOCATION/endpoints/ENDPOINT_ID
```

Bu dize, ADK'da doğrudan `LlmAgent` sınıfının `model` parametresine geçirilir:

```python
from google.adk.agents import LlmAgent
from google.genai import types

custom_endpoint = "projects/my-gcp-project/locations/us-central1/endpoints/1234567890"

agent = LlmAgent(
    name="custom_hosted_agent",
    model=custom_endpoint,
    instruction="You are a specialized enterprise assistant.",
    generate_content_config=types.GenerateContentConfig(max_output_tokens=2048),
)
```

---

## 2. ADK Model Kayıt Defteri (Registry Resolution) Kuralları

ADK'ya bir model dizesi verildiğinde dahili kayıt defteri (Registry) şu kurallarla yönlendirme yapar:

| Model Dizesi Şablonu | Çözümleme Mekanizması | Gereken Kütüphane / Ortam |
| :--- | :--- | :--- |
| `gemini-*` (örn. `gemini-flash-latest`) | `google-genai` kütüphanesi | `GOOGLE_API_KEY` veya ADC |
| `projects/.../locations/.../endpoints/...` | `google-genai` kütüphanesi (Vertex Endpoint) | `GOOGLE_GENAI_USE_ENTERPRISE=True` + ADC |
| `claude-3-*` veya `claude-*-4*` | `Claude` bağdaştırıcısı (`anthropic[vertex]`) | `anthropic[vertex]` + ADC |
| `vertex_ai/...` (MaaS modelleri) | `LiteLlm` bağdaştırıcısı | `litellm>=1.84` + ADC |

> [!NOTE]
> Bu şablonlara uymayan özel üçüncü taraf modeller veya özel adaptörler için doğrudan ilgili sınıf (`Claude(...)`, `LiteLlm(...)`, `Gemini(...)`) örneği oluşturulmalıdır.

---

## 3. Model Garden Dağıtımları & İnce Ayarlı (Fine-Tuned) Modeller

### A. Model Garden'dan Dağıtılan Açık Modeller (örn. Llama 3)
Model Garden üzerinden Vertex AI Endpoint'ine dağıtılmış bir Llama 3 modeli doğrudan endpoint dizesiyle çağrılır:

```python
from google.adk.agents import LlmAgent

llama_endpoint = "projects/my-prj/locations/us-central1/endpoints/9876543210"

agent_llama = LlmAgent(
    name="llama3_agent",
    model=llama_endpoint,
    instruction="You are an assistant running on self-hosted Llama 3 on Vertex AI.",
)
```

### B. İnce Ayarlı (Fine-Tuned) Gemini Modelleri
Kurumsal veriyle eğitilmiş ince ayarlı Gemini modelleri de aynı endpoint mekanizmasını kullanır:

```python
from google.adk.agents import LlmAgent

finetuned_endpoint = "projects/my-prj/locations/us-central1/endpoints/finetuned-gemini-id"

agent_finetuned = LlmAgent(
    name="finetuned_agent",
    model=finetuned_endpoint,
    instruction="You are a specialized legal document reviewer fine-tuned on corporate contracts.",
)
```

### C. Java ile Endpoint Kullanımı:
```java
import com.google.adk.agents.LlmAgent;
import com.google.adk.models.Gemini;

String endpoint = "projects/my-prj/locations/us-central1/endpoints/1234567890";

LlmAgent agent = LlmAgent.builder()
    .model(Gemini.builder().modelName(endpoint).build())
    .name("vertex_hosted_agent")
    .instruction("Assisting user with hosted model.")
    .build();
```

---

## 4. Model-as-a-Service (MaaS) Açık Modelleri

Altyapı veya GPU tahsis etmeden (serverless) Google Cloud tarafından yönetilen açık kaynaklı modeller `LiteLlm` ile doğrudan tüketilir:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Meta Llama 4 Scout (MaaS)
maas_agent = LlmAgent(
    name="llama4_scout_agent",
    model=LiteLlm(model="vertex_ai/meta/llama-4-scout-17b-16e-instruct-maas"),
    instruction="Assist user with technical analysis.",
)
```

---

## 5. İlgili Belgeler & Yetkilendirme
- Kimlik doğrulama, ADC ve Hizmet Hesabı (Service Account) yapılandırması için bkz: [`gcp-agent-platform-auth.md`](gcp-agent-platform-auth.md).
- Anthropic Claude modelleri için bkz: [`anthropic-claude-and-agent-platform.md`](anthropic-claude-and-agent-platform.md).
