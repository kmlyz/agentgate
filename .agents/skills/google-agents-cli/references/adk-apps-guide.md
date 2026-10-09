---
title: "ADK App Workflow Management Class Guide"
description: "Complete architectural guide for the top-level App class, managing lifecycle hooks, root_agent, plugins, context caching, event compaction, and app-level state in Google ADK."
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - app
  - root-agent
  - lifecycle
  - on-startup
  - on-shutdown
  - context-caching
  - events-compaction
  - resumability
  - plugins
  - architecture
---

# Google ADK `App` İş Akışı Yönetim Sınıfı Rehberi

Google ADK'da **`App` sınıfı**, tüm ajan iş akışını (workflow) kapsülleyen en üst düzey konteynerdir. Bir **`root_agent`** etrafında kümelenmiş ajanların yaşam döngüsünü, kurumsal konfigürasyonunu ve paylaşılan durumunu (state) yönetmek üzere tasarlanmıştır.

`App` sınıfının temel felsefesi, **operasyonel altyapı gereksinimleri** (bağlantı havuzları, önbellekleme, telemetri eklentileri) ile tekil ajanların **görev odaklı bilişsel akıl yürütme** (reasoning) süreçlerini birbirinden ayırmaktır.

---

## 1. `App` Sınıfının Sağladığı Mimari Avantajlar

1. **Merkezi Konfigürasyon (Centralized Configuration):** API anahtarları, veritabanı istemcileri ve ortak servisler her ajana ayrı ayrı parametre olarak geçirilmek yerine tek bir merkezden yönetilir.
2. **Yaşam Döngüsü Kancaları (Lifecycle Management):** `on_startup` ve `on_shutdown` kancaları sayesinde oturumlar ve çağrılar boyunca yaşaması gereken veritabanı bağlantı havuzları ve bellek içi önbellekler güvenle yönetilir.
3. **Uygulama Durum Sınırı (Application State Scope):** `app:*` önekiyle tanımlanan açık durum alanı, verinin uygulama seviyesinde tüm oturumlar ve kullanıcılar için geçerli olduğunu kesinleştirir.
4. **Resmi Dağıtım Birimi (Unit of Deployment):** Ajan sistemini sürümlenebilir, bağımsız test edilebilir ve sunulabilir resmi bir dağıtım paketi haline getirir.

---

## 2. `App` Düzeyinde Yapılandırılan Temel Özellikler

`App` nesnesi başlatılırken aşağıdaki kurumsal özellikler modüler olarak atanır:

- **`root_agent` (Zorunlu):** Projenin birincil kontrolör ajanı (ve alt uzman ekipleri).
- **`context_cache_config`:** Gemini API bağlam önbelleklemesini (Context Caching) yönetir; tekrarlanan büyük sistem talimatları ve belgeler için token maliyetini ve yanıt gecikmesini minimize eder.
- **`events_compaction_config`:** Uzun diyaloglarda olay geçmişinin bağlam penceresini aşmaması için otomatik özetleme ve sıkıştırma (Context Compaction) kurallarını belirler.
- **`resumability_config`:** Kesintiye uğrayan veya insan onayı (HITL) bekleyen süreçlerin durumunu koruyarak kaldığı yerden devam edebilmesini (`resume`) sağlar.
- **`plugins`:** Telemetri, yapılandırılmış loglama, PII maskeleme ve Model Armor gibi kurumsal eklentileri sisteme enjekte eder.

---

## 3. Kod Örneği ve Proje Konvansiyonu

### A. Ajan ve Uygulama Tanımı (`agent.py`)

> [!TIP]
> **Değişken Adı Konvansiyonu:** ADK komut satırı araçlarının (`agents-cli playground`, `adk web`, `adk run`) uygulamayı otomatik tanıması için `App` nesnesi kesinlikle **`app`** değişken adına atanmalıdır.

