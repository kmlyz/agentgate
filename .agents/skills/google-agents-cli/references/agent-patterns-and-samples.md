---
title: "Agent Patterns & Samples"
description: "Core architectural patterns and reference samples for Google ADK agents"
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - patterns
  - architecture
  - samples
---

# Google ADK Temel Tasarım Desenleri & Örnekler

Google ADK projelerinde kullanılan 4 ana mimari desen:

## 1. Multi-Tool Agent (Çoklu Araç Ajanı)
- **Kapsam:** Tek bir ajanın birden fazla aracı (döküman okuma, arama, veri çekme vb.) otonom olarak sırayla veya paralel çağırdığı desen.
- **Kullanım Yeri:** Döküman analiz ajanı (`doc-agent`) gibi tekil uzmanlık alanları.

## 2. Agent Team (Ajan Takımı)
- **Kapsam:** Görev devri (delegation), oturum yönetimi (session management) ve güvenlik geri çağrıları (safety callbacks) içeren hiyerarşik veya işbirlikçi çoklu ajan takımları (`sub_agents`).
- **Kullanım Yeri:** Biri dökümanı okuyan, diğeri özetleyen, diğeri denetleyen çok adımlı kurumsal süreçler.

## 3. Streaming Agent (Akış Ajanı)
- **Kapsam:** Canlı akış (Gemini Live API, WebSocket, gerçek zamanlı ses/metin) senaryoları.

## 4. Resmi Örnek Deposu (adk-samples)
- Perakende, seyahat, müşteri hizmetleri ve döküman analizi için resmi Google örnekleri:
  - Repository: `https://github.com/google/adk-samples`
