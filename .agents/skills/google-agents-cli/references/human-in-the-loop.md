---
title: "Human in the Loop (HITL)"
description: "Interrupting workflows for user input, external approval tools, and policy engines"
category: workflows
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - human-in-the-loop
  - policy-engine
  - workflows
---

# Google ADK Graf Akışlarında İnsan Onayı ve Müdahalesi (HITL)

> [!NOTE]
> **Kapsamlı Mimari Kılavuzlar:** Araç seviyesinde insan onayı mekanizması (`Tool Confirmation`) için [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md); graf rotaları ve durum duraklatma için [`graph-workflows.md`](graph-workflows.md) kılavuzlarını inceleyiniz.

ADK v2.0 içinde deterministik insan müdahalesi (onaylama, veri girişi, karar alma), LLM modeline ihtiyaç duymaksızın doğrudan graf düğümü seviyesinde **`RequestInput`** ile sağlanır.

---

## 1. Temel Mantık ve İçe Aktarma

```python
from google.adk.events import RequestInput
from google.adk import Workflow, Agent
from pydantic import BaseModel, Field
```

- **Model Bağımsız:** Düğüm, bir LLM çağrısı yapmadan doğrudan akışı duraklatır (pause).
- **Otomatik Devam:** Kullanıcı arayüz veya CLI üzerinden yanıt verdiğinde akış devam eder (resume) ve kullanıcının yanıtı doğrudan sıradaki düğümün `node_input` parametresine iletilir.

---

## 2. `RequestInput` Parametreleri

| Parametre | Tip | Açıklama |
| :--- | :--- | :--- |
| `message` | `str` | Kullanıcıya gösterilecek soru veya onay metni. |
| `payload` | `dict` (opsiyonel) | Arayüzün zengin önizleme veya bağlam çizmesi için gönderilen veri sözlüğü. |
| `response_schema` | `Type[BaseModel]` (opsiyonel) | Kullanıcının vereceği yanıtın uymak zorunda olduğu Pydantic model şeması. |

---

## 3. Örnek: Hassas Döküman İşleme ve İnsan Onayı Akışı

```python
class ApprovalDecision(BaseModel):
    is_approved: bool = Field(description="İşlemin onaylanıp onaylanmadığı")
    rejection_reason: str = Field(
        default="", description="Reddedildiyse gerekçesi"
    )


def ask_human_approval(node_input: dict):
    """Kullanıcıdan onay isteyen HITL düğümü."""
    doc_id = node_input.get("doc_id")
    summary = node_input.get("summary")

    # Akış burada duraklatılır
    yield RequestInput(
        message=f"{doc_id} dökümanı için hazırlanan özeti onaylıyor musunuz?",
        payload={"doc_id": doc_id, "summary_preview": summary},
        response_schema=ApprovalDecision,  # Form yanıtı bu şemaya uymalıdır
    )


def finalize_processing(node_input: ApprovalDecision):
    """Kullanıcı onayından sonra çalışan düğüm."""
    if node_input.is_approved:
        return {"status": "success", "message": "Döküman onaylandı ve arşivlendi."}
    return {
        "status": "rejected",
        "message": f"Döküman reddedildi: {node_input.rejection_reason}",
    }


root_agent = Workflow(
    name="document_approval_workflow",
    edges=[("START", prepare_document_node, ask_human_approval, finalize_processing)],
)
```

---

## 4. Kritik Kurallar
- **Hassas İşlemler:** Veritabanı yazma, dosya silme veya dış dünyaya e-posta gönderme gibi geri döndürülemez adımlardan önce mutlaka `RequestInput` kullanılmalıdır.
- **Şema Doğrulama:** Serbest metin yerine `response_schema` kullanılarak kullanıcıdan form formatında doğrulanmış veri alınması sağlanmalıdır.
