---
title: "ADK Conversational Context Architecture Guide (Session, State & Memory)"
description: "Comprehensive guide to Google ADK Conversational Context covering Session properties, 7-step lifecycle, SessionService backends (InMemory, Database with 2-tier locking, Vertex AI), MemoryService, and SessionNotFoundError handling."
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - sessions
  - state
  - memory
  - session-service
  - memory-service
  - in-memory
  - database
  - concurrency
  - locking
  - vertex-ai
  - python
  - java
  - typescript
  - go
  - kotlin
  - architecture
---

# Google ADK Konuşma Bağlamı Rehberi (`Session`, `State` ve `Memory`)

Yapay zeka ajanlarının insanlarla anlamlı ve tutarlı çok turlu (multi-turn) diyaloglar kurabilmesi için konuşma geçmişini hatırlaması, bağlamı koruması ve tekrarlardan kaçınması şarttır. 

Google ADK, bu bağlamı 3 temel sütun (**`Session`**, **`State`**, **`Memory`**) ve bu sütunları yöneten 2 merkezi servis (**`SessionService`**, **`MemoryService`**) ile kurumsal seviyede yapılandırır.

---

## 1. Konuşma Bağlamının 3 Temel Sütunu

| Sütun | Temsil Ettiği Kavram | Yaşam Döngüsü & Kapsam | Yönetici Servis | Tipik Kullanım Senaryosu |
| :--- | :--- | :--- | :--- | :--- |
| **`Session`** | **Aktif Konuşma İpliği (Thread):** Kullanıcı ile ajan sistemi arasındaki tekil, kesintisiz etkileşim akışı. | Tek bir sohbet oturumu boyunca. | `SessionService` | O anki sohbetin kronolojik mesaj ve araç çağrısı geçmişi (`Events`). |
| **`State`** | **Çalışma Belleği (Scratchpad):** Aktif `Session` içinde saklanan yapılandırılmış anahtar-değer verileri. | Oturum süresince (veya `temp:` ile çağrı süresince). | `SessionService` (`session.state`) | Alışveriş sepeti, aktif bilet numarası, hesaplama ara değerleri. |
| **`Memory`** | **Uzun Vadeli Bilgi Deposu:** Geçmiş oturumları ve harici bilgi kaynaklarını kapsayan aranabilir arşiv. | Oturumlar arası kalıcı (Kullanıcı geneli). | `MemoryService` | Kullanıcının geçmiş tercihleri ("Fıstık alerjim var"), şirket intranet dokümanları. |

```mermaid
graph TD
    User["Kullanıcı"] --> Runner["Runner.run_async()"]
    
    subgraph Konuşma Bağlamı (Current Context)
        Runner <--> SS["SessionService"]
        SS <--> Session["Session (id, app_name, user_id)"]
        Session --> Events["Events (Kronolojik Mesaj & Eylem Geçmişi)"]
        Session --> State["State (Aktif Oturum Değişkenleri: sepet, tercihler)"]
    end
    
    subgraph Uzun Vadeli Hafıza (Long-Term Archive)
        Runner <--> MS["MemoryService"]
        MS <--> Memory["Memory Store (Vektör & Semantik Bilgi Tabanı)"]
        Session -.->|"Tamamlanan Oturum Bilgisi (Ingest)"| Memory
    end
```

---

## 2. `Session` Nesnesi ve Alanları

ADK'da bir kullanıcı etkileşimi başladığında, `SessionService` tarafından `google.adk.sessions.Session` nesnesi oluşturulur:

```python
class Session:
    id: str                 # Oturumun benzersiz kimliği (örn: "session_abc123")
    app_name: str           # Hangi ajan uygulamasına ait olduğu (örn: "customer_support")
    user_id: str            # Oturumun bağlı olduğu kullanıcı (örn: "user_789")
    events: list[Event]     # Kronolojik olay geçmişi (User content, Agent response, Tool calls)
    state: dict[str, Any]   # Bu oturumun çalışma belleği / scratchpad sözlüğü
    last_update_time: float # Son etkileşim Unix zaman damgası
```

