---
title: "Agent Team Patterns"
description: "Hierarchical and collaborative multi-agent team patterns and runner lifecycle"
category: multi-agent
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - agent-team
  - coordinator
  - delegation
  - subagents
  - multi-agent
---

# Google ADK Çoklu Ajan Takımı (Agent Team) Referansı

> [!NOTE]
> **Kapsamlı Mimari Kılavuzlar:** Sıralı, paralel ve iş birlikçi çoklu ajan iş akışları için [`adk-workflows-overview.md`](adk-workflows-overview.md); yerel alt ajan vs. dağıtık ağ ajanları (A2A) mimari karar matrisi için [`adk-a2a-guide.md`](adk-a2a-guide.md) kılavuzunu inceleyiniz.

## 1. Koordinatör ve Alt Ajanlar (Delegation)
```python
from google.adk.agents import Agent

# Uzman Alt Ajan 1: Karşılama ve Nezaket
greeting_agent = Agent(
    name="greeting_agent",
    model="gemini-flash-latest",
    description="Handles greetings, pleasantries, and polite introductory interactions.",
    instruction="Politely greet the user and offer assistance.",
)

# Uzman Alt Ajan 2: Döküman / Veri Analizi
doc_agent = Agent(
    name="doc_analysis_agent",
    model="gemini-1.5-pro",
    description="Analyzes documents, executes semantic vector search, and extracts answers.",
    instruction="Analyze indexed documents to answer questions with verifiable citations.",
    tools=[search_documents, read_document_file],
)

# Ana Koordinatör (Root Agent)
root_agent = Agent(
    name="coordinator_agent",
    model="gemini-1.5-pro",
    description="Main coordinator delegating user requests to specialized agents.",
    instruction="Greet users or delegate document queries to doc_analysis_agent.",
    sub_agents=[greeting_agent, doc_agent],
)
```

## 2. Çoklu Model Entegrasyonu (LiteLLM)
```python
from google.adk.models.lite_llm import LiteLlm

# Farklı görev için farklı model seçimi (OpenAI, Claude vb.):
code_agent = Agent(
    name="code_evaluator",
    model=LiteLlm(model="openai/gpt-4o"),
    instruction="Evaluate code quality and security.",
)
```

## 3. Programatik Çalıştırma Yaşam Döngüsü (Runner & Session)
```python
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

session_service = InMemorySessionService()
session = await session_service.create_session("my_app", "user_1", "session_1")

runner = Runner(agent=root_agent, app_name="my_app", session_service=session_service)

content = types.Content(role="user", parts=[types.Part(text="Dökümanı özetle")])
async for event in runner.run_async(user_id="user_1", session_id="session_1", new_message=content):
    if event.is_final_response():
        print(event.content.parts[0].text)
```
