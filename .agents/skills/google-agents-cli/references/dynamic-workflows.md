---
title: "Dynamic Workflows"
description: "Programmatic code-level agent and node orchestration with control flow logic"
category: workflows
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - dynamic-workflows
  - programmatic
  - python
  - control-flow
  - workflows
---

# Google ADK Dinamik İş Akışları (`Dynamic Workflows`)

> [!NOTE]
> **Kapsamlı Mimari Kılavuzlar:** Sıralı, paralel, döngüsel ve iş birlikçi iş akışı desenleri için ana başvuru belgesi: [`adk-workflows-overview.md`](adk-workflows-overview.md); graf rotaları ve koşullu dallanmalar için [`graph-workflows.md`](graph-workflows.md).

ADK v2.0 içinde döngüler (`for`, `while`), karmaşık koşullar (`if/else`) ve özyinelemeli mantıklar için programatik dinamik akışlar kullanılır.

---

## 1. Temel Bileşenler

```python
from google.adk import Context, Workflow
from google.adk.workflow import node
from typing import Any
```

- **`@node` Dekoratörü:** Python fonksiyonlarını dinamik iş akışında çalışabilir düğümlere dönüştürür.
- **`ctx.run_node(node, node_input=...)`:** Orkestratör düğüm içinden alt düğümleri programatik olarak çağırır ve çıktısını döndürür.
- **`rerun_on_resume=True`:** HITL veya duraklatma sonrası orkestratörün baştan yeniden yürütülmesini sağlar. Tamamlanan alt düğümler otomatik kontrol noktalarından (checkpoint) okunur, tekrar çalıştırılmaz.

---

## 2. Kod Örneği: İteratif Döküman İnceleme Akışı

```python
@node(name="extract_text")
def extract_text(node_input: str) -> str:
    return f"Extracted: {node_input}"


@node(name="check_quality")
def check_quality(node_input: str) -> bool:
    return len(node_input) > 20


@node(rerun_on_resume=True)
async def iterative_review_workflow(ctx: Context, node_input: str) -> str:
    text = await ctx.run_node(extract_text, node_input=node_input)

    # Standart Python döngüsü ve dallanması
    is_valid = await ctx.run_node(check_quality, node_input=text)
    if not is_valid:
        return "Kalite kontrolünden geçemedi."

    return f"Başarılı: {text}"


root_agent = Workflow(
    name="dynamic_review_pipeline", edges=[("START", iterative_review_workflow)]
)
```
