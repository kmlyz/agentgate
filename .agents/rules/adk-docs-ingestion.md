---
title: "ADK Dokümantasyon Öğrenme ve Referans Sentezleme Standartları"
description: "adk.dev kaynaklarından derinlemesine kılavuz çıkarma, kesintisiz tarama ve 3'lü checkpoint protokolü"
type: rule
scope: project
status: active
version: "1.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - rules
  - documentation
  - adk
  - checkpoints
---

# ADK Dokümantasyon Öğrenme ve Referans Sentezleme Standartları

Bu kural; `adk.dev` veya diğer Google resmi dokümantasyon kaynaklarından öğrenilen her yeni modülün yerel kütüphaneye (`references/`) aktarılmasında zorunludur.

## 1. Tam Kapsam ve Alt Sayfa Taraması (No Truncation)
- Yalnızca ana `index.md` okunarak yetinilmez.
- Konunun tüm alt sayfaları (`sitemap.xml` veya sayfa içi bağlantılar taranarak: `intro/`, `quickstart-exposing/`, `quickstart-consuming/`, uzantılar vb.) tam metin olarak taranır ve eksiksiz okunur.
- Çekilen içerikte kesilme (`truncated`) tespit edilirse ilgili parçalar tamamlanmadan doküman üretimine başlanmaz.
- Alt sayfalarda bulunan kurulum bayrakları (`pip install google-adk[...]`), ortam değişkenleri (`$env:...`), SDK sürüm uyumlulukları, port dinamikleri ve iç mimari sınıfları asla özetlenerek budanamaz; ana rehberin ilgili bölümüne eksiksiz aktarılır.

## 2. Referans Kılavuz Standartları (Deep-Dive Synthesis)
- **Konum:** `.agents/skills/google-agents-cli/references/adk-<modül_adı>-guide.md`
- **Şablon Referansı:** `references/adk-memory-guide.md` derinliği ve yapısı esas alınır.
- **Format:**
  1. YAML Frontmatter (`title`, `description`, `tags`).
  2. Kavramsal ayrım ve mimari genel bakış (Türkçe).
  3. Mimari ve akış diyagramları (`mermaid`).
  4. Sınıf, metot ve imza tabloları (parametreler, dönüş tipleri, sözleşmeler).
  5. Üretim seviyesinde çalışan kod blokları (İngilizce, Python öncelikli, çok dilli destek varsa Go/TS/Java karşılaştırmalı).
  6. Üretim en iyi uygulamaları (best practices), kısıtlar ve hata yönetimi desenleri.

## 3. Üçlü Kontrol Noktası Senkronizasyonu (Checkpoint Sync)
Yeni bir kılavuz tamamlandığında, aynı işlem adımı içinde şu 3 dosya güncellenir:
1. `references/adk-docs-index.md`: Yeni kılavuz fihriste eklenir; taranan tüm alt sayfalar, kılavuz içindeki ilgili bölüm bağlantılarıyla (anchor) madde madde indekslenir. Aktif durak bir sonraki konuya taşınır.
2. `README.md`: "5. Dokümantasyon Öğrenme Durumu ve Kontrol Noktası" altındaki kontrol listesine `[x]` olarak işlenir.
3. `not.md`: Bir sonraki oturumda başlanacak olan aktif durak URL'si ve konu başlığı tek satırlık uyarı kutusuyla güncellenir.

## 4. Otomatik Git Commit Protokolü (Conventional Commits)
Her modülün öğrenilmesi, referans kılavuzunun oluşturulması ve 3'lü kontrol noktası senkronizasyonu tamamlandığında:
- Değişiklikler gecikmeksizin Git üzerinde commit edilir.
- Commit standartları:
  - Format: Conventional Commits (`docs(<modül>): <öz ve odaklı teknik mesaj>`).
  - Dil & Biçim: Tamamen İngilizce, emir kipi (imperative mood), küçük harfle başlayan, sonda nokta içermeyen, < 72 karakter.
  - Örnekler:
    - `docs(live): synthesize adk live agents bidirectional streaming guide`
    - `docs(models): add google gemini integration reference and sync checkpoints`

