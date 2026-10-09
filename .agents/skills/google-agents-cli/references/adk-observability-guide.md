---
title: "ADK Observability Guide"
description: "In-depth guide for ADK agent observability, OpenTelemetry traces, structured logging, metrics, and TelemetryConfig"
category: observability
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - observability
  - opentelemetry
  - tracing
  - logging
  - metrics
  - otlp
---

# Google ADK Ajan Gözlemlenebilirlik (Observability) Rehberi

Ajan sistemlerinde temel girdi-çıktı takibi, çok adımlı karar mekanizmalarını ve araç çağrılarını analiz etmek için yetersizdir. ADK; model akıl yürütme adımlarını (reasoning traces), araç çalıştırmalarını ve gecikmeleri ölçmek için yerleşik gözlemlenebilirlik araçları sunar (Python v0.1.0, Go v0.1.0 ve Kotlin v0.1.0 desteklenir).

---

## 1. Üç Temel Sütun (Three Pillars of Observability)

1. **Logging (Yapılandırılmış Aktivite Loglama):**
   - Her ajan dönüşünün, durum değişikliğinin ve hata durumunun yapılandırılmış formatta kaydedilmesi.
   - `LoggingPlugin` aracılığıyla konsola, `DebugLoggingPlugin` ile YAML dosyasına veya Cloud Logging audit hatlarına aktarılır.
2. **Metrics (Metrikler):**
   - Model token kullanım sayıları, araç yürütme gecikmeleri ve işlem başarı/başarısızlık oranları.
3. **Traces (Dağıtık İzleme - OpenTelemetry):**
   - İstem başlangıcından nihai yanıta kadar geçen süredeki her bir alt adımı (LLM çağrısı, tool execution, route seçimi) bir `Span` olarak kaydeden OpenTelemetry mimarisi.

---

## 2. Loglama Felsefesi ve Hiyerarşik Yapı

