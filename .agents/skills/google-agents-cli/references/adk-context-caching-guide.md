---
title: "ADK Context Caching Architecture Guide (Gemini 2.0+ Token & Latency Optimization)"
description: "Comprehensive technical guide to Google ADK Context Caching covering ContextCacheConfig parameters (min_tokens, ttl_seconds, cache_intervals), multi-language implementations in Python, Java, and Kotlin, latency/cost reduction, and comparison with Context Compaction."
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - context-caching
  - gemini-2
  - min-tokens
  - ttl
  - cache-intervals
  - latency-optimization
  - token-cost
  - app
  - python
  - java
  - kotlin
  - architecture
---

# Google ADK Bağlam Önbellekleme Rehberi (`Context Caching`)

Ajan iş akışlarında modelden geniş kapsamlı sistem talimatlarını (instructions), büyük şirket politika belgelerini veya onlarca karmaşık araç (tool) şemasını her kullanıcı mesajında yeniden işlemesi beklenebilir. Bu verileri her istekte modele baştan göndermek:
1. **Yanıt Süresini (Latency / TTFT - Time to First Token) uzatır.**
2. **Girdi Belirteç (Input Token) maliyetlerini katlar.**

Google ADK'nın **Context Caching (Bağlam Önbellekleme)** mimarisi, Gemini 2.0 ve üzeri modellerin yerel bağlam önbellekleme desteğini `App` seviyesinde devreye sokar. Bu özellik ajan koduna tamamen şeffaftır (transparent); ajan mantığında hiçbir değişiklik yapmadan model düzeyinde önbellekleme sağlar.

---

## 1. Desteklenen Diller ve Sürümler

| SDK Dili | Asgari ADK Sürümü | Uyumlu Model Ailesi |
| :--- | :--- | :--- |
| **Python** | `v1.15.0+` | Gemini 2.0 Flash / Pro ve üzeri |
| **Java** | `v0.1.0+` | Gemini 2.0 Flash / Pro ve üzeri |
| **Kotlin** | `v0.7.0+` | Gemini 2.0 Flash / Pro ve üzeri |

---

## 2. `ContextCacheConfig` Yapılandırma Parametreleri

Önbellekleme ayarları `App` nesnesine geçirilen `ContextCacheConfig` sınıfı ile yönetilir:

| Parametre | Tip | Açıklama |
| :--- | :--- | :--- |
| **`min_tokens`** | `int` | Önbelleğin tetiklenmesi için gereken asgari token eşiğidir. Bağlam boyutu bu değerin altındaysa standart çağrı yapılır, önbellek oluşturulmaz (örn: `2048`). |
| **`ttl_seconds`** (veya `ttl`) | `int` / `Duration` | Önbelleğe alınan bağlamın geçerlilik süresidir (Time-To-Live). Süre dolduğunda önbellek otomatik olarak temizlenir (örn: `600` saniye / 10 dakika veya `1800` saniye / 30 dakika). |
| **`cache_intervals`** | `int` | Önbelleğin kaç model çağrısında/kullanımında bir yeniden oluşturulacağını (refresh) belirler (örn: `5` veya `10`). |

---

## 3. Çok Dilli SDK Uygulama Örnekleri

### 3.1. Python (`ADK v1.15.0+`)

Python'da `ContextCacheConfig`, `google.adk.agents.context_cache_config` modülünden içe aktarılır ve `App` kurucusuna verilir:

```python
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

# 1. Kök ajanı Gemini 2.0+ modeliyle tanımla
root_agent = Agent(
    name="customer_support_agent",
    model="gemini-2.5-flash",
    instruction="""
    Sen kurumsal bir müşteri destek ajanısın. Aşağıda yer alan geniş kapsamlı
    hizmet şartlarını ve ürün garanti politikalarını harfiyen uygula:
    ... [Büyük Boyutlu Kurumsal Politika Metinleri ve Kurallar] ...
    """
)

# 2. Bağlam önbellekleme yapılandırmasını App seviyesinde tanımla
app = App(
    name="support_app",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,     # Yalnızca bağlam 2048 token'ı aştığında önbelleğe al
        ttl_seconds=600,     # Önbelleği 10 dakika (600 saniye) boyunca sakla
        cache_intervals=5    # 5 çağrıda bir önbelleği tazele
    )
)
```

