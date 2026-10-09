---
title: "ADK Custom Tools and Tool Context Guide"
description: "Complete guide for building custom tools, using ToolContext, managing state deltas, controlling agent flow, and organizing toolsets in Google ADK"
category: integrations
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - tools
  - function-tool
  - tool-context
  - state-delta
  - tool-filter
  - integrations
---

# Google ADK Özel Araçlar ve Araç Bağlamı (Custom Tools & ToolContext)

ADK araçları (Tools), bir ajanın salt metin üretiminin ötesine geçerek harici API'lara erişmesini, veri tabanlarını sorgulamasını, kod çalıştırmasını ve eylemler gerçekleştirmesini sağlayan yapılandırılmış fonksiyonlardır (Python, TypeScript, Go, Java, Kotlin destekli).

---

## 1. Araç Tipleri ve Mimarisi

Ajanlar araçları dinamik **Function Calling** mekanizması ile çalıştırır. ADK, farklı karmaşıklık düzeylerine uygun üç temel özel araç tipi sunar:

---

### 1.1. Standart Fonksiyon Araçları (`FunctionTool`)
Herhangi bir Python fonksiyonu ajanın `tools` listesine verildiğinde ADK tarafından otomatik olarak `FunctionTool` olarak sarmalanır.

#### Parametre ve Şema Çözümleme Kuralları:
- **Zorunlu Parametreler (Required):** Tip ipucu (type hint) olan ve varsayılan değeri bulunmayan parametrelerdir. Model bu parametreleri doldurmak zorundadır (eksik bırakırsa framework modele hata fırlatarak düzeltmesini ister).
- **İsteğe Bağlı Parametreler (Optional):** Varsayılan değeri olan (`param: str = "default"`) veya `Optional[T]` olarak tanımlanan parametrelerdir.
- **Docstring Önemi:** Parametrelerin ve fonksiyonun açıklamaları docstring üzerinden okunarak LLM'in araç seçim şemasına dönüştürülür.
- **Diller Arası Şema Kuralları:**
  - **Go:** `struct` etiketleri kullanılır; `omitempty` olmayan alanlar zorunludur, `jsonschema:"açıklama"` parametre tanımını sağlar.
  - **Java:** `@Schema(name="...", description="...")` anotasyonları kullanılır; ilkel tipler (`int`, `boolean`) doğası gereği zorunludur.
  - **Kotlin:** `@Tool` ve `@Param("açıklama")` anotasyonları kullanılır; `null` olamayan tipler zorunludur.

---

### 1.2. Uzun Süreli Fonksiyon Araçları (`LongRunningFunctionTool`)
Finansal onaylar (HITL - Human-in-the-Loop), uzun süren veri işleme veya harici asenkron iş emirleri gibi anında yanıt veremeyen işlemler için kullanılır.

#### İki Aşamalı Çalışma Mekanizması:
1. **Tur 1 (Başlatma & Askıya Alma):** Model aracı çağırdığında araç geçici bir durum (`status: 'pending'`) döner. ADK bu çağrıyı `event.long_running_tool_ids` içine kaydeder ve yürütmeyi duraksatır.
2. **Tur 2 (Dış Yanıtla Devam Ettirme):** Onay/asenkron işlem tamamlandığında, dış sistem veya uygulama ilgili `function_call_id`'yi içeren bir `FunctionResponse` nesnesini ajanın oturumuna yeni bir kullanıcı mesajı olarak enjekte eder (`runner.run_async(...)`). Ajan süreci kaldığı yerden tamamlar.

```python
from typing import Any
from google.adk.agents import Agent
from google.adk.tools import LongRunningFunctionTool

def ask_for_manager_approval(purpose: str, amount: float) -> dict[str, Any]:
    """100$ uzeri harcamalar icin yonetici onay bileti olusturur."""
    # Bilet olusturulur ve onayciya bildirim gider
    return {"status": "pending", "ticket_id": "TICKET-1234", "approver": "Finance Lead"}

long_tool = LongRunningFunctionTool(func=ask_for_manager_approval)

reimbursement_agent = Agent(
    model="gemini-flash-latest",
    name="reimbursement_agent",
    instruction="100$ uzeri islemlerde 'ask_for_manager_approval' aracini kullan.",
    tools=[long_tool],
)
```

