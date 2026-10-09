---
title: "ADK Deployment & Production Guide"
description: "Google ADK ajanlarının Cloud Run, Agent Platform (Agent Runtime), GKE ve Docker konteyner ortamlarına dağıtımı."
category: deployment
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - deploy
  - cloud-run
  - agent-runtime
  - gke
  - docker
  - deployment
---

# Google ADK Ajan Dağıtım & Üretim Rehberi

ADK ile geliştirilen ve yerel ortamda test edilen ajanlar, ölçeklenebilir ve güvenli üretim ortamlarına taşınabilir.

---

## 1. Dağıtım Ortamı Seçenekleri

| Hedef Ortam | Dağıtım Yöntemi | Ne Zaman Tercih Edilmeli? |
| :--- | :--- | :--- |
| **Agent Runtime on Agent Platform** | `adk deploy` veya `agents-cli deploy` | Tam yönetilen, ajana özel altyapı, kurumsal yönetişim ve CI/CD pipeline'ları |
| **Cloud Run** | `adk deploy cloud_run` veya `gcloud run deploy` | Sunucusuz (serverless), trafik bazlı otomatik ölçekleme, webhook & trigger entegrasyonu |
| **Google Kubernetes Engine (GKE)** | Helm / Kubernetes manifests | Açık kaynak modeller (vLLM, Ollama), GPU cluster yönetimi ve hibrit bulut |
| **Standart Docker / Podman** | `docker build -t my-agent .` | Şirket içi (on-premise), internete kapalı (air-gapped) veya GCP dışı ortamlar |

---

## 2. Dil Bazlı Kod ve Yapı Konvansiyonları

Dağıtım araçlarının ajanı otomatik tanıması için aşağıdaki kurallar zorunludur:

- **Python:**
  - Dosya adı: `agent.py`
  - Değişken adı: `root_agent`
  - Dizin içinde: `__init__.py` (`from . import agent` içermeli) ve `requirements.txt`.
  - **MCP Dağıtım Kuralı:** Ajan ve `McpToolset` modül seviyesinde kesinlikle **senkron** oluşturulmalıdır. `adk web` asenkron fabrikalara izin verse de dağıtım ortamlarında (Cloud Run, Agent Runtime, GKE) `async def get_agent()` desteklenmez (`references/adk-mcp-guide.md`).
- **TypeScript:**
  - Dosya adı: `agent.ts`
  - Dışa aktarılan değişken: `export const rootAgent = ...`
  - Dizin içinde: `package.json` (`@google/adk` bağımlılığı ile).
- **Go:**
  - Dosya adı: `main.go`
  - Giriş noktası: `agent.NewSingleLoader(yourAgent)` ile konfigüre edilmiş launcher.
  - Dizin içinde: `go.mod` ve `go.sum`.
- **Java:**
  - Dosya adı: `<AgentName>.java`
  - Değişken: `public static final BaseAgent ROOT_AGENT`.


---

## 3. Cloud Run Dağıtımı

Cloud Run, ajanların Google altyapısında sunucusuz (serverless) olarak ölçeklenmesini sağlar. Python, TypeScript, Go ve Java desteklenir.

### 3.1. Ön Koşullar & Yetkilendirme
- **Gerekli Ortam Değişkenleri:**
  ```powershell
  $env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"
  $env:GOOGLE_CLOUD_LOCATION = "us-central1"
  $env:GOOGLE_GENAI_USE_ENTERPRISE = "True"
  ```
- **Cloud Build İzni:** `adk deploy` arka planda Cloud Build kullandığı için varsayılan compute servis hesabına build izni verilir:
  ```powershell
  gcloud projects add-iam-policy-binding $env:GOOGLE_CLOUD_PROJECT `
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" `
    --role="roles/cloudbuild.builds.builder"
  ```
- **Secret Manager (`GOOGLE_API_KEY`):** API anahtarı kullanılıyorsa gizli tutulmalı ve servis hesabına `roles/secretmanager.secretAccessor` izni atanmalıdır:
  ```powershell
  "AIzaSy..." | gcloud secrets create GOOGLE_API_KEY --project=$env:GOOGLE_CLOUD_PROJECT --data-file=-
  gcloud secrets add-iam-policy-binding GOOGLE_API_KEY `
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" `
    --role="roles/secretmanager.secretAccessor" `
    --project=$env:GOOGLE_CLOUD_PROJECT
  ```

