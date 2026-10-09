---
title: "ADK MemoryService Architecture Guide (Long-Term Knowledge, Memory Bank & RAG)"
description: "Comprehensive guide to Google ADK MemoryService covering BaseMemoryService methods, InMemoryMemoryService, VertexAiMemoryBankService with LLM consolidation, VertexAiRagMemoryService over Knowledge Engine, load_memory tool, and multi-memory architecture patterns."
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - memory
  - memory-service
  - rag
  - knowledge-engine
  - vertex-ai
  - vector-search
  - python
  - typescript
  - go
  - java
  - kotlin
  - architecture
---

# Google ADK Uzun Vadeli Hafıza Rehberi (`MemoryService`, Memory Bank & RAG)

Bir konuşma oturumu (`Session`), tek bir diyalog boyunca gerçekleşen olayları (`events`) ve geçici çalışma verilerini (`state`) takip ederken; **`MemoryService`**, kullanıcının geçmişteki tüm etkileşimlerini ve harici kurumsal bilgi kaynaklarını kapsayan **aranabilir, uzun vadeli kurumsal hafızayı** yönetir.

- **`Session` / `State`:** Kısa süreli çalışma belleğidir (tek bir sohbette ne konuşulduğu).
- **`MemoryService`:** Uzun süreli arşiv ve kütüphanedir (kullanıcının geçmiş tercihleri, önceki haftalarda konuşulan projeler, şirket dokümanları).

---

## 1. `BaseMemoryService` Sözleşmesi ve Temel İşlemler

