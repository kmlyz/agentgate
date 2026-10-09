---
title: "ADK API Reference Guide: Multi-Language SDKs, CLI, REST & YAML"
description: "Comprehensive master API reference and architectural link directory for Python (google.adk), TypeScript (@google/adk), Go (v2/v1), Java, Kotlin, ADK CLI, Agent Config YAML, and REST/WebSocket API endpoints"
category: api-reference
doc_type: reference
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - api-reference
  - sdk
  - python
  - typescript
  - golang
  - java
  - kotlin
  - cli
  - rest-api
  - yaml
---

# Google ADK API Referansı ve Çoklu Dil SDK Kılavuzu (Master API Directory)

Kaynak: `https://adk.dev/api-reference/index.md`  
Desteklenen Diller: **Python, TypeScript, Go, Java, Kotlin**  
Protokol Arayüzleri: **CLI, REST API, WebSocket (`/run_live`), YAML Config**

Agent Development Kit (ADK); kurumsal seviyede yapay zeka ajanları inşa etmek için çoklu programlama dili desteği ve standartlaştırılmış çalışma zamanı arayüzleri sunar. Bu kılavuz, tüm dillerdeki API paketlerini, sınıfları, CLI seçeneklerini ve REST uç noktalarını bir araya getiren **Master API Fihristidir**.

---

## 1. Python API Referansı (`google.adk`)