---

### 1.3. Gelişmiş Ajan-Araç Yapılandırması (`AgentTool`)
Uzmanlaşmış bir alt ajanı, üst koordinatör ajanın tek bir fonksiyon gibi çağırabileceği bir araca dönüştürür.

#### Kritik Yapılandırma Parametreleri:
- **`propagate_grounding_metadata: bool` (Varsayılan: False):**
  `True` yapıldığında, alt arama uzmanı ajanın ürettiği Google Search kaynak ve alıntıları (grounding metadata) üst ajanın oturum durumuna eksiksiz aktarılır.
- **`include_plugins: bool` (Varsayılan: True):**
  Alt ajanın üst runner eklentilerini (telemetri, trace spans vb.) devralıp devralmayacağını belirler. `False` ayarlandığında alt ajan tamamen yalıtılmış, eklentisiz bir ortamda çalışır.
- **`skip_summarization: bool` (Varsayılan: False):**
  `True` yapıldığında, üst ajanın alt ajandan gelen nihai cevabı tekrar özetlemesi engellenir; alt ajanın çıktısı doğrudan kullanıcıya aktarılır (gecikmeyi düşürür).

```python
from google.adk.agents import Agent
from google.adk.tools import AgentTool

# 1. Uzman arama ajani
search_agent = Agent(
    model="gemini-flash-latest",
    name="search_agent",
    instruction="Web uzerinde arama yap ve kaynaklari derle.",
)

# 2. AgentTool ile sarmalama
search_tool = AgentTool(
    agent=search_agent,
    propagate_grounding_metadata=True,  # Arama kaynaklarini koru
    skip_summarization=True,             # Fazladan ozetleme cagrisini atla
    include_plugins=True,                # Telemetriyi devral
)

# 3. Ust koordinator ajan
root_agent = Agent(
    model="gemini-flash-latest",
    name="root_agent",
    instruction="Kullanici arastirma istediginde 'search_agent' aracini cagir.",
    tools=[search_tool],
)
```


---

## 2. Ajan Talimatlarında Araç Yönlendirmesi

Model, araçları fonksiyon adı ve **docstring açıklamaları** üzerinden tanır:
- **Ne Zaman Kullanılmalı:** İstemde aracın teknik parametre detaylarından çok, modelin hangi senaryoda bu aracı tetiklemesi gerektiği vurgulanmalıdır.
- **Dönüş Değeri Yönetimi:** Aracın dönebileceği başarı (`status: "success"`) ve hata (`status: "error"`) yanıtlarında ajanın nasıl tepki vereceği istemde açıkça tanımlanmalıdır.
- **Sıralı Zincirleme (Sequential Tool Use):** Bir aracın çıktısının diğerine girdi olacağı durumlar model talimatlarında adım adım tarif edilmelidir.

### Örnek Ajan Tanımı:
```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

def get_weather(city: str) -> dict:
    """Retrieves current weather for a city."""
    if city.lower() == "london":
        return {"status": "success", "report": "18C, cloudy"}
    return {"status": "error", "error_message": f"Weather for '{city}' unavailable."}

def analyze_sentiment(text: str) -> dict:
    """Analyzes sentiment of user feedback."""
    return {"sentiment": "positive", "confidence": 0.8}

weather_agent = Agent(
    name="weather_sentiment_agent",
    model="gemini-flash-latest",
    instruction="""You provide weather information and analyze feedback sentiment.
- If the user asks about a city, use 'get_weather'.
- If 'get_weather' returns 'success', report the weather.
- If 'get_weather' returns 'error', politely inform the user.
- If user provides feedback, call 'analyze_sentiment' and acknowledge it.""",
    tools=[FunctionTool(func=get_weather), FunctionTool(func=analyze_sentiment)],
)
```

---

## 3. Gelişmiş Araç Bağlamı (`ToolContext`)

Gelişmiş senaryolarda fonksiyon imzasında `tool_context: ToolContext` parametresi yer aldığında, ADK bu nesneyi çalışma zamanında **otomatik olarak enjekte eder**.

