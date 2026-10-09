---
title: "ADK Documentation Index & Knowledge Map"
description: "Google ADK official documentation index with direct local guide references and upstream raw markdown links."
category: architecture
doc_type: reference
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - documentation
  - index
  - knowledge-map
---

# Google ADK Resmi Dokümantasyon İndeks Haritası (Knowledge Map)

Bu fihrist; Google ADK'nın tüm resmi konularının hem upstream ham markdown bağlantılarını (`https://adk.dev/`) hem de yerel kütüphanemizde inşa edilmiş derinlemesine teknik mimari kılavuzlarını (`references/`) içeren ana navigasyon haritasıdır.

> [!IMPORTANT]
> **Aktif Kalınan Durak (Active Checkpoint):** [`https://adk.dev/live/`](https://adk.dev/live/) (ADK Live - Gerçek Zamanlı Çift Yönlü Ses/Görüntü Akış Protokolü)

---

## 1. Temel Ajanlar ve Yapılandırma
- [About ADK (Temel Mimari ve Primitifler)](https://adk.dev/get-started/about/index.md) — Yerel Kılavuz: [`llm-agent-deep-dive.md`](llm-agent-deep-dive.md)
- [Get Started](https://adk.dev/get-started/index.md) — Yerel Kılavuz: [`llm-agent-deep-dive.md`](llm-agent-deep-dive.md)
- [Simple Agents (LLM Agents)](https://adk.dev/agents/llm-agents/index.md) — Yerel Kılavuz: [`llm-agent-deep-dive.md`](llm-agent-deep-dive.md)
- [Agent Config](https://adk.dev/agents/config/index.md) — Yerel Kılavuz: [`agent-config-yaml.md`](agent-config-yaml.md)
- [Agent Routing](https://adk.dev/agents/routing/index.md) — Yerel Kılavuz: [`model-routing-routed-llm.md`](model-routing-routed-llm.md)
- [Artifacts (BaseArtifactService, GCS & LoadArtifactsTool)](https://adk.dev/artifacts/index.md) — Yerel Kılavuz: [`adk-artifacts-guide.md`](adk-artifacts-guide.md)
- [App Workflow Management Class (App, Lifecycle, Plugins, Context Caching/Compaction)](https://adk.dev/apps/index.md) — Yerel Kılavuz: [`adk-apps-guide.md`](adk-apps-guide.md)
- [Callbacks (Execution Interception, State Management & Guardrails)](https://adk.dev/callbacks/index.md) — Yerel Kılavuz: [`adk-callbacks-guide.md`](adk-callbacks-guide.md)
- [Types of Callbacks (Kwarg Rules, Error Hooks & Chaining)](https://adk.dev/callbacks/types-of-callbacks/index.md) — Yerel Kılavuz: [`adk-callbacks-guide.md`](adk-callbacks-guide.md)
- [Callbacks Design Patterns & Best Practices (8 Patterns, State Deltas & Artifacts)](https://adk.dev/callbacks/design-patterns-and-best-practices/index.md) — Yerel Kılavuz: [`adk-callbacks-guide.md`](adk-callbacks-guide.md)
- [Plugins (Global Workflow Interception, Guardrails & Prebuilt Extensions)](https://adk.dev/plugins/index.md) — Yerel Kılavuz: [`adk-plugins-guide.md`](adk-plugins-guide.md)
- [Agent Context (InvocationContext, ReadonlyContext, Context & ToolContext)](https://adk.dev/context/index.md) — Yerel Kılavuz: [`adk-context-guide.md`](adk-context-guide.md)
- [Context Compaction (Token-Based & Sliding-Window Event Summarization)](https://adk.dev/context/compaction/index.md) — Yerel Kılavuz: [`adk-context-compaction-guide.md`](adk-context-compaction-guide.md)
- [Context Caching with Gemini (ContextCacheConfig & Token/Latency Optimization)](https://adk.dev/context/caching/index.md) — Yerel Kılavuz: [`adk-context-caching-guide.md`](adk-context-caching-guide.md)
- [Conversational Context (Session, State & Memory Overview)](https://adk.dev/sessions/index.md) — Yerel Kılavuz: [`adk-sessions-guide.md`](adk-sessions-guide.md)
- [Session Tracking & Storage (Lifecycle, DB Locking & Vertex AI)](https://adk.dev/sessions/session/index.md) — Yerel Kılavuz: [`adk-sessions-guide.md`](adk-sessions-guide.md)
- [Session Rewind (State Rollback & Alternative Paths)](https://adk.dev/sessions/session/rewind/index.md) — Yerel Kılavuz: [`adk-sessions-guide.md`](adk-sessions-guide.md)
- [Session Database Schema Migration (v0 Pickle to v1 JSON)](https://adk.dev/sessions/session/migrate/index.md) — Yerel Kılavuz: [`adk-sessions-guide.md`](adk-sessions-guide.md)
- [State: The Session's Scratchpad (Prefixes, Templating & Modifying)](https://adk.dev/sessions/state/index.md) — Yerel Kılavuz: [`adk-sessions-guide.md`](adk-sessions-guide.md) & [`data-handling-and-state.md`](data-handling-and-state.md)
- [Events: The Communication & State Signal Protocol](https://adk.dev/events/index.md) — Yerel Kılavuz: [`adk-events-guide.md`](adk-events-guide.md)
- [Memory: Long-Term Knowledge with MemoryService (Memory Bank & RAG)](https://adk.dev/sessions/memory/index.md) — Yerel Kılavuz: [`adk-memory-guide.md`](adk-memory-guide.md)

---

## 2. Şablon İş Akışları (Template Workflows)
- [Sequential Workflow (Sıralı Ajanlar)](https://adk.dev/agents/workflow-agents/sequential-agents/index.md) — Yerel Kılavuz: [`adk-workflows-overview.md`](adk-workflows-overview.md)
- [Parallel Workflow (Paralel Ajanlar)](https://adk.dev/agents/workflow-agents/parallel-agents/index.md) — Yerel Kılavuz: [`adk-workflows-overview.md`](adk-workflows-overview.md)
- [Loop Workflow (Döngüsel Ajanlar)](https://adk.dev/agents/workflow-agents/loop-agents/index.md) — Yerel Kılavuz: [`adk-workflows-overview.md`](adk-workflows-overview.md)

---

## 3. Graf Tabanlı Gelişmiş İş Akışları (Graph Workflows)
- [Graph Workflows Overview](https://adk.dev/graphs/index.md) — Yerel Kılavuz: [`graph-workflows.md`](graph-workflows.md)
- [Graph Routes (Koşullu Rotalar)](https://adk.dev/graphs/routes/index.md) — Yerel Kılavuz: [`graph-workflows.md`](graph-workflows.md)
- [Data Handling (Veri Taşıma)](https://adk.dev/graphs/data-handling/index.md) — Yerel Kılavuz: [`data-handling-and-state.md`](data-handling-and-state.md)
- [Human Input / HITL (İnsan Onayı)](https://adk.dev/graphs/human-input/index.md) — Yerel Kılavuz: [`human-in-the-loop.md`](human-in-the-loop.md)
- [Dynamic Workflows](https://adk.dev/graphs/dynamic/index.md) — Yerel Kılavuz: [`dynamic-workflows.md`](dynamic-workflows.md)

---

## 4. Çoklu Ajan İş Birlikleri ve Protokoller (Multi-Agent & Protocols)
- [Workflows Overview (Multi-Agent, Multi-Node)](https://adk.dev/workflows/index.md) — Yerel Kılavuz: [`adk-workflows-overview.md`](adk-workflows-overview.md)
- [Collaborative Workflows](https://adk.dev/workflows/collaboration/index.md) — Yerel Kılavuz: [`adk-workflows-overview.md`](adk-workflows-overview.md)
- [Workflow Patterns](https://adk.dev/workflows/patterns/index.md) — Yerel Kılavuz: [`agent-team-patterns.md`](agent-team-patterns.md)

### Agent2Agent (A2A) Protokol Ailesi (Tamamı `adk-a2a-guide.md` İçindedir)
- [A2A Overview & Core Capabilities](https://adk.dev/a2a/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md)
- [A2A Introduction & Local vs Remote Decision Matrix](https://adk.dev/a2a/intro/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 1)
- [A2A Quickstart (Exposing) - Python & uvicorn](https://adk.dev/a2a/quickstart-exposing/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 4)
- [A2A Quickstart (Consuming) - Python & RemoteA2aAgent](https://adk.dev/a2a/quickstart-consuming/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 5)
- [A2A Extension (V2 Implementation & Streaming Reliability)](https://adk.dev/a2a/a2a-extension/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 6)
- [A2A Custom Converters & Interceptors](https://adk.dev/a2a/quickstart-exposing/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 7)
- [A2A Quickstart (Exposing) - Go](https://adk.dev/a2a/quickstart-exposing-go/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 8.1.A)
- [A2A Quickstart (Consuming) - Go](https://adk.dev/a2a/quickstart-consuming-go/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 8.1.B)
- [A2A Quickstart (Exposing) - Java & Quarkus](https://adk.dev/a2a/quickstart-exposing-java/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 8.2.A)
- [A2A Quickstart (Consuming) - Java](https://adk.dev/a2a/quickstart-consuming-java/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 8.2.B)
- [A2A Quickstart (Consuming) - Kotlin Coroutines](https://adk.dev/a2a/quickstart-consuming-kotlin/index.md) — Yerel Kılavuz: [`adk-a2a-guide.md`](adk-a2a-guide.md) (Bölüm 8.3)

### Canlı Ses ve Görüntü Protokolü (Live & Voice Agents - Tamamı `adk-live-guide.md` İçindedir)
- [Live Overview & Core Concepts](https://adk.dev/live/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 1)
- [Live Models & Backends (Gemini 2.5 vs 3.1 Flash Live)](https://adk.dev/live/models/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 1.1)
- [Live Get Started Overview](https://adk.dev/live/get-started/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 2)
- [Live Get Started - Streaming Python](https://adk.dev/live/get-started/streaming-python/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 2.1)
- [Live Get Started - Streaming Java (Dev UI & Native LiveAudioRun)](https://adk.dev/live/get-started/streaming-java/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 2.2 & 2.3)
- [Live Sessions, Scopes & Lifecycle](https://adk.dev/live/sessions/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 3 & 7)
- [Live Media Contract (16kHz Audio In, 24kHz Audio Out, 1 FPS Video)](https://adk.dev/live/audio-video/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 4.3)
- [Live Events, UI State Machine & Error Handling](https://adk.dev/live/events/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 5.1 - 5.5)
- [Live Tools, Streaming Tools & Video Streams](https://adk.dev/live/tools/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 6.1 - 6.6)
- [Live Configuration (RunConfig, Speech, VAD, S2S)](https://adk.dev/live/configuration/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 7.1 - 7.10)
- [Live Guardrails & Multi-Layer Safety](https://adk.dev/live/guardrails/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 8.1 - 8.7)
- [Live Production FastAPI & WebSocket Server (Custom Server)](https://adk.dev/live/custom-server/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 9.1 - 9.7)
- [Live Agent Evaluation & Audio User Simulation](https://adk.dev/live/evaluation/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 10) & [`adk-evaluation-guide.md`](adk-evaluation-guide.md) (Bölüm 8)
- [Live Graph Workflows & Handoffs](https://adk.dev/live/workflows/index.md) — Yerel Kılavuz: [`adk-live-guide.md`](adk-live-guide.md) (Bölüm 11)

---

## 5. Modeller ve Entegrasyonlar
### Google & Enterprise Modeller
- [Gemini Models](https://adk.dev/agents/models/google-gemini/index.md) — Yerel Kılavuz: [`gemini-models-and-interactions.md`](gemini-models-and-interactions.md)
- [Google Gemma Models](https://adk.dev/agents/models/google-gemma/index.md) — Yerel Kılavuz: [`gemma-models-and-mcp.md`](gemma-models-and-mcp.md)
- [Agent Platform Hosted & Open Models](https://adk.dev/agents/models/agent-platform/index.md) — Yerel Kılavuz: [`agent-platform-hosted-models.md`](agent-platform-hosted-models.md)
- [Deferred Scheduling](https://adk.dev/agents/models/google-gemini/deferred-schedule/index.md) — Yerel Kılavuz: [`deferred-scheduling-guide.md`](deferred-scheduling-guide.md)
- [Apigee AI Gateway](https://adk.dev/agents/models/apigee/index.md) — Yerel Kılavuz: [`apigee-ai-gateway.md`](apigee-ai-gateway.md)

### Harici & Yerel Model Sağlayıcıları
- [Anthropic Claude Models](https://adk.dev/agents/models/anthropic/index.md) — Yerel Kılavuz: [`anthropic-claude-and-agent-platform.md`](anthropic-claude-and-agent-platform.md)
- [OpenAI Models](https://adk.dev/agents/models/openai/index.md) — Yerel Kılavuz: [`openai-models-integration.md`](openai-models-integration.md)
- [Ollama Models (Yerel Modeller)](https://adk.dev/agents/models/ollama/index.md) — Yerel Kılavuz: [`ollama-local-models.md`](ollama-local-models.md)
- [vLLM Models (Öz Barındırılan)](https://adk.dev/agents/models/vllm/index.md) — Yerel Kılavuz: [`vllm-model-hosting.md`](vllm-model-hosting.md)
- [LiteRT-LM On-Device Models](https://adk.dev/agents/models/litert-lm/index.md) — Yerel Kılavuz: [`litert-lm-edge-models.md`](litert-lm-edge-models.md)
- [LiteLLM Multi-Model Gateway](https://adk.dev/agents/models/litellm/index.md) — Yerel Kılavuz: [`litellm-integration-guide.md`](litellm-integration-guide.md)
- [Model Routing (RoutedLlm)](https://adk.dev/agents/models/routing/index.md) — Yerel Kılavuz: [`model-routing-routed-llm.md`](model-routing-routed-llm.md)

### Araçlar ve Protokoller (Tools & MCP)
- [Tools & Integrations (106 Entegrasyonluk Ana Link Fihristi)](https://adk.dev/integrations/index.md) — Yerel Kılavuz: [`adk-integrations-catalog.md`](adk-integrations-catalog.md) & [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md)
- [Custom Tools & ToolContext](https://adk.dev/tools-custom/index.md) — Yerel Kılavuz: [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md)
- [Function Tools (Long-Running & AgentTool)](https://adk.dev/tools-custom/function-tools/index.md) — Yerel Kılavuz: [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md) & [`multi-tool-patterns.md`](multi-tool-patterns.md)
- [Tool Performance & Parallel Execution](https://adk.dev/tools-custom/performance/index.md) — Yerel Kılavuz: [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md)
- [Tool Confirmation (HITL)](https://adk.dev/tools-custom/confirmation/index.md) — Yerel Kılavuz: [`adk-custom-tools-guide.md`](adk-custom-tools-guide.md) & [`human-in-the-loop.md`](human-in-the-loop.md)
- [Model Context Protocol (MCP Tools & Server)](https://adk.dev/tools-custom/mcp-tools/index.md) — Yerel Kılavuz: [`adk-mcp-guide.md`](adk-mcp-guide.md)
- [Advanced MCP Configuration](https://adk.dev/tools-custom/mcp-tools/advanced/index.md) — Yerel Kılavuz: [`adk-mcp-guide.md`](adk-mcp-guide.md)
- [Deploy Agents with MCP Tools](https://adk.dev/tools-custom/mcp-tools/deployment/index.md) — Yerel Kılavuz: [`adk-mcp-guide.md`](adk-mcp-guide.md)
- [Configure ADK Agents as MCP Servers](https://adk.dev/tools-custom/mcp-tools/agent-as-server/index.md) — Yerel Kılavuz: [`adk-mcp-guide.md`](adk-mcp-guide.md)
- [Manage MCP with Sub-Agents](https://adk.dev/tools-custom/mcp-tools/agent-managed/index.md) — Yerel Kılavuz: [`adk-mcp-guide.md`](adk-mcp-guide.md)
- [Authentication for Tools & GCP](https://adk.dev/tools-custom/authentication/index.md) — Yerel Kılavuz: [`adk-auth-guide.md`](adk-auth-guide.md) & [`gcp-agent-platform-auth.md`](gcp-agent-platform-auth.md)
- [Skills for ADK Agents (SkillToolset & agentskills.io)](https://adk.dev/skills/index.md) — Yerel Kılavuz: [`adk-skills-guide.md`](adk-skills-guide.md)

### Veri Temellendirme ve Arama (Grounding & Search)
- [Grounding Agents with Data (Genel Bakış)](https://adk.dev/grounding/index.md) — Yerel Kılavuz: [`adk-grounding-guide.md`](adk-grounding-guide.md) (Bölüm 1)
- [Google Search Grounding (Web Temellendirme)](https://adk.dev/grounding/google_search_grounding/index.md) — Yerel Kılavuz: [`adk-grounding-guide.md`](adk-grounding-guide.md) (Bölüm 2 & 4)
- [Grounding with Search (Kurumsal Agent Search)](https://adk.dev/grounding/grounding_with_search/index.md) — Yerel Kılavuz: [`adk-grounding-guide.md`](adk-grounding-guide.md) (Bölüm 3 & 4)
- [Agentic RAG & Deep Search Architecture](https://adk.dev/grounding/index.md) — Yerel Kılavuz: [`adk-grounding-guide.md`](adk-grounding-guide.md) (Bölüm 5)

---

## 6. Agent Runtime (Çalışma Zamanı ve Yürütme Araçları)
- [Agent Runtime Genel Bakış](https://adk.dev/runtime/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Dev UI (Web Arayüzü)](https://adk.dev/runtime/web-interface/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Command Line (CLI)](https://adk.dev/runtime/command-line/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [REST API Server](https://adk.dev/runtime/api-server/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Runtime Event Loop](https://adk.dev/runtime/event-loop/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Runtime Config (RunConfig)](https://adk.dev/runtime/runconfig/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Cancel Agent Runs](https://adk.dev/runtime/cancel/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Resume Stopped Agents](https://adk.dev/runtime/resume/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)
- [Ambient Agents](https://adk.dev/runtime/ambient-agents/index.md) — Yerel Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)

---

## 7. Dağıtım ve Üretim Ortamları (Deployment & Production)
- [Deploying Your Agent Genel Bakış](https://adk.dev/deploy/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Cloud Run Dağıtımı](https://adk.dev/deploy/cloud-run/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Deploy to Agent Runtime](https://adk.dev/deploy/agent-runtime/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Agents CLI ile Hızlandırılmış Dağıtım](https://adk.dev/deploy/agent-runtime/agents-cli/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Standard Deployment](https://adk.dev/deploy/agent-runtime/deploy/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Test Deployed Agents](https://adk.dev/deploy/agent-runtime/test/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)
- [Google Kubernetes Engine (GKE)](https://adk.dev/deploy/gke/index.md) — Yerel Kılavuz: [`adk-deployment-guide.md`](adk-deployment-guide.md)

---

## 8. Gözlemlenebilirlik (Observability)
- [Observability for Agents Genel Bakış](https://adk.dev/observability/index.md) — Yerel Kılavuz: [`adk-observability-guide.md`](adk-observability-guide.md)
- [Logging (Yapılandırılmış Loglama)](https://adk.dev/observability/logging/index.md) — Yerel Kılavuz: [`adk-observability-guide.md`](adk-observability-guide.md)
- [Metrics (Metrikler)](https://adk.dev/observability/metrics/index.md) — Yerel Kılavuz: [`adk-observability-guide.md`](adk-observability-guide.md)
- [Traces (OpenTelemetry Dağıtık İzleme)](https://adk.dev/observability/traces/index.md) — Yerel Kılavuz: [`adk-observability-guide.md`](adk-observability-guide.md)

---

## 9. Değerlendirme ve Test (Evaluation & Conformance)
- [Why Evaluate Agents Genel Bakış](https://adk.dev/evaluate/index.md) — Yerel Kılavuz: [`adk-evaluation-guide.md`](adk-evaluation-guide.md)
- [Evaluation Criteria (Kriterler)](https://adk.dev/evaluate/criteria/index.md) — Yerel Kılavuz: [`adk-evaluation-guide.md`](adk-evaluation-guide.md)
- [User Simulation (Kullanıcı Simülasyonu)](https://adk.dev/evaluate/user-sim/index.md) — Yerel Kılavuz: [`adk-evaluation-guide.md`](adk-evaluation-guide.md)
- [Environment Simulation (Ortam Simülasyonu)](https://adk.dev/evaluate/environment_simulation/index.md) — Yerel Kılavuz: [`adk-evaluation-guide.md`](adk-evaluation-guide.md)
- [Custom Metrics (Özel Metrikler)](https://adk.dev/evaluate/custom_metrics/index.md) — Yerel Kılavuz: [`adk-evaluation-guide.md`](adk-evaluation-guide.md)

---

## 10. Ajan Optimizasyonu (Optimization)
- [Optimize Agents Genel Bakış](https://adk.dev/optimize/index.md) — Yerel Kılavuz: [`adk-optimization-guide.md`](adk-optimization-guide.md)

---

## 11. Güvenlik ve Emniyet (Safety & Security)
- [Safety and Security for AI Agents Genel Bakış](https://adk.dev/safety/index.md) — Yerel Kılavuz: [`adk-safety-security-guide.md`](adk-safety-security-guide.md)

---

## 12. Geçiş ve Gelişmiş Mimari Desenler (Migration & Patterns)
- [ADK 2.0 Welcome & Migration Guide (1.x -> 2.0 Dönüşümü)](https://adk.dev/2.0/index.md) — Yerel Kılavuz: [`adk-2-migration-guide.md`](adk-2-migration-guide.md)
- [Multi-Language Setup (Python, Go, Java, TypeScript)](https://adk.dev/get-started/index.md) — Yerel Kılavuz: [`multi-language-setup.md`](multi-language-setup.md)
- [Migration to ADK (LangChain / CrewAI / AutoGen -> ADK)](https://adk.dev/get-started/migrate/index.md) — Yerel Kılavuz: [`migration-to-adk.md`](migration-to-adk.md)
- [Agent Patterns & Production Samples](https://adk.dev/tutorials/index.md) — Yerel Kılavuz: [`agent-patterns-and-samples.md`](agent-patterns-and-samples.md)

---

## 13. API Referansı ve Çoklu Dil SDK Rehberi (API Reference)
- [API Reference Hub (Genel Bakış)](https://adk.dev/api-reference/index.md) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md)
- [Python API Reference (`google.adk`)](https://adk.dev/api-reference/python/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 1)
- [TypeScript API Reference (`@google/adk`)](https://adk.dev/api-reference/typescript/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 2)
- [Go API Reference (`google.golang.org/adk/v2`)](https://pkg.go.dev/google.golang.org/adk/v2) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 3)
- [Java Javadoc (`com.google.adk`)](https://adk.dev/api-reference/java/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 4)
- [Kotlin KDoc (`com.google.adk.kt`)](https://adk.dev/api-reference/kotlin/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 5)
- [ADK CLI Reference (`adk` & `agents-cli`)](https://adk.dev/api-reference/cli/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 6)
- [Agent Config YAML Syntax](https://adk.dev/api-reference/agentconfig/) — Yerel Kılavuz: [`agent-config-yaml.md`](agent-config-yaml.md) & [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 7)
- [REST & WebSocket API Reference](https://adk.dev/api-reference/rest/) — Yerel Kılavuz: [`adk-api-reference-guide.md`](adk-api-reference-guide.md) (Bölüm 8) & [`adk-runtime-guide.md`](adk-runtime-guide.md)

---

## 14. Sürüm Notları ve Değişiklik Günlüğü (Release Notes)
Resmi Sayfa: [https://adk.dev/release-notes/index.md](https://adk.dev/release-notes/index.md)
- [ADK Python Releases](https://github.com/google/adk-python/releases)
- [ADK TypeScript Releases](https://github.com/google/adk-js/releases)
- [ADK Go Releases](https://github.com/google/adk-go/)

---

## 15. Topluluk ve Katkı Sağlama (Community & Contributing)
Resmi Sayfa: [https://adk.dev/community/index.md](https://adk.dev/community/index.md)  
Katkı Kılavuzu: [https://adk.dev/community/contributing-guide/index.md](https://adk.dev/community/contributing-guide/index.md)

### Topluluk Kanalları:
- **Tartışmalar & Soru-Cevap:** [Reddit - r/agentdevelopmentkit](https://www.reddit.com/r/agentdevelopmentkit/)
- **Topluluk Çağrıları:** [ADK Community Google Group](https://groups.google.com/g/adk-community)

### Resmi Depo Matrisi (GitHub):
| Depo | Açıklama |
| :--- | :--- |
| [`google/adk-python`](https://github.com/google/adk-python) | Çekirdek Python ADK kütüphanesi |
| [`google/adk-python-community`](https://github.com/google/adk-python-community) | Topluluk araçları, entegrasyonlar ve scriptler |
| [`google/adk-js`](https://github.com/google/adk-js) | TypeScript / JavaScript SDK |
| [`google/adk-go`](https://github.com/google/adk-go) | Go SDK çekirdek kütüphanesi |
| [`google/adk-java`](https://github.com/google/adk-java) | Java SDK çekirdek kütüphanesi |
| [`google/adk-docs`](https://github.com/google/adk-docs) | `adk.dev` dokümantasyon sitesi kaynak kodları |
| [`google/adk-samples`](https://github.com/google/adk-samples) | Resmi referans ajan örnekleri ve şablonları |
| [`google/adk-web`](https://github.com/google/adk-web) | `adk web` Dev UI (Playground) ön yüz kaynak kodları |

### Katkı Süreci (Contributing Workflow):
1. **Google CLA:** Katkıların kabul edilmesi için [cla.developers.google.com](https://cla.developers.google.com/) üzerinden Contributor License Agreement imzalanması zorunludur.
2. **Lisans:** Tüm katkılar **Apache 2.0** lisansı altında dağıtılır.
3. **Akış:** GitHub Issues (Hata & Özellik) -> GitHub Pull Request (PR) -> Ekip Kod İncelemesi (Review).