Resmi Dokümantasyon: [https://adk.dev/api-reference/python/](https://adk.dev/api-reference/python/)  
Paket Kurulumu: `pip install google-adk`

### Çekirdek Modül Haritası

| Modül Yolu | Temel Sınıflar & Fonksiyonlar | Görev ve İşlev Özeti |
| :--- | :--- | :--- |
| `google.adk.agents` | `Agent`, `LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`, `RunConfig`, `LiveRequestQueue` | Ajan tanımları, orkestrasyon tipleri ve canlı oturum kuyrukları. |
| `google.adk.runners` | `Runner` (`run`, `run_async`, `run_live`) | Ajan yürütme motoru; senkron, SSE token akışı ve WebSocket canlı akış. |
| `google.adk.sessions` | `Session`, `BaseSessionService`, `InMemorySessionService`, `DatabaseSessionService`, `VertexAiSessionService` | Oturum yaşam döngüsü, durum saklama ve veritabanı kilitleri. |
| `google.adk.events` | `Event`, `EventActions` | İletişim protokolü olayları, durum sinyalleri, barge-in ve transkripsiyon. |
| `google.adk.tools` | `BaseTool`, `ToolContext`, `FunctionTool`, `google_search`, `VertexAiSearchTool` | Özel Python fonksiyon araçları ve yerleşik Google grounding araçları. |
| `google.adk.workflow` | `Workflow`, `START`, `END` | Graf tabanlı yönlendirme ve devir (handoff) mimarisi (ADK 2.0). |
| `google.adk.models` | `Gemini`, `BaseLlm` | Gemini modelleri bağdaştırıcısı ve Interactions API yapılandırması. |
| `google.adk.apps` | `App` | Uygulama seviyesinde eklentiler, yaşam döngüsü ve context caching. |
| `google.adk.plugins` | `BasePlugin` | Global kancalar, Model Armor güvenlik filtreleri ve telemetri. |
| `google.adk.eval` | `AgentEvaluator`, `EvalSet` | Yörünge analizi, kullanıcı simülatörü (`llm_audio`) ve rubrik testleri. |

---

## 2. TypeScript API Referansı (`@google/adk`)

Resmi Dokümantasyon: [https://adk.dev/api-reference/typescript/](https://adk.dev/api-reference/typescript/)  
Paket Kurulumu: `npm install @google/adk` (Güncel Sürüm: `v2.2.0`)

### Temel Sınıflar ve Tipler
- **`LlmAgent`:** TypeScript için çekirdek LLM ajanı.
- **`Runner`:** Ajanları istemci veya sunucu ortamında çalıştırma sınıfı.
- **`InMemorySessionService` & `DatabaseSessionService`:** Oturum ve hafıza yönetimi.
- **`GOOGLE_SEARCH`:** Yerleşik Google Arama aracı sabiti.
- **`Event` & `ToolContext`:** Olay yakalama ve araç yürütme bağlamları.

```typescript
import { LlmAgent, Runner, InMemorySessionService, GOOGLE_SEARCH } from '@google/adk';

const agent = new LlmAgent({
    name: "research_agent",
    model: "gemini-flash-latest",
    instruction: "You are a professional research agent.",
    tools: [GOOGLE_SEARCH],
});

const runner = new Runner({
    appName: "web_service",
    agent: agent,
    sessionService: new InMemorySessionService(),
});
```

---

## 3. Go API Referansı (`google.golang.org/adk`)

Resmi Dokümantasyon:
- **Go v2.x (Güncel):** [https://pkg.go.dev/google.golang.org/adk/v2](https://pkg.go.dev/google.golang.org/adk/v2)
- **Go v1.x (Legacy):** [https://pkg.go.dev/google.golang.org/adk](https://pkg.go.dev/google.golang.org/adk)

Paket Kurulumu: `go get google.golang.org/adk/v2`

### Go v2 Özellikleri:
- Eşzamanlı (goroutine güvenli) ajan yürütme kanalları.
- A2A (Agent-to-Agent) protokol sunucusu (`a2a.NewServer`) ve istemcisi (`a2a.NewClient`).
- Yüksek performanslı mikrosaniyeler mertebesinde araç çalıştırma.

---

## 4. Java API Referansı (`com.google.adk` - Javadoc)

Resmi Dokümantasyon: [https://adk.dev/api-reference/java/](https://adk.dev/api-reference/java/)  
Maven Bağımlılığı: `com.google.adk:adk-core`

### Temel Sınıflar:
- **`com.google.adk.agents.LlmAgent`:** Builder deseniyle (`LlmAgent.builder()`) oluşturulan tip güvenli Java ajanı.
- **`com.google.adk.tools.GoogleSearchTool`:** `GoogleSearchTool.INSTANCE`.
- **`com.google.adk.tools.VertexAiSearchTool`:** Kurumsal veri ambarı aracı.
- **`com.google.adk.sessions.InMemorySessionService`:** Oturum servisi.
- **`com.google.adk.web.AdkWebServer`:** Yerleşik geliştirici Dev UI sunucusu.

```java
import com.google.adk.agents.LlmAgent;
import com.google.adk.tools.GoogleSearchTool;

LlmAgent agent = LlmAgent.builder()
    .name("java_agent")
    .model("gemini-flash-latest")
    .instruction("Help the user with facts.")
    .tools(GoogleSearchTool.INSTANCE)
    .build();
```

---

## 5. Kotlin API Referansı (`com.google.adk.kt` - KDoc)

Resmi Dokümantasyon: [https://adk.dev/api-reference/kotlin/](https://adk.dev/api-reference/kotlin/)  
Gradle Bağımlılığı: `implementation("com.google.adk:adk-kotlin")`

### Kotlin İdiomları:
- Coroutine (`suspend`) ve `Flow<Event>` desteğiyle asenkron olay akışları.
- DSL tabanlı ajan yapılandırması.

```kotlin
import com.google.adk.kt.agents.LlmAgent
import com.google.adk.kt.agents.Instruction
import com.google.adk.kt.models.Gemini

val agent = LlmAgent(
    name = "kotlin_agent",
    model = Gemini(name = "gemini-flash-latest"),
    instruction = Instruction("Friendly Kotlin assistant."),
)
```

---

## 6. ADK CLI Referansı (`adk` ve `agents-cli`)

Resmi Dokümantasyon: [https://adk.dev/api-reference/cli/](https://adk.dev/api-reference/cli/)

### ADK CLI (`adk`) Mimari ve Yaşam Döngüsü Komutları

ADK CLI (`adk`), doğrudan Python `google-adk` çekirdeğinde yer alan ve ajanın tüm geliştirme, test, optimize, değerlendirme ve bulut dağıtım yaşam döngüsünü yöneten yürütücüdür. (Kurumsal iskeleleme ve Gemini Enterprise kaydı için ise `agents-cli` kullanılır.)

| Komut Ailesi | Alt Komutlar / Kullanım | Temel Bayraklar & Açıklama |
| :--- | :--- | :--- |
| **Geliştirme & Web UI** | `adk web [AGENTS_DIR]` | Yerel tarayıcı Playground'u başlatır. `--port`, `--host`, `--logo-text`, `--logo-image-url`, `--avatar_config` (Canlı video Kai avatarı), `--session_service_uri`, `--memory_service_uri` (`rag://`, `agentengine://`, `sqlite://`). |
| **API Sunucusu** | `adk api_server [AGENTS_DIR]` | Canlı REST, SSE (`/run_async`) ve WebSocket (`/run_live`) sunucusu. `--with_ui`, `--a2a` (Agent-to-Agent protokolü), `--trigger_sources pubsub,eventarc`, `--trigger_oidc_audience`, `--max_llm_calls`. |
| **Terminal Sohbet** | `adk run AGENT [QUERY]` | Ajanı terminalde interaktif veya tek sorguluk (`QUERY`) metin modunda çalıştırır. `--enable_features`, `--stream`. |
| **Proje Başlatma** | `adk create APP_NAME` | Şablon ajan dizini oluşturur. `--model <model>`, `--api_key <key>`. |
| **Birim & JSON Testleri** | `adk test [FOLDER]` | Ajan JSON test dosyaları üzerinde pytest çalıştırır. `--rebuild` bayrağı gerçek ajan etkileşimiyle test dosyalarını otomatik günceller. |
| **Uyumluluk (Conformance)** | `adk conformance record`<br>`adk conformance test` | Ajanın deterministik tutarlılığını test eder. `input.yaml` spesifikasyonundan `test.yaml` altın iz (golden trace) etkileşimleri üretir ve regresyon kontrolü yapar. |
| **Değerlendirme (Eval)** | `adk eval AGENT_PATH EVAL_SET` | Eval setlerini çalıştırarak LLM-as-a-judge puanlaması yapar. `--config_file_path`, `--eval_storage_uri gs://...`. |
| **Eval Set Yönetimi** | `adk eval_set create`<br>`adk eval_set add_eval_case`<br>`adk eval_set generate_eval_cases` | Vertex AI Eval SDK ile ajan tanımlarından dinamik sentetik test senaryoları üretir (`generate_eval_cases`) veya mevcut senaryo dosyalarını bağlar. |
| **Prompt Optimizasyonu** | `adk optimize AGENT_PATH SAMPLER_CONFIG` | **GEPA** (*Generative Prompt Optimization*) algoritmasını kullanarak root agent sistem talimatlarını eval başarı skoruna göre otonom olarak optimize eder (`GEPARootAgentPromptOptimizer`). |
| **Dağıtım (Deploy)** | `adk deploy agent_engine`<br>`adk deploy cloud_run`<br>`adk deploy docker`<br>`adk deploy gke` | Ajanı hedeflenen altyapıya paketleyip dağıtır. Vertex AI Agent Engine (`--worker_pool` ile VPC-SC desteği), Cloud Run (`--` ile gcloud passthrough), GKE (`--cluster_name`), Docker. |
| **Oturum Göçü (Migrate)** | `adk migrate session` | Oturum veritabanını yeni şemaya taşır (`--source_db_url`, `--dest_db_url`). Eski güvensiz pickle v0 formatından güvenli yapılandırılmış JSON v1 şemasına geçiş sağlar (`--allow-unsafe-unpickling`). |
| **Telemetri** | `adk telemetry enable/disable/status` | CLI ve SDK telemetri toplama durumunu yapılandırır. Sunucu tarafında ise `--trace_to_cloud` ve `--otel_to_cloud` bayrakları kullanılır. |

### Kurumsal Araç Seti Ayrımı (`adk` vs `agents-cli`):
- **`adk`**: Python SDK çekirdek CLI'dır. Yerel çalışma, canlı Web UI, eval yürütme, prompt optimizasyonu ve doğrudan runtime dağıtımı yapar.
- **`agents-cli`**: Üst düzey Google Agent platform orkestratörüdür. Sıfırdan kurumsal çok dilli iskeleleme (`scaffold create`), kurumsal CI/CD dağıtımı ve Gemini Enterprise Agent Registry kaydı (`publish gemini-enterprise`) için kullanılır.

---

## 7. Agent Config YAML Sözdizimi (`AgentConfig`)

Resmi Dokümantasyon: [https://adk.dev/api-reference/agentconfig/](https://adk.dev/api-reference/agentconfig/)  
Referans Kılavuz: [`agent-config-yaml.md`](agent-config-yaml.md)

Kod yazmadan saf YAML dosyalarıyla ajanları yapılandırmak için kullanılan resmi şemadır:

```yaml
name: support_agent
description: Customer support specialist
agent_class: google.adk.agents.LlmAgent
model: gemini-flash-latest
instruction: Provide friendly and accurate customer service.
tools:
  - name: google.adk.tools.google_search
sub_agents:
  - config_path: billing_agent.yaml
```

---

## 8. REST ve WebSocket API Referansı (`ADK Server` - OAS 3.1)

Resmi Swagger Dokümantasyonu: [https://adk.dev/api-reference/rest/](https://adk.dev/api-reference/rest/)  
OpenAPI JSON Şeması: [https://adk.dev/api-reference/rest/openapi.json](https://adk.dev/api-reference/rest/openapi.json)  
Referans Kılavuz: [`adk-runtime-guide.md`](adk-runtime-guide.md)

ADK API Sunucusu (`adk api_server`), ADK 2.11.0 sürümünde standart **OpenAPI 3.1** sözleşmesine uygun olarak aşağıdaki rotaları sunar:

### A. Sistem ve Uygulama Bilgisi
| Uç Nokta | Metot | Açıklama |
| :--- | :--- | :--- |
| `/health` | `GET` | Sunucu sağlık kontrolü. |
| `/version` | `GET` | Çalışan ADK sürümü (örn. `2.11.0`). |
| `/list-apps` | `GET` | Sunucuda kayıtlı ajan uygulamalarını listeler. |
| `/apps/{app_name}/app-info` | `GET` | Belirtilen ajanın şema, açıklama ve kök ajan meta verilerini döner. |
| `/agent-identity/finalize` | `POST` | Agent Identity kimlik doğrulama sürecini sonlandırır. |

### B. Ajan Çalıştırma (Execution)
| Uç Nokta | Protokol / Metot | Açıklama |
| :--- | :--- | :--- |
| `/run` | `POST` (JSON) | Tekil istek/yanıt yürütme; nihai JSON cevabı döner. |
| `/run_sse` | `POST` (SSE) | Token token akıcı metin akışı (*Server-Sent Events*). |
| `/run_live` | `WebSocket` (Bidi) | Çift yönlü canlı 16kHz PCM ses ve 1 FPS video akışı. |

### C. Kullanıcı Oturumları (`Sessions`)
*ADK REST API hiyerarşisi `/apps/{app_name}/users/{user_id}/sessions` formatındadır:*
| Uç Nokta | Metot | Açıklama |
| :--- | :--- | :--- |
| `/apps/{app_name}/users/{user_id}/sessions` | `GET` / `POST` | Kullanıcının oturumlarını listeler veya yeni oturum başlatır. |
| `/apps/{app_name}/users/{user_id}/sessions/{session_id}` | `GET` / `POST` | Belirli bir oturumu detaylarıyla getirir veya özel ID ile açar. |
| `/apps/{app_name}/users/{user_id}/sessions/{session_id}` | `PATCH` / `DELETE` | Oturum durumunu/bağlamını günceller veya oturumu siler. |

### D. Bellek ve Eserler (`Memory` & `Artifacts`)
| Uç Nokta | Metot | Açıklama |
| :--- | :--- | :--- |
| `/apps/{app_name}/users/{user_id}/memory` | `PATCH` | Kullanıcıya ait Memory Bank verilerini kısmi günceller. |
| `.../sessions/{session_id}/artifacts` | `GET` / `POST` | Oturumda üretilen artifact'leri (dosya, rapor vb.) listeler veya kaydeder. |
| `.../sessions/{session_id}/artifacts/{name}` | `GET` / `DELETE` | Belirtilen artifact'i yükler veya siler. |
| `.../sessions/{session_id}/artifacts/{name}/versions` | `GET` | Bir artifact'in tüm versiyonlarını ve meta verilerini listeler. |
| `.../sessions/{session_id}/artifacts/{name}/versions/{ver_id}` | `GET` | Belirli bir versiyonun içeriğini ve meta verisini getirir. |

---

## 9. İlgili Bağlantılar
- Resmi API Hub: [ADK API Reference](https://adk.dev/api-reference/index.md)
- Python Belgeleri: [Python API Reference](https://adk.dev/api-reference/python/)
- TypeScript Belgeleri: [TypeScript API Reference](https://adk.dev/api-reference/typescript/)
- Go Belgeleri: [Go v2 Reference on pkg.go.dev](https://pkg.go.dev/google.golang.org/adk/v2)
- Java Javadoc: [Java API Reference](https://adk.dev/api-reference/java/)
- Kotlin KDoc: [Kotlin API Reference](https://adk.dev/api-reference/kotlin/)
- CLI Dokümantasyonu: [CLI Reference](https://adk.dev/api-reference/cli/)
- YAML Şeması: [Agent Config YAML reference](https://adk.dev/api-reference/agentconfig/)
- REST Uç Noktaları: [REST API Reference](https://adk.dev/api-reference/rest/)