- **`id`**: Tekil bir konuşma ipliğini işaret eder; oturumu durdurup devam ettirmek (`--resume`, `--session_id`) için birincil anahtardır.
- **`app_name`**: Oturumun ait olduğu ajan uygulamasının mantıksal adı veya Agent Platform Reasoning Engine kaynak yoludur.
- **`user_id`**: Oturumu belirli bir son kullanıcıyla ilişkilendirir.
- **`events`**: Ajanın önceki turlarda ne konuştuğunu ve hangi araçları çağırdığını takip ettiği temel LLM bağlam girdisidir.
- **`state`**: Araçların ve callback kancalarının çalışma zamanında durum paylaştığı sözlüktür (`initial_state` ile başlatılabilir).
- **`last_update_time`**: Oturuma son olay eklendiğinde otomatik güncellenen zaman damgasıdır (oturum zaman aşımı / TTL kontrolleri için kullanılır).

---

## 3. `State` (Çalışma Belleği) Mimarisi, Kapsam Önekleri ve Şablonlama

`Session` konuşmanın kronolojik tarihçesini (`events`) saklarken, **`state`** ajanın turlar boyunca dinamik detayları kaydettiği **çalışma belleğidir (scratchpad)**.

### 3.1. `State` Temel Karakteristiği ve Serileştirme Kuralları
- **Yapı:** Anahtarları her zaman `str` olan, değerleri ise temel serileştirilebilir tiplerden (string, number, boolean, basit liste ve sözlük) oluşan bir koleksiyondur (Python `dict`, TypeScript `Map`, Go `map[string]any`, Java `Map<String, Object>`).
- **Karmaşık Nesne Yasağı (Avoid Complex Objects):** Özel sınıf örnekleri (custom class instances), veritabanı bağlantıları veya fonksiyonlar gibi serileştirilemeyen nesneler **asla doğrudan state içine konulmamalıdır**. İhtiyaç halinde yalnızca nesnenin tekil kimliği (ID) saklanmalı, nesnenin kendisi ilgili servisten çağrılmalıdır.
- **Kalıcılık:** Durumun kalıcılığı seçilen `SessionService`'e bağlıdır: `InMemorySessionService` bellekte tutar ve yeniden başlatmada silinir; `DatabaseSessionService` ve `VertexAiSessionService` ise kalıcı veritabanına yazar.

### 3.2. Kapsam Önekleri (State Prefixes & Scope)
Anahtarların başına eklenen önekler, durumun kapsamını ve kalıcılık sınırlarını belirler:

| Önek | Kapsam (Scope) | Kalıcılık (Persistence) | Tipik Kullanım |
| :--- | :--- | :--- | :--- |
| **Öneksiz** | **Oturum Düzeyi:** Yalnızca o anki tekil `session_id`'ye aittir. | Yalnızca `Database` veya `VertexAI` ile kalıcıdır. | Görev adımları (`booking_step`), anlık filtreler. Örn: `session.state["cart_items"] = [...]` |
| **`user:`** | **Kullanıcı Düzeyi:** Belirli bir `user_id`'ye bağlıdır; o kullanıcının **tüm oturumları arasında** paylaşılır. | `Database` veya `VertexAI` ile oturumlar arası kalıcıdır. | Kullanıcı tercihleri, dil seçimi, profil bilgisi. Örn: `session.state["user:preferred_theme"] = "dark"` |
| **`app:`** | **Uygulama Düzeyi:** Belirli bir `app_name`'e bağlıdır; **tüm kullanıcılar ve tüm oturumlar** arasında küreseldir. | `Database` veya `VertexAI` ile kalıcıdır. | Küresel ayarlar, indirim kodları, ortak şablonlar. Örn: `session.state["app:global_discount"] = "SAVE20"` |
| **`temp:`** | **Çağrı (Invocation) Düzeyi:** Yalnızca tek bir kullanıcı girdisi ile nihai model yanıtı arasındaki tek turda geçerlidir. | **Kalıcı Değildir.** Çağrı bittiğinde otomatik olarak hafızadan atılır. | Ara hesaplamalar, araçlar arası geçici bayraklar. Örn: `session.state["temp:api_token"] = "..."` |

