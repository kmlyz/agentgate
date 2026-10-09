---
title: "Migration to ADK"
description: "Migrating existing agent frameworks (LangChain, CrewAI, AutoGen) to Google ADK"
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - migration
  - langchain
  - crewai
  - autogen
  - architecture
---

# Mevcut Ajan Yapılarını ADK'ya Dönüştürme (Migration) Kılavuzu

Geleneksel ajan bileşenlerinin yerel Google ADK karşılıkları:

## 1. Mimari Eşleme Matrisi

| Geleneksel / Mevcut Model | ADK Karşılığı | Açıklama & Kod Deseni |
| :--- | :--- | :--- |
| **Özel Araç Şemaları / Wrapper'lar** | Saf Python Fonksiyonu veya `FunctionTool` | Tip ipucu ve docstring içeren standart fonksiyonlar. ADK şemayı otomatik çıkarır. |
| **Özel Ajan Döngüsü / Runner** | `google.adk.agents.Agent` | Model, talimat, araçlar ve alt ajanları deklaratif tanımlayan temel ajan nesnesi (`root_agent`). |
| **Bellek ve Retrieval (Vektör vb.)** | `BaseMemoryService` & Retrieval Tools | `InMemoryMemoryService`, `VertexAiRagMemoryService` veya özel döküman arama fonksiyonları. |
| **Durum (State) & Scratchpad** | `ToolContext` üzerinden `session.state` | Fonksiyon parametresine `context: ToolContext` eklenerek oturum durumuna (`context.state`) erişilir ve mutasyona uğratılır. |
| **Çoklu Ajan Handoffs** | `Agent(sub_agents=[...])` | Koordinatör ajanın spesifik alt ajanlara hiyerarşik görev devri yapması. |
| **Graf Tabanlı İş Akışları** | `google.adk.workflow.Workflow` | Koşullu yönlendirme, döngüler ve paralel dallanmalar içeren açık iş akışı grafları. |
| **Uzak Ajan İletişimi** | A2A Protocol | HTTP üzerinden ajanlar arası standart iletişim protokolü. |

## 2. Kritik Kod Örneği (ToolContext & State)
```python
from google.adk.agents import Agent
from google.adk.tools import ToolContext

def process_doc(doc_id: str, context: ToolContext) -> str:
    """Dökümanı işler ve oturum durumuna kaydeder."""
    context.state["last_doc"] = doc_id
    return f"{doc_id} başarıyla işlendi."
```

## 3. Doğrulama ve Test
```bash
agents-cli eval run     # Değerlendirme setlerini çalıştırır
agents-cli playground   # Hot-reload destekli UI ile test eder
```