### 3.2. Dağıtım Yükü ve Durum Kalıcılığı (Persistence)
> [!WARNING]
> `--session_service_uri` ve `--artifact_service_uri` belirtilmediğinde Cloud Run varsayılan olarak bellek içi (`memory://`) depolamaya düşer. Cloud Run konteyneri her yeniden başladığında (recycle / scale to zero) oturumlar ve üretilen artifact'ler kaybolur.

Kalıcı üretim ortamları için şu URI parametreleri sağlanmalıdır:
- **Oturum Servisi:** `--session_service_uri="agentengine://<engine_id>"` (Agent Runtime yönetilen oturum) veya `sqlite+aiosqlite:///./sessions.db` ya da harici SQLAlchemy DB URL.
- **Artifact Servisi:** `--artifact_service_uri="gs://<bucket_name>"` (Cloud Storage kovası).
- **Bellek (Memory) Servisi:** `--memory_service_uri="rag://<corpus_id>"` veya `agentengine://<engine_id>`.

### 3.3. Python ile Dağıtım Yöntemleri

#### A. ADK CLI ile Otomatik Dağıtım
```powershell
adk deploy cloud_run `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --region=$env:GOOGLE_CLOUD_LOCATION `
  --service_name="my-agent-service" `
  --app_name="my_agent" `
  --session_service_uri="agentengine://my-engine" `
  --artifact_service_uri="gs://my-bucket" `
  --with_ui `
  path/to/my_agent `
  -- --no-allow-unauthenticated --min-instances=1
```
- `--with_ui`: ADK web arayüzünü API sunucusu ile birlikte sunar.
- `--trigger_sources="pubsub,eventarc"`: Ambient ajan modunda olay tetikleyicilerini bağlar.
- `-- [GCLOUD_FLAGS]`: Çift tire sonrasındaki tüm bayraklar doğrudan `gcloud run deploy` komutuna aktarılır.

#### B. Özel FastAPI + Dockerfile ile Dağıtım (`gcloud run deploy`)
Çoklu ajanları aynı Cloud Run örneğinde barındırmak veya özel rotalar eklemek için:
```text
my-project/
├── capital_agent/          # 1. Ajan (agent.py: root_agent)
├── population_agent/       # 2. Ajan (agent.py: root_agent)
├── main.py                 # FastAPI giriş noktası
├── requirements.txt
└── Dockerfile
```
`main.py` içinde ADK FastAPI entegrasyonu:
```python
import os, uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri="sqlite+aiosqlite:///./sessions.db",
    allow_origins=["*"],
    web=True,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
```

Dağıtım komutu:
```powershell
gcloud run deploy my-agent-service `
  --source . `
  --region $env:GOOGLE_CLOUD_LOCATION `
  --project $env:GOOGLE_CLOUD_PROJECT `
  --allow-unauthenticated `
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$env:GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=$env:GOOGLE_CLOUD_LOCATION"
```

### 3.4. TypeScript ile Dağıtım
`package.json` dosyasının bulunduğu dizinde:
```powershell
npx adk deploy cloud_run `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --region=$env:GOOGLE_CLOUD_LOCATION `
  --service_name="ts-agent-service" `
  --with_ui
```

### 3.5. Go ile Dağıtım (`adkgo`)
Go projelerinde `cmd/adkgo` derlenir. Tool; Linux statik ikili dosyasını üretir, minimal container hazırlar ve dağıtır:
```powershell
./adkgo deploy cloudrun `
  -p $env:GOOGLE_CLOUD_PROJECT `
  -r $env:GOOGLE_CLOUD_LOCATION `
  -s "go-agent-service" `
  -e "./main.go" `
  --proxy_port=8081 `
  --server_port=8080 `
  --a2a --api --webui
