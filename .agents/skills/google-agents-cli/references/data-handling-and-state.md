---
title: "Data Handling & State Management"
description: "Managing session state, schema validation, and data transfer across agent nodes"
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - data-handling
  - state
  - sessions
  - schemas
  - architecture
---

# Google ADK Veri Taşıma ve Durum Yönetimi (Data Handling & State)

> [!NOTE]
> **Kapsamlı Mimari Kılavuzlar:** Oturum yaşam döngüsü, veritabanı kilitleme ve state prefix'leri için [`adk-sessions-guide.md`](adk-sessions-guide.md); olay sinyal protokolü için [`adk-events-guide.md`](adk-events-guide.md) kılavuzlarını inceleyiniz.

ADK v2.0 içinde ajanlar ve graf düğümleri arasında veri iletimi iki ana yöntemle gerçekleştirilir: **Olaylar (`Events`)** ve **Oturum Durumu (`Session State`)**.

---

## 1. Graf Düğümleri Arasında Olay Tabanlı İletim (`Event`)

Graf tabanlı iş akışlarında (`Workflow`), düğümler ardışık adımlara `Event` nesneleri aracılığıyla veri aktarır.

### Temel Alanlar:
- **`output`**: Sıradaki düğüme iletilecek nesnedir. Sıradaki düğüm bu veriyi `node_input` olarak doğrudan teslim alır.
- **`message`**: Doğrudan kullanıcıya veya sohbet arayüzüne gönderilecek yanıttır. Sonraki düğüme girdi olarak aktarılmaz.
- **`state`**: `session.state` içine kalıcı olarak yazılacak sözlük (`dict`) verisidir.

```python
from google.adk import Event


def transform_node(node_input: str):
    processed = node_input.strip().upper()

    # Sıradaki düğüme aktarılacak veri
    return Event(output=processed)


def final_response_node(node_input: str):
    # Kullanıcıya dönecek nihai yanıt
    return Event(message=f"İşlem sonucu: {node_input}")
```

> [!CAUTION]
> **Tekil `Event.output` Kuralı:** Bir düğüm tek bir çalıştırmada yalnızca BİR adet `Event(output=...)` yayınlayabilir. Birden fazla `yield Event(output=...)` yapılması çalışma zamanı hatasına yol açar veya son değer öncekini ezer. İlerleme mesajları için `Event(message=...)` veya `Event(content=...)` kullanılmalıdır.

---

## 2. Oturum Durumu Kapsamı ve Önekler (State Key Prefixes)

`session.state` anahtarlarında kullanılan önekler, verinin yaşam döngüsünü ve görünürlüğünü belirler:

| Önek | Kapsam ve Yaşam Döngüsü | Kullanım Amacı |
| :--- | :--- | :--- |
| `temp:` | Mevcut çağrı (turn) bittiğinde otomatik temizlenir. | Ara hesaplamalar, geçici bayraklar |
| `user:` | Kullanıcıya bağlıdır; kullanıcının tüm oturumlarında kalıcıdır. | Kullanıcı tercihleri, kimlik bilgileri |
| `app:` | Uygulama genelidir; tüm kullanıcılar ve oturumlarda ortaktır. | Paylaşılan önbellek, sistem yapılandırması |
| *(yok)* | Yalnızca ilgili oturum (session) boyunca kalıcıdır. | Konuşma bağlamı, oturum geçmişi |

```python
# Araç içinde context.state kullanımı örneği
def save_temp_calculation(ctx: ToolContext, value: float):
    # Bu veri mevcut tur tamamlandığında bellekten silinir
    ctx.state["temp:calc_cache"] = value
    # Bu veri oturum boyunca saklanır
    ctx.state["last_result"] = value
```

---

## 3. Hazır Şablon Ajanlarda Veri İletimi (`output_key`)

`Workflow` (graf) yerine hazır şablon ajanlar (`SequentialAgent`, `ParallelAgent`) kullanıldığında, ajanlar arası veri iletimi oturum durumu üzerinden `output_key` ile sağlanır:

```python
from google.adk.agents import Agent, SequentialAgent

# 1. Adım: Çıktısını state["doc_summary"] anahtarına yazar
summarizer = Agent(
    name="summarizer",
    model="gemini-1.5-pro",
    instruction="Belgeyi özetle.",
    output_key="doc_summary",  # Nihai yanıt state["doc_summary"] içine kaydedilir
)

# 2. Adım: Önceki ajanın çıktısını {doc_summary} şablonuyla okur
evaluator = Agent(
    name="evaluator",
    model="gemini-1.5-pro",
    instruction="Aşağıdaki özeti kalite açısından değerlendir:\n{doc_summary}",
)

root_agent = SequentialAgent(
    name="doc_pipeline", sub_agents=[summarizer, evaluator]
)
```