> [!CAUTION]
> `tool_context` parametresi fonksiyonun docstring'ine **yazılmamalıdır!** Model bu parametreyi görmemeli ve doldurmaya çalışmamalıdır; enjeksiyon tamamen ADK çalışma zamanı tarafından yapılır.

### 3.1. Oturum Durumu Yönetimi (`tool_context.state`)
`tool_context.state` doğrudan oturum durumuna okuma ve yazma erişimi sağlar. Yapılan tüm değişiklikler otomatik olarak `state_delta` içine kaydedilir ve `SessionService` tarafından kalıcılaştırılır.

#### Durum Prefix Hiyerarşisi:
- **`app:*`:** Uygulamanın tüm kullanıcıları arasında paylaşılan genel durum.
- **`user:*`:** İlgili kullanıcının tüm oturumları boyunca geçerli durum (örn: `user:preferences`).
- **(Ön eksiz):** Yalnızca geçerli oturuma (`Session`) özel durum.
- **`temp:*`:** Geçici, kalıcılaştırılmayan çalışma zamanı verisi.

```python
from google.adk.tools import ToolContext, FunctionTool

def update_user_preference(preference: str, value: str, tool_context: ToolContext) -> dict:
    """Updates a user-specific preference."""
    user_prefs_key = "user:preferences"
    prefs = tool_context.state.get(user_prefs_key, {})
    prefs[preference] = value
    # Durumu doğrudan güncelle (otomatik delta olarak kaydedilir)
    tool_context.state[user_prefs_key] = prefs
    return {"status": "success", "updated_preference": preference}
```

---

### 3.2. Ajan Yürütme Akışını Yönlendirme (`tool_context.actions`)
`tool_context.actions` (`EventActions`) nesnesi, araç bittikten sonra ajanın veya çerçevenin ne yapacağını kontrol eder:

- **`skip_summarization: bool` (Varsayılan: False):**
  - `True` yapıldığında, modelin araç çıktısını özetlemek için fazladan yapacağı LLM çağrısı atlanır. Aracın dönüşü doğrudan son kullanıcıya iletilir (gecikmeyi ve token maliyetini düşürür).
