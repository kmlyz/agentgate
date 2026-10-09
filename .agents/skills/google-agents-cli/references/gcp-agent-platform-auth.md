---
title: "GCP Agent Platform Authentication"
description: "Authentication modes, ADC, service accounts, and enterprise environment variables"
category: integrations
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - gcp
  - authentication
  - enterprise
  - integrations
---

# Google Cloud Agent Platform & ADK Yetkilendirme Kılavuzu

> [!NOTE]
> **Kapsamlı Mimari Kılavuz:** Google ADK'nın kimlik doğrulama şemaları, araç yetkilendirmesi (`adk_request_credential`), OAuth2/OIDC ve üretim en iyi uygulamaları için ana başvuru kaynağı: [`adk-auth-guide.md`](adk-auth-guide.md).

Google ADK ajanlarını kurumsal Google Cloud Agent Platform'a bağlama seçenekleri:

## 1. Yetkilendirme Modları Özeti

| Yöntem | Kullanım Amacı | Mekanizma | Gereken Değişkenler |
| :--- | :--- | :--- | :--- |
| **Google AI Studio** | Hızlı geliştirme / test | API Key | `GOOGLE_API_KEY=...` |
| **User Credentials (ADC)** | Yerel kurumsal test | `gcloud auth application-default login` | `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`<br>`GOOGLE_CLOUD_PROJECT=...`<br>`GOOGLE_CLOUD_LOCATION=...` |
| **Service Account** | Prod / CI-CD / Cloud Run | IAM Role (`Agent Platform User`) | Cloud Run'da otomatik; dış sunucularda `GOOGLE_APPLICATION_CREDENTIALS` |
| **Express Mode** | Hızlı kurumsal prototipleme | Express Mode API Key | `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`<br>`GOOGLE_GENAI_API_KEY=...` |

## 2. Kritik Çevresel Değişken Kuralları
- `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` (Eski ADK sürümlerinde `GOOGLE_GENAI_USE_VERTEXAI=TRUE`).
- Bu bayrak açıldığında SDK, AI Studio anahtarı yerine Google Cloud projesini ve ADC/IAM yetkisini devreye sokar.

## 3. Barındırılan Modeller ve Endpoint Kullanımı
Agent Platform Endpoint kaynak adları (`projects/.../endpoints/...`), Model Garden dağıtımları ve ince ayarlı (fine-tuned) modeller için bkz: [`agent-platform-hosted-models.md`](agent-platform-hosted-models.md).