```
> [!NOTE]
> `adkgo` dağıtım tamamlandığında yerel terminalde güvenli bir kimlik doğrulayıcı proxy (`--proxy_port=8081`) başlatır; tarayıcıdan veya yerel curl ile bu port üzerinden doğrudan test edilebilir.

### 3.6. Java ile Dağıtım (Maven & AdkWebServer)
Java projelerinde `com.google.adk.web.AdkWebServer` ve çok aşamalı (multi-stage) Dockerfile kullanılır:
```xml
<!-- pom.xml -->
<dependency>
  <groupId>com.google.adk</groupId>
  <artifactId>google-adk</artifactId>
  <version>1.11.0</version>
</dependency>
<dependency>
  <groupId>com.google.adk</groupId>
  <artifactId>google-adk-dev</artifactId>
  <version>1.11.0</version>
</dependency>
```
Dockerfile `ENTRYPOINT`:
```dockerfile
ENTRYPOINT ["sh", "-c", "mvn compile exec:java \
    -Dexec.mainClass=com.google.adk.web.AdkWebServer \
    -Dexec.classpathScope=compile \
    -Dexec.args='--server.port=${PORT:-8080} --adk.agents.source-dir=target'"]
```
Dağıtım için proje kök dizininde `gcloud run deploy --source .` komutu çalıştırılır.

### 3.7. Cloud Run Ajanını Test Etme

#### A. Web UI Testi
Dağıtımda `--with_ui` (veya `web=True`) etkinleştirildiyse, Cloud Run servis URL'sini doğrudan tarayıcıda açarak test edebilirsiniz (`https://<service-url>`).

#### B. curl ve API ile Test
1. **Kimlik Belirteci (Token) Edinme:**
   ```powershell
   $env:TOKEN = (gcloud auth print-identity-token)
   $env:APP_URL = "https://your-service-url.a.run.app"
   ```
2. **Uygulamaları Listeleme:**
   ```powershell
   curl -X GET -H "Authorization: Bearer $env:TOKEN" "$env:APP_URL/list-apps"
   ```
3. **Oturum Oluşturma:**
   ```powershell
   curl -X POST -H "Authorization: Bearer $env:TOKEN" `
     -H "Content-Type: application/json" `
     -d '{"preferred_language": "Turkish"}' `
     "$env:APP_URL/apps/my_agent/users/user_123/sessions/session_abc"
   ```
4. **Ajanı Çalıştırma (`/run_sse`):**
   ```powershell
   curl -X POST -H "Authorization: Bearer $env:TOKEN" `
     -H "Content-Type: application/json" `
     -d '{
       "app_name": "my_agent",
       "user_id": "user_123",
       "session_id": "session_abc",
       "new_message": {"role": "user", "parts": [{"text": "Turkiye nin baskenti neresidir?"}]},
       "streaming": true
     }' `
     "$env:APP_URL/run_sse"
   ```

---

## 4. Agent Runtime on Agent Platform Dağıtımı

Google Cloud Vertex AI [Agent Runtime](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview) (Reasoning Engine), yapay zeka ajanlarını tam yönetilen, otomatik ölçeklenen ve kurumsal yönetişim standartlarına sahip bir ortamda çalıştırmak için tasarlanmıştır (Python ve Go v1.2.0+).

### 4.1. Ön Koşullar ve GCP API Etkinleştirme
Dağıtım öncesinde ilgili GCP projesinde gerekli servislerin açık ve ADC'nin tanımlı olması zorunludur:

```powershell
# Gerekli Google Cloud API'lerini etkinleştirme:
gcloud services enable aiplatform.googleapis.com cloudresourcemanager.googleapis.com

# Kullanıcı ve ADC (Application Default Credentials) doğrulaması:
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 4.2. Dağıtım Paketi (Payload) Mantığı
- **Yüklenen İçerik:** Ajan kaynak kodları ve bağımlılıklar (`requirements.txt`, `pyproject.toml` veya `go.mod`).
- **API Sunucusu Farkı:** Python projelerinde yerel ADK API Server veya Web UI kodları servise **yüklenmez**; API server kabiliyetleri doğrudan Agent Runtime motoru tarafından yerel olarak sunulur. Go dağıtımlarında ise özel ADK API sunucusu pakete dahil edilir.