- **`transfer_to_agent: str`:**
  - Mevcut ajanın çalışması durdurulur ve diyalog kontrolü adı verilen başka bir uzman alt ajana devredilir (örn: acil bir talepte `support_agent`'a aktarım).
- **`escalate: bool` (Varsayılan: False):**
  - Talebin mevcut ajan tarafından karşılanamadığını bildirir ve hiyerarşideki üst ajana (parent agent) devreder. `LoopAgent` içinde `escalate=True` döngüyü kırıp sonlandırır.

```python
def check_and_transfer(query: str, tool_context: ToolContext) -> str:
    """Checks urgency and transfers to support_agent if required."""
    if "urgent" in query.lower():
        tool_context.actions.transfer_to_agent = "support_agent"
        return "Talebiniz acil olarak işaretlendi, destek uzmanına aktarılıyorsunuz..."
    return f"Sorgu işlendi: '{query}'."
```

---

### 3.3. Olay ve Servis Erişimi
`ToolContext` üzerinden ek meta verilere erişilebilir:
- **`function_call_id`:** O çağrıya ait tekil kimlik (paralel çağrılarda eşleştirme sağlar).
- **`function_call_event_id`:** Aracı tetikleyen olayın kimliği.
- **`auth_response`:** Kimlik doğrulama akışından dönen kimlik bilgileri/tokenlar.
- **Servis Metotları:** `ArtifactService` ve `MemoryService` erişimi.

---

## 4. Modüler Araç Kümeleri (`Toolset` / `BaseToolset`)

Birden fazla aracı tek bir çatı altında gruplamak ve dinamik olarak sunmak için kullanılır:
- **`get_tools(readonly_context)`:** Oturum durumuna göre sunulacak araç listesini döner.
- **`close()`:** Araç kümesinin kullandığı kaynakları (veritabanı bağlantısı, HTTP client vb.) temizler.

### Dinamik Filtreleme (`ToolFilter`):
- **İsim Bazlı:** `ToolFilter.allowList("tool1", "tool2")` ile sabit alt küme sunma.
- **Koşullu Predicate:** Oturum durumundaki bir anahtara (`context.state.get("enable_advanced_math") == True`) veya kullanıcı rolüne göre araçları dinamik olarak açıp kapatma.

---

## 5. Araç Performansı ve Paralel Yürütme (Parallel Tool Execution - v1.10.0+)

ADK (Python v1.10.0+), bir ajan tek bir turda birden çok araç çağrısı ürettiğinde bu araçları otomatik olarak eşzamanlı/paralel (`asyncio` event loop) çalıştırmayı dener.
Örneğin her biri 2 saniye süren 3 bağımsız API çağrısı, sıralı 6 saniye beklemek yerine paralel olarak **yaklaşık 2 saniyede** tamamlanır.

### Paralel Yürütmenin Etkili Olduğu Senaryolar:
- **Araştırma Görevleri:** Ajann bir sonraki adıma geçmeden önce birden çok kaynaktan (arama, doküman, intranet) paralel bilgi toplaması.
- **Çoklu API Çağrıları:** Bağımsız servislerden eşzamanlı veri çekme (örn: farklı havayollarından uçuş arama).
- **Çok Kanallı Bildirim:** Bağımsız kanallara (Slack, E-posta, SMS) eşzamanlı mesaj gönderme.

> [!WARNING]
> **Kritik Senkron Bloklama Uyarısı:**
> Paralel yürütülmesi planlanan bir araç grubu içinde **tek bir senkron (`def`) fonksiyon bile bulunursa**, diğer tüm asenkron araçların da eşzamanlı çalışmasını engeller ve tüm işlem grubunu kilitler! Tüm araçlar `async def` olarak tasarlanmalıdır.

---

### 5.1. Asenkron Araç Geliştirme Desenleri

#### 1. Asenkron HTTP İstemcisi (`aiohttp`):
```python
import aiohttp

async def get_weather(city: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.weather.com/{city}") as response:
            return await response.json()
```

#### 2. Asenkron Veritabanı Sorguları (`asyncpg`):
```python
import asyncpg

async def query_database(query: str) -> list:
    async with asyncpg.connect("postgresql://user:pass@host/db") as conn:
        return await conn.fetch(query)
```

#### 3. Uzun Döngülerde İşlemciyi Bırakma (Yielding via `asyncio.sleep(0)`):
Yoğun veri işleme döngülerinde event loop'un diğer araçları çalıştırmasına fırsat tanımak için periyodik yield noktaları eklenmelidir:
```python
import asyncio

async def process_data(data: list) -> dict:
    results = []
    for i, item in enumerate(data):
        processed = await process_item(item)
        results.append(processed)
        if i % 100 == 0:
            await asyncio.sleep(0)  # Kontrolü diger asenkron islemlere devret
    return {"results": results}
```

#### 4. CPU Yoğun İşlemler İçin İş Parçacığı Havuzu (`ThreadPoolExecutor`):
Ağır matematiksel hesaplama veya bloklayan CPU görevleri ana event loop'u tıkamamalıdır:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def cpu_intensive_tool(data: list) -> dict:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, expensive_computation, data)
    return {"result": result}
```

#### 5. Büyük Veri Kümelerini Parçalama (Process Chunking):
```python
async def process_large_dataset(dataset: list) -> dict:
    results = []
    chunk_size = 1000
    loop = asyncio.get_event_loop()

    for i in range(0, len(dataset), chunk_size):
        chunk = dataset[i:i + chunk_size]
        with ThreadPoolExecutor() as executor:
            chunk_result = await loop.run_in_executor(executor, process_chunk, chunk)
        results.extend(chunk_result)
        await asyncio.sleep(0)  # Dilimler arasinda event loop'a nefes aldir

    return {"total_processed": len(results), "results": results}
```

---

### 5.2. Paralelliği Teşvik Eden İstem ve Docstring Tasarımı

Modelin tek seferde birden çok fonksiyon çağırmasını tetiklemek için ajan talimatlarına ve docstring'lerine açık ipuçları verilmelidir:

**Ajan Talimatı (Instruction) Örneği:**
```text
Kullanıcı birden çok bilgi talep ettiğinde fonksiyonları her zaman eşzamanlı/paralel çağır.
Örnek: "Londra hava durumunu ve USD/EUR kurunu getir" -> İki aracı aynı anda tetikle.
Tekil ve karmaşık çağrılar yerine birden çok spesifik fonksiyon çağrısını tercih et.
```

**Docstring İpucu:**
```python
async def get_city_metrics(city: str) -> dict:
    """Belirli bir sehir icin metrikleri getirir.
    
    Bu fonksiyon paralel calisma icin optimize edilmistir; birden cok sehir
    icin ayni anda birden fazla kez cagrilabilir.
    """
    ...
```

---

## 6. Araç Eylem Onayı (Tool Confirmation - HITL - v1.14.0+)

Kritik işlemler (finansal harcamalar, izin talepleri, sistem ayarlarını değiştirme, veri silme) öncesinde insan onayı (Human-in-the-Loop) veya denetleyici bir sistemden onay almak için **Tool Confirmation** mekanizması kullanılır (Supported in ADK Python v1.14.0+, Experimental).

Araç çağrıldığında yürütme duraksar (pause edilir), kullanıcıdan onay veya ek yapılandırılmış veri alındıktan sonra kaldığı yerden devam eder (resume).

---

### 6.1. Basit Onay (Boolean Confirmation - Evet/Hayır)

Aracın çalışması için kullanıcının yalnızca onay verip vermemesi yeterliyse iki şekilde yapılandırılabilir:

#### A. Statik Onay Zorunluluğu:
```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

def reimburse(amount: float) -> dict:
    """Calisan masrafini oder."""
    return {"status": "success", "amount": amount}

root_agent = Agent(
    name="finance_agent",
    model="gemini-flash-latest",
    tools=[
        # require_confirmation=True ile her cagridan once onay penceresi acilir
        FunctionTool(reimburse, require_confirmation=True),
    ],
)
```

#### B. Dinamik Eşik Fonksiyonu (Conditional Threshold):
Onay ihtiyacını parametreye göre dinamik belirleme (örn: yalnızca 1000$ üzerindeki masraflar için onay isteme):

```python
from google.adk.tools import ToolContext

async def confirmation_threshold(amount: float, tool_context: ToolContext) -> bool:
    """1000$ uzerindeki tutarlar icin onay gerektirir."""
    return amount > 1000.0

root_agent = Agent(
    name="finance_agent",
    model="gemini-flash-latest",
    tools=[
        FunctionTool(reimburse, require_confirmation=confirmation_threshold),
    ],
)
```

---

### 6.2. Gelişmiş Yapılandırılmış Onay (Advanced Confirmation)

Yalnızca evet/hayır yerine kullanıcıdan veya yöneticiden yapılandırılmış veri (örn: onaylanan gün sayısı, gerekçe, revize tutar) toplamak gerektiğinde kullanılır:

#### İki Aşamalı Akış:
1. **Talep Aşaması:** `tool_context.tool_confirmation` boşsa, `request_confirmation(hint=..., payload=...)` çağrılarak işlem duraksatılır ve ara durum döndürülür.
2. **Onay Aşaması:** Kullanıcı yanıt verdikten sonra araç yeniden tetiklenir; `tool_confirmation.confirmed` ve `tool_confirmation.payload` okunarak işlem tamamlanır.

```python
from google.adk.tools import ToolContext

def request_time_off(days: int, tool_context: ToolContext) -> dict:
    """Calisan icin izin talebi olusturur."""
    tool_confirmation = tool_context.tool_confirmation

    # 1. Aşama: Henüz onay gelmediyse onay talep et ve duraksat
    if not tool_confirmation:
        tool_context.request_confirmation(
            hint=f"{days} günlük izin talebi için yönetici onayı gereklidir.",
            payload={"approved_days": 0},
        )
        return {"status": "PENDING_MANAGER_APPROVAL", "requested_days": days}

    # 2. Aşama: Onay yanıtı alındı, sonucu değerlendir
    if not tool_confirmation.confirmed:
        return {"status": "REJECTED", "message": "İzin talebi yönetici tarafından reddedildi."}

    approved_days = tool_confirmation.payload.get("approved_days", 0)
    return {
        "status": "APPROVED",
        "requested_days": days,
        "approved_days": min(approved_days, days),
    }
```

---

### 6.3. Uzaktan REST API / SSE ile Onaylama (`/run_sse`)

Web arayüzü olmayan senaryolarda (Slack botu, e-posta onay linki veya mikroservis entegrasyonu), onay kararı ADK API sunucusuna `FunctionResponse` formatında iletilir:

```bash
curl -X POST http://localhost:8000/run_sse \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "human_tool_confirmation",
    "user_id": "user",
    "session_id": "7828f575-2402-489f-8079-74ea95b6a300",
    "new_message": {
      "parts": [
        {
          "function_response": {
            "id": "adk-13b84a8c-c95c-4d66-b006-d72b30447e35",
            "name": "adk_request_confirmation",
            "response": {
              "confirmed": true,
              "payload": {
                "approved_days": 5
              }
            }
          }
        }
      ],
      "role": "user"
    }
  }'
