---
title: "Gemini Deferred Scheduling"
description: "Off-peak batch processing, service tiers, and asynchronous interaction queuing in ADK"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - gemini
  - deferred-scheduling
  - service-tiers
  - batch
  - models
---

# Google ADK Gemini Deferred Scheduling & Service Tiers Rehberi

Kaynak: `https://adk.dev/agents/models/google-gemini/deferred-schedule/index.md`  
Destek: ADK Python v2.10.0+ (Preview)  
Gereksinim: Google Cloud Project Allowlist & Gemini Interactions API (`use_interactions_api=True`)

---

## 1. Genel Bakış ve Mimari

Farklı ajan iş yüklerinin gecikme (latency) gereksinimleri farklıdır:
- Etkileşimli bir asistan kullanıcıya anında yanıt vermelidir.
- Toplu doküman özetleme, veri ayıklama veya periyodik değerlendirme (eval) işleri kapasite bekleyebilir.

**Deferred Scheduling (Gecikmeli Zamanlama)**, model çağrılarını yoğun saatlerde pahalı ve sıkışık etkileşimli kapasiteyle yarıştırmak yerine, **yoğun olmayan (off-peak)** kapasitede arka uç kuyruğuna (queue) alarak çalıştırır.

### Nasıl Çalışır?
1. İstek `ServiceTier.DEFERRED` ile gönderildiğinde Google arka ucu çağrıyı kuyruğa alır ve hemen bir `interaction_id` döner.
2. ADK Runner, bu sonucu üstel geri çekilme (exponential backoff) ile arka planda otomatik olarak sorgular (polling).
3. Sonuç hazır olduğunda standart bir olay (`event`) olarak `run_async` döngüsüne iletilir. İstemci tarafında hiçbir ek sorgulama kodu yazılması gerekmez.
4. Çok turlu veya araç çağıran ajanlarda her tur (turn) kendi bağımsız etkileşim kuyruğuna girer.

---

## 2. Kapasite Kademeleri (`ServiceTier`)

`RunConfig` nesnesinin `service_tier` parametresi her model çağrısının kapasite havuzunu belirler:

| Kademe (`ServiceTier`) | Açıklama |
| :--- | :--- |
| `ServiceTier.DEFERRED` (`'deferred'`) | Çağrıyı yoğun olmayan kapasitede kuyruğa alır. Kapasite kısıtında hata fırlatmak yerine sırasını bekler. **Streaming ile kullanılamaz.** |
| `ServiceTier.FLEX` (`'flex'`) | Düşük maliyetli, gecikme garantisi olmayan best-effort havuzu. |
| `ServiceTier.STANDARD` (`'standard'`) | Varsayılan kapasite havuzu (atanmadığında varsayılan olarak kullanılır). |
| `ServiceTier.PRIORITY` (`'priority'`) | Gecikmeye duyarlı kritik çağrılar için rezerve kapasite. |

---

## 3. Kod Örneği (Python)

> [!IMPORTANT]
> `service_tier` ayarı model veya ajan tanımına **değil**, çalıştırma anında `RunConfig` nesnesine verilir. Bu sayede aynı ajan hem anlık hem de toplu işlerde kullanılabilir.

```python
import asyncio
from google.adk.agents import LlmAgent, RunConfig
from google.adk.apps import App
from google.adk.models import ServiceTier
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

# 1. Model mutlaka use_interactions_api=True ile oluşturulmalıdır
batch_agent = LlmAgent(
    name="batch_processor",
    model=Gemini(
        model="gemini-flash-latest",
        use_interactions_api=True,  # Zorunlu gereksinim
    ),
    instruction="Process input documents and produce thorough summaries.",
)

app = App(name="batch_pipeline", root_agent=batch_agent)
runner = InMemoryRunner(app=app)


async def execute_batch_task():
    session = await runner.session_service.create_session(
        app_name=app.name, user_id="worker_1", session_id="job_101"
    )

    # 2. Çalıştırma konfigürasyonunda DEFERRED kademesini seçin
    run_config = RunConfig(service_tier=ServiceTier.DEFERRED)

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Analyze and summarize the annual report.")],
    )

    # İsteğe bağlı: İstemci tarafında tavan bekleme süresi (deadline)
    try:
        async with asyncio.timeout(600):  # 10 dakika tavan süre
            async for event in runner.run_async(
                user_id="worker_1",
                session_id=session.id,
                new_message=message,
                run_config=run_config,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text)
    except TimeoutError:
        print("İstemci bekleme süresi aşıldı.")


# asyncio.run(execute_batch_task())
```

> [!WARNING]
> **Zaman Aşımı ve Faturalandırma:** `asyncio.timeout()` yalnızca ADK'nın sonucu yoklamasını durdurur; Google arka ucundaki kuyruktaki işi iptal etmez. Çağrı tamamlanır ve faturalandırılır. İptal mekanizması olarak kullanılmamalıdır.

---

## 4. HTTP ve Cloud Run Yapılandırması

ADK API Sunucusu (`adk api_server`) üzerinden istek atarken:
```json
{
  "app_name": "batch_pipeline",
  "user_id": "worker_1",
  "session_id": "job_101",
  "new_message": {
    "role": "user",
    "parts": [{"text": "Summarize batch documents"}]
  },
  "service_tier": "deferred"
}
```

- `/run_sse` kullanılıyorsa `"streaming": false` verilmelidir (aksi takdirde HTTP 422 döner).
- Cloud Run veya Load Balancer ingress zaman aşımları kuyrukta bekleme süresini karşılayacak şekilde artırılmalıdır (örn. `Cloud Run request timeout`). Uzun işler için Google Cloud Agent Platform / Agent Runtime container mimarisi önerilir.

---

## 5. Kritik Sınırlar ve Hata Ayıklama

1. **Streaming ile Kullanılamaz:**
   `RunConfig(service_tier=ServiceTier.DEFERRED, streaming_mode=StreamingMode.SSE)` doğrudan `pydantic.ValidationError` üretir.
2. **Yalnızca Gemini + Interactions API:**
   Ajanın modeli `use_interactions_api=True` olan bir `Gemini` örneği değilse, ADK kademeyi sessizce düşürür ve standart kapasitede çalıştırır. Loglarda şu uyarı aranmalıdır:
   ```text
   run_config.service_tier=... has no effect for agent <name>: its model does not
   use the interactions API...
   ```
3. **Yeniden Başlatmada Bağlanma Yoktur (No Resumption):**
   İstemci süreci çöker veya yeniden başlarsa bekleyen kuyruk etkileşimine tekrar bağlanılamaz.
