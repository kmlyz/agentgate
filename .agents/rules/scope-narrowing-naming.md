---
title: "Dynamic Scope-Narrowing Naming Engine & Strict Immutability"
description: "Yeni bileşenler için 3 seviyeli daralan kapsamlı isimlendirme formülleri, over-specification yasağı ve mevcut koda sıfır dokunma (immutability) kuralı"
type: rule
scope: workspace
status: active
version: "1.0"
last_updated: "2026-10-07"
author: "Antigravity Engineering"
tags:
  - rules
  - naming
  - immutability
  - architecture
  - guardrails
---

# Dynamic Scope-Narrowing Naming Engine & Strict Immutability

## 1. Altın Kural: Sıfır Kırılma (Strict Immutability)
- Mevcut çalışan dosyalara, fonksiyon adlarına ve import yollarına KESİNLİKLE dokunulmaz.
- Bu kural motoru; ŞU ANDAN İTİBAREN yazılacak tüm yeni dosyalar, sınıflar ve fonksiyonlar için zorunlu üretim standardıdır.

---

## 2. Üretim Algoritması: 3 Seviyeli Daralan Kapsam Formülü

Herhangi bir yeni bileşen tasarlarken sırasıyla şu 3 soruyu sor ve yanıtları birleştir:

### Adım 1: Kök Alanı Belirle (Root Domain - En Genel)
"Bu bileşenin sistemdeki ana sorumluluk katmanı nedir?"
- Karar / onay mekanizması ise ➔ `gate`
- Tip güvenli veri modeli / şeması ise ➔ `proposal`
- Güvenlik kuralı / filtre ise ➔ `guardrail`
- Harici bir araç / kütüphane bağlayıcısı ise ➔ `adapter`
- Bağımsız bir görev / işlem ise ➔ `task`
- Çalışma zamanı / lifecycle / kanca ise ➔ `runtime`
- Test / kırmızı takım / metrik ise ➔ `eval`
- CLI / kod üretici / otomasyon ise ➔ `scaffold`
- *(Yeni bir katman gerekirse: Sorumluluğu tanımlayan tekil bir isim kökü seç.)*

### Adım 2: Kategori / Rolü Belirle (Category - Orta Katman)
"Bu bileşen kök alanın hangi alt dalı veya hangi sistemle etkileşimde?"
- Örneğin: `approval`, `git`, `slack`, `injection`, `validation`, `callback`, `persistence`, `audit`

### Adım 3: Detayı Belirle (Detail - En Özel Nitelik)
"Bunu diğer benzerlerinden ayıran özgün durum / varyant nedir?"
- Örneğin: `prompt_leak`, `schema_bypass`, `atomic_file`, `pull_request`, `direct_call`

---

## 3. Sentaks Sözdizimi Kuralları (Syntax Rules)

### A. Dosya İsimlendirmesi (snake_case - Genelden Özele)
FORMÜL: `{kök}_{kategori}_{detay}.py`
- Kural: Dosya adı tek başına sistemdeki yerini belli etmelidir.
- Kural: `utils.py`, `helpers.py`, `models.py`, `handler.py` gibi jenerik/bağlamsız isimler KESİNLİKLE YASAKTIR.
- Doğru Türetim Örnekleri:
  - `gate_approval_redis.py` (Yeni bir Redis onay deposu)
  - `adapter_slack_webhook.py` (Yeni bir Slack entegratörü)
  - `task_injection_jailbreak.py` (Yeni bir jailbreak görevi)

### B. Sınıf İsimlendirmesi (PascalCase - Doğal Tamlama / Suffix Noun)
FORMÜL: `{Detay}{Kategori}{Kök}`
- Kural: Kök alan veya ana rol mutlaka kelimenin sonunda bir isim (noun) olarak yer almalıdır.
- Doğru Türetim Örnekleri:
  - `RedisApprovalGate`
  - `SlackWebhookAdapter`
  - `JailbreakInjectionTask`

### C. Fonksiyon İsimlendirmesi
1. **Modül Düzeyi / Bağımsız Fonksiyonlar (Açık Bağlam):**
   FORMÜL: `{eylem_fiili}_{kök}_{kategori}_{detay}()`
   - Kural: İlk kelime kesinlikle eylem fiili olmalıdır (`validate_`, `execute_`, `intercept_`, `render_`, `audit_`).
   - Örnek: `intercept_runtime_callback_tool()`
   - Örnek: `execute_adapter_slack_message()`

2. **Sınıf İçi Metotlar (Bağlam Koruma):**
   - Kural: Sınıf adı zaten kökü tanımladığı için metodun içinde sınıf adını tekrarlama (Over-specification yasağı).
   - Doğru: `gate.submit_proposal()`
   - Yanlış: `gate.submit_gate_approval_proposal()`

---

## 4. Statik Kabul Kriteri (PR / Code Gen Gate)
Yeni üretilen herhangi bir kod şu denetimden geçmeden tamamlanmış sayılmaz:
1. Dosya adı `_` ile ayrılmış en az 3 parçalı hiyerarşiye (`kök_kategori_detay`) sahip mi?
2. Bütün Pydantic sınıflarında `model_config = ConfigDict(extra="forbid")` tanımlı mı?
3. Yan etki üreten işlemler doğrudan çalışmak yerine `propose_*` ve `execute_*` olarak ayrılmış mı?