```

- **`id`:** Orijinal `adk_request_confirmation` olayındaki `function_call_id` ile eşleşmelidir.
- **`name`:** `adk_request_confirmation` olmalıdır.
- **`response`:** `confirmed` (bool) ve varsa `payload` nesnesini içerir.
- **Resume Desteği:** Oturumda `Resume` özelliği kullanılıyorsa, onay mesajı orijinal çağrının `invocation_id` değerini içermelidir.

---

### 6.4. Bilinen Kısıtlar (Known Limitations)
- `DatabaseSessionService` bu özelliği şu an desteklememektedir.
- `VertexAiSessionService` bu özelliği şu an desteklememektedir.

---

---

## 7. OpenAPI ile REST API Entegrasyonu (`OpenAPIToolset` & `RestApiTool`)

ADK, mevcut bir [OpenAPI v3.x](https://swagger.io/specification/) spesifikasyonundan doğrudan çağrılabilir araçlar (`RestApiTool`) üreten `OpenAPIToolset` bileşenini sunar. Her API uç noktası için ayrı ayrı fonksiyon yazma ihtiyacını ortadan kaldırır.

### 7.1. Temel Bileşenler
- **`OpenAPIToolset`:** OpenAPI spesifikasyonunu ayrıştıran, dahili referansları (`$ref`) çözen ve araçları üreten ana fabrika sınıfı.
- **`RestApiTool`:** Spesifikasyondaki her bir tekil HTTP operasyonunu (`GET /pets/{petId}`, `POST /pets`) temsil eden çalıştırılabilir araç birimi.

---

### 7.2. Otomatik Araç Türetme ve Çalışma Mekanizması

1. **Ayrıştırma ve Referans Çözümleme:**
   - Spesifikasyon bir Python `dict`, JSON string veya YAML string olarak verilebilir.
   - Dahili tüm `$ref` bileşenleri otomatik olarak çözümlenir.
2. **Operasyon Keşfi ve Araç İsimlendirme:**
   - `paths` nesnesi altındaki tüm geçerli HTTP metodları (`GET`, `POST`, `PUT`, `DELETE` vb.) keşfedilir.
   - **Araç Adı:** Operasyonun `operationId` değerinden türetilir (`snake_case` formatına dönüştürülür, maks 60 karakter). Eğer `operationId` belirtilmemişse, HTTP metodu ve uç nokta yolundan otomatik isim oluşturulur.
   - **Araç Açıklaması:** Operasyonun `summary` veya `description` metni kullanılarak LLM için araç dokümantasyonuna dönüştürülür.
3. **Dinamik Şema İnşası (`FunctionDeclaration`):**
   - Path, query, header, cookie parametreleri ve request body şeması analiz edilerek LLM'in araç çağırırken uyması gereken şema oluşturulur.
4. **Asenkron Yürütme ve Yanıt:**
   - Model aracı tetiklediğinde, `RestApiTool` `httpx` kütüphanesini kullanarak asenkron HTTP isteğini oluşturur ve yürütür.
   - Dönen JSON yanıtı ajanın olay akışına aktarılır.
5. **Küresel Kimlik Doğrulama:**
   - `OpenAPIToolset` başlatılırken `auth_scheme` ve `auth_credential` parametreleri verilerek tüm üretilen `RestApiTool` nesnelerine otomatik olarak uygulanır.

---

### 7.3. Uçtan Uca Kod Örneği

```python
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.genai import types

