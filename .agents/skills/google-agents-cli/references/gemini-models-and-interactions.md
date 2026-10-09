---
title: "Gemini Models & Interactions API"
description: "Google Gemini model configuration, stateful Interactions API, tool compatibility, and retry policies"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
    - adk
    - gemini
    - interactions-api
    - tools
    - error-handling
    - models
---

# Google Gemini Modelleri ve Interactions API Rehberi

Kaynak: `https://adk.dev/agents/models/google-gemini/index.md`\
Destek: Python v0.1.0+, TypeScript v0.2.0+, Go v0.1.0+, Java v0.2.0+, Kotlin
v0.1.0+

---

## 1. Model Seçimi ve Bölgesel Kurallar

Google ADK, Gemini modellerini hem takma ad (alias) hem de açık sürüm dizesiyle
kabul eder:

```python
from google.adk.agents import Agent

# En güncel kararlı Flash modelini otomatik seçmek için:
agent = Agent(
    name="flash_agent",
    model="gemini-flash-latest",
    instruction="You are a fast, factual assistant.",
)
```

> [!NOTE]
> `gemini-flash-latest` takma adı Google AI Studio genel uç noktasında çalışır.
> Ancak Google Cloud / Vertex AI üzerinde bölgesel bir uç nokta (örneğin
> `us-central1`) kullanıyorsanız bu takma ad çözümlenemeyebilir. Bu durumda açık
> model kimliği (`gemini-2.0-flash`, `gemini-1.5-pro` vb.) belirtilmelidir.

> [!IMPORTANT]
> **Canlı ve Sesli Ajanlar İçin Özel Modeller (Live Models):** Çift yönlü
> WebSocket akışı (`run_live()`) kullanan canlı ajanlar standart Gemini
> modellerini kullanamaz. Doğrudan ses üreten yerel modeller
> (`gemini-live-2.5-flash-native-audio` veya `gemini-3.1-flash-live-preview`)
> kullanılmalıdır. Detaylı canlı model karşılaştırması ve kotalar için bkz:
> [`adk-live-guide.md` Bölüm 1.1](adk-live-guide.md#11-desteklenen-canl-modeller-ve-arka-ular-supported-live-models--backends).

---

## 2. Kimlik Doğrulama (Authentication)

`.env` dosyası veya ortam değişkenleri ile iki farklı entegrasyon yöntemi:

### A. Google AI Studio (Doğrudan Gemini API)

```text
GOOGLE_API_KEY="AIzaSy..."
```

### B. Google Cloud / Vertex AI (Gemini Enterprise Agent Platform)

```text
GOOGLE_CLOUD_PROJECT="proje-id"
GOOGLE_CLOUD_LOCATION="us-central1"
GOOGLE_GENAI_USE_ENTERPRISE="True"
```

---

## 3. Gemini Interactions API (`use_interactions_api=True`)

Destek: ADK Python v1.21.0+

Geleneksel `generateContent` API'si durumsuzdur (stateless); her istekte tüm
konuşma geçmişinin modele tekrar gönderilmesini gerektirir. **Interactions
API**, konuşmayı `previous_interaction_id` referansıyla sunucu tarafında
zincirleyerek durum bilgili (stateful) kılar:

- Uzun ve çok adımlı oturumlarda token tüketimini ve ağ yükünü ciddi biçimde
  azaltır.
- İş kuyruğu oluşturma ve off-peak kapasitede gecikmeli çalıştırma (Deferred
  Scheduling) olanakları sunar (Detaylar için bkz:
  [`deferred-scheduling-guide.md`](deferred-scheduling-guide.md)).

### Yapılandırma ve Yerleşik Araç Uyumluluk Deseni:

> [!IMPORTANT]
> **Kritik Kısıtlama:** Interactions API aktifken yerleşik Google araçları (ör.
> `GoogleSearchTool`) ile özel fonksiyon araçları (`custom function tools`) aynı
> ajanda doğrudan birlikte kullanılamaz.\
> **Çözüm:** Yerleşik araçta `bypass_multi_tools_limit=True` bayrağı ayarlanarak
> aracın bir fonksiyon aracına (`GoogleSearchAgentTool`) dönüştürülmesi
> sağlanır.

```python
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.google_search_tool import GoogleSearchTool


def get_current_weather(city: str) -> str:
    """Returns weather information for the specified city."""
    return f"Weather in {city}: 22°C, sunny"


root_agent = Agent(
    name="interactions_agent",
    model=Gemini(
        model="gemini-flash-latest",
        use_interactions_api=True,  # Interactions API'yi etkinleştir
    ),
    instruction="Assist the user using search or custom weather tools.",
    tools=[
        # bypass_multi_tools_limit=True ile fonksiyon aracına dönüştürülür:
        GoogleSearchTool(bypass_multi_tools_limit=True),
        get_current_weather,
    ],
)
```

---

## 4. 429 Kota Aşımı (RESOURCE_EXHAUSTED) & Yeniden Deneme (Retry) Politikası

Yoğun istek veya anlık kota aşımlarında istemci tarafında üstel geri çekilme
(exponential backoff) uygulanmalıdır.

### Seçenek 1: Ajan Düzeyinde `generate_content_config` ile

Model doğrudan bir dize (`model="gemini-flash-latest"`) olarak verildiğinde
kullanılır:

```python
from google.adk.agents import Agent
from google.genai import types

root_agent = Agent(
    name="resilient_agent",
    model="gemini-flash-latest",
    generate_content_config=types.GenerateContentConfig(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=1.0,  # İlk bekleme süresi (saniye)
                attempts=3,  # Maksimum deneme sayısı
            )
        )
    ),
)
```

### Seçenek 2: Model Bağdaştırıcısı (`Gemini`) Düzeyinde

Model nesnesi açıkça oluşturulduğunda:

```python
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import types

resilient_model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(initial_delay=1.0, attempts=3),
)

root_agent = Agent(
    name="resilient_agent",
    model=resilient_model,
)
```

### TypeScript Örneği:

```typescript
import { LlmAgent } from "@google/adk";

export const agent = new LlmAgent({
    name: "resilient_agent",
    model: "gemini-flash-latest",
    // Model seviyesinde HTTP veya retry konfigürasyonları eklenebilir
});
```

---

## 5. Ses ve Video Canlı Akış Desteği (Gemini Live API)

Gerçek zamanlı iki yönlü ses/video akışı (streaming) gerektiren senaryolarda
`Live API` destekleyen modeller seçilmelidir:

- `gemini-2.0-flash-exp` veya Gemini Live API resmi model kimlikleri.
- `WebSocket` üzerinden tam çift yönlü (full-duplex) iletişim için kullanılır.
