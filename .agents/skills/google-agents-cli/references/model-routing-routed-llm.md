---
title: "Model Routing (RoutedLlm)"
description: "Dynamic model selection, automatic failover, and A/B testing in ADK TypeScript"
category: models
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - model-routing
  - routed-llm
  - failover
  - typescript
  - models
---

# ADK Model Routing (`RoutedLlm`) Kılavuzu

Kaynak: `https://adk.dev/agents/models/routing/index.md`  
Destek: TypeScript v1.0.0+ (Experimental)

---

## 1. Genel Bakış
`RoutedLlm`, istek anında modeller arasında dinamik seçim yapmayı sağlar:
- Hata anında yedek modele geçiş (Failover/Fallback).
- Farklı modeller arasında A/B testleri.
- Girdi karmaşıklığına göre otomatik yönlendirme (Auto-routing).

> [!TIP]
> - Yalnızca model değişecekse: **`RoutedLlm`**
> - Talimatlar, araçlar veya alt ajanlar da değişecekse: **`RoutedAgent`** (`/agents/routing/`)

---

## 2. Failover ve Fallback Deseni (TypeScript)

Birincil model yanıt üretmeden hata verirse, `errorContext.failedKeys` kontrol edilerek ikincil modele otomatik geçilir:

```typescript
import {
  BaseLlm,
  Gemini,
  LlmRequest,
  LlmAgent,
  RoutedLlm,
  InMemoryRunner,
} from '@google/adk';

const primaryModel = new Gemini({ model: 'gemini-flash-latest' });
const fallbackModel = new Gemini({ model: 'gemini-pro-latest' });

const router = (
  models: Readonly<Record<string, BaseLlm>>,
  request: LlmRequest,
  errorContext?: { failedKeys: ReadonlySet<string>; lastError: unknown },
) => {
  if (!errorContext) return 'primary';
  if (errorContext.failedKeys.has('primary')) return 'fallback';
  return undefined; // Hata fırlat ve sonlandır
};

const routedLlm = new RoutedLlm({
  models: { primary: primaryModel, fallback: fallbackModel },
  router,
});

const agent = new LlmAgent({
  name: 'resilient_agent',
  model: routedLlm,
  instruction: 'You are a reliable assistant with automated model failover.',
});
```

---

## 3. Kurallar ve Sınırlar
- **Failover:** Model henüz herhangi bir yanıt parçası (chunk) üretmeden hata verirse router tekrar çağrılır. Çıktı başladıktan sonra oluşan hatalar retry edilmez.
- **Canlı Akış (Live):** Canlı bağlantı kurulduktan sonra akış ortasında model değiştirilemez.