# 1. OpenAPI v3.0 Spesifikasyonu (JSON veya YAML)
petstore_spec = """
{
  "openapi": "3.0.0",
  "info": {"title": "Pet Store API", "version": "1.0.0"},
  "servers": [{"url": "https://httpbin.org"}],
  "paths": {
    "/get": {
      "get": {
        "operationId": "listPets",
        "summary": "Mevcut evcil hayvanları listeler.",
        "parameters": [
          {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["available", "pending", "sold"]}}
        ]
      }
    },
    "/post": {
      "post": {
        "operationId": "createPet",
        "summary": "Yeni bir evcil hayvan kaydı oluşturur.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}, "tag": {"type": "string"}}
              }
            }
          }
        }
      }
    }
  }
}
"""

# 2. OpenAPIToolset Örneği Oluşturma
petstore_toolset = OpenAPIToolset(
    spec_str=petstore_spec,
    spec_str_type="json",
)

# 3. Ajanı Tanımlama ve Toolset'i Bağlama
root_agent = LlmAgent(
    name="petstore_agent",
    model="gemini-2.5-flash",
    tools=[petstore_toolset],
    instruction="""Evcil hayvan yönetim sisteminden sorumlusunuz.
    Gerektiğinde 'list_pets' ve 'create_pet' araçlarını kullanarak kullanıcı isteklerini yerine getirin.
    Oluşturma işleminden sonra sunucu yanıtındaki ayrıntıları teyit edin.""",
)