### 4.3. Standart Dağıtım (`adk deploy agent_engine`)

Mevcut bir Google Cloud projesinde hızlıca Reasoning Engine kaynağı oluşturmak için:

```powershell
$PROJECT_ID = "proje-id"
$LOCATION_ID = "us-central1"

adk deploy agent_engine `
  --project=$PROJECT_ID `
  --region=$LOCATION_ID `
  --display_name="Destek Asistani" `
  path/to/my_agent
```

Go projelerinde:
```powershell
adkgo deploy agentengine -e ./main.go -s "my_agent" -p $PROJECT_ID -r $LOCATION_ID -d .
```

Dağıtım komutu arka planda bir Uzun Süreli Operasyon (LRO - Long Running Operation) başlatır:
`Create AgentEngine backing LRO: projects/.../locations/.../reasoningEngines/.../operations/...`
Canlı dağıtım ve container oluşturma logları Google Cloud Logging üzerinden izlenebilir:
`https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID`

Dağıtım tamamlandığında çıktı olarak ajana atanan benzersiz bir **`RESOURCE_ID`** üretilir:
`projects/<PROJECT_NUM>/locations/<REGION>/reasoningEngines/<RESOURCE_ID>`

### 4.4. Agents CLI ile Hızlandırılmış Kurumsal Dağıtım

Kurumsal CI/CD (Cloud Build) ve Altyapı Kodları (Terraform) ile üretim ortamı hazırlamak için `agents-cli` kullanılır:

#### A. Ön Koşullar & IAM Rolleri
- **Gerekli Araçlar:** Python, `uv`, `gcloud`, `make`.
- **IAM Yetkileri:**
  - `Agent Platform User`: Yalnızca ajanı Agent Runtime üzerine yüklemek için yeterlidir.
  - `Owner`: CI/CD (Cloud Build), Terraform altyapı provizyonu ve IAM servis hesabı rolleri için tam üretim kurulumunda gereklidir.

#### B. Projeyi Kurumsal Şablona Genişletme (`scaffold enhance`)
Ajan klasörünüzün bulunduğu ana dizinde çalıştırın:
```powershell
agents-cli scaffold enhance --deployment-target agent_runtime
```
Komut; projeyi yedekler ve şu kurumsal mimariyi oluşturur:
```text
my-agent/
├── app/
│   ├── agent.py               # Ana ajan mantığı (root_agent)
│   ├── agent_engine_app.py    # Agent Runtime entegrasyonu
│   └── utils/                 # Oturum ve yardımcı fonksiyonlar
├── .cloudbuild/               # Cloud Build otomatik CI/CD hatları
├── deployment/                # Terraform altyapı kodları (IaC)
├── notebooks/                 # Değerlendirme ve prototip not defterleri
├── tests/                     # Unit, integration ve eval testleri
├── Makefile                   # Sık kullanılan derleme/test komutları
├── GEMINI.md                  # Ajan kodlama yönergeleri
└── pyproject.toml             # deployment_target = "agent_runtime"
```

#### C. Hedef Projeyi Belirleme ve Dağıtma
```powershell
gcloud config set project your-project-id
agents-cli deploy
```
Komut, `pyproject.toml` dosyasındaki `deployment_target` yapılandırmasını okur, konteyneri derler, Artifact Registry'ye yükler ve Agent Runtime üzerinde başlatır.

#### D. Gözlemlenebilirlik ve Telemetri Altyapısı (Opsiyonel)
```powershell
agents-cli infra single-project
```
İstem-yanıt loglama ve içerik audit telemetrisi altyapısını otomatik ayağa kaldırır.

### 4.5. Dağıtılan Ajanı Test Etme ve Doğrulama

