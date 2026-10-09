---
title: "ADK Context Compaction Architecture Guide (Token-Based & Sliding-Window Event Summarization)"
description: "Comprehensive guide to Google ADK Context Compaction covering token-based and sliding-window compaction strategies, EventsCompactionConfig, LlmEventSummarizer, prompt customization, and multi-language configuration in Python, TypeScript, Go, Java, and Kotlin."
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - context-compaction
  - events-compaction
  - token-threshold
  - sliding-window
  - llm-summarizer
  - latency-optimization
  - cost-reduction
  - app
  - runner
  - python
  - typescript
  - go
  - java
  - kotlin
  - architecture
---

# Google ADK Bağlam Sıkıştırma Rehberi (`Context Compaction`)

Bir ajan uygulaması çalıştıkça kullanıcı talimatları, harici araç yanıtları, model çıktıları ve olay geçmişi (`events`) hızla büyür. Bağlam penceresinin şişmesi; **model yanıt sürelerini (latency) uzatır, token maliyetini katlar** ve modelin dikkatini dağıtabilir.

Google ADK'nın **Context Compaction (Bağlam Sıkıştırma)** mimarisi, SingleFlow iş akışındaki `CompactionRequestProcessor` aracılığıyla eski konuşma geçmişini arka planda otomatik olarak özetleyerek bağlam penceresini kompakt, hızlı ve ekonomik tutar.

---

## 1. 2 Temel Sıkıştırma Stratejisi

ADK, `EventsCompactionConfig` üzerinden iki farklı sıkıştırma stratejisi sunar:

| Strateji | Tetiklenme Mantığı | Temel Parametreler | İdeal Kullanım Senaryosu |
| :--- | :--- | :--- | :--- |
| **Token Tabanlı (Token-Based - Birincil)** | Oturumun tükettiği gerçek token hacmine göre | `token_threshold`, `event_retention_size` | Kullanıcının büyük kod blokları veya dokümanlar yapıştırdığı öngörülemeyen iş yükleri. |
| **Kayan Pencere (Sliding Window - Tur Tabanlı)** | Sabit sayıda tamamlanan çağrı/tur sayısına göre | `compaction_interval`, `overlap_size` | Standart, öngörülebilir metin tabanlı sohbetler. |

> [!IMPORTANT]
> **Öncelik Kuralı (Priority Rule):** İki strateji birden yapılandırıldığında sistem her zaman **Token Tabanlı** sıkıştırmaya öncelik verir. Oturumdaki token miktarı `token_threshold` değerini aştığında token tabanlı sıkıştırma çalışır ve o tur için kayan pencere sıkıştırması atlanır.

---

## 2. Stratejilerin Derinlemesine Anatomisi

### 2.1. Token Tabanlı Sıkıştırma (Token-Based Compaction)
Belirli bir tur sayısını beklemek yerine, oturumun toplam token yükünü izler:
- **`token_threshold`:** Sıkıştırmayı tetikleyen tavan token limitidir (örn: 4000 token).
- **`event_retention_size`:** Sıkıştırma yapıldığında en son kaç olayın **ham (sıkıştırılmamış)** olarak korunacağını belirler (örn: 5 olay). Bu olaylar özetlenmez; böylece model son turlardaki zamirleri ("o", "bunu"), son kullanıcı isteklerini ve anlık bağlamı kaybetmez.

### 2.2. Kayan Pencere Sıkıştırması (Sliding Window Compaction)
Konuşma turları belirli bir aralığa ulaştığında çalışır:
- **`compaction_interval`:** Kaç olayda/turda bir sıkıştırma yapılacağı (örn: 3). Olay 3, 6, 9... tamamlandığında özetleme tetiklenir.
- **`overlap_size`:** Önceki özet penceresinden yeni sıkıştırma penceresine kaç olayın örtüşme (overlap) olarak dahil edileceğini belirler (örn: 1). Bu örtüşme, özetler arası bilgi kopukluğunu engeller.

---

## 3. Çok Dilli SDK Yapılandırması

Sıkıştırma ayarları; Python, Java ve Kotlin'de **`App`** seviyesinde, TypeScript'te **`LlmAgent`** seviyesinde, Go'da ise doğrudan **`Runner`** konfigürasyonunda tanımlanır.

