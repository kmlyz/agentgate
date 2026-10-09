---
title: "Agent Config YAML"
description: "Declarative configuration of Google ADK agents using YAML specifications (AgentConfig JSON Schema)"
category: architecture
doc_type: guide
status: active
version: "2.11.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - agent-config
  - yaml
  - declarative
  - json-schema
  - architecture
---

# Google ADK Agent Config (YAML) Referansı

Resmi Şema Dokümantasyonu: [https://adk.dev/api-reference/agentconfig/](https://adk.dev/api-reference/agentconfig/)  
ADK v1.11.0+, kod yazmadan deklaratif YAML sözdizimiyle (`root_agent.yaml`) tam teşekküllü ajan hiyerarşileri oluşturmayı destekler.

---

## 1. Mimari Şema Özeti (`AgentConfig`)

ADK YAML şeması `AnyOf` mantığıyla 4 temel ajan sınıfı ve referans mekanizmalarından oluşur:

```text
AgentConfig (root)
 ├── LlmAgentConfig         (agent_class: "LlmAgent")
 ├── SequentialAgentConfig  (agent_class: "SequentialAgent")
 ├── ParallelAgentConfig    (agent_class: "ParallelAgent")
 ├── LoopAgentConfig        (agent_class: "LoopAgent")
 └── AgentRefConfig         (config_path: "sub_agent.yaml")
```

---

## 2. Temel Ajan Türleri ve YAML Örnekleri

### A. Standart LLM Ajanı (`LlmAgentConfig`)
```yaml
name: doc_assistant
agent_class: LlmAgent # veya boş bırakılabilir
model: gemini-flash-latest
description: Döküman analizi ve soru-cevap ajanı.
instruction: |
  Sen döküman analizi konusunda uzman bir asistansın.
  Kullanıcı sorularını doğrudan ve kaynak göstererek yanıtla.
tools:
  - name: google.adk.tools.google_search
  - name: my_module.tools.custom_db_search # CodeConfig referansı
before_agent_callbacks:
  - name: my_module.security.audit_log
sub_agents:
  - config_path: billing_agent.yaml # AgentRefConfig
```

### B. Sıralı Ajan Zinciri (`SequentialAgentConfig`)
Girdiyi ilk ajana verir, çıktısını zincirleme olarak sonrakine iletir.
```yaml
name: document_pipeline
agent_class: SequentialAgent
description: Dökümanı önce özetleyen, ardından çeviren sıralı boru hattı.
sub_agents:
  - config_path: summarizer_agent.yaml
  - config_path: translator_agent.yaml
```

### C. Paralel Ajan Havuzu (`ParallelAgentConfig`)
Aynı kullanıcı girdisini birden fazla ajana eşzamanlı dağıtır.
```yaml
name: multi_analyst_team
agent_class: ParallelAgent
description: Finansal, hukuki ve teknik analizi paralel yürüten ekip.
sub_agents:
  - config_path: financial_analyst.yaml
  - config_path: legal_analyst.yaml
  - config_path: tech_analyst.yaml
```

### D. Döngüsel Ajan (`LoopAgentConfig`)
Bir sonlanma kriterine veya maksimum adım sayısına kadar döngü işletir.
```yaml
name: iterative_refiner
agent_class: LoopAgent
description: Çıktıyı tatmin edici olana kadar yinelemeli düzelten ajan.
max_iterations: 3
sub_agents:
  - config_path: writer_agent.yaml
  - config_path: critic_agent.yaml
```

---

## 3. Kod Entegrasyonu (`CodeConfig`)

Python fonksiyonları YAML dosyasına doğrudan modül yoluyla bağlanabilir:
* **Araçlar (Tools):** `tools: [{ name: "my_package.tools.fetch_data" }]`
* **Geri Çağrımlar (Callbacks):** `before_agent_callbacks: [{ name: "my_package.auth.validate" }]`
* **Geçiş Kısıtları:** `disallow_transfer_to_parent: true`, `disallow_transfer_to_peers: true`

---

## 4. Ne Zaman YAML, Ne Zaman Python?

| Özellik | YAML (`AgentConfig`) | Saf Python (`agent.py`) |
| :--- | :--- | :--- |
| **Kullanım Amacı** | Dinamik, konfigüre edilebilir, no-code/low-code ajanlar | Karmaşık mantık, custom RAG, harici DB entegrasyonu |
| **Geliştirme Hızı** | Çok hızlı; kod derleme/import gerektirmez | Esnek; tüm Python ekosistemi elinizin altında |
| **Bakım & CI/CD** | YAML linter ve JSON Schema doğrulama | Pytest, tip denetimi (mypy), debugger |
| **Örnek Senaryo** | Şablon müşteri hizmetleri botları, basit LLM zincirleri | Döküman analiz asistanımız (`doc-agent`), özel bridge sunucuları |

---

## 5. Çalıştırma
Tüm standart `adk` CLI komutları YAML yapılandırmalarını yerel olarak tanır:
```powershell
adk run my_agent_dir
adk web my_agent_dir --port 8000
adk deploy cloud_run my_agent_dir
```