> [!TIP]
> **Alt Ajanlara Miras (Sub-Agents & InvocationContext):** Bir üst ajan (`SequentialAgent`, `ParallelAgent` vb.) bir alt ajanı çağırdığında kendi `InvocationContext`'ini aktarır. Bu sayede tüm ajan zinciri aynı invocation ID'yi ve dolayısıyla aynı **`temp:`** durumunu paylaşır.

> [!NOTE]
> **Oturum Olmadan Kullanıcı Durumunu Okuma (`get_user_state`):** Python SDK'da henüz bir oturum açılmadan kullanıcının durumunu okumak için `await session_service.get_user_state(app_name=..., user_id=...)` metodu kullanılır (anahtarlardaki `user:` öneki soyulmuş olarak döner). **İstisna:** `VertexAiSessionService`, Agent Runtime API kısıtlaması nedeniyle bu çağrıda `NotImplementedError` fırlatır; Vertex AI ortamında `list_sessions` ile oturumlar taranıp `get_session` çağrılmalıdır.

---

### 3.3. Ajan Talimatlarında `{key}` ile Durum Şablonlama (Direct State Injection)
`LlmAgent` tanımlarken talimat string'i (`instruction`) içerisine `{key}` yazarak oturum durumundaki değerleri model çağrılmadan önce doğrudan istem metnine enjekte edebilirsiniz:

```python
from google.adk.agents import LlmAgent

story_agent = LlmAgent(
    name="StoryGenerator",
    model="gemini-2.5-flash",
    # session.state["topic"] değeri çalışma zamanında otomatik olarak buraya enjekte edilir:
    instruction="Bir kedi hakkında kısa bir hikaye yaz. Tema: {topic}."
)
```

#### Önemli Kurallar:
1. **Opsiyonel Değişkenler (`{key?}`):** Eğer durum değişkeni oturumda henüz mevcut değilse ADK hata fırlatır. Değişkenin varlığının zorunlu olmadığı durumlarda soru işareti eklenmelidir: `{topic?}`.
2. **Python f-string Kaçışı (Escaping):** Talimat string'i Python `f"..."` formatında tanımlanıyorsa, `f"Tema: {{topic}}"` şeklinde çift süslü parantez kullanılmalıdır. Python bunu çalışma zamanında `{topic}` yapar ve ADK durum enjeksiyonunu başarıyla tamamlar. Düz string'lerde tek parantez (`"{topic}"`) yeterlidir.

---

### 3.4. `InstructionProvider` ile Tam Kontrol ve JSON Koruması
Talimatlarınız süslü parantez içeren JSON şablonları veya formatlama örnekleri barındırıyorsa, string yerine `ReadonlyContext` alan bir fonksiyon (`InstructionProvider`) tanımlamalısınız:

```python
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.utils import instructions_utils

# 1. Salt JSON / Literal parantez içeren statik sağlayıcı (State enjeksiyonu yapılmaz):
def json_instruction_provider(context: ReadonlyContext) -> str:
    return 'Yanıtını mutlaka şu JSON formatında üret: {"city": "<sehir>", "temp": <derece>}'

# 2. Hem JSON parantezlerini koruyup hem de dinamik State enjekte etmek için:
async def dynamic_instruction_provider(context: ReadonlyContext) -> str:
    template = "Kullanıcı dili: {user:language}. Yanıt formatı: {\"status\": \"ok\"}."
    # instructions_utils.inject_session_state yalnızca geçerli state anahtarlarını çözer,
    # JSON sözdizimini korur:
    return await instructions_utils.inject_session_state(template, context)

agent = LlmAgent(
    name="format_agent",
    model="gemini-2.5-flash",
    instruction=dynamic_instruction_provider
)
```

---

### 3.5. Durum Güncelleme Yöntemleri: `output_key` ve Context Kullanımı

#### 1. En Kolay Yol: `output_key` (Ajan Yanıtını Kaydetme)
Modelin ürettiği metin yanıtını tek satırda oturum durumuna kaydetmek için `output_key` parametresi kullanılır:
```python
greeting_agent = LlmAgent(
    name="Greeter",
    model="gemini-2.5-flash",
    instruction="Kullanıcıya samimi ve kısa bir selamlama yap.",
    output_key="last_greeting" # Yanıt doğrudan session.state["last_greeting"] içine yazılır
)
```