### Python
```python
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents import Agent

root_agent = Agent(name="support_agent", model="gemini-2.5-flash")

# Hem token tabanlı güvenlik ağı hem kayan pencere kuralı:
compaction_config = EventsCompactionConfig(
    token_threshold=4000,      # Token limiti
    event_retention_size=3,    # Korunacak ham son olay sayısı
    compaction_interval=5,     # 5 turda bir kayan pencere kontrolü
    overlap_size=1             # 1 olaylık örtüşme
)

app = App(
    name="compacted_support_app",
    root_agent=root_agent,
    events_compaction_config=compaction_config
)
```

### TypeScript
```typescript
import { Gemini, LlmAgent, LlmSummarizer, TokenBasedContextCompactor } from '@google/adk';

const agent = new LlmAgent({
  name: 'my-agent',
  model: 'gemini-2.5-flash',
  contextCompactors: [
    new TokenBasedContextCompactor({
      tokenThreshold: 2000,   // 2000 token aşıldığında sıkıştır
      eventRetentionSize: 2,  // Son 2 ham olayı koru
      summarizer: new LlmSummarizer({
        llm: new Gemini({ model: 'gemini-flash-latest' }),
      }),
    }),
  ],
});
```

### Go
```go
import (
    "google.golang.org/adk/v2/runner"
    "google.golang.org/adk/v2/session/compaction"
)

// Go'da sıkıştırma doğrudan Runner üzerinde yapılandırılır:
r, err := runner.New(runner.Config{
    AppName:        "my-agent",
    Agent:          rootAgent,
    SessionService: sessionService,
    Compaction: &compaction.Config{
        CompactionInterval: 4, // Her 4 çağrıda bir tetikle
        OverlapSize:        1, // 1 olay örtüşme
    },
})
```

### Java
```java
import com.google.adk.apps.App;
import com.google.adk.summarizer.EventsCompactionConfig;

App app = App.builder()
    .name("my-agent")
    .rootAgent(rootAgent)
    .eventsCompactionConfig(EventsCompactionConfig.builder()
        .compactionInterval(3)
        .overlapSize(1)
        .build())
    .build();
```

### Kotlin
```kotlin
import com.google.adk.kt.apps.App
import com.google.adk.kt.summarizer.EventsCompactionConfig

val app = App(
    appName = "my-agent",
    rootAgent = rootAgent,
    eventsCompactionConfig = EventsCompactionConfig(
        tokenThreshold = 3000,
        eventRetentionSize = 2,
    ),
)
```

---

## 4. Özel Özetleyici Tanımlama (`LlmEventSummarizer`)

Varsayılan özetleyici yerine daha hızlı veya daha ekonomik bir AI modelini özetleme görevine atayabilir; özetleme istemini (`prompt_template`) özelleştirebilirsiniz:

```python
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models import Gemini

# 1. Özetleme için hafif ve hızlı bir model seç:
summarization_llm = Gemini(model="gemini-flash-latest")

# 2. Özel istem şablonu ile özetleyiciyi oluştur:
custom_summarizer = LlmEventSummarizer(
    llm=summarization_llm,
    # prompt_template parametresi özelleştirilebilir:
    prompt_template=(
        "Aşağıdaki konuşma geçmişini kullanıcı tercihleri ve alınan aksiyonlar "
        "odağında kısa, maddeler halinde özetle:\n\n{conversation_history}"
    )
)

# 3. App konteynerine bağla:
app = App(
    name="custom_summary_app",
    root_agent=root_agent,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
        summarizer=custom_summarizer
    )
)
```

### Şablon Değişkeni Kuralı:
Özetleyici şablonu özelleştirilirken geçmiş konuşmanın yerleşeceği **`{conversation_history}`** yer tutucusu (placeholder) şablon içinde mutlaka yer almalıdır (Go'da `PromptTemplate`, TypeScript'te `prompt`).

---

## 5. Üretim İçin En İyi Pratikler

1. **Özetleme İçin Hafif Model Kullanın:** Ana akıl yürütme için `gemini-2.5-pro` kullansanız bile, özetleme için `LlmEventSummarizer(llm=Gemini(model="gemini-flash-latest"))` gibi hızlı ve ekonomik modeller seçin.
2. **`event_retention_size` Değerini Sıfır Yapmayın:** Son 2 ila 5 olayı her zaman ham bırakın. Aksi takdirde kullanıcının *"az önce bahsettiğim dosya"* gibi zamir ve referans içeren son cümleleri model tarafından anlaşılamaz.
3. **Karmaşık İş Yüklerinde Token Eşiğini Mutlaka Ekleyin:** Kod yazdıran veya dosya yüklenen ajanlarda sadece tur sayısına güvenmeyin; tek bir turda 50.000 token gelebileceği için `token_threshold` güvenlik kilidini mutlaka tanımlayın.
