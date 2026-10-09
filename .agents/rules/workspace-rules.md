---
title: "Workspace Kuralları"
description: "Çalışma alanı işletim sistemi, kabuk, Python bağımlılık ve iletişim standartları"
type: rule
scope: workspace
status: active
version: "1.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - rules
  - workspace
  - pwsh
  - uv
---

# Workspace Kuralları

## 1. Ortam & Yürütme
- **OS & Kabuk:** Windows 11, PowerShell (`pwsh`). Bash/Unix sözdizimi kullanılmaz.
- **Python:** Paket ve bağımlılık yönetimi `uv` üzerinden yürütülür.
- **Framework:** Google ADK (`google-adk`).

## 2. İletişim & Kodlama Standardı
- **Prensip:** Yüksek sinyal, düşük token (High SNR, low token).
- **Format:** Doğrudan, öz ve doğrulanabilir teknik çıktılar.
- **İşlem Sonrası Yanıtlar:** Kullanıcı açıkça talep etmedikçe işlem özetleri kısa (minimal, tek/iki cümlelik yüksek sinyalli) tutulur; uzun tekrarlı raporlamalardan kaçınılır.
