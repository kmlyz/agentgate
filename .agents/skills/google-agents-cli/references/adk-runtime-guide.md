---
title: "ADK Runtime & Execution Guide"
description: "Google ADK Agent Runtime, Dev UI, CLI runner, REST API Server, Event Loop ve RunConfig kapsamlı rehberi."
category: runtime
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - runtime
  - dev-ui
  - api-server
  - event-loop
  - runconfig
  - resume
---

# Google ADK Agent Runtime & Yürütme Mimarisi

ADK Runtime, tanımlanan ajanları, araçları ve callback'leri kullanıcı istekleriyle orkestre eden temel yürütme motorudur (Execution Engine).

---

## 1. Çalıştırma Yöntemleri (Ways to Run Agents)

| Yöntem | Python Komutu | TypeScript / Node | Go (main.go launcher) | Java / Gradle | Kullanım Amacı |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dev UI (Web)** | `adk web` | `npx adk web` | `go run agent.go web api webui` | `gradle runADKWebServer` | Tarayıcıda görsel chat, state inceleme, event geçmişi |
| **CLI Runner** | `adk run <agent>` | `npx @google/adk-devtools run <agent>` | `go run agent.go` veya `go run agent.go console` | `mvn compile exec:java -Dexec.mainClass=...` | Terminalde hızlı test, scriptler ve CI/CD |
| **API Server** | `adk api_server` | `npx adk api_server` | `go run agent.go web api` (Port: 8080, `/api` prefix) | `AdkWebServer` | Programatik entegrasyon, REST & SSE akışları |

> [!WARNING]
> `adk web` (Dev UI) yalnızca yerel geliştirme ve hata ayıklama (debugging) içindir; üretim ortamlarında doğrudan kullanılmamalıdır.

### 1.1. Dev UI Ayrıntılı Yapılandırma ve Parametreler (`adk web`)

ADK Dev UI arayüzü 5 ana geliştirici işlevi sunar:
- **Chat Interface:** Ajanla gerçek zamanlı mesajlaşma ve model çıktısını izleme.
- **Session Management:** Farklı kullanıcılar/oturumlar oluşturma, geçmiş oturumlar arasında geçiş yapma.
- **State Inspection & Edit:** Çalışma anında session state sözlüğünü görüntüleme ve doğrudan düzenleme.
- **Event & Trace History:** Yürütme sırasında üretilen tüm olayları (state delta, tool çağrıları, dönüşler) adım adım denetleme.
- **Visual Builder:** Sürükle-bırak ajan tasarımcısı ve AI destekli görsel asistan (Python).

#### `adk web` Komut Satırı Seçenekleri (Python & TypeScript)

| Seçenek | Açıklama | Varsayılan |
| :--- | :--- | :--- |
| `--port` | Web sunucusunun dinleyeceği port | `8000` |
| `--host` | Sunucu host adresi | `127.0.0.1` |
| `--session_service_uri` | Oturum SQLite veritabanı URI'si | `<agent_dir>/.adk/session.db` (Python) / In-memory (TS) |
| `--artifact_service_uri` | Artifact depolama klasörü URI'si | `<agent_dir>/.adk/artifacts` |
| `--reload / --no-reload` | Kod değişikliklerinde anında hot-reload | `true` |
| `--no_use_local_storage` | Yerel `.adk` dizini yerine bellek içi (in-memory) servisleri kullanma | `false` |

Örnek çalıştırma:
```powershell
adk web --port 3000 --session_service_uri "sqlite:///sessions.db" --reload
```

#### Go Web Launcher Alt Komut Bayrakları
Go'da bayraklar `web`, `api` ve `webui` alt komutlarının ardına ayrı ayrı eklenir:
- **`web` bayrakları:** `-port 8080`, `-write-timeout 15s`, `-read-timeout 15s`, `-idle-timeout 60s`, `-shutdown-timeout 15s`, `-otel_to_cloud false`
- **`api` bayrakları:** `-webui_address localhost:8080`, `-path_prefix /api`, `-sse-write-timeout 120s`, `-trace_capacity 10000`
- **`webui` bayrakları:** `-api_server_address http://localhost:8080/api`