#### 2. Kancalarda ve Araçlarda: `Context.state`
Callback veya FunctionTool içinde durumu güncellemenin doğru yolu enjekte edilen `context` nesnesini kullanmaktır:
```python
def my_tool(item: str, tool_context: ToolContext) -> str:
    # State doğrudan güncellenir; değişiklikler otomatik olarak Event.actions.state_delta'ya yazılır
    tool_context.state["last_purchased"] = item
    tool_context.state["temp:transient_token"] = "xyz"
    return f"{item} başarıyla eklendi."
```

---

### 3.6. Kritik Uyarı: Context Dışında Doğrudan `session.state` Değiştirme Yasağı (Anti-Pattern)
`SessionService` üzerinden çekilen bir oturum nesnesinde (`session_service.get_session()` vb.) **çağrı/kanca bağlamı dışında** doğrudan `session.state["key"] = value` yazmak **KESİNLİKLE YASAKTIR**.

**Neden Tehlikelidir?**
1. **Olay Geçmişini Atlar:** Değişiklik bir `Event` olarak kaydedilmez; denetim izi (audit trail) kaybolur.
2. **Kalıcılığı Bozar:** `DatabaseSessionService` ve `VertexAiSessionService` durum değişikliklerini yalnızca `append_event()` tetiklendiğinde veritabanına yazar. Doğrudan atanan değerler **veritabanına kaydedilmez ve kaybolur**.
3. **Eşzamanlılık Riski:** Süreç ve satır düzeyi kilitleri işletmediği için yarış koşullarına (race condition) ve veri kaybına yol açar.

---

## 4. 7 Aşamalı Konuşma Döngüsü (Session Lifecycle)

Bir konuşma turunda `Session` ve `SessionService` aşağıdaki döngüyü takip eder:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Runner as Runner / App
    participant SS as SessionService
    participant Agent as Agent Reasoning Engine

    User->>Runner: 1. İstek / Mesaj Gönder
    Runner->>SS: 2. Oturum Getir (get_session / auto_create)
    SS-->>Runner: Session (events, state)
    Runner->>Agent: 3. Olay Geçmişi ve Durumu Aktar
    Agent->>Agent: 4. Akıl Yürütme ve Yanıt Üretme
    Agent-->>Runner: Yanıt ve Durum Değişiklikleri (state_delta)
    Runner->>SS: 5. append_event(session, event)
    Note over SS: State güncellenir, last_update_time yenilenir
    Runner-->>User: 6. Kullanıcıya Nihai Yanıtı İlet
    opt Oturum Tamamlandığında
        Runner->>SS: 7. delete_session(app_name, user_id, session_id)
    end
```

---

## 5. `SessionService` Depolama Arka Uçları (Backends)

ADK, farklı çalışma ortamları için 3 temel servis sağlayıcısı sunar:

### 1. `InMemorySessionService` (Geliştirme ve Test)
- **Çalışma Şekli:** Tüm oturumları ve durumları doğrudan Python/Node/Go sürecinin belleğinde (RAM) tutar.
- **Kalıcılık:** **YOKTUR.** Uygulama yeniden başlatıldığında tüm oturumlar silinir.
- **Kullanım:** Hızlı prototipleme, `agents-cli playground` ve otomatik birim testleri.

```python
from google.adk.sessions import InMemorySessionService
session_service = InMemorySessionService()
```

---

### 2. `DatabaseSessionService` (Üretim Seviyesi İlişkisel Veritabanları)
- **Çalışma Şekli:** PostgreSQL, MySQL, MariaDB veya SQLite veritabanlarına bağlanarak tablolar üzerinde kalıcı oturum yönetimi sağlar.
- **Kurulum:** `pip install google-adk[db]` gerektirir (Go için GORM).

> [!CAUTION]
> **Zorunlu Asenkron Sürücü Kuralı:** `DatabaseSessionService` mimarisi asenkron çalışır. Standart senkron veritabanı sürücüleri çalışma zamanında hata verir!
> - SQLite: `sqlite+aiosqlite:///./my_agent_data.db` (Düz `sqlite` kullanılamaz!)
> - PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/dbname`
> - MySQL: `mysql+aiomysql://user:pass@host:3306/dbname`

