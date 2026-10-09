---
title: "Deterministik Güvenlik Katmanı ve Araç Tasarım Kuralları"
description: "Modelin doğrudan yıkıcı mutasyonlar yapmasını engelleyen, serbest metin yasaklarını ve propose-* kalıbını zorunlu kılan kural dokümanı"
type: rule
scope: workspace
status: active
version: "1.0"
last_updated: "2026-10-07"
author: "Antigravity Engineering"
tags:
  - rules
  - security
  - guardrails
  - tools
  - determinism
---

# Deterministik Güvenlik ve Araç Tasarım Kuralları

Bu kurallar, AgentGate çalışma alanında geliştirilen tüm araçlar, MCP sunucuları ve Antigravity asistanı için bağlayıcıdır.

## 1. Temel İlke: Serbest Metin Yasağı
- Araç girdilerinde (`tool input parameters`) açık uçlu, serbest metin (`string`) alanları (`message: str`, `raw_query: str`, `free_text: str`) kullanmak kesinlikle yasaktır.
- Serbest metinler modelin olasılıksal doğası nedeniyle halüsinasyon, veri kaçağı veya laf kalabalığı üretir.
- Her parametre mutlaka katı tip sınırlamalarına (`Enum`, Regex deseni, azami uzunluk sınırı) tabi tutulmalıdır.

## 2. Eylem Yetkisi Yerine Teklif Deseni (Propose Pattern)
- Model hiçbir harici sisteme doğrudan mutasyon (Git commit/push, veri tabanı DROP/TRUNCATE/UPDATE, Cloud kaynak silme/dağıtma) yapacak araçlara doğrudan erişemez.
- Model sadece teklif sunan araçları çağırabilir (`propose_commit`, `propose_migration`, `propose_deployment`).
- Nihai metin birleştirmesi (string templating) modele değil, Python/TypeScript kodundaki deterministik şablon motoruna aittir.

## 3. Denetim Kapısı ve İnsan Onayı (Human-in-the-Loop)
- Tüm teklifler önce kod seviyesindeki linter/doğrulayıcıdan geçer. Kural ihlalinde harici API çağrılmadan modele anında hata dönülür.
- Geçerli teklifler `PENDING_APPROVAL` durumunda bekletilir; insan (operatör/geliştirici) onayı alınmadan icra katmanına aktarılamaz.