```powershell
go run agent.go web -port 9090 api -path_prefix /myapi webui -api_server_address http://localhost:9090/myapi
```

#### Telemetri ve Gizlilik Tercihleri
Web UI telemetrisi varsayılan olarak **kapalıdır** (`telemetry: false`). Kullanıcı tercihleri `~/.adk/config.json` dosyasında saklanır:
```json
{
  "telemetry": false
}
```
> [!NOTE]
> Telemetri açık olsa dahi; ajan istemleri (prompts), sistem talimatları, LLM yanıtları, API anahtarları, GCP proje ID'leri ve kişisel veriler (PII) **kesinlikle toplanmaz**.

---

## 2. ADK Event Loop (Olay Döngüsü) Mimarisi

ADK Runtime, ajan uygulamasının motorudur (Engine). Tüm yürütme, `Runner` (Orkestratör) ile `Execution Logic` (Ajanlar, Araçlar, Callback'ler) arasında dönen asenkron bir **Olay Döngüsü (Event Loop)** üzerinden gerçekleşir.

### 2.1. İç Mekanizma: Yield -> Pause -> Commit -> Resume

1. **Giriş (Initiation):** `Runner`, kullanıcı mesajını (`new_message`) alır ve `SessionService.append_event` ile oturum geçmişine kaydeder.
2. **Başlatma (Kick-off):** Ana ajanın `agent.run_async(ctx)` fonksiyonu tetiklenir.
3. **Üretim ve Duraklama (Yield & Pause):** Ajan bir yanıt parçası, araç çağrısı veya durum değişikliği oluşturduğunda bir `Event` üretir ve `yield` eder. Bu anda **ajan yürütmesi derhal duraklar (PAUSE)**.
4. **Taahhüt (Commit & Process):** `Runner` yielded olayı yakalar; `event.actions` içindeki `stateDelta` ve `artifactDelta` değişikliklerini yapılandırılmış servislere (`SessionService`, `ArtifactService`) kaydeder (COMMIT).
5. **İletim ve Devam (Resume):** Olay yukarıya (UI / SSE akışına) iletilir. Runner taahhüdü tamamladıktan sonra ajana devam sinyali verir; ajan durakladığı satırdan **devam eder (RESUME)**. Artık `ctx.session.state` güncel taahhüt edilmiş durumu kesin olarak yansıtır.

```python
# Ajan içi mantık:
yield Event(author=self.name, actions=EventActions(state_delta={"status": "processing"}))
# << YÜRÜTME BURADA DURAKLAR (PAUSE) >>
# << RUNNER OLAYI YAKALAR VE VERİTABANINA TAAHHÜT EDER (COMMIT) >>
# << AJAN DEVAM EDER (RESUME) >>
current_status = ctx.session.state["status"] # Kesinlikle "processing" değerindedir
```

### 2.2. Oturum Durumunda "Kirli Okumalar" (Dirty Reads)

Bir callback veya araç içerisinde `ctx.session.state["key"] = "val"` şeklinde yerel olarak değiştirilen bir değer, **henüz bir Event ile yield edilip Runner tarafından taahhüt edilmeden önce**, aynı tur içindeki sonraki araçlar veya callback'ler tarafından okunabilir. Buna **Dirty Read** denir.
- **Fayda:** Tek bir karmaşık LLM turu içinde birden fazla araç veya callback'in state üzerinden hızlıca haberleşmesini sağlar.
- **Risk & Güvenlik:** Eğer sistem olay yield edilmeden veya Runner taahhüdü tamamlayamadan çökerse bu değer kalıcı olmaz. Kritik iş mantığı durumları mutlaka bir `Event(actions=EventActions(state_delta=...))` ile taahhüt edilmelidir.

### 2.3. Akışta Atomik Durum Taahhüdü (`partial=True` vs `partial=False`)

LLM token akışı (streaming) sırasında:
- Model token ürettikçe üretilen ara olaylar `partial=True` olarak işaretlenir.
- `Runner`, `partial=True` olan olayları anında istemciye (daktilo efekti için) iletir; ancak **`actions` (state_delta / artifact_delta) taahhüt adımlarını atlar (skip eder)**.
- Yanıt bittiğinde üretilen son olay `partial=False` (veya `turn_complete=True`) olarak işaretlenir.
- `Runner`, durum taahhüdünü **yalnızca bu son olay geldiğinde atomik olarak** uygular. Bu sayede yarım kalan yanıtların oturum durumunu bozması engellenir.

### 2.4. Asenkron Öncelikli Tasarım & Bloklama Uyarısı (Blocking I/O)

- ADK Runtime çekirdeği asenkrondur (`Runner.run_async`). Senkron `Runner.run` yalnızca basit testler için bir kolaylık sarmalayıcısıdır.
- **Blocking I/O Uyarısı:** Senkron çalışan araçlar (`time.sleep()`, senkron `requests.get()`) Python asyncio veya Node.js olay döngüsünü kilitler (stall). Ağ ve dosya işlemleri için her zaman asenkron API'ler (`httpx`, `aiofiles`) veya `RunConfig(tool_thread_pool_config=...)` arka plan iş parçacığı havuzu kullanılmalıdır.

---

## 3. Command Line (CLI) ve Oturum Yönetimi

Python ADK CLI (`adk run`), hızlı geliştirme, CI/CD testleri ve otomatik boru hatları için iki çalıştırma modu ve gelişmiş oturum yönetimi sunar.

### 3.1. Çalıştırma Modları

- **Etkileşimli Terminal (Interactive REPL):**
  ```powershell
  adk run path/to/my_agent
  ```
  Terminalde konuşma başlatır (`exit`, `Ctrl+C` veya `Ctrl+D` ile çıkılır).

- **Tek Mesaj / Scripting Modu (Non-Interactive):**
  ```powershell
  adk run path/to/my_agent "Hava durumunu kontrol et"
  ```
  Sorguyu argüman olarak gönderir, yanıtı üretir ve hemen sonlanır (CI/CD ve pipeline entegrasyonları için idealdir).

### 3.2. Oturum Kaydetme, Devam Ettirme ve Replay

```powershell
# Oturumu çıkışta kaydetmek
adk run --save_session path/to/my_agent

# Belirli bir session ID ile kaydetmek
adk run --save_session --session_id my_session path/to/my_agent

# Kaydedilmiş oturumu devam ettirmek (Resume)
adk run --resume path/to/my_agent/my_session.session.json path/to/my_agent

# Geçmiş oturumu adım adım yeniden yürütmek (Replay)
adk run --replay path/to/input.json path/to/my_agent
```

Otomatik replay testlerinde kullanılan `input.json` şeması:
```json
{
  "state": {"customer_tier": "gold"},
  "queries": [
    "2 + 2 kaç yapar?",
    "Hesap bakiyemi kontrol et"
  ]
}
```

### 3.3. Tüm `adk run` Parametreleri (Python CLI)

| Seçenek | Açıklama |
| :--- | :--- |
| `--save_session` | Çıkışta oturumu JSON dosyasına kaydeder |
| `--session_id <id>` | Kaydedilecek oturum kimliği |
| `--resume <dosya>` | Kaydedilmiş `.session.json` dosyasını yükleyip devam eder |
| `--replay <dosya>` | JSON dosyasından otomatik sorguları yürütür |
| `--state '<json>'` | Başlangıç state'ini JSON dizesi olarak tanımlar |
| `--timeout <sure>` | Tek bir sorgu turu için zaman aşımı (örn: `30s`, `5m`) |
| `--in_memory` | Oturumu diske kaydetmeden tamamen RAM'de tutar |
| `--jsonl` | İnsan okunabilir metin yerine satır bazlı yapılandırılmış JSONL çıktısı üretir |
| `--default_llm_model <model>` | Ajan dosyasında model belirtilmemişse varsayılan modeli belirler |
| `--session_service_uri <uri>` | Özel oturum veritabanı yolu (varsayılan: `<agent>/.adk/session.db`) |
| `--artifact_service_uri <uri>`| Özel artifact dizini (varsayılan: `<agent>/.adk/artifacts`) |
| `--memory_service_uri <uri>`  | Özel bellek servisi URI'si (varsayılan: in-memory) |
| `--no_use_local_storage`      | Yerel `.adk` klasörünü devre dışı bırakır |

### 3.4. Go Konsol Çalıştırıcı Bayrakları
Go'da bayraklar `console` alt komutunun ardına eklenir:
```powershell
go run agent.go console -streaming_mode sse   # Token düzeyinde gerçek zamanlı çıktı
go run agent.go console -streaming_mode none  # Toplu blok yanıt
```

### 3.5. Terminal Üzerinden Telemetri Yönetimi
```powershell
adk telemetry status    # Mevcut telemetri durumunu kontrol eder
adk telemetry enable    # Anonim kullanım telemetrisini açar
adk telemetry disable   # Telemetriyi kapatır (~/.adk/config.json)
```

---

## 4. REST API Server ve Endpoint Referansı

Varsayılan adres: Python/TS/Java için `http://localhost:8000`, Go için `http://localhost:8080/api`.  
Etkileşimli Swagger dokümantasyonu: `http://localhost:8000/docs` (Python & TS).

> [!IMPORTANT]
> **JSON İsimlendirme Kuralı:** İstek ve yanıt gövdelerindeki tüm alan adları katı biçimde `camelCase` formatında olmalıdır (`appName`, `userId`, `sessionId`, `newMessage`, `streaming`, `stateDelta`).

### Temel Uç Noktalar:

1. **Uygulamaları Listeleme:**
   - `GET /list-apps` -> `["my_sample_agent", "support_agent"]`
2. **Oturum Oluşturma & Durum Başlatma:**
   - `POST /apps/{appName}/users/{userId}/sessions/{sessionId}`
   - Body (opsiyonel önceden tanımlı state): `{"key1": "value1", "counter": 0}`
   - *Çakışma Kuralı:* Aynı `userId` ve `sessionId` ile ikinci kez oluşturma denenirse `Session already exists` hatası döner. Yeniden başlamak için önce oturum silinmelidir.
3. **Oturum Güncelleme:**
   - `PATCH /apps/{appName}/users/{userId}/sessions/{sessionId}`
   - Body: `{"stateDelta": {"counter": 1}}`
   - *Go Notu:* Go API sunucusunda `PATCH` endpoint'i yoktur. Go'da durum güncellemesi `/run` veya `/run_sse` isteği içerisine `stateDelta` eklenerek yapılır.
4. **Oturum Detayı ve Olay Geçmişi:**
   - `GET /apps/{appName}/users/{userId}/sessions/{sessionId}`
5. **Oturum Silme:**
   - `DELETE /apps/{appName}/users/{userId}/sessions/{sessionId}`
   - Yanıt: TypeScript'te `204 No Content`, Python'da `200 OK` (`null` gövde), Go'da `200 OK` (boş gövde).
6. **Ajan Yürütme (Toplu Sonuç - Single Response):**
   - `POST /run`
   - Body:
     ```json
     {
       "appName": "my_sample_agent",
       "userId": "u_123",
       "sessionId": "s_123",
       "newMessage": {
         "role": "user",
         "parts": [{"text": "Bugün hava nasıl?"}]
       }
     }
     ```
7. **Ajan Yürütme (Server-Sent Events - SSE Stream):**
   - `POST /run_sse`
   - Body:
     ```json
     {
       "appName": "my_sample_agent",
       "userId": "u_123",
       "sessionId": "s_123",
       "newMessage": {
         "role": "user",
         "parts": [{"text": "Bana detaylı bir analiz raporu yaz."}]
       },
       "streaming": true
     }
     ```
   - `streaming: true` parametresi token düzeyinde gerçek zamanlı akış (token streaming) sağlar.

### 4.1. Çok Modlu (Multimodal / Dosya) İstek Gönderimi

Görseller veya belgeler base64 formatında `newMessage.parts` dizisine `inlineData` objesi olarak eklenebilir:
```json
{
  "appName": "my_sample_agent",
  "userId": "u_123",
  "sessionId": "s_123",
  "newMessage": {
    "role": "user",
    "parts": [
      {"text": "Bu görselde ne görüyorsun?"},
      {
        "inlineData": {
          "displayName": "diagram.png",
          "mimeType": "image/png",
          "data": "iVBORw0KGgoAAAANSUhEUgAA..."
        }
      }
    ]
  },
  "streaming": false
}
```

---

## 5. Çalışma Zamanı Yapılandırması (RunConfig)

`RunConfig`, ajanların çalışma zamanı davranışlarını (`streaming_mode`, oturum bağlamı, ses ayarları, thread havuzu ve güvenlik sınırları) yönetir. `runner.run_async(..., run_config=config)` veya `runner.run_live(...)` çağrılarına aktarılır.

### 5.1. Akış Modları ve Dinamik Fonksiyon Çağrısı (CFC)

- **`StreamingMode.NONE` (Varsayılan):** Her tur için tek parça tam blok yanıt üretir (CLI ve batch işlemler).
- **`StreamingMode.SSE`:** Server-Sent Events akışı; LLM token ürettikçe kısmi olaylar yield edilir (daktilo efekti / gerçek zamanlı sohbet).
- **`support_cfc=True` (Deneysel):** Compositional Function Calling; modelin karmaşık araç çağrılarını dinamik olarak tek adımda birleştirip yürütmesini sağlar (Live API altyapısı kullanır).

```python
config = RunConfig(
    streaming_mode=StreamingMode.SSE,
    support_cfc=True,
    max_llm_calls=150,
)
```

### 5.2. Oturum ve Bağlam (Context) Optimizasyonu

Büyük ve uzun soluklu oturumlarda veritabanı yükünü ve token tüketimini azaltmak için kullanılır:
- **`get_session_config`:** Oturum yüklenirken yalnızca son olayların çekilmesini sağlar:
  ```python
  from google.adk.sessions.base_session_service import GetSessionConfig

  config = RunConfig(
      get_session_config=GetSessionConfig(num_recent_events=50),
      context_window_compression=True, # Bağlam dolduğunda otomatik sıkıştırma
  )
  ```
- **`model_input_context`:** Yalnızca o tur için modele aktarılan, ancak oturum geçmişine **kaydedilmeyen** geçici içerik listesi (`list[types.Content]`).
- **`include_thoughts_from_other_agents`:** Diğer alt uzman ajanların düşünce (thought) bloklarının LLM bağlamına katılıp katılmayacağını belirler (varsayılan: False).

### 5.3. Ses, Konuşma ve Modalite Yapılandırması

```python
from google.genai import types

config = RunConfig(
    response_modalities=["AUDIO"], # Sesli ajanlar için AUDIO, metin için TEXT
    speech_config=types.SpeechConfig(
        language_code="en-US",
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
        ),
    ),
    streaming_mode=StreamingMode.SSE,
)
```

### 5.4. Çalışma Zamanı Korumaları ve Thread Pool

- **`max_llm_calls`:** Bir çalıştırmada yapılabilecek azami LLM çağrı sınırı (varsayılan: 500). Döngülerin ve maliyetin kontrolden çıkmasını engeller.
- **`custom_metadata`:** Tracing ve loglama için tura iliştirilen isteğe bağlı meta veriler (`dict[str, Any]`).
- **`service_tier`:** `ServiceTier.DEFERRED` ile off-peak kapasite kullanımı (gecikmeye toleranslı toplu işler; SSE ile birlikte kullanılamaz).
- **`tool_thread_pool_config`:** I/O veya ağ bekleyen araçların asenkron event loop'u kilitlemesini önlemek için iş parçacığı havuzu tanımlar:
  ```python
  from google.adk.agents.run_config import ToolThreadPoolConfig

  config = RunConfig(
      tool_thread_pool_config=ToolThreadPoolConfig(max_workers=8),
  )
  ```

---

## 6. Kesinti Yönetimi ve İptal (Cancel & Resume)

### 6.1. Zarif İptal (Graceful Cancellation)
Çalışması gereğinden uzun süren veya koşulların değişmesiyle iptal edilmek istenen süreçler için `AbortController` / `AbortSignal` kullanılır:
- İptal işlemi **tahribatsızdır (non-destructive)**; iptal sinyaline kadar oturuma (`SessionService`) taahhüt edilmiş olaylar kalıcı kalır.

#### İptalin Yürütme Yığınında Yayılması (Cancellation Propagation)

Sinyal tetiklendiğinde (`controller.abort()`), iptal yığındaki tüm bileşenlere kademeli olarak yayılır:

| Bileşen | İptal Anındaki Davranış |
| :--- | :--- |
| **Runner** | Oturum sorgulama öncesinde, eklenti callback'leri sonrasında ve olay akış döngüsünde işlemi durdurur. |
| **LlmAgent** | Adımlar arasında, model callback'lerinde ve token akışında anında sonlanır. |
| **LoopAgent** | İterasyonlar ve alt ajan geçişleri arasında durur. |
| **ParallelAgent** | Eşzamanlı çalışan alt ajanların sonuçları birleştirilirken durur. |
| **Gemini Modelleri** | Sinyal Google GenAI SDK'ya iletilir; havada uçuşan (in-flight) HTTP isteği iptal edilerek ağ/kota kaynakları serbest bırakılır. |
| **AgentTool / MCPTool** | Sinyali alt ajana veya MCP istemcisinin `callTool` metoduna iletir. |

#### Temel İlkeler:
- **Hatasız Sonlanma:** `runner.runAsync()` hata (Exception) fırlatmadan zarifçe sonlanır.
- **Kalıcılık:** O ana kadar üretilen olaylar oturum geçmişinde korunur; henüz yield edilmemiş yarım olaylar atılır.

#### Gelişmiş İptal Kalıpları

**1. Zaman Aşımı (Timeout) ile İptal:**
```typescript
const run = runner.runAsync({
  userId: session.userId,
  sessionId: session.id,
  newMessage: { role: 'user', parts: [{ text: 'Karmaşık bir analiz yap.' }] },
  abortSignal: AbortSignal.timeout(5_000), // 5 saniye sonra otomatik iptal
});
```

**2. Kombine İptal (Manuel UI Butonu + Zaman Aşımı):**
```typescript
const controller = new AbortController();
const combinedSignal = AbortSignal.any([
  controller.signal,
  AbortSignal.timeout(60_000), // 60 saniye veya kullanıcı butona bastığında
]);

runner.runAsync({ ..., abortSignal: combinedSignal });
```

**3. Özel Araçlar (Custom Tools) İçinde Sinyal Denetimi:**
```typescript
const longRunningTool = new FunctionTool({
  name: 'batch_processor',
  parameters: z.object({ items: z.array(z.string()) }),
  execute: async (args, toolContext) => {
    const results = [];
    for (const item of args.items) {
      // Her adım öncesi iptal sinyalini kontrol et
      if (toolContext?.abortSignal?.aborted) {
        return { status: 'cancelled', processed: results.length };
      }
      results.push(await processItem(item));
    }
    return { status: 'complete', results };
  },
});
```

### 6.2. Kesintiden Devam Ettirme (Resumability Mimarisi)
Ağ kopması, elektrik kesintisi veya servis yeniden başlatmalarında akışın baştan başlamak yerine kaldığı adımdan devam etmesini sağlar (Python v1.16.0+, Kotlin v0.1.0+).

#### A. Yapılandırma
```python
from google.adk.apps import App, ResumabilityConfig

app = App(
    name='my_resumable_agent',
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
```

#### B. Kesilen Ajanı Yeniden Başlatma (`invocation_id`)
Olay geçmişindeki `invocation_id` değeri kullanılarak süreç kaldığı adımdan tetiklenir:

**1. REST API Server Üzerinden:**
```powershell
curl -X POST http://localhost:8000/run_sse `
  -H "Content-Type: application/json" `
  -d '{
    "app_name": "my_resumable_agent",
    "user_id": "u_123",
    "session_id": "s_abc",
    "invocation_id": "invocation-123"
  }'
```

**2. Python Kodundan Programatik Olarak:**
```python
async for event in runner.run_async(
    user_id='u_123',
    session_id='s_abc',
    invocation_id='invocation-123',
):
    print(event)
```
> [!NOTE]
> Dev UI (`adk web`) veya CLI (`adk run`) üzerinden resume doğrudan desteklenmez; resume işlemi API Server veya programatik Runner üzerinden yürütülmelidir.

### 6.3. Çoklu Ajan ve Araç Davranışı
- **Sequential Agent:** Kayıtlı durumdaki `current_sub_agent` değerini okur ve sıradaki alt ajandan devam eder.
- **Loop Agent:** `current_sub_agent` ve `times_looped` sayaçlarını okuyarak döngünün kaldığı iterasyondan devam eder.
- **Parallel Agent:** Hangi alt ajanların tamamlandığını kontrol eder ve yalnızca yarım kalanları çalıştırır.
- **Araç (Tool) Davranışı & İdempotency Uyarısı:** Başarıyla tamamlanan fonksiyon araçlarının sonuçları korunur; kesinti anında çalışan araç yeniden çalıştırılır (*at least once* garantisi). Satın alma, SMS gönderme gibi yan etki yaratan araçlar mükerrer çalışmaya karşı idempotent tasarlanmalıdır.

### 6.4. Özel Ajanlar (Custom Agents) için Checkpoint Kalıbı
Standart dışı özel ajan sınıflarında (`BaseAgent`) resumability'yi desteklemek için durum denetim noktaları (checkpoints) tanımlanmalıdır:
```python
from enum import Enum
from google.adk.agents import BaseAgentState

class WorkflowStep(int, Enum):
    STEP_1 = 1
    STEP_2 = 2

class MyAgentState(BaseAgentState):
    step: WorkflowStep

# _run_async_impl içerisinde:
agent_state = self._load_agent_state(ctx, MyAgentState)
if agent_state is None:
    agent_state = MyAgentState(step=WorkflowStep.STEP_1)
    ctx.set_agent_state(self.name, agent_state=agent_state)
    yield self._create_agent_state_event(ctx)

# Adım tamamlandığında checkpoint:
agent_state = MyAgentState(step=WorkflowStep.STEP_2)
ctx.set_agent_state(self.name, agent_state=agent_state)
yield self._create_agent_state_event(ctx)

# Ajan bittiğinde:
ctx.set_agent_state(self.name, end_of_agent=True)
yield self._create_agent_state_event(ctx)
```

---

## 7. Visual Builder (Görsel Ajan Tasarımcısı & AI Asistanı)

> [!NOTE]
> Visual Builder, ADK Python v1.18.0+ sürümlerinde deneysel (experimental) olarak sunulan web tabanlı bir sürükle-bırak tasarım ortamıdır.

### 7.1. Çalışma Mantığı ve Arayüz Panelleri

`adk web` komutu çalıştırılan geliştirme dizininde yeni ajan projeleri oluşturur:
1. **Sol Panel:** Seçili ajan ve bileşen parametrelerinin (model, instructions, state vb.) düzenlenmesi.
2. **Orta Panel (Canvas):** Sürükle-bırak ile ajan düğümlerinin ve bağlantıların görsel olarak inşa edilmesi.
3. **Sağ Panel (AI Assistant):** Doğal dille talimat vererek ajanı inşa etme veya düzenleme (örneğin: *"Help me add a dice roll tool to my current agent"*).

### 7.2. Desteklenen Bileşenler
- **Ajan Türleri:** Root Agent, LLM Agent, Sequential Agent, Parallel Agent, Loop Agent.
- **Araçlar (Tools):** ADK hazır entegrasyonları (prebuilt tools) ve tam nitelikli Python fonksiyon adı (fully-qualified function name) ile bağlanan özel fonksiyonlar (custom tools).
- **Akış Kontrolleri:** Yaşam döngüsü callback'leri.

### 7.3. Üretilen Proje Yapısı (Agent Config Formatı)
Visual Builder, arayüzde tasarlanan ajanları `Agent Config` uyumlu `.yaml` ve `.py` dosyalarına derler:
```text
MyVisualAgent/
├── root_agent.yaml      # Ana ajan yapılandırması
├── sub_agent_1.yaml     # Alt uzman ajanlar (varsa)
└── tools/               # Özel araç fonksiyonları
    ├── __init__.py
    └── custom_tool.py
```

### 7.4. Güvenlik ve Dağıtım Koruma Önlemleri (Security Guardrails)
- **Dağıtım İzolasyonu:** Görsel düzenleme ve dosya yazma API uç noktaları yalnızca `adk web` ile yerel sunucuda kayıtlıdır. Cloud Run veya GKE dağıtımlarında (`adk deploy cloud_run`) yetkisiz dosya yazımını önlemek amacıyla bu endpoint'ler kaydedilmez.
- **Dosya Yükleme Sınırlamaları:** Yalnızca `.yaml` ve `.yml` uzantılı konfigürasyon dosyaları kabul edilir.
- **Kötü Niyetli Kod Engelleme:** Sunucu; mutlak dizin yollarını, dizin atlama dizilimlerini (`..` path traversal) ve rastgele kod yürütmeye yol açabilecek engellenmiş anahtarları (`args` vb.) otomatik olarak reddeder.

---

## 8. Ambient Agents (Olay Odaklı Arka Plan Ajanları & Trigger Mimarisi)

> [!NOTE]
> Ambient Ajanlar, kullanıcı etkileşimi beklemeden Cloud Storage yüklemeleri, veritabanı değişiklikleri, kuyruk mesajları veya cron zamanlamalarıyla arka planda otonom çalışan süreçlerdir (Python v1.29.0+, Go v1.1.0+).

### 8.1. İnşa Yaklaşımları

| Özellik | `/run` Entegrasyonu | Yerel Trigger Uç Noktaları |
| :--- | :--- | :--- |
| **Olay Kaynakları** | Genel Webhook'lar, GitHub, 3. parti API'ler | Cloud Pub/Sub, Eventarc (Standard & Advanced) |
| **Yük Ayrıştırma** | Geliştirici manuel yapar | Otomatik Base64 decode ve CloudEvent parsing |
| **Oturum Açma** | `--auto_create_session` bayrağı gerekir | Her olay için tekil UUID ile otomatik açılır |
| **Eşzamanlılık / Retry** | Manuel yönetim gerektirir | Dahili semafor ve jitter'lı üstel geri çekilme |

#### A. `/run` ile Webhook Karşılama
```powershell
adk api_server --auto_create_session path/to/your/agent
```
Dış sistemlerden gelen HTTP POST istekleri doğrudan `/run` uç noktasına iletilir.

#### B. Yerel Trigger Uç Noktaları
- **Pub/Sub Push:** `POST /apps/{app_name}/trigger/pubsub`
- **Eventarc CloudEvents:** `POST /apps/{app_name}/trigger/eventarc`
Ajan; gelen yükü `raw_event` formatında alır, JSON ve attribute'ları ayrıştırarak aksiyon üretir.

### 8.2. Eşzamanlılık (Concurrency) ve Kota Denetimi
Ani olay akınlarında LLM model kotalarının tükenmesini önlemek için semafor tabanlı eşzamanlılık sınırı uygulanır:
- **Ortam Değişkeni:** `ADK_TRIGGER_MAX_CONCURRENT=10` (veya Go'da `--trigger_max_concurrent_runs=10`)
Limit dolduğunda yeni istekler bekletilir ve slot boşaldıkça sırayla işlenir.

### 8.3. Hata Toleransı, Retry ve DLQ
- **Dahili Retry:** `429 RESOURCE_EXHAUSTED` gibi geçici hatalarda 3 denemeye kadar (`ADK_TRIGGER_MAX_RETRIES=3`, 1s - 30s arası) üstel geri çekilme (exponential backoff ve jitter) uygulanır.
- **Durum Kodları & DLQ:** İşlem tamamlandığında `HTTP 200` (Ack), giderilemeyen hatalarda `HTTP 500` (Nack) döner. Pub/Sub veya Eventarc başarısız mesajları Dead-Letter Topic/Queue (DLQ) üzerine yönlendirir.

### 8.4. Zaman Aşımı Kuralı (10 Dakika Limiti)
- Trigger uç noktaları senkron çalışır ve push aboneliklerinin azami onay süresi **10 dakikadır**.
- 10 dakikayı aşan uzun soluklu işler için push trigger yerine **Pub/Sub Pull aboneliği** veya **Cloud Run Jobs** tercih edilmelidir.

### 8.5. Cloud Run Dağıtımı
```powershell
adk deploy cloud_run `
  --project=$GOOGLE_CLOUD_PROJECT `
  --region=$GOOGLE_CLOUD_LOCATION `
  --trigger_sources="pubsub,eventarc" `
  path/to/your/agent
```