#### Eşzamanlılık ve İki Katmanlı Kilitleme Mimarisi (Concurrency & Locking)
`DatabaseSessionService`, çok kullanıcılı veya yatay ölçeklenen ortamlarda veri bütünlüğünü korumak için 2 katmanlı kilitleme uygular:
1. **İç Süreç Kilidi (In-Process Locking):** Aynı Python/Go süreci içinde aynı oturuma gelen eşzamanlı `append_event` çağrılarını sıralı hale getirir (serialize eder).
2. **Satır Düzeyi Kilit (Row-Level Locking):** PostgreSQL, MySQL ve MariaDB üzerinde `SELECT ... FOR UPDATE` mekanizması kullanarak farklı konteyner pod'larının veya sunucu replikalarının aynı oturum üzerinde yarış koşulu (race condition) oluşturmasını engeller.

#### Go'da `AutoMigrate` Zorunluluğu:
Go SDK'da veritabanı tabloları otomatik oluşturulmaz; her uygulama başlangıcında çağrılmalıdır:
```go
sessionService, err := database.NewSessionService(sqlite.Open("my_agent_data.db"), &gorm.Config{})
if err := database.AutoMigrate(sessionService); err != nil {
    log.Fatal(err)
}
```

---

### 3. `VertexAiSessionService` (Google Cloud Yönetilen Altyapı)
- **Çalışma Şekli:** Google Cloud Agent Platform / Reasoning Engine altyapısı üzerinden tam yönetilen sunucusuz oturum depolaması sağlar.
- **Kurulum:** `pip install google-adk[gcp]`, GCP Proje kimliği, bölge (`us-central1` vb.) ve Cloud Storage bucket gerektirir.
- **Uygulama Adı Formatı:** `app_name` olarak Reasoning Engine kaynak adı kullanılır:
  `projects/<PROJECT_ID>/locations/<LOCATION>/reasoningEngines/<ENGINE_ID>`.

```python
from google.adk.sessions import VertexAiSessionService

session_service = VertexAiSessionService(
    project="my-gcp-project",
    location="us-central1"
)
```

> [!NOTE]
> Kotlin SDK'da `VertexAiSessionService`, Reasoning Engine kimliğini doğrudan kurucuda (constructor) bağlar (`reasoningEngineId = "1234567890"` yalın sayısal kimlik).

---

## 6. Hata Yönetimi: `SessionNotFoundError`

Ajan çalıştırılırken en sık karşılaşılan istisna `SessionNotFoundError`'dır (geriye dönük uyumluluk için `ValueError` sınıfından türer).

- **Sebepleri:**
  1. Geçersiz, süresi dolmuş veya henüz oluşturulmamış bir `session_id` ile `runner.run_async()` çağrılması.
  2. Oturum oluşturulmadan doğrudan çalıştırma adımı tetiklenmesi.
- **Çözüm 1 (Önceden Oluşturma):**
  ```python
  await session_service.create_session(app_name="app", user_id="user1", session_id="ses_123")
  ```
- **Çözüm 2 (`auto_create_session=True` ile Otomatik Oluşturma):**
  Runner başlatılırken `auto_create_session=True` atanırsa, belirtilen `session_id` veritabanında yoksa Runner onu hata fırlatmadan anında otomatik olarak oluşturur:
  ```python
  runner = Runner(
      agent=my_agent,
      session_service=session_service,
      auto_create_session=True # Oturum yoksa otomatik başlatır
  )
  ```

---

## 7. Oturum Geri Sarma (Session Rewind) & Alternatif Dallanma Yolları

ADK (Python v1.17.0+, Kotlin v0.3.0+), ajan yürütmesinde yapılan hataları geri almak, kullanıcının fikrini değiştirdiği durumlarda önceki bir adıma dönmek veya alternatif dallanma (branching) yollarını keşfetmek için **Session Rewind** (`runner.rewind_async`) mimarisini sunar.

