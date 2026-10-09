---
title: "Graph Workflows"
description: "Flexible graph-based workflows, conditional routing, and deterministic nodes in ADK v2.0"
category: workflows
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - graph-workflows
  - routes
  - branching
  - deterministic-nodes
  - workflows
---

# Google ADK v2.0 Graf Tabanlı İş Akışları (`Workflow`)

Google ADK v2.0 ile gelen `Workflow` sınıfı, deterministik Python mantığı ile LLM akıl yürütmesini tek bir yürütme grafında birleştirir.

## 1. Temel Bileşenler ve Importlar

```python
from google.adk import Agent, Workflow, Event
from pydantic import BaseModel
```

- **`Workflow`**: Düğümler ve kenarlar (edges) üzerinden süreci yöneten orkestratör sınıfıdır.
- **`Agent`**: Graf içinde doğal dil işleme, karar alma ve araç çağırma adımlarını yürüten LLM düğümü.
- **Saf Python Fonksiyonları**: LLM çağırmaya gerek olmayan adımlarda (veri tabanı sorgusu, metin temizleme, matematiksel hesaplama) sıfır gecikme ve maliyetle doğrudan düğüm olarak kullanılır.
- **`Event`**: Akışın tamamlandığını veya özel bir sistem durumunu bildiren olay nesnesi (`Event(message=...)`).

---

## 2. Düğümler Arası Otomatik Veri İletimi

Düğümler birbirine doğrudan veri aktarır. Bir önceki düğümün `return` değeri, bir sonraki düğümün `node_input` parametresine otomatik olarak verilir. Oturum durumuna (`session.state`) manuel veri yazıp okuma ihtiyacı kalkar.

### Tip Güvenlikli Veri Sözleşmesi (Pydantic):
```python
class ParsedDocument(BaseModel):
    document_id: str
    cleaned_text: str
    word_count: int


def preprocess_document(node_input: str) -> ParsedDocument:
    """Belgeyi temizleyen ve yapılandıran saf Python fonksiyon düğümü."""
    text = node_input.strip()
    return ParsedDocument(
        document_id="doc_101", cleaned_text=text, word_count=len(text.split())
    )


doc_summary_agent = Agent(
    name="doc_summary_agent",
    model="gemini-1.5-pro",
    input_schema=ParsedDocument,  # Önceki düğümün döndürdüğü Pydantic modelini bekler
    instruction="""Aşağıdaki dokümanı özetle:
    ID: {ParsedDocument.document_id}
    Metin: {ParsedDocument.cleaned_text}""",
)
```

---

## 3. Akış Kenarları (`edges`) ve Giriş Noktası

Graf akışı `"START"` anahtar kelimesi ile başlar ve tuple zincirleriyle tanımlanır.

```python
def notify_completion(node_input: str):
    """İş akışının tamamlandığını bildiren son düğüm."""
    return Event(message=f"Rapor:\n{node_input}\n\n[DÖKÜMAN İŞLEME TAMAMLANDI]")


root_agent = Workflow(
    name="document_processing_workflow",
    edges=[
        (
            "START",
            preprocess_document,  # Saf kod düğümü
            doc_summary_agent,  # LLM ajanı düğümü
            notify_completion,  # Event düğümü
        )
    ],
)
```

---

## 4. Ne Zaman Kullanılmalı?

- **Deterministik Adımlar Varsa:** Sıralı veri temizleme, API sorgulama, formatlama gibi adımlar LLM'e yaptırılmamalı; saf Python fonksiyon düğümleri olarak grafa eklenmelidir.
- **Katı Süreç Kontrolü:** Modelin kendi kendine halüsinatif rota çizmesi istenmeyen, adımları katı kurallara bağlı iş akışlarında `Workflow` tercih edilir.

> [!TIP]
> **Canlı Ses ve Görüntü Ajanları ile Kullanım (`run_live`):** ADK 2.0 ile graf iş akışları canlı iki yönlü ses hatlarında (`runner.run_live()`) kesintisiz tek döngü ve tek WebSocket bağlantısıyla çalıştırılabilir. Düğümlerde `mode='task'` zorunluluğu ve kesintisiz el sıkışma mimarisi için bkz: [`adk-live-guide.md`](adk-live-guide.md#11-canlı-ajanlar-için-graf-iş-akışları-ve-devir-mimarisi-graph-workflows--handoffs---adk-20).