# 4. Çalıştırma
async def main():
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="petstore_app", session_service=session_service)
    session = await session_service.create_session(app_name="petstore_app", user_id="user_1")

    msg = types.Content(role="user", parts=[types.Part(text="Satıştaki uygun evcil hayvanları listeler misin?")])
    async for event in runner.run_async(session_id=session.id, user_id=session.user_id, new_message=msg):
        if event.is_final_response() and event.content and event.content.parts:
            print("Ajan Yanıtı:", event.content.parts[0].text)

if __name__ == "__main__":
    asyncio.run(main())
```

---

---

## 8. Yerleşik Araç Kısıtlamaları ve Mimari Çözüm Yolları (Tool Limitations & Workarounds)

ADK'nın yerleşik (built-in) Gemini API araçları bazı platform ve sürüm kısıtlamalarına tabidir. Bu kısıtlar doğru mimari kalıplar kullanılmadığında çalışma zamanı hatalarına yol açar.

### 8.1. Ajan Başına Tek Yerleşik Araç Kısıtı (Mutual Exclusion)

Aşağıdaki yerleşik araçlar, tek bir ajan nesnesi içerisinde diğer özel araçlarla (`FunctionTool`) veya birbirleriyle doğrudan **birlikte kullanılamaz**:
- **Code Execution (`BuiltInCodeExecutor`):** Gemini API ile kod yürütme (Not: TypeScript'te Gemini 2.0+ modelleriyle bu sınırlama kalkmıştır).
- **Google Search (`GoogleSearchTool` / `google_search`):** Web araması (Not: ADK Python v1.15.0 ve altında geçerlidir; v1.16.0+ ile dahili olarak çözülmüştür. TypeScript'te yalnızca Gemini 1.x'te sınırlıdır).
- **Agent Search (`VertexAiSearchTool`):** Kurumsal bilgi tabanı araması.

```python
# DESTEKLENMEZ: Yerleşik kod yürütücü ile özel fonksiyon aynı ajana verilemez
root_agent = Agent(
    name="RootAgent",
    model="gemini-2.5-flash",
    tools=[custom_function],
    code_executor=BuiltInCodeExecutor() # HATA: tools ile birlikte kullanılamaz!
)
```

---

### 8.2. Çözüm Yolu 1: `AgentTool` ile İzolasyon (Evrensel Kalıp)

Farklı yerleşik araçları veya yerleşik araçlarla özel fonksiyonları birlikte kullanmanın standart yolu, her yerleşik aracı tek başına bir **uzman alt ajana** atamak ve bu alt ajanları ana orkestratöre `AgentTool` olarak sunmaktır:

```python
from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.code_executors import BuiltInCodeExecutor