### 6.1. Çalışma Mantığı ve `rewind_before_invocation_id`
Oturumu geri sararken geri alınmak istenen çağrı (invocation) kimliği belirtilir. Sistem, belirtilen çağrıyı ve ondan sonraki **tüm sonraki çağrıları** geri alır:
- Örnek: `A -> B -> C` çağrı dizisinde `B`'nin kimliği (`rewind_before_invocation_id=B`) verildiğinde, `B` ve `C` çağrılarındaki tüm değişiklikler geri alınır ve oturum `A` anındaki durumuna geri döner.

```python
# Runner ve oturum oluşturma
runner = InMemoryRunner(agent=agent.root_agent, app_name=APP_NAME)
session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)

# 1. Çağrı (A)
await call_agent_async(runner, USER_ID, session.id, "state color'ı red yap")

# 2. Çağrı (B - Geri alınacak çağrı)
events_list = await call_agent_async(runner, USER_ID, session.id, "state color'ı blue yap")
rewind_invocation_id = events_list[1].invocation_id

# Oturumu B öncesine geri sar (State color yeniden 'red' olur)
await runner.rewind_async(
    user_id=USER_ID,
    session_id=session.id,
    rewind_before_invocation_id=rewind_invocation_id,
)
```

Kotlin SDK eşdeğeri:
```kotlin
// Invocation ID elde etme ve geri sarma
val rewindInvocationId = events[1].invocationId ?: return

runner.rewindAsync(
    userId = USER_ID,
    sessionId = sessionId,
    rewindBeforeInvocationId = rewindInvocationId,
)
```

### 6.2. Denetim İzi (Audit Trail) ve LLM Bağlam Filtreleme
- **Loglar Silinmez:** Geri sarılan olaylar ve mesajlar veritabanından fiziki olarak silinmez; geriye dönük denetim (audit), analiz ve hata ayıklama için kalıcı depolamada saklanmaya devam eder.
- **Modelden Filtreleme:** Geri sarma işleminden sonraki ajan çalıştırmalarında Runner, geri sarılan turları LLM'e gönderilecek istem geçmişinden (prompt context) otomatik olarak filtreler. Böylece AI modeli geri sarılan adımları tamamen "unutur".

### 6.3. Kapsam ve Kritik Kısıtlamalar
1. **Yalnızca Oturum Kapsamı:** Geri sarma işlemi yalnızca oturum düzeyindeki durumu (`session.state`) ve oturuma bağlı artifact'leri (`session_id`) eski haline getirir. Uygulama düzeyi (`app:*`) veya kullanıcı düzeyi (`user:*`) durumlar ve eserler **asla geri sarılmaz**.
2. **Dış Sistem Yan Etkileri (No External Rollback):** Araçların dış dünyada gerçekleştirdiği eylemler (harici API çağrıları, ödeme tahsilatları, e-posta gönderimleri, veritabanı yazımları) ADK tarafından geri alınamaz. Bu tür işlemler için geliştiricinin telafi mekanizması (compensating transaction) kurması gerekir.
3. **Atomisite ve Eşzamanlılık:** Durum güncellemeleri, artifact restorasyonu ve olay kalıcılığı tek bir atomik veritabanı işleminde (transaction) yürütülmez. Bu nedenle, aktif olarak çalışan bir oturum aynı anda geri sarılmamalı veya geri sarma sırasında oturum eserleri eşzamanlı olarak değiştirilmemelidir.

---

## 8. Uçtan Uca Python Uygulama Örneği