Agent Runtime üzerinde dağıtılan ajanlar Cloud Console, REST API veya Vertex AI Python SDK üzerinden test edilir.

#### A. Cloud Console Arayüzü
- **Adres:** `https://console.cloud.google.com/vertex-ai/agents/agent-engines`
- Tüm deployed reasoning engine örnekleri listelenir, metrikler, oturumlar ve Cloud Logging çıktıları doğrudan incelenebilir.

#### B. Bağlantı ve Kimlik Doğrulama Ön Testi (Connection Check)
Ajan metodunu çalıştırmadan önce uç nokta erişimini ve IAM izinlerini `:query` eki olmadan test edin:
```powershell
curl -X GET `
  -H "Authorization: Bearer $(gcloud auth print-access-token)" `
  "https://${LOCATION_ID}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION_ID}/reasoningEngines"
```
> [!NOTE]
> Express Mode yapılandırmalarında OAuth Bearer token yerine `-H "x-goog-api-key: $GEMINI_API_KEY"` başlığı kullanılabilir.

#### C. REST API ile İki Adımlı Oturum ve Akış Protokolü
Agent Runtime üzerindeki ajanlarla etkileşim iki adımlı asenkron bir protokole dayanır:

1. **Adım 1: Oturum Oluşturma (`async_create_session`)**
   ```powershell
   curl -X POST `
     -H "Authorization: Bearer $(gcloud auth print-access-token)" `
     -H "Content-Type: application/json" `
     -d '{"class_method": "async_create_session", "input": {"user_id": "user_123"}}' `
     "https://${LOCATION_ID}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION_ID}/reasoningEngines/${RESOURCE_ID}:query"
   ```
   Dönen JSON yanıtındaki `.output.id` değeri bir sonraki adımda `session_id` olarak kullanılır.

2. **Adım 2: Akışlı Sorgu Gönderme (`async_stream_query`)**
   ```powershell
   curl -X POST `
     -H "Authorization: Bearer $(gcloud auth print-access-token)" `
     -H "Content-Type: application/json" `
     -d '{
       "class_method": "async_stream_query",
       "input": {
         "user_id": "user_123",
         "session_id": "'"$SESSION_ID"'",
         "message": "Merhaba, bugünkü görevlerimi listeler misin?"
       }
     }' `
     "https://${LOCATION_ID}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION_ID}/reasoningEngines/${RESOURCE_ID}:streamQuery?alt=sse"
   ```
   Yanıt Server-Sent Events (SSE) formatında parça parça akar.

#### D. Vertex AI Python SDK ile Test
Python ortamlarında `vertexai.agent_engines` kütüphanesi ile asenkron test yürütülür:
```python
import asyncio
import vertexai

vertexai.init(project="PROJECT_ID", location="LOCATION_ID")