Tüm bellek sağlayıcıları `BaseMemoryService` (Go'da `memory.Service`) soyut sınıfından türer ve 4 temel işlem sunar:

1. **`add_session_to_memory(session, custom_metadata=None)`**:
   Tamamlanmış bir `Session` nesnesini hafızaya ekler. Oturumdaki kritik bilgileri otomatik olarak ayıklar ve uzun vadeli depoya kaydeder.
2. **`add_events_to_memory(app_name, user_id, events, session_id=None, custom_metadata=None)`**:
   Uzun süren bir oturumu baştan sona yeniden yüklemek yerine, yalnızca son turdaki yeni olay deltasını (artımlı olarak) hafızaya yazar.
3. **`add_memory(app_name, user_id, memories, custom_metadata=None)`**:
   Dış kaynaklardan veya manuel işlemlerden doğrudan açık olguları (`MemoryEntry` listesi) hafıza tabanına enjekte eder.
4. **`search_memory(app_name, user_id, query)`**:
   Ajanın veya aracın verdiği arama sorgusuna (`query`) göre anlamsal veya anahtar kelime eşleşmesi yapar; `SearchMemoryResponse` içinde `MemoryEntry` listesi döner.

### `MemoryEntry` Veri Yapısı
```python
class MemoryEntry:
    content: types.Content          # Hafızadaki mesaj veya olgu metni (Role ve Parts)
    id: Optional[str]               # Tekil kayıt kimliği
    author: Optional[str]           # Bilgiyi oluşturan yazar ('user' veya ajan)
    timestamp: Optional[float]      # Kayıt zaman damgası
    custom_metadata: Optional[dict] # Kategori, kaynak veya etiket gibi ek metaveriler
```

---

## 2. 3 Bellek Servisi Karşılaştırma Matrisi

| Özellik | `InMemoryMemoryService` | `VertexAiMemoryBankService` | `VertexAiRagMemoryService` |
| :--- | :--- | :--- | :--- |
| **Kalıcılık** | Yok (Yeniden başlatmada silinir) | **Var** (Google Agent Platform tarafından yönetilir) | **Var** (Vertex AI Knowledge Engine üzerinde saklanır) |
| **Arama Yeteneği** | Temel anahtar kelime (keyword) eşleme | **İleri seviye anlamsal (semantic) arama** | **Vektör benzerlik araması** (Vector Similarity Search) |
| **Hafıza Çıkarımı** | Tüm konuşmayı ham metin olarak tutar | Konuşmalardan anlamlı bilgileri ayıklar ve **LLM ile konsolide eder** | Tüm konuşma dökümünü RAG parçacıklarına böler |
| **Kurulum Zorluğu** | Yok (Varsayılan yerel servis) | Düşük (GCP Projesi ve Agent Runtime ID) | Orta (GCP Projesi ve Knowledge Engine RAG Corpus) |
| **Paket Gereksinimi**| `google-adk` | `google-adk[gcp]` | `google-adk[gcp]` |
| **En İyi Kullanım** | Yerel geliştirme, prototipleme, birim test | **Kullanıcıyı tanıyan, zamanla öğrenen akıllı asistanlar** | Ham konuşma dökümleri üzerinde kurumsal RAG altyapısı |

---

## 3. Servislerin Kurulumu ve Yapılandırması

### 1. `InMemoryMemoryService` (Yerel Geliştirme)
```python
from google.adk.memory import InMemoryMemoryService
memory_service = InMemoryMemoryService()
```

### 2. `VertexAiMemoryBankService` (LLM Hafıza Konsolidasyonu)
Memory Bank, Google Cloud'un diyaloglardan otomatik hafıza çıkaran ve yeni bilgileri eskilerle birleştiren tam yönetilen servisidir.

#### Doğrudan Hafıza Enjeksiyonu ve Konsolidasyon:
- **Doğrudan Ekleme (Varsayılan):** Her `MemoryEntry` bağımsız bir kayıt olarak eklenir (`memories.create` API).
- **Konsolidasyon ile Ekleme (`enable_consolidation=True`):** Yeni eklenen bilgi mevcut bilgilerle çelişiyorsa veya tekrarsa, LLM bunları birleştirir ve günceller (`memories.generate` API).

```python
from google.adk.memory import VertexAiMemoryBankService
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part

memory_service = VertexAiMemoryBankService(
    project="my-gcp-project",
    location="us-central1",
    agent_engine_id="1234567890" # Agent Platform Agent Engine ID
)

# Konsolidasyon ile olgu enjeksiyonu:
await memory_service.add_memory(
    app_name="customer_care",
    user_id="user_42",
    memories=[
        MemoryEntry(content=Content(parts=[Part(text="Kullanıcının tercih ettiği koltuk: Pencere kenarı.")]))
    ],
    custom_metadata={"enable_consolidation": True}
)
```

CLI ile çalıştırma:
```powershell
adk web my_agent/ --memory_service_uri="agentengine://1234567890"
```

### 3. `VertexAiRagMemoryService` (Knowledge Engine Vektör Araması)
Konuşmaları Knowledge Engine vektör veritabanında saklayıp kosinüs benzerliğiyle geri çağırmak için kullanılır:

```python
from google.adk.memory import VertexAiRagMemoryService

memory_service = VertexAiRagMemoryService(
    rag_corpus="projects/PROJECT_ID/locations/LOCATION/ragCorpora/CORPUS_ID",
    similarity_top_k=5,
    vector_distance_threshold=0.6
)
```

---

## 4. Ajanların Belleğe Erişimi

### Yöntem 1: Yerleşik `load_memory` Aracı (Tavsiye Edilen)
ADK, modelin geçmiş konuşmaları hatırlaması gerektiğinde kendi kendine tetikleyebileceği yerleşik `load_memory` aracını sunar:

```python
from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.runners import Runner

recall_agent = LlmAgent(
    name="MemoryRecallAgent",
    model="gemini-2.5-flash",
    instruction=(
        "Kullanıcının sorularını yanıtla. Yanıt geçmiş konuşmalarda olabilecek bir "
        "bilgiyse mutlaka 'load_memory' aracını kullanarak geçmişi ara."
    ),
    tools=[load_memory] # Yerleşik bellek sorgulama aracı
)

runner = Runner(
    agent=recall_agent,
    app_name="customer_app",
    session_service=session_service,
    memory_service=memory_service # Bellek servisi Runner'a bağlanmalıdır
)
```

### Yöntem 2: Özel Araç Fonksiyonu İçinde `ToolContext.search_memory`
Özel bir fonksiyon aracının içinden hafızayı sorgulamak için `ToolContext` kullanılır:

```python
from google.adk.tools import ToolContext

async def search_past_trips(query: str, tool_context: ToolContext) -> dict:
    # Framework'e bağlı olan aktif memory_service sorgulanır:
    response = await tool_context.search_memory(query)
    
    extracted = []
    for entry in response.memories:
        for part in (entry.content.parts or []):
            if part.text:
                extracted.append(part.text)
                
    return {"past_records": extracted}
```

### Yöntem 3: Kancalarda (Callbacks) Hafıza Yönetimi
Ajan veya model kancalarında (`CallbackContext`) hafızaya anlık kayıt yapmak veya arama yapmak:

```python
from google.adk.agents.callback_context import CallbackContext
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part

async def on_user_preference_callback(callback_context: CallbackContext):
    # Kullanıcı açık bir tercih belirttiyse hafızaya anında işle:
    await callback_context.add_memory(
        memories=[
            MemoryEntry(content=Content(parts=[Part(text="Kullanıcı vejetaryendir.")]))
        ]
    )
```

> [!CAUTION]
> Eğer `Runner` başlatılırken `memory_service` tanımlanmamışsa, `tool_context.search_memory()` veya `callback_context` bellek çağrıları çalışma zamanında **`IllegalStateException`** fırlatır!

---

## 5. İleri Seviye: Çoklu Bellek Servisi Deseni (Multi-Memory Pattern)

### Soru: Bir ajan aynı anda birden fazla bellek servisine bağlanabilir mi?
- **CLI / Framework Seviyesinde: HAYIR.** Standart `--memory_service_uri` veya `Runner(memory_service=...)` aynı anda yalnızca **tek bir** bellek servisi kabul eder.
- **Kod Seviyesinde: EVET (Hibrit Mimari).** Bir ajan hem sohbet geçmişini (`InMemoryMemoryService` veya Memory Bank) hem de harici şirket dokümantasyonunu (`VertexAiRagMemoryService` veya ikinci bir bellek servisi) aynı anda tarayabilir.

```python
from google.adk.agents import LlmAgent
from google.adk.memory import InMemoryMemoryService, VertexAiRagMemoryService
from google.adk.tools import ToolContext

# 1. Dokümanlar için ikinci bağımsız bellek servisi
docs_rag_memory = VertexAiRagMemoryService(
    rag_corpus="projects/my-p/locations/us-central1/ragCorpora/company_docs",
    similarity_top_k=3
)

# 2. İki hafızayı da tek araçta tarayan hibrit fonksiyon
async def search_all_sources(query: str, tool_context: ToolContext) -> dict:
    """Hem geçmiş konuşmaları hem de şirket dokümanlarını birlikte tarar."""
    # A) Konuşma geçmişi (Runner'daki ana servisten gelir):
    conversational = await tool_context.search_memory(query)
    
    # B) Doküman korpusu (Manuel oluşturulan RAG servisinden gelir):
    docs = await docs_rag_memory.search_memory(
        app_name="docs_repo",
        user_id="shared_pool",
        query=query
    )
    
    return {
        "conversations": [p.text for e in conversational.memories for p in e.content.parts if p.text],
        "documents": [p.text for e in docs.memories for p in e.content.parts if p.text]
    }

multi_agent = LlmAgent(
    name="HybridKnowledgeAgent",
    model="gemini-2.5-flash",
    instruction="Kullanıcı sorularını yanıtlarken search_all_sources aracını kullan.",
    tools=[search_all_sources]
)
```

---

## 6. Uçtan Uca Python Yaşam Döngüsü Örneği

```python
import asyncio
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.tools import load_memory
from google.genai import types

async def main():
    app_name, user_id = "support_desk", "vip_customer_9"
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

    # 1. Bilgi Toplama Ajanı
    ingest_agent = LlmAgent(name="IngestAgent", model="gemini-2.5-flash", instruction="Kullanıcıyı dinle.")
    runner1 = Runner(agent=ingest_agent, app_name=app_name, session_service=session_service, memory_service=memory_service)

    # 1. Tur: Oturum aç ve tercihi bildir
    s1 = "session_001"
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=s1)
    msg1 = types.Content(parts=[types.Part.from_text("En sevdiğim renk laciverttir.")], role="user")
    
    async for event in runner1.run_async(user_id=user_id, session_id=s1, new_message=msg1):
        pass

    # Oturumu tamamla ve Hafızaya Kaydet (Ingest)
    completed_s1 = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=s1)
    await memory_service.add_session_to_memory(completed_s1)
    print("Oturum 1 hafıza kütüphanesine aktarıldı.")

    # 2. Tur: Farklı bir oturumda geçmişi sorgula
    recall_agent = LlmAgent(
        name="RecallAgent",
        model="gemini-2.5-flash",
        instruction="Kullanıcının sorusunu yanıtla. Geçmiş tercihleri için 'load_memory' aracını kullan.",
        tools=[load_memory]
    )
    runner2 = Runner(agent=recall_agent, app_name=app_name, session_service=session_service, memory_service=memory_service)

    s2 = "session_002"
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=s2)
    msg2 = types.Content(parts=[types.Part.from_text("Benim en sevdiğim renk hangisiydi?")], role="user")

    async for event in runner2.run_async(user_id=user_id, session_id=s2, new_message=msg2):
        if event.is_final_response():
            print(f"\nAjan Yanıtı: {event.content.parts[0].text}")

if __name__ == "__main__":
    asyncio.run(main())
```
