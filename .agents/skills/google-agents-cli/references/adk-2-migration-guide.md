---
title: "ADK 2.0 Architecture and Migration Guide"
description: "Comprehensive guide for migrating from Google ADK 1.x to ADK 2.0 Workflow Runtime, breaking changes, and best practices"
category: migration
doc_type: guide
status: active
version: "2.11.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - adk-2
  - migration
  - workflow-runtime
  - breaking-changes
  - graph-workflows
  - base-node
---

# Google ADK 2.0 Mimari Dönüşümü ve Geçiş (Migration) Kılavuzu

Resmi Dokümantasyon: [https://adk.dev/2.0/index.md](https://adk.dev/2.0/index.md)  
Genel Kullanıma Sunulma (GA): Python (Mayıs 2026), Go (Haziran 2026), TypeScript (Ağustos 2026).

---

## 1. Temel Mimari Paradigma Değişimi: Workflow Runtime

ADK 1.x sürümünde framework, **Hiyerarşik Ajan Yürütücüsü (Hierarchical Agent Executor)** olarak çalışmaktaydı (Kök ajan alt ajanları çağırır veya `SequentialAgent`, `ParallelAgent`, `LoopAgent` konteynerleri işletilirdi).

ADK 2.0 ile birlikte framework tamamen **Graf Tabanlı Yürütme Motoruna (Workflow Graph Engine)** dönüştürülmüştür:
* **`BaseAgent` -> `BaseNode`:** Ajanlar artık bağımsız çalıştırıcılar değil, graf motorunun birer düğümüdür (`BaseAgent extends BaseNode`).
* **Tek Tip Elemanlar:** Ajanlar (`Agent`), Araçlar (`Tools`) ve saf Python/Go/TS fonksiyonları graf içinde eşit statüde birer **Node (Düğüm)** olarak yürütülür.
* **Üç Temel 2.0 Deseni:**
  1. [**Graph-Based Workflows (`/graphs/`)**](graph-workflows.md): Deterministik yönlendirme, kenarlar (edges) ve yönlü graflar.
  2. [**Dynamic Workflows (`/graphs/dynamic/`)**](dynamic-workflows.md): Kod tabanlı dallanma, koşullu geçişler ve dinamik döngüler.
  3. [**Collaborative Workflows (`/workflows/collaboration/`)**](agent-team-patterns.md): Koordinatör ve uzman alt ajanların takım halinde çalışması.

```
       ADK 1.x (Hiyerarşik)                     ADK 2.0 (Graf Motoru)
       
        [ Root Agent ]                              [ Start Node ]
         /          \                                     │
   [ SubAgent A ]  [ SubAgent B ]              [ Deterministic Preprocess ]
                                                          │
                                                [ LLM Agent Node ]
                                                   /          \
                                       [ Tool Node A ]    [ Tool Node B ]
                                                   \          /
                                                [ Evaluator Node ]
```

---

## 2. ADK Python 1.x -> 2.0 Kırıcı Değişiklikler (Breaking Changes)

### A. Olay Şeması ve Veritabanı Uyumsuzluğu (`Event Schema`)
ADK 2.0, graf durumunu ve düğüm çıktılarını izlemek için `Event` nesnesine iki yeni alan eklemiştir:
* `node_info`: Olayı hangi düğümün fırlattığını belirten meta veri.
* `output`: Düğümün ürettiği genel veri çıktısı.

> [!WARNING]
> **Özel Oturum Depolama (Custom Session Storage) Tehlikesi:**
> Katı sütun yapısına sahip SQL/NoSQL veritabanı şemaları (örn. SQLAlchemy, PostgreSQL) 2.0 `Event` nesnesi yazılırken `insertion failure` veya ORM deserialize hatası verir.
> * **Çözüm:** Veritabanı tablonuza `node_info` ve `output` sütunlarını ekleyin veya oturum olaylarını doğrudan JSON blob olarak saklayın.

### B. Ajan Yürütme Metot Override'ları Devre Dışı (`BaseAgent to BaseNode`)
ADK 1.x'te `_run_async_impl()`, `generate_content()` veya `run()` metotlarını override ederek telemetri ya da özel durum mantığı enjekte eden kodlar:
* **ADK 2.0 graf motoru tarafından SESSİZCE YOK SAYILIR (silently ignored)!**
* **Çözüm:** Özel yürütme mantığını standart `BeforeAgentCallback` ve `AfterAgentCallback` arayüzlerine taşıyın.

### C. Doğrudan Olay Ekleme Yasağı (In-Place Mutation)
ADK 1.x'te yapılan `context.session.events.append(custom_event)` veya `enqueue_event` çağrıları:
* ADK 2.0 graf motorunun deterministik durum makinesini ve SSE streaming akışını bozar.
* **Çözüm:** Olayları manuel listeye eklemeyin; düğüm veya ajan içerisinden açıkça `yield` edin:
  ```python
  # ADK 2.0 Doğru Kullanım:
  yield Event(message="İşlem tamamlandı", node_info=...)
  ```

### D. Geniş Hata Yakalama ve Otomatik Retry Tuzağı (`except Exception`)
ADK 2.0, yerel otomatik retry (`RetryConfig(max_attempts=3)`) ve Human-in-the-Loop (HITL) duraklatma mekanizmalarına sahiptir.
* **Tuzak 1:** Tool fonksiyonları içinde geniş `except Exception:` bloğu bırakılırsa hata framework'ten gizlenir ve 2.0 otomatik retry motoru çalışmaz.
* **Tuzak 2:** Asla `except BaseException:` yakalanmamalıdır! Bu blok, framework'ün insan onayı beklerken fırlattığı `NodeInterruptedError` istisnasını yutar ve akışı kilitler.
* **Çözüm:** Standart hataların framework'e fırlatılmasına izin verin:
  ```python
  # RetryConfig ile güvenli retry
  from google.adk.workflows import RetryConfig
  
  node = MyNode(retry_config=RetryConfig(max_attempts=3))
  ```

---

## 3. ADK TypeScript 1.x -> 2.0 Değişiklikleri

### A. `InvocationContext.agent` Artık Opsiyoneldir (`undefined`)
Graf motorunda bir düğüm (Node) doğrudan çalıştırıldığında bir ajana bağlı olmak zorunda değildir. Bu nedenle `ctx.agent` tanımsız (`undefined`) olabilir.
```typescript
// ADK 1.x
const agentName = ctx.agent.name; // 2.0'da TypeError riski!

// ADK 2.0 - Ajan kendi içinde çalışırken:
import { requireAgent } from '@google/adk';
const agentName = requireAgent(ctx).name;

// ADK 2.0 - Düğüm veya callback dışındayken:
const agentName = ctx.agent?.name;
```

### B. Eski Ajan Konteynerleri Kullanımdan Kaldırıldı (Deprecated)
* `SequentialAgent`, `ParallelAgent`, `LoopAgent` sınıfları TypeScript 2.0'da **deprecated** edilmiştir ve konsola uyarı basar.
* **Çözüm:** Bu hiyerarşiler doğrudan [Graph Workflows](graph-workflows.md) API'sine taşınmalıdır.

---

## 4. ADK Go 1.x -> 2.0 Değişiklikleri

### A. Modül Import Yolu Değişimi
Go modül yolu v2 olarak güncellenmelidir:
* **Eski:** `google.golang.org/adk`
* **Yeni:** `google.golang.org/adk/v2` (`go get google.golang.org/adk/v2`)

### B. `session.NewEvent` Zorunlu Context Parametresi
Deterministik replay ve zaman kontrolü için `session.NewEvent` artık ilk parametre olarak `context.Context` bekler:
```go
// ADK 1.x (Kaldırıldı)
ev := session.NewEvent(ctx.InvocationID())

// ADK 2.0 (Doğru)
ev := session.NewEvent(ctx, ctx.InvocationID())
```

### C. Go Event Struct Alan Genişlemesi (5 Yeni Alan)
Katı veritabanı şemalarında güncellenmesi gereken Go alanları:
1. `IsolationScope string` (`isolationScope`): LLM prompt geçmişi görünürlüğünü sınırlar.
2. `Routes []string` (`Routes`): Koşullu kenar yönlendirme anahtarları.
3. `RequestedInput *RequestInput` (`RequestedInput`): HITL insan girdisi bekleme sinyali.
4. `Output any` (`Output`): Düğümün genel veri çıktısı.
5. `NodeInfo *NodeInfo` (`nodeInfo`): Düğüm meta verisi.

---

## 5. Eski Sürüme Sabitleme (Rollback / Pinning)

2.0'a geçişe hazır olmayan projeler için bağımlılık kilitleme:

* **Python:**
  ```bash
  pip install "google-adk~=1.0"
  ```
* **TypeScript:**
  ```bash
  npm install @google/adk@^1.6.0
  ```
* **Go:**
  ```bash
  go get google.golang.org/adk@v1
  ```

---

## 6. Özet Geçiş Kontrol Listesi (Checklist)

- [ ] Veritabanı Event şemasına `node_info` ve `output` alanları eklendi mi?
- [ ] Özel `_run_async_impl()` ve `run()` override'ları `BeforeAgentCallback`/`AfterAgentCallback` sınıflarına taşındı mı?
- [ ] Tool fonksiyonlarındaki kontrolsüz `except Exception:` ve `except BaseException:` blokları temizlendi mi?
- [ ] `context.session.events.append` kullanımları `yield Event(...)` ile değiştirildi mi?
- [ ] TypeScript projelerinde `requireAgent(ctx)` veya opsiyonel zincirleme (`ctx.agent?.name`) uygulandı mı?
- [ ] Go projelerinde `google.golang.org/adk/v2` ve `session.NewEvent(ctx, ...)` güncellendi mi?