async def main():
    # Dağıtılmış ajan örneğini bağlama
    remote_app = vertexai.agent_engines.get(
        "projects/PROJECT_ID/locations/LOCATION_ID/reasoningEngines/RESOURCE_ID"
    )

    # 1. Asenkron oturum başlatma
    session = await remote_app.async_create_session(user_id="user_123")
    session_id = session["id"]
    print(f"Oturum açıldı: {session_id}")

    # 2. Asenkron akışlı sorgulama
    async for event in remote_app.async_stream_query(
        user_id="user_123",
        session_id=session_id,
        message="Sistem mimarisini özetle.",
    ):
        print(event, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

#### E. Çok Modlu (Multimodal) Girdiler ve GCS URI Kuralı
> [!IMPORTANT]
> Yerel ADK sunucusu gömülü base64 verilerini desteklerken, Agent Runtime üretim ortamında yüksek boyutlu görseller ve belgeler için **Google Cloud Storage (`gs://`) URI**'ları kullanılmalıdır:

```python
from google.genai import types

image_part = types.Part.from_uri(
    file_uri="gs://my-bucket/architecture-diagram.png",
    mime_type="image/png",
)

async for event in remote_app.async_stream_query(
    user_id="user_123",
    session_id=session_id,
    message=[image_part, "Bu mimari diyagramdaki darboğazları analiz et."],
):
    print(event)
```

#### F. Test Sonrası Kaynak Temizliği (Teardown)
Test veya deneme ortamı tamamlandığında gereksiz maliyet oluşmasını engellemek için kaynağı silin:
- **Python SDK:**
  ```python
  # force=True parametresi tüm oturum ve alt verileriyle birlikte kaynağı kaldırır:
  remote_app.delete(force=True)
  ```
- **gcloud CLI:**
  ```powershell
  gcloud ai reasoning-engines delete ${RESOURCE_ID} `
    --project=${PROJECT_ID} `
    --location=${LOCATION_ID} `
    --quiet
  ```

---

## 5. Google Kubernetes Engine (GKE) Dağıtımı

GKE, ADK ajanlarının kurumsal Kubernetes kümelerinde otomatik ölçekleme, yüksek erişilebilirlik ve özel ağ izolasyonu ile çalıştırılmasını sağlar (Python ve Go desteklenir).

### 5.1. Ön Koşullar & Gerekli API'ler
- **Gerekli Araçlar:** `gcloud`, `kubectl`.
- **GCP API'leri:**
  ```powershell
  gcloud services enable container.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com
  ```
- **Cloud Build Servis Hesabı İzinleri:**
  ```powershell
  $ROLES = @("roles/artifactregistry.writer", "roles/storage.objectViewer", "roles/logging.logWriter")
  foreach ($role in $ROLES) {
    gcloud projects add-iam-policy-binding $env:GOOGLE_CLOUD_PROJECT `
      --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" `
      --role=$role
  }
  ```

### 5.2. Workload Identity Yapılandırması (Kritik)
Ajanların Vertex AI / Agent Platform modellerine güvenli erişimi için Kubernetes Service Account (KSA) ile GCP IAM eşlemesi zorunludur:

- **Otomatik Dağıtımda (`adk deploy gke`):** CLI aracı manifestlerde `default` KSA'yı kullandığından doğrudan `default` hesabına izin verilir:
  ```powershell
  gcloud projects add-iam-policy-binding projects/$env:GOOGLE_CLOUD_PROJECT `
    --role="roles/aiplatform.user" `
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$($env:GOOGLE_CLOUD_PROJECT).svc.id.goog/subject/ns/default/sa/default"
  ```
  > [!CAUTION]
  > Bu adım atlanırsa podlar başarıyla ayağa kalksa dahi ilk LLM isteğinde `403 PERMISSION_DENIED` hatası alınır.

- **Manuel Dağıtımda Özel KSA:**
  ```powershell
  kubectl create serviceaccount adk-agent-sa
  gcloud projects add-iam-policy-binding projects/$env:GOOGLE_CLOUD_PROJECT `
    --role="roles/aiplatform.user" `
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$($env:GOOGLE_CLOUD_PROJECT).svc.id.goog/subject/ns/default/sa/adk-agent-sa"
  ```

### 5.3. Yöntem 1: `adk deploy gke` ile Otomatik Dağıtım (Sadece Python)
Python ajanları için ADK CLI; derleme, imaj yükleme ve manifest uygulama adımlarını otomatik yürütür:
```powershell
adk deploy gke `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --cluster_name="adk-cluster" `
  --region=$env:GOOGLE_CLOUD_LOCATION `
  --service_type="LoadBalancer" `
  --with_ui `
  --log_level="info" `
  path/to/my_agent
```
- `--service_type`: Varsayılan `ClusterIP`'dir (dahili). Dış dünyaya açmak için `LoadBalancer` seçilmelidir.
- Test için port yönlendirme:
  ```powershell
  kubectl port-forward svc/adk-default-service-name 8080:80
  ```

### 5.4. Yöntem 2: Manuel Kubernetes Manifestleri ile Dağıtım (Python & Go)

#### A. Go için Distroless Çok Aşamalı Dockerfile
Go statik ikili olarak derlendiğinden minimal `gcr.io/distroless/static-debian12` tabanı ile güvenli ve hafif paketlenir:
```dockerfile
# Aşama 1: Derleme
FROM golang:1.25 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o capital_agent .

# Aşama 2: Distroless Çalışma Zamanı
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/capital_agent /app/capital_agent
EXPOSE 8080
CMD ["/app/capital_agent", "web", "-port", "8080", "api", "webui"]
```

#### B. Kubernetes Manifesti (`deployment.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adk-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: adk-agent
  template:
    metadata:
      labels:
        app: adk-agent
    spec:
      serviceAccountName: adk-agent-sa
      containers:
      - name: adk-agent
        image: LOCATION-docker.pkg.dev/PROJECT_ID/adk-repo/adk-agent:latest
        resources:
          limits: { cpu: "500m", memory: "128Mi" }
          requests: { cpu: "500m", memory: "128Mi" }
        ports:
        - containerPort: 8080
        env:
        - name: PORT
          value: "8080"
        - name: GOOGLE_CLOUD_PROJECT
          value: "PROJECT_ID"
        - name: GOOGLE_CLOUD_LOCATION
          value: "LOCATION"
        - name: GOOGLE_GENAI_USE_ENTERPRISE
          value: "true"
---
apiVersion: v1
kind: Service
metadata:
  name: adk-agent
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: adk-agent
```
Uygulamak için:
```powershell
kubectl apply -f deployment.yaml
```

### 5.5. GKE Ajanını Test Etme & Diller Arası REST Farkları
Harici IP edinme:
```powershell
$env:APP_URL = "http://" + (kubectl get svc adk-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
```

> [!IMPORTANT]
> **Python vs Go REST Farklılıkları:**
> - **API Path Prefix:** Go ADK sunucusu uç noktaları varsayılan olarak `/api` ön ekiyle sunar (`$APP_URL/api/list-apps`, `$APP_URL/api/run_sse`). Python doğrudan kökten sunar (`$APP_URL/list-apps`, `$APP_URL/run_sse`).
> - **JSON İsimlendirme:** Python REST API `snake_case` (`app_name`, `user_id`, `new_message`) beklerken; Go REST API `camelCase` (`appName`, `userId`, `newMessage`) bekler.

**Python Sorgulama:**
```powershell
curl -X POST "$env:APP_URL/run_sse" `
  -H "Content-Type: application/json" `
  -d '{"app_name": "capital_agent", "user_id": "u1", "session_id": "s1", "new_message": {"role": "user", "parts": [{"text": "Merhaba"}]}, "streaming": false}'
```

**Go Sorgulama:**
```powershell
curl -X POST "$env:APP_URL/api/run_sse" `
  -H "Content-Type: application/json" `
  -d '{"appName": "capital_agent", "userId": "u1", "sessionId": "s1", "newMessage": {"role": "user", "parts": [{"text": "Merhaba"}]}, "streaming": false}'
```

### 5.6. Sık Karşılaşılan Sorunlar ve Çözümleri (Troubleshooting)
- **403 PERMISSION_DENIED:** KSA Workload Identity ataması eksiktir. Kümeyi inceleyin ve Bölüm 5.2'deki IAM bağlamasını yapın.
- **`sqlite3.OperationalError: attempt to write a readonly database`:** Yerel çalıştırma sırasında üretilen `sessions.db` imaj derlenirken container içine kopyalandığında salt-okunur olur. Çözüm: Proje köküne `.dockerignore` ekleyip içine `sessions.db` yazın veya derlemeden önce silin.
- **Dev UI Live API Ses Hatası (`ConnectionClosedError`):** Ajan `gemini-flash-latest` gibi Live API desteklemeyen bir modelle yapılandırıldığında mikrofona basılması hataya yol açar. Çift yönlü ses için Live API destekli modeller gereklidir.

### 5.7. Kaynak Temizliği (Teardown)
```powershell
gcloud container clusters delete adk-cluster --location=$env:GOOGLE_CLOUD_LOCATION --quiet
gcloud artifacts repositories delete adk-repo --location=$env:GOOGLE_CLOUD_LOCATION --quiet
```