```python
# agent.py
from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig

# 1. Kök Ajanı (Root Agent) Tanımla
root_agent = Agent(
    model="gemini-2.5-flash",
    name="greeter_agent",
    description="Kullanıcıları karşılayan ve yönlendiren kök ajan.",
    instruction="Kullanıcıya kibar ve profesyonel bir karşılama sunun.",
)

# 2. Üst Düzey App Konteynerini Yapılandır
app = App(
    name="enterprise_agent_app",
    root_agent=root_agent,
    # Bağlam önbellekleme (Context Caching - references/adk-context-caching-guide.md):
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=600,
        cache_intervals=5,
    ),
    # Opsiyonel kurumsal ayarlar:
    # plugins=[LoggingPlugin(), ModelArmorPlugin()],
    # events_compaction_config=...,
    # resumability_config=...,
)
```

### B. Java Uygulama Tanımı (`AgentConfiguration.java`)

```java
import com.google.adk.agents.LlmAgent;
import com.google.adk.agents.ContextCacheConfig;
import com.google.adk.apps.App;
import java.time.Duration;

LlmAgent rootAgent = LlmAgent.builder()
    .model("gemini-2.5-flash")
    .name("greeter_agent")
    .description("Kullanıcıları karşılayan kök ajan.")
    .instruction("Kullanıcıyı karşılayın.")
    .build();

App app = App.builder()
    .name("enterprise_agent_app")
    .rootAgent(rootAgent)
    .contextCacheConfig(
        new ContextCacheConfig(5, Duration.ofMinutes(10), 2048)
    )
    // .plugins(plugins)
    // .eventsCompactionConfig(eventsCompactionConfig)
    .build();
```

---

## 4. `App` ile Çalıştırma Modelleri (`Runner`)

`App` nesnesi `Runner` veya `InMemoryRunner` ile doğrudan çalıştırılabilir:

### Hızlı Hata Ayıklama (`run_debug`) - Python v1.18.0+
Geliştirme aşamasında oturum servisi ve karmaşık olay döngüsü kurmadan tek satırda test etmek için `run_debug` kullanılır:

```python
# main.py
import asyncio
from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from agent import app # agent.py dosyasından app nesnesini içe aktar

load_dotenv()

runner = InMemoryRunner(app=app)

async def main():
    try:
        # run_debug hızlı test sağlar (ADK Python v1.18.0+)
        response = await runner.run_debug("Merhaba! Bana sistem hakkında bilgi verir misin?")
        print("Yanıt:", response)
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Kurumsal Üretim Yürütücüsü (Full Event Loop)
```python
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.artifacts import GcsArtifactService
from agent import app

runner = Runner(
    app=app,
    session_service=DatabaseSessionService(db_url="..."),
    artifact_service=GcsArtifactService(bucket_name="..."),
)
```

---

## 5. Yaşam Döngüsü Kancaları (Lifecycle Hooks)

Uygulama açılırken ve kapanırken kritik altyapı kaynaklarını yönetmek için:

```python
from google.adk.apps import App

app = App(name="db_agent_app", root_agent=root_agent)

@app.on_startup
async def initialize_resources():
    print("Veritabanı bağlantı havuzu ve Redis önbelleği başlatılıyor...")
    # app.state["db_pool"] = await asyncpg.create_pool(...)

@app.on_shutdown
async def cleanup_resources():
    print("Bağlantı havuzları ve açık soketler kapatılıyor...")
    # await app.state["db_pool"].close()
```

---

## 6. Özet ve En İyi Uygulamalar

| Seviye | Sorumluluk Alanı | Tipik Bileşenler |
| :--- | :--- | :--- |
| **`App` Seviyesi** | Altyapı, Dağıtım, Güvenlik, Yaşam Döngüsü | `root_agent`, `on_startup`, `on_shutdown`, `plugins`, `context_cache`, `app:*` state |
| **`Agent` Seviyesi** | Görev Akıl Yürütmesi, Rol Tanımı | `instruction`, `model`, `tools`, `sub_agents`, ReAct döngüsü |
| **`Tool` Seviyesi** | Dış Dünya Entegrasyonu | `FunctionTool`, `McpToolset`, `RestApiTool`, `ToolContext` |