---

### 3.2. Java (`ADK v0.1.0+`)

Java'da `App.builder()` akıcı arayüzü ve `java.time.Duration` kullanılır:

```java
import com.google.adk.agents.BaseAgent;
import com.google.adk.agents.LlmAgent;
import com.google.adk.agents.ContextCacheConfig;
import com.google.adk.apps.App;
import java.time.Duration;

LlmAgent rootAgent = LlmAgent.builder()
    .name("enterprise_support_agent")
    .model("gemini-2.5-flash")
    .instruction("Detaylı şirket yönergeleri...")
    .build();

App app = App.builder()
    .name("enterprise-caching-app")
    .rootAgent(rootAgent)
    .contextCacheConfig(
        new ContextCacheConfig(
            5,                      // cache_intervals (azami çağrı sayısı)
            Duration.ofMinutes(10), // ttl
            2048                    // min_tokens
        )
    )
    .build();
```

---

### 3.3. Kotlin (`ADK v0.7.0+`)

Kotlin'de tip güvenli yapılandırıcı ve `kotlin.time.Duration` sözdizimi kullanılır:

```kotlin
import com.google.adk.kt.agents.ContextCacheConfig
import com.google.adk.kt.agents.LlmAgent
import com.google.adk.kt.apps.App
import com.google.adk.kt.models.Gemini
import kotlin.time.Duration.Companion.minutes

val rootAgent = LlmAgent(
    name = "enterprise_support_agent",
    model = Gemini(name = "gemini-2.5-flash"),
    instruction = "Kapsamlı kurumsal belgeler ve talimatlar..."
)

val app = App(
    name = "enterprise-caching-app",
    rootAgent = rootAgent,
    contextCacheConfig = ContextCacheConfig(
        cacheIntervals = 5,
        ttl = 10.minutes,
        minTokens = 2048
    )
)
```

---

## 4. Context Caching vs. Context Compaction Karşılaştırması

ADK mimarisinde hem **Caching** hem **Compaction** bağlam optimizasyonu sağlar; ancak hedefleri ve çalıştıkları katmanlar tamamen farklıdır:

| Kriter | Context Caching (`ContextCacheConfig`) | Context Compaction (`EventsCompactionConfig`) |
| :--- | :--- | :--- |
| **Temel Amaç** | Statik, büyük ve tekrarlayan verileri (talimatlar, dokümanlar) modelde önbelleğe almak. | Dinamik, uzayan konuşma/olay geçmişini (`events`) özetleyerek pencere taşmasını önlemek. |
| **Çalıştığı Katman** | Model / Altyapı API katmanı (Gemini Caching). | ADK Olay Döngüsü / İstemci katmanı (`CompactionRequestProcessor`). |
| **Optimizasyon Türü** | Gecikme (Latency / TTFT) ve girdi belirteç maliyet tasarrufu. | Maksimum bağlam aşımını (context window overflow) engelleme. |
| **Veri Niteliği** | Statik / Yarı-statik (System Prompt, RAG şablonları, Tools). | Dinamik konuşma geçmişi (User, Agent, Tool Event'leri). |

### Hibrit Kurumsal Mimari (Hybrid Best Practice)
Üretim ortamındaki yüksek hacimli kurumsal uygulamalarda her iki konfigürasyon `App` nesnesinde aynı anda tanımlanmalıdır:

```python
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents.context_cache_config import ContextCacheConfig

app = App(
    name="enterprise_super_agent",
    root_agent=root_agent,
    # 1. Statik yönergeleri ve dokümanları önbelleğe alarak gecikmeyi ve maliyeti düşür:
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=1800,
        cache_intervals=10
    ),
    # 2. Uzun süren oturumlarda olay geçmişi şişmesini engelle:
    events_compaction_config=EventsCompactionConfig(
        token_threshold=4000,
        event_retention_size=3
    )
)
```

Bu hibrit yapı sayesinde ajan; hem başlangıçtaki devasa şirket dokümanlarını önbellekten okuyarak ilk belirteç yanıt süresini minimuma indirir, hem de konuşma yüzlerce tura uzadığında hafızasını otomatik özetleyerek bağlam taşmasını engeller.