ADK, dillerin standart loglama altyapısını ve OpenTelemetry GenAI Semantic Conventions standardını kullanır:
- **Python:** Standart `logging` modülü. Tüm ADK bileşenleri hiyerarşik olarak `google_adk` ana loglayıcısı altında toplanır. Tüm ADK logları topluca `logging.getLogger("google_adk")` ile yönetilebilir.
- **Go:** Standart `log` paketi (varsayılan olarak `stderr`'e yazar) ve `google.golang.org/adk/v2/telemetry`.
- **Kotlin:** JVM loglama backend'i (varsayılan Flogger, SLF4J veya `java.util.logging`).

### Log Seviyeleri (Python Teşhis Rehberi):
| Seviye | Kullanım Alanı | Kaydedilen Bilgi |
| --- | --- | --- |
| **`DEBUG`** | **Derinlemesine Hata Ayıklama** | Tam LLM istemleri, sistem talimatları, geçmiş, araç tanımları, API yanıtları, iç durum dönüşümleri. |
| **`INFO`** | **Üretim Standardı** | Ajan yaşam döngüsü, oturum açma/silme, çalıştırılan araç isimleri ve parametreleri. |
| **`WARNING`** | **Dikkat Gerektiren Durumlar** | Kullanımdan kalkan (deprecated) metotlar, tolere edilen sistem hataları. |
| **`ERROR`** | **Kritik Hatalar** | Başarısız LLM / Session API çağrıları, yakalanmamış istisnalar. |

---

## 3. CLI ve Web Sunucusunda Log Kontrolleri

`adk web`, `adk api_server`, `adk deploy cloud_run` ve `adk deploy gke` ortamlarında log akışı parametrelerle yönetilir:
```powershell
# Log seviyesi belirleme:
adk web --log_level DEBUG path/to/agents_dir

# Google Cloud Logging'e doğrudan aktarım:
adk web --otel_to_cloud path/to/agents_dir

# OTLP uyumlu toplayıcıya aktarım:
$env:OTEL_EXPORTER_OTLP_LOGS_ENDPOINT = "http://localhost:4318/v1/logs"
adk web path/to/agents_dir
```

---

## 4. Prompt İçeriğini Yakalama (Capture Content) ve 4 Mod

Varsayılan olarak güvenlik ve gizlilik gereği istem metinleri loglarda gizlenir (`elided`).
Ortam değişkeni ile açılabilir:
```powershell
$env:OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = "true"
```

Desteklenen 4 Mod:
1. `NO_CONTENT`: Hiçbir istem/yanıt içeriği kaydedilmez (varsayılan).
2. `EVENT_ONLY`: İçeriği log olaylarına yazar (`true` veya `1` buna denktir).
3. `SPAN_ONLY`: Çıkarım (inference) span'ine yazar (`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` gerektirir).
4. `SPAN_AND_EVENT`: Hem span hem log olaylarına yazar.

> [!CAUTION]
> **Üretim Ortamlarında PII / KVKK Güvenlik Uyarısı:**
> Bu ayar kullanıcı girdilerini ve ajan yanıtlarını tam metin kaydettiğinden üretimde PII/KVKK sızıntısı yaratabilir. Üretimde kapalı tutulmalı veya veri maskeleme uygulanmalıdır.

### `RunConfig` ile Çağrı Bazlı Telemetri Kapsamı Belirleme
Tüm proses genelinde ortam değişkenini değiştirmek yerine, yalnızca belirli bir ajan çağrısında içeriği yakalamak için `RunConfig.telemetry` kullanılır:
```python
from google.adk.agents.run_config import RunConfig
from google.adk.telemetry import ContentCapturingMode, TelemetryConfig

run_config = RunConfig(
    telemetry=TelemetryConfig(
        capture_message_content=ContentCapturingMode.SPAN_AND_EVENT,
    ),
)
```

---

## 5. Programatik OTLP ve Google Cloud Logging Aktarımı

### Python ile Cloud Logging:
```python
import os
from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers

os.environ["OTEL_SERVICE_NAME"] = "my-adk-agent"
gcp_exporters = get_gcp_exporters(enable_cloud_logging=True)
maybe_set_otel_providers([gcp_exporters])
```

### Go ile Cloud Logging:
```go
package main

import (
    "context"
    "google.golang.org/adk/v2/telemetry"
)

func main() {
    ctx := context.Background()
    tp, err := telemetry.New(ctx, telemetry.WithOtelToCloud(true))
    if err != nil { /* hata yönetimi */ }
    defer tp.Shutdown(ctx)
    tp.SetGlobalOtelProviders()
}
```

---

## 6. Eklentilerle Aktivite Loglama (Logging Plugins)

Ajan mantığını değiştirmeden aktivite loglarını yakalamak için ADK yerleşik eklentiler sunar:

### A. Konsol Aktivite Loglama (`LoggingPlugin`)
Kullanıcı mesajlarını, model istek/yanıtlarını ve araç çağrılarını konsola yapılandırılmış basar:
```python
from google.adk.apps import App
from google.adk.plugins import LoggingPlugin

app = App(name="my_app", root_agent=root_agent, plugins=[LoggingPlugin()])
```

### B. Dosyaya Tam YAML Dökümü (`DebugLoggingPlugin` - Python v1.23.0+, Kotlin v0.6.0+)
Konsol yerine tüm etkileşimi, oturum durumunu ve sistem talimatlarını `adk_debug.yaml` dosyasına kaydeder:
```python
from google.adk.apps import App
from google.adk.plugins import DebugLoggingPlugin

app = App(
    name="my_app",
    root_agent=root_agent,
    plugins=[
        DebugLoggingPlugin(
            output_path="adk_debug.yaml",
            include_session_state=True,
            include_system_instruction=True,
        )
    ],
)
```
> [!NOTE]
> `DebugLoggingPlugin`, Python'da kimlik bilgilerini ve `temp:` ile başlayan oturum anahtarlarını otomatik sansürler (redact).

---

---

## 7. Ajan Aktivite Metrikleri (Metrics)

Metrikler, log ve trace'lere kıyasla çok daha düşük maliyetli ve yüksek performanslıdır. ADK, model gecikmeleri, token harcamaları ve araç güvenilirliğini OpenTelemetry GenAI Semantic Conventions formatında ölçer (Python v1.32.0+, Kotlin v0.1.0+).

### 7.1. Temel GenAI Metrikleri
Ajan çalıştığında otomatik olarak üretilen histogram metrikleri:

| Metrik Adı | Tip | Açıklama | Ana Boyutlar (Dimensions) |
| --- | --- | --- | --- |
| **`gen_ai.invoke_agent.duration`** | Histogram (sn) | Ajanın tüm çalıştırma süresi (prompt -> yanıt). | `gen_ai.agent.name`, `error.type` |
| **`gen_ai.invoke_workflow.duration`** | Histogram (sn) | İş akışının toplam tamamlanma süresi. | `gen_ai.operation.name`, `gen_ai.workflow.name`, `gen_ai.workflow.nested`, `error.type` |
| **`gen_ai.execute_tool.duration`** | Histogram (sn) | Tekil araçların yürütme gecikmesi (yavaş API tespiti). | `gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.tool.type`, `error.type` |
| **`gen_ai.invoke_agent.inference_calls`** | Histogram (sayı) | Bir çalıştırmadaki model çağrısı adedi. | `gen_ai.agent.name` |
| **`gen_ai.invoke_agent.tool_calls`** | Histogram (sayı) | Bir çalıştırmadaki araç çalıştırma adedi. | `gen_ai.agent.name` |
| **`gen_ai.client.operation.duration`** | Histogram (sn) | Tek bir `generate_content` çağrısının süresi. | `gen_ai.agent.name`, `gen_ai.request.model`, `gen_ai.response.model`, `error.type` |
| **`gen_ai.client.token.usage`** | Histogram (token) | Model çağrısı başına harcanan token sayısı. | `gen_ai.token.type` (`input` vs `output`), `gen_ai.request.model` |

### 7.2. Deneysel Metrikler (`adk.experimental.*`)
Tekil model çağrıları yerine **tüm ajan dönüşü veya iş akışı genelinde toplanmış (aggregated)** token ve çağrı sayılarını ölçer:
- **Token Dağılımı:**
  - `adk.experimental.invoke_agent.input_tokens`: İstek, prompt cache ve sunucu araç sonuçları toplamı.
  - `adk.experimental.invoke_agent.output_tokens`: Üretilen metin, düşünme (reasoning/CoT) ve tool çağrı tokenları.
  - `adk.experimental.invoke_agent.cache_read.input_tokens`: Önbellekten okunan girdi tokenları.
  - `adk.experimental.invoke_agent.reasoning.output_tokens`: Modelin akıl yürütme (extended thinking) tokenları.
  - `adk.experimental.invoke_agent.tool.input_tokens`: Server-side araç dönüşleri (kod çalıştırma veya Google Search).
- **İş Akışı Metrikleri:** `adk.experimental.invoke_workflow.*` (`total_tokens`, `inference_calls`, `tool_calls`).

#### Aktifleştirme:
```powershell
$env:ADK_EXPERIMENTAL_TELEMETRY = "true"
# Vertex AI Agent Engine harici ortamlarda workflow metrikleri için schema v2 zorunludur:
$env:ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN = "2"
```

Programatik istek bazlı aktifleştirme:
```python
from google.adk.agents.run_config import RunConfig
from google.adk.telemetry import TelemetryConfig

run_config = RunConfig(
    telemetry=TelemetryConfig(adk_experimental_telemetry_opt_in=True)
)
```

> [!WARNING]
> **İş Akışlarında Çift Sayım (Double Counting) Riski:**
> İç içe (nested) iş akışları kendi metriğini kaydeder ve bu veriler üst iş akışına da dahil edilir. Tüm veri noktaları düz toplandığında mükerrer sayım oluşur. Panolarda sorgulama yaparken `gen_ai.workflow.nested` boyutu hariç tutularak yalnızca en dış akış metriği izlenmelidir.

### 7.3. Metrik Dışa Aktarma (Export)

#### A. CLI ve Web Arayüzünde
```powershell
# OTLP uyumlu toplayıcıya gönderme:
$env:OTEL_EXPORTER_OTLP_METRICS_ENDPOINT = "http://localhost:4318/v1/metrics"
adk web path/to/agents_dir

# Google Cloud Monitoring'e gönderme:
adk web --otel_to_cloud path/to/agents_dir
```

#### B. Programatik Python Yapılandırması
```python
import os
from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers

os.environ["OTEL_SERVICE_NAME"] = "my-adk-agent"
# Google Cloud Monitoring metriğini aktifleştirme:
gcp_exporters = get_gcp_exporters(enable_cloud_metrics=True)
maybe_set_otel_providers([gcp_exporters])
```

---

## 8. Ajan Dağıtık İzleme (Distributed Tracing)

Dağıtık izleme, bir isteğin ajan mimarisi boyunca izlediği uçtan uca yolculuğu görselleştirir. Metrikler sürecin *ne kadar sürdüğünü*, loglar *ne olduğunu* bildirirken; trace'ler olayları birbirine bağlayarak zamanın *nerede harcandığını* ve alt çağrılar arasındaki bağımlılıkları ortaya koyar (Python v1.17.0+, Go v1.0.0+, Kotlin v0.1.0+).

### 8.1. Hiyerarşik Şelale (Waterfall) ve Context Propagation
- **Şelale Hiyerarşisi:** Ajan etkileşimi bir Kök Span (`invoke_agent`) başlatır. Ajanın modele gönderdiği her istek bir alt span (`generate_content`), modelin tetiklediği her araç çağrısı ise bunun altında başka bir alt span (`execute_tool`) oluşturur.
- **Bağlam Yayılımı (Context Propagation):** ADK, işlem sınırları ötesinde trace bağlamını otomatik olarak aktarır. Bir araç harici bir mikroservisi veya Cloud Run servisini çağırdığında, o servisin ürettiği span'ler ajanın ana trace kimliğine (`trace_id`) bağlanır.

### 8.2. Dört Temel GenAI Span Şeması
ADK, OpenTelemetry [Semantic Conventions for GenAI Agents](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-agent-spans.md) standartlarını takip eder:

| Span Adı | Tip | Açıklama | Ana Boyutlar (Attributes) |
| --- | --- | --- | --- |
| **`invoke_agent {agent.name}`** | Client / Internal | Ajanın tüm etkileşim yaşam döngüsünü temsil eden kök span. | `gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.conversation.id` |
| **`invoke_workflow {workflow.name}`** | Child Span | Çok adımlı bir iş akışının yürütmesini temsil eder. | `gen_ai.operation.name`, `gen_ai.workflow.name`, `gen_ai.workflow.nested` |
| **`execute_tool {tool.name}`** | Child Span | Model tarafından talep edilen belirli bir aracın veya fonksiyonun yürütülmesini izler. | `gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.tool.type`, `gen_ai.tool.call.id`, `error.type` |
| **`generate_content {model.name}`** | Internal Span | Alttaki LLM'e yapılan çıkarım çağrısını temsil eder. İstek, yanıt ve token metriklerini kaydeder. | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |

### 8.3. CLI ve Web Arayüzünde Trace Aktarımı
```powershell
# OTLP uyumlu toplayıcıya aktarım (Jaeger, Tempo, Datadog):
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"
adk web path/to/agents_dir

# Google Cloud Trace'e aktarım:
adk web --otel_to_cloud path/to/agents_dir
```

### 8.4. Programatik Python Yapılandırması
```python
import os
from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers

os.environ["OTEL_SERVICE_NAME"] = "my-adk-agent"
# Google Cloud Trace'i aktifleştirme:
gcp_exporters = get_gcp_exporters(enable_cloud_tracing=True)
maybe_set_otel_providers([gcp_exporters])
```

### 8.5. Kotlin / JVM Yapılandırması
ADK Kotlin'de trace'ler `GlobalOpenTelemetry` üzerinden yayılır:
```kotlin
val spanExporter = OtlpGrpcSpanExporter.builder()
    .setEndpoint("http://localhost:4317")
    .build()

val resource = Resource.getDefault().merge(
    Resource.create(Attributes.of(AttributeKey.stringKey("service.name"), "my-kotlin-agent"))
)

val tracerProvider = SdkTracerProvider.builder()
    .addSpanProcessor(BatchSpanProcessor.builder(spanExporter).build())
    .setResource(resource)
    .build()

OpenTelemetrySdk.builder()
    .setTracerProvider(tracerProvider)
    .buildAndRegisterGlobal()
```

---

## 9. Log Çıktılarını Okuma ve Teşhis

`DEBUG` modunda `google_adk.google.adk.models.google_llm` modülü şu dökümü üretir:
```text
2026-10-04 15:26:13,778 - DEBUG - google_adk.google.adk.models.google_llm -
LLM Request:
-----------------------------------------------------------
System Instruction:
      You roll dice and answer questions about the outcome of the dice rolls.
Contents:
{"parts":[{"text":"Roll a 6 sided dice"}],"role":"user"}
{"parts":[{"function_call":{"args":{"sides":6},"name":"roll_die"}}],"role":"model"}
{"parts":[{"function_response":{"name":"roll_die","response":{"result":2}}}],"role":"user"}
Functions:
roll_die: {'sides': {'type': <Type.INTEGER: 'INTEGER'>}}
-----------------------------------------------------------
2026-10-04 15:26:14,309 - INFO - google_adk.google.adk.models.google_llm -
LLM Response:
-----------------------------------------------------------
Text:
I have rolled a 6 sided die, and the result is 2.
```

Bu döküm üzerinden şunlar doğrulanır:
- **System Instruction:** Ajan sistem talimatının modele doğru gidip gitmediği.
- **Contents:** `user` ve `model` konuşma geçmişi ile `function_call` / `function_response` zinciri.
- **Functions:** Modele sunulan tool şemalarının parametre tipleri.
- **Latency & Tokens:** Modelin yanıt üretme süresi ve token tüketimi.

---

## 10. İlgili Bağlantılar ve Entegrasyonlar
- Resmi Dokümantasyon: [Observability for Agents](https://adk.dev/observability/index.md)
- Loglama: [ADK Logging](https://adk.dev/observability/logging/index.md)
- Metrikler: [ADK Metrics](https://adk.dev/observability/metrics/index.md)
- Dağıtık İzleme: [ADK Traces](https://adk.dev/observability/traces/index.md)
- Dış Entegrasyonlar: [Observability ADK Integrations](https://adk.dev/integrations/?topic=observability)