# 1. Yalnızca Google Search kullanan alt ajan
search_agent = Agent(
    model="gemini-2.5-flash",
    name="SearchAgent",
    instruction="Web araması konusunda uzman ajansınız.",
    tools=[google_search],
)

# 2. Yalnızca Kod Yürütme yetkisine sahip alt ajan
coding_agent = Agent(
    model="gemini-2.5-flash",
    name="CodeAgent",
    instruction="Python kodu yazma ve çalıştırmada uzman ajansınız.",
    code_executor=BuiltInCodeExecutor(),
)

# 3. Alt ajanları AgentTool olarak tüketen ana orkestratör
root_agent = Agent(
    name="RootAgent",
    model="gemini-2.5-flash",
    description="Kullanıcı isteklerini yöneten ana orkestratör.",
    tools=[
        AgentTool(agent=search_agent),
        AgentTool(agent=coding_agent),
        custom_function, # İstenirse diğer özel fonksiyonlar da buraya eklenebilir
    ],
)
```
*(Java'da `AgentTool.create(searchAgent)`, Kotlin'de `AgentTool(agent = searchAgent)` kullanılır).*

---

### 8.3. Kritik Mimari Tuzak: `sub_agents` Anti-Pattern

> [!CAUTION]
> **Yerleşik Araçlar `sub_agents` İçinde Kullanılamaz:**
> Birçok geliştirici alt ajanları doğrudan `root_agent = Agent(sub_agents=[search_agent, coding_agent])` şeklinde bağlamaya çalışır. Yerleşik araç içeren ajanlar (Code Executor, Google Search) klasik `sub_agents` listesine verildiğinde sistem çöker!
> 
> **Kural:** Yerleşik araç barındıran alt ajanlar **kesinlikle `AgentTool(agent=...)` ile sarmalanarak `tools` listesine verilmelidir**.

---

### 8.4. Çözüm Yolu 2: `bypass_multi_tools_limit=True` Bayrağı

ADK Python, Java ve Kotlin ortamlarında `GoogleSearchTool` ve `VertexAiSearchTool` araçlarının aynı ajanda diğer araçlarla doğrudan çalışabilmesi için yerleşik bir bayrak sunar:

```python
from google.adk.tools import GoogleSearchTool

search_tool = GoogleSearchTool(bypass_multi_tools_limit=True)

# Artık aynı ajan içinde diğer fonksiyonlarla birlikte kullanılabilir
agent = Agent(
    model="gemini-2.5-flash",
    tools=[search_tool, custom_calc_tool],
)
```

---

## 9. İlgili Bağlantılar
- Resmi Dokümantasyon: [Custom Tools for ADK](https://adk.dev/tools-custom/index.md)
- Araç Kısıtlamaları: [Limitations for ADK Tools](https://adk.dev/tools/limitations/index.md)
- Fonksiyon Araçları: [Function Tools](https://adk.dev/tools-custom/function-tools/index.md)
- OpenAPI Araçları: [Integrate REST APIs with OpenAPI](https://adk.dev/tools-custom/openapi-tools/index.md)
- Kimlik Doğrulama: [ADK Auth Guide](file:///c:/dev/doc-agent/.agents/skills/google-agents-cli/references/adk-auth-guide.md)
- Model Context Protocol: [ADK MCP Guide](file:///c:/dev/doc-agent/.agents/skills/google-agents-cli/references/adk-mcp-guide.md)
- Araç Performansı: [Tool Performance](https://adk.dev/tools-custom/performance/index.md)
- Araç Eylem Onayı: [Tool Confirmation](https://adk.dev/tools-custom/confirmation/index.md)
- Güvenlik Rehberi: [ADK Safety Guide](file:///c:/dev/doc-agent/.agents/skills/google-agents-cli/references/adk-safety-security-guide.md)