```python
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext, FunctionTool
from google.genai import types

def update_cart(item: str, quantity: int, tool_context: ToolContext) -> dict:
    cart = tool_context.state.get("cart", {})
    cart[item] = cart.get(item, 0) + quantity
    tool_context.state["cart"] = cart # Durum otomatik olarak oturuma kaydedilir
    return {"status": "success", "current_cart": cart}

cart_tool = FunctionTool(func=update_cart)
shopping_agent = LlmAgent(
    name="shopping_assistant",
    model="gemini-2.5-flash",
    instruction="Sen bir alışveriş asistanısın. Kullanıcının sepet işlemlerini yönet.",
    tools=[cart_tool]
)

async def main():
    runner = InMemoryRunner(agent=shopping_agent, app_name="ecommerce_demo")
    session_service = runner.session_service
    user_id = "customer_42"
    session_id = "cart_session_001"

    # Başlangıç durumu ile oturum açma
    session = await session_service.create_session(
        app_name="ecommerce_demo",
        user_id=user_id,
        session_id=session_id,
        state={"cart": {"elma": 2}}
    )
    print(f"Oturum Başlatıldı: ID={session.id}, Başlangıç={session.state['cart']}")

    prompt = "Sepetime 3 adet muz ekler misin?"
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(parts=[types.Part.from_text(text=prompt)])
    ):
        if event.is_final_response() and event.content:
            print(f"\nAjan Yanıtı: {event.content.parts[0].text}")

    # Oturumun son durumunu doğrula
    updated_session = await session_service.get_session(
        app_name="ecommerce_demo",
        user_id=user_id,
        session_id=session_id
    )
    print(f"\nOturumun Son Durumu: {updated_session.state['cart']}")
    print(f"Son Güncelleme Zamanı: {updated_session.last_update_time}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 9. Çok Dilli SDK Desteği

| SDK Dili | Oturum Nesnesi | Oturum Servisi | Bellek Servisi |
| :--- | :--- | :--- | :--- |
| **Python** | `google.adk.sessions.Session` | `google.adk.sessions.SessionService` | `google.adk.memory.MemoryService` |
| **TypeScript** | `Session` (`@google/adk`) | `SessionService` | `MemoryService` |
| **Java** | `com.google.adk.sessions.Session` | `SessionService` | `MemoryService` |
| **Go** | `session.Session` (`google.golang.org/adk/v2/session`)| `session.Service` | `memory.Service` |
| **Kotlin** | `Session` (`com.google.adk.sessions`) | `SessionService` | `MemoryService` |

---

## 10. Oturum Veritabanı Şema Migrasyonu (`v0 Pickle -> v1 JSON`)

ADK Python v1.22.0 sürümü ile birlikte `DatabaseSessionService` veritabanı şeması önemli bir mimari modernizasyondan geçmiştir. Eski sürümlerde kullanılan Python'a özgü, ikili ve güvensiz **`v0` (pickle tabanlı serileştirme)**, yerini güvenli, okunabilir ve diller arası uyumlu **`v1` (JSON tabanlı serileştirme)** şemasına bırakmıştır.

Eski `v0` şemasına sahip veritabanları ADK Python v1.22.0+ sürümlerinde çalışmaya devam eder; ancak ileriki sürümlerde `v1` JSON şeması zorunlu hale gelecektir. Bu nedenle üretim veritabanlarının taşınması önerilir.

### 9.1. Sürüm ve Ön Koşullar
* **Gerekli Sürüm:** `ADK Python >= v1.22.1`
* v1.22.1 sürümü, CLI tabanlı migrasyon fonksiyonunu ve şema değişikliğine ilişkin kritik hata düzeltmelerini içerir.

### 9.2. `adk migrate session` CLI ile Otomasyon
ADK CLI, mevcut `v0` veritabanındaki verileri okuyup yeni formata dönüştürerek hedef `v1` veritabanına yazan yerleşik bir migrasyon aracı sunar:

```bash
adk migrate session \
  --source_db_url=<eski_db_url> \
  --dest_db_url=<yeni_db_url>
```

#### Örnek 1: SQLite Veritabanı Migrasyonu
```bash
adk migrate session \
  --source_db_url=sqlite:///source.db \
  --dest_db_url=sqlite:///dest.db
```

#### Örnek 2: PostgreSQL Veritabanı Migrasyonu
```bash
adk migrate session \
  --source_db_url=postgresql://localhost:5432/v0 \
  --dest_db_url=postgresql://localhost:5432/v1
```

### 9.3. Migrasyon Sonrası Yapılandırma
Migrasyon komutu başarıyla tamamlandıktan sonra, uygulamanızdaki `DatabaseSessionService` bağlantı adresini yeni `dest_db_url` değerine güncelleyin:

```python
# Eski:
# session_service = DatabaseSessionService(db_url="sqlite+aiosqlite:///source.db")

# Yeni (v1 JSON Şeması):
session_service = DatabaseSessionService(db_url="sqlite+aiosqlite:///dest.db")
```

