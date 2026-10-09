---
title: "ADK Model Context Protocol (MCP) Integration & Server Guide"
description: "Comprehensive architectural guide for consuming external MCP servers via McpToolset, exposing ADK agents as MCP servers via to_mcp_server, and multi-tier AgentTool delegation."
category: integrations
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - model-context-protocol
  - agenttool
  - stdio
  - streamable-http
  - sse
  - resources
  - integrations
---

# ADK Model Context Protocol (MCP) Entegrasyon ve Sunucu Mimarisi Rehberi

Model Context Protocol (MCP), yapay zekâ modellerinin harici veri kaynakları, dosya sistemleri, API'lar ve geliştirici araçları ile standartlaştırılmış açık bir protokol üzerinden iletişim kurmasını sağlar. 

Google ADK (Agent Development Kit), çift yönlü birinci sınıf MCP desteği sunar:
1. **MCP Client (`McpToolset`):** Dış dünyadaki herhangi bir MCP sunucusunun sunduğu araçları (`tools`) ve kaynakları (`resources`) tüketir.
2. **MCP Server (`to_mcp_server`):** Geliştirdiğiniz bir ADK ajanını Claude Code, Cursor, Windsurf veya harici LLM hostlarının çağırabileceği bağımsız bir MCP Server olarak dış dünyaya sunar.
3. **Specialized Sub-Agent Delegation (`AgentTool`):** Geniş MCP araç havuzlarının ana ajanın bağlam penceresini şişirmesini (`context bloat`) önler ve model katmanlaması (`Model Tiering`) sağlar.

---

## 1. Kurulum ve Sistem Bağımlılıkları

ADK'nın MCP yetenekleri opsiyonel bir bağımlılık paketi olarak sunulur:

```bash
# Python ADK MCP eklentisi
pip install "google-adk[mcp]"

# uv ile proje bağımlılığı ekleme
uv add "google-adk[mcp]"
```

> [!IMPORTANT]
> Yerel Stdio tabanlı MCP sunucuları (örneğin `@modelcontextprotocol/server-filesystem` gibi Node/TypeScript paketleri) çalıştırılacaksa, sistemde **Node.js (v18+)** ve `npx` komutunun kurulu ve `PATH` üzerinde erişilebilir olması gerekir.

---

## 2. Üç Temel MCP Entegrasyon Modeli

```mermaid
graph TD
    subgraph Pattern 1: Direct Integration
        A1[LlmAgent] -->|tools=[McpToolset]| B1[External MCP Server]
    end

    subgraph Pattern 2: Agent as MCP Server
        C2[External Client / IDE / Claude Code] -->|MCP Protocol / Stdio or SSE| D2[ADK Agent exposed via to_mcp_server]
    end

    subgraph Pattern 3: Sub-Agent Delegation
        E3[Root Agent - Pro Model] -->|AgentTool| F3[MCP Specialist Sub-Agent - Flash Model]
        F3 -->|tools=[McpToolset]| G3[External Large MCP Server]
    end
```

### Pattern 1: Doğrudan MCP İstemcisi (`McpToolset`)
En basit modeldir. Harici MCP sunucusundaki araçlar doğrudan ana ajana atanır:

```python
import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp import McpToolset, StdioConnectionParams, StdioServerParameters

# Stdio üzerinden yerel bir MCP sunucusuna bağlanma
fs_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "./data"],
            env={"NODE_ENV": "production"}
        )
    ),
    tool_filter=["read_file", "list_directory"] # En az yetki prensibi
)

agent = LlmAgent(
    name="file_analyst",
    model="gemini-2.5-flash",
    instruction="Analiz edilecek dosyaları MCP araçlarını kullanarak inceleyin.",
    tools=[fs_mcp_toolset]
)
```

---

### Pattern 2: ADK Ajan ve Araçlarını MCP Sunucusu Olarak Dışa Açma (`agent-as-server`)

ADK yeteneklerinizi harici MCP istemcilerine (Antigravity, Claude Code, Cursor, Windsurf veya harici LLM hostları) sunmak için iki temel yaklaşım bulunur:

#### Yaklaşım A: Tüm Ajanı Sunma (`to_mcp_server` - FastMCP)
Ajanın çok turlu akıl yürütmesini, planlamasını ve dahili araç yürütme zincirini tek bir satırla standart bir FastMCP sunucusuna dönüştürür:

```python
from google.adk.agents import LlmAgent
from google.adk.tools.load_web_page import load_web_page
from google.adk.tools.mcp_tool import to_mcp_server

# 1. ADK ajanını tanımla
agent = LlmAgent(
    model="gemini-2.5-flash",
    name="web_reader_agent",
    instruction="Web sayfalarını getiren ve kullanıcı için özetleyen uzman ajan.",
    tools=[load_web_page],
)

# 2. Ajanı doğrudan MCP sunucusuna dönüştür (FastMCP)
app = to_mcp_server(agent)

if __name__ == "__main__":
    # Standart Stdio MCP sunucusu olarak çalıştır
    app.run()
```

#### Yaklaşım B: Bağımsız ADK Araçlarını Düşük Seviyeli Sunucu ile Sunma
Modelin bilişsel akıl yürütme döngüsü olmadan, yalnızca belirli bağımsız ADK araçlarını (`FunctionTool` vb.) standart MCP sunucusu olarak dışa açmak için düşük seviyeli `Server` ve ADK şema dönüştürücüsü kullanılır:

```python
import asyncio
import json
from dotenv import load_dotenv

# MCP Düşük Seviye Sunucu
from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio

# ADK Araç ve Şema Dönüştürme
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.load_web_page import load_web_page
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

load_dotenv()

# 1. Dışa açılacak ADK aracını hazırla
adk_tool_to_expose = FunctionTool(load_web_page)

# 2. Düşük seviyeli MCP sunucusunu başlat
app = Server("adk-tool-exposing-mcp-server")

# 3. Araç listesi işleyicisi (ADK şemasını MCP şemasına dönüştürür)
@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    mcp_tool_schema = adk_to_mcp_tool_type(adk_tool_to_expose)
    return [mcp_tool_schema]

# 4. Araç çağırma işleyicisi
@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    if name == adk_tool_to_expose.name:
        try:
            # ADK aracını çalıştır (tool_context=None)
            adk_tool_response = await adk_tool_to_expose.run_async(
                args=arguments,
                tool_context=None,
            )
            return [mcp_types.TextContent(type="text", text=json.dumps(adk_tool_response, indent=2))]
        except Exception as e:
            return [mcp_types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
    return [mcp_types.TextContent(type="text", text=json.dumps({"error": f"Tool '{name}' not found."}))]

# 5. Stdio sunucu yürütücüsü
async def run_mcp_stdio_server():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(run_mcp_stdio_server())
```

---

#### Özel Sunucuyu ADK İstemcisi ile Test Etme
Geliştirdiğiniz özel MCP sunucusunu test etmek için istemci rolünde bir test ajanı kullanılır:

```python
import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, StdioServerParameters

MCP_SERVER_SCRIPT = os.path.abspath("./my_adk_mcp_server.py")

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="web_reader_mcp_client_agent",
    instruction="Web sayfalarını getirmek için sunulan aracı kullanın.",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python3",
                    args=[MCP_SERVER_SCRIPT],
                )
            )
        )
    ],
)
```
Terminalden `adk web` başlatılarak web arayüzünden uçtan uca test edilir.

---

#### Google Cloud Genmedia MCP Ekosistemi
Google Cloud, üretken medya modellerini MCP üzerinden entegre eden açık kaynaklı sunucular sunar:
- **Imagen:** Görsel üretimi ve görsel düzenleme.
- **Veo:** Yüksek çözünürlüklü video üretimi.
- **Chirp 3 HD Voices:** Doğal ses sentezleme ve çok dilli ses üretimi.
- **Lyria:** Müzik ve ses kompozisyonu.

ADK ve Genkit, bu Genmedia MCP sunucularını doğrudan tüketerek ajanların çok modlu (multimodal) medya iş akışlarını koordine etmesini sağlar.


---

### Pattern 3: Uzman Alt-Ajan Delegasyonu (`AgentTool` ile MCP Yönetimi)

Büyük kurumsal MCP sunucuları (örn. Google Cloud, GitHub, PostgreSQL, Jira, Salesforce) 20-50'den fazla araç dönebilir. Bunların tamamını doğrudan ana orkestratör ajana bağlamak iki ciddi soruna yol açar:
1. **Context Bloat & Dikkat Kaybı:** Onlarca aracın şeması ve ara JSON yanıtları ana modelin penceresini doldurur, akıl yürütme kalitesini düşürür.
2. **Maliyet ve Gecikme:** Her adımda büyük ve pahalı bir orkestratör model (`gemini-2.5-pro`) tetiklenir.

#### Mimari Rol ve Araç Adaptasyonu
ADK mimarisinde `AgentTool`, bir `LlmAgent`'ı ana ajan için yerel bir `BaseTool` olarak sarmalar. Alt ajan ise araçları `McpToolset` üzerinden tüketir:
- `McpToolset`, MCP sunucusuna bağlanarak (`list_tools`) harici MCP araç şemalarını ADK uyumlu `BaseTool` nesnelerine dönüştürür.
- Tüm yürütme çağrılarını (`call_tool`) arka planda asenkron olarak vekalet eder (proxy).
- Alt ajanın ara araç adımları ve ham JSON çıktıları alt ajanın çalışma belleğinde izole kalır; ana orkestratöre sadece konsolide edilmiş nihai analiz sonucu döner.

```python
import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, StdioServerParameters

# 1. MCP Bağlantısını Yapılandır
db_mcp_connection = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", "postgres://user:pass@localhost:5432/db"],
    )
)

# 2. Bilişsel Kapsam ve Güvenlik Filtresi ile Alt Uzman Ajanı Oluştur (Flash Model)
database_sub_agent = LlmAgent(
    name="database_specialist",
    model="gemini-2.5-flash",
    instruction="Veritabanı sorguları ve şema analizinde uzman ajansınız. Yalnızca salt okunur sorguları çalıştırın.",
    tools=[
        McpToolset(
            connection_params=db_mcp_connection,
            tool_filter=["query_db", "list_tables", "describe_table"], # Bilişsel Odak & Sandboxing
        )
    ],
)
database_tool = AgentTool(agent=database_sub_agent, skip_summarization=False)

# 3. Ana Orkestratör Ajanı Tanımla (Pro Model)
root_orchestrator = LlmAgent(
    name="primary_orchestrator",
    model="gemini-2.5-pro",
    instruction="Kullanıcı gereksinimlerini planlayan lider mimarsınız. Veritabanı sorgu ve analiz işlerini database_tool uzmanına delege edin.",
    tools=[database_tool],
)
```

---

#### Bilişsel Kapsam ve Güvenlik Filtreleme (`tool_filter`)
Alt ajana `McpToolset` atanırken `tool_filter` kullanımı iki temel fayda sağlar:
- **Bilişsel Odak (Cognitive Focus):** Modelin dikkat penceresine sadece alt ajanın uzmanlık alanına giren araçlar (`query_db`, `list_tables`) sunulur; alakasız araçlar gizlenerek akıl yürütme isabeti artırılır.
- **Güvenlik Kum Havuzu (Security Sandboxing):** MCP sunucusunun sunduğu tehlikeli, yıkıcı veya yetki dışı fonksiyonlara (örn. `drop_database`, `exec_shell`) erişim tamamen engellenerek saldırı yüzeyi izole edilir.

---

#### Oturum Kalıcılığı ve Dinamik Soket Restorasyonu
Çoklu ajan sistemlerinin üretim ortamlarında kesintisiz çalışması için oturum ve soket yönetimi kuralları:
- **Serileştirme (`getstate` / `setstate`):** `McpToolset`, ADK oturum serileştirmesini tam olarak destekler. Oturum durumu (`state`), konuşma geçmişi ve araç yürütme kayıtları oturum veritabanında saklanır.
- **Dinamik Soket Restorasyonu:** Konteyner yeniden başladığında veya oturum başka bir çalışma zamanında devam ettirildiğinde (`resume`), kapatılmış olan TCP soketleri veya Stdio subprocess bağlantıları `McpToolset` tarafından **otomatik ve dinamik olarak yeniden kurulur**.
- **Senkron Başlatma Zorunluluğu:** Cloud Run, GKE ve Agent Engine gibi üretim ortamlarında hem alt ajan hem de `McpToolset` `agent.py` içinde kesinlikle **senkron** tanımlanmalıdır.


---

## 3. Bağlantı Taşıma Tipleri (Transports)

ADK iki ana bağlantı protokolünü destekler:

### A. Stdio Transport (Yerel Süreç İletişimi)
Yerel geliştirme, CLI araçları ve subprocess yönetimi için kullanılır. Standart girdi/çıktı (stdin/stdout) üzerinden JSON-RPC mesajlaşması yapar.

```python
from google.adk.tools.mcp import StdioConnectionParams, StdioServerParameters

stdio_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command="python",
        args=["-m", "my_custom_mcp_server"],
        env={"CUSTOM_KEY": "value"}
    ),
    timeout=30.0 # Bağlantı zaman aşımı (saniye)
)
```

### B. Streamable HTTP & SSE Transport (Uzak Mikroservisler)
Uzak bir sunucuda, Docker container'ında veya Cloud Run üzerinde çalışan MCP sunucularına ağ üzerinden bağlanmak için kullanılır.

```python
from google.adk.tools.mcp import StreamableHTTPConnectionParams, SseConnectionParams

# Streamable HTTP (Modern MCP standardı)
http_params = StreamableHTTPConnectionParams(
    url="https://mcp-gateway.company.internal/v1/mcp",
    headers={
        "Authorization": "Bearer sk-mcp-internal-token",
        "X-Tenant-ID": "tenant-corp-42"
    }
)

# SSE (Server-Sent Events) Transport
sse_params = SseConnectionParams(
    url="https://api.example.com/sse",
    headers={"Authorization": "Bearer token"}
)

remote_toolset = McpToolset(connection_params=http_params)
```

---

## 4. MCP Kaynakları (Resources) Desteği

MCP yalnızca çalıştırılabilir fonksiyonları (`tools`) değil, aynı zamanda statik veya yarı-dinamik veri kaynaklarını (`resources`) da tanımlar (örneğin dosya içerikleri, veritabanı şemaları, sistem logları).

ADK, MCP kaynaklarını iki şekilde yönetir:

### A. Programatik Erişim
```python
# Mevcut kaynakları listeleme
resources = await remote_toolset.list_resources()
for res in resources:
    print(f"URI: {res.uri}, Name: {res.name}, MimeType: {res.mimeType}")

# Belirli bir kaynağın içeriğini okuma
resource_content = await remote_toolset.read_resource("file:///workspace/schema.sql")
```

### B. `use_mcp_resources=True` ile Ajan Entegrasyonu
`McpToolset` oluşturulurken `use_mcp_resources=True` parametresi verildiğinde, ADK ajana otomatik olarak yerleşik `LoadMcpResourceTool` aracını ekler:

```python
resource_toolset = McpToolset(
    connection_params=http_params,
    use_mcp_resources=True # Ajana LoadMcpResourceTool enjekte eder
)

agent = LlmAgent(
    name="data_doc_agent",
    model="gemini-2.5-flash",
    instruction="İhtiyaç duyduğunuz veritabanı şemalarını LoadMcpResourceTool kullanarak okuyun.",
    tools=[resource_toolset]
)
```
Model bir kaynağa ihtiyaç duyduğunda ilgili URI'yi geçirerek otomatik olarak içeriği çeker.

---

## 5. Güvenlik, Doğrulama ve En Az Yetki Prensibi (Least Privilege)

Harici MCP sunucuları geniş ve potansiyel olarak riskli komutlar (dosya silme, DB drop, harici web çağrıları) sunabilir. Güvenliği sağlamak için 3 kural uygulanmalıdır:

1. **`tool_filter` ile Yalnızca Gerekli Araçları İzin Verme:**
   ```python
   toolset = McpToolset(
       connection_params=params,
       tool_filter=["list_files", "search_docs"] # write_file veya delete_file engellenir
   )
   ```
2. **`before_tool_callback` ile Parametre Denetimi:**
   MCP aracına iletilen argümanlar ajanın çalıştırıcısı tarafından araya girilerek filtrelenebilir:
   ```python
   def validate_mcp_args(tool_name: str, args: dict, context):
       if tool_name == "read_file":
           path = args.get("path", "")
           if not path.startswith("/safe/directory/"):
               raise PermissionError(f"Erişim engellendi: {path} güvenli dizin dışında!")
       return args
   ```
3. **Onay Mekanizması (HITL):**
   Kritik MCP eylemleri için `require_confirmation` kuralı uygulanmalıdır (`references/adk-custom-tools-guide.md`).

---

## 6. Üretim Dağıtım Mimarisi (Cloud Run, Agent Runtime & GKE)

MCP araçları kullanan ADK ajanlarını dağıtırken dikkat edilmesi gereken en kritik mimari kurallar ve üretim kalıpları aşağıdadır:

### Kritik Dağıtım Kuralı: `agent.py` İçinde Kesinlikle Senkron Tanım

> [!WARNING]
> **Asenkron Ajan Fabrikaları Dağıtımda Çalışmaz:** `adk web` yerel testlerde asenkron ajan oluşturmaya izin verse de, **Agent Engine**, **Cloud Run** ve **GKE** çalışma zamanları modül yükleme anında ajanın ve `McpToolset`'in **senkron** olarak tanımlanmasını zorunlu kılar.

```python
# DOĞRU: Dağıtım için senkron kök ajan tanımı
import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, StdioServerParameters

_allowed_path = os.path.dirname(os.path.abspath(__file__))

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="enterprise_assistant",
    instruction=f"İzin verilen dizindeki dosyalara erişin: {_allowed_path}",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", _allowed_path],
                ),
                timeout=5,
            ),
            tool_filter=[
                "read_file", "read_multiple_files", "list_directory",
                "directory_tree", "search_files", "get_file_info"
            ],
        )
    ],
)
```

```python
# YANLIŞ: Asenkron kalıplar üretim dağıtımında çöker
async def get_agent():  # Bu fonksiyon dağıtım ortamında ÇALIŞMAZ!
    toolset = await create_mcp_toolset_async()
    return LlmAgent(tools=[toolset])
```

---

### Hızlı Dağıtım Komutları (CLI)

```bash
# 1. Agent Runtime (Agent Engine / Vertex AI) Dağıtımı
uv run adk deploy agent_engine \
  --project="my-gcp-project" \
  --region="us-central1" \
  --display_name="Enterprise MCP Agent" \
  ./path/to/agent_directory

# 2. Cloud Run Konteyner Dağıtımı
uv run adk deploy cloud_run \
  --project="my-gcp-project" \
  --region="us-central1" \
  --service_name="enterprise-mcp-agent" \
  ./path/to/agent_directory
```

---

### Üç Üretim Dağıtım Deseni

```mermaid
graph TD
    subgraph Desen 1: Self-Contained Stdio
        C1[Container: Python + Node.js] -->|stdio npx| S1[MCP Subprocess Filesystem]
    end

    subgraph Desen 2: Remote Streamable HTTP
        A2[Cloud Run: ADK Agent Service] -->|HTTPS Streamable| M2[Cloud Run: Stateless Starlette MCP Service]
    end

    subgraph Desen 3: GKE Sidecar
        subgraph Kubernetes Pod
            K_Agent[adk-agent:8080] -->|localhost:8081| K_Sidecar[mcp-server:8081]
        end
    end
```

#### Desen 1: Bağımsız Stdio Konteyneri (Self-Contained Dockerfile)
NPM tabanlı (örn. `@modelcontextprotocol/server-filesystem`) veya yerel Python modülü şeklindeki MCP araçları tek bir konteyner imajında paketlenebilir. Hem Python hem Node.js/npm kurulmalıdır:

```dockerfile
# Dockerfile - NPM ve Python MCP ajanı tek konteynerde
FROM python:3.13-slim

# Node.js ve npm kurulumu
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# npx subprocess yerel olarak konteyner içinde çalıştırılır
CMD ["python", "main.py"]
```

#### Desen 2: Bağımsız Uzak Streamable HTTP Mikroservisi (Cloud Run)
Yüksek trafik ve ölçeklenebilirlik gerektiren kurumsal sistemlerde MCP sunucusu ayrı bir Cloud Run servisi olarak barındırılır. Sunucu tarafında `StreamableHTTPSessionManager(stateless=True)` ve Starlette ASGI kullanılır:

```python
# deploy_mcp_server.py - Bağımsız Cloud Run MCP Mikroservisi
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
import uvicorn

app = Server("enterprise-streamable-mcp")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query_customer_crm",
            description="Müşteri CRM profilini sorgular.",
            inputSchema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
    if name == "query_customer_crm":
        cid = arguments.get("customer_id")
        return [types.TextContent(type="text", text=f"Müşteri {cid} Profili: VIP, Aktif")]
    raise ValueError(f"Bilinmeyen araç: {name}")

# Cloud Run ölçeklenebilirliği için stateless=True ZORUNLUDUR
session_manager = StreamableHTTPSessionManager(app=app, event_store=None, stateless=True)

async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)

@contextlib.asynccontextmanager
async def lifespan(starlette_app: Starlette) -> AsyncIterator[None]:
    async with session_manager.run():
        yield

starlette_app = Starlette(
    routes=[Mount("/mcp", app=handle_streamable_http)],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(starlette_app, host="0.0.0.0", port=8080)
```

**ADK Ajanı Bağlantısı:**
```python
McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp-crm-service.run.app/mcp",
        headers={"Authorization": "Bearer sk-corp-internal-token"}
    )
)
```

#### Desen 3: Kubernetes Sidecar Deseni (GKE)
GKE ortamlarında MCP sunucusu pod içinde ayrı bir yan konteyner (sidecar) olarak çalıştırılarak ağ gecikmesi sıfırlanır:

```yaml
# deployment.yaml - GKE MCP Sidecar Deseni
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adk-agent-with-mcp
spec:
  template:
    spec:
      containers:
      # Ana ADK ajan konteyneri
      - name: adk-agent
        image: gcr.io/my-proj/adk-agent:latest
        ports:
        - containerPort: 8080
        env:
        - name: MCP_SERVER_URL
          value: "http://localhost:8081/mcp"

      # MCP sunucu sidecar konteyneri
      - name: mcp-server
        image: gcr.io/my-proj/mcp-server:latest
        ports:
        - containerPort: 8081
```

---

### Çoklu Dil İstemci Desteği (Java & Kotlin)

ADK, Python dışında Java ve Kotlin dillerinde de Streamable HTTP MCP entegrasyonu sunar:

**Java:**
```java
import java.util.Map;
import com.google.adk.tools.mcp.StreamableHttpServerParameters;
import com.google.adk.tools.mcp.McpToolset;

StreamableHttpServerParameters params = StreamableHttpServerParameters.builder()
        .url("https://mcp-service.run.app/mcp")
        .headers(Map.of("Authorization", "Bearer your-token"))
        .build();

McpToolset toolset = new McpToolset(params);
```

**Kotlin:**
```kotlin
import com.google.adk.kt.tools.mcp.McpConnectionParameters
import com.google.adk.kt.tools.mcp.McpToolset

val toolset = McpToolset.McpToolsetConfig(
    streamableHttpConnectionParams = McpConnectionParameters.StreamableHttp(
        url = "https://mcp-service.run.app/mcp",
    ),
).toToolset(headerProvider = { mapOf("Authorization" to "Bearer ${fetchToken()}") })
```

---

### Üretim Ortamı Güvenlik ve Kaynak Kılavuzu

1. **Mutlak ve Kısıtlanmış Dosya Yolları:** Filesystem MCP sunucularında dizin geçişlerini (directory traversal) engellemek için her zaman `os.path.dirname(os.path.abspath(__file__))` veya güvenli mutlak dizinler atanmalıdır.
2. **Konteyner Kaynak Limitleri:** Stdio bağlantılarında her oturum işletim sistemi düzeyinde yeni bir alt süreç (`npx`/`python`) başlattığından, CPU ve RAM sınırları dikkatle belirlenmelidir. Yüksek trafikli sistemlerde Streamable HTTP mikroservis mimarisi tercih edilmelidir.
3. **Zaman Aşımları:** Ağ veya alt süreç kilitlenmelerini önlemek için `timeout=5` ve `sse_read_timeout=300` gibi açık zaman aşımı sınırları yapılandırılmalıdır.


---

## 7. Özet Karşılaştırma Matrisi

| Yetenek | Doğrudan MCP Client (`McpToolset`) | MCP Server (`to_mcp_server`) | Delegasyon (`AgentTool`) |
| :--- | :--- | :--- | :--- |
| **Rolü** | Harici MCP'yi Tüketen | Dışarıya Servis Sunan | Context İzole Eden Tüketici |
| **Kullanım Senaryosu** | Yerel dosya sistemi, GitHub vb. | Ajanı Claude Code / IDE'ye sunma | 20+ araçlı büyük kurumsal MCP'ler |
| **Model Dağılımı** | Tek model | Tek model | Hiyerarşik (Pro + Flash) |
| **Context Etkisi** | Tüm araç şemaları ana modelde | Dış host tarafından yönetilir | Ara adımlar izole, özet döner |
| **Desteklenen Taşıma** | Stdio, Streamable HTTP, SSE | Stdio, SSE | İç çağrı (In-process Python) |

---

## 8. Dinamik Kimlik Doğrulama ve Oturum Başlıkları (`header_provider`)

Çok kiracılı (multi-tenant) veya son kullanıcıya açık sistemlerde kimlik bilgilerini bağlantı parametrelerine sabit (hardcoded) yazmak güvensizdir. `McpToolset`, her araç çağrısında aktif `ReadonlyContext`'e erişerek dinamik başlıklar üreten senkron veya asenkron bir `header_provider` çağrılabilirini destekler:

```python
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

async def extract_per_user_headers(context: ReadonlyContext) -> dict[str, str]:
    """Her turda kullanıcı veya oturum bazlı JWT/OAuth token'ını dinamik enjekte eder."""
    user_token = context.state.get("user_access_token", "ANONYMOUS_TOKEN")
    return {
        "Authorization": f"Bearer {user_token}",
        "X-User-ID": context.user_id,
        "X-Session-ID": context.session.id,
    }

toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp-server.example.com/mcp",
        timeout=5,
        sse_read_timeout=300,
    ),
    header_provider=extract_per_user_headers,
)
```

---

## 9. Koşullu ve Fonksiyonel İnsan Onayı (`require_confirmation`)

MCP sunucuları veritabanı şeması değiştirme veya tablo silme gibi yüksek riskli işlemler barındırabilir. `require_confirmation` parametresine bir boolean veya araç argümanlarını dinamik olarak denetleyen bir yüklem (predicate) fonksiyonu verilebilir:

```python
def should_require_approval(query: str = "", **kwargs) -> bool:
    """Yıkıcı SQL komutları içeriyorsa kullanıcı onayı zorunlu kılınır."""
    query_str = str(query).lower()
    destructive_keywords = ["drop", "delete", "truncate", "alter", "update"]
    return any(keyword in query_str for keyword in destructive_keywords)

toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/db"],
        ),
        timeout=5,
    ),
    require_confirmation=should_require_approval,
)
```

---

## 10. Gerçek Zamanlı İlerleme Takibi (`progress_callback`)

Web scraping, indeksleme veya büyük SQL sorguları gibi uzun süren MCP operasyonları, ara ilerleme bildirimlerini `notifications/progress` kanalı üzerinden iletir.

### Seçenek A: Genel Geri Çağırma (Global Callback)
```python
async def on_mcp_progress(progress: float, total: float | None, message: str | None) -> None:
    percentage = (progress / total * 100) if total else progress
    print(f"[MCP İlerleme] %{percentage:.1f}: {message or 'İşleniyor...'}")

toolset = McpToolset(
    connection_params=...,
    progress_callback=on_mcp_progress,
)
```

### Seçenek B: Oturum Duyarlı Fabrika (Session-Aware Factory)
`ToolContext.state` nesnesine yazma yetkisi olan araç bazlı işleyiciler üretmek için `ProgressCallbackFactory` deseni kullanılır:

```python
from google.adk.tools.tool_context import ToolContext

def create_tool_progress_tracker(tool_name: str, callback_context: ToolContext, **kwargs):
    """Araç bazlı özel ilerleme işleyicisi üretir ve oturum durumunu günceller."""
    async def progress_handler(progress: float, total: float | None, message: str | None):
        callback_context.state[f"{tool_name}_status"] = message
        callback_context.state[f"{tool_name}_progress"] = progress
    return progress_handler

toolset = McpToolset(
    connection_params=...,
    progress_callback=create_tool_progress_tracker,
)
```

---

## 11. Bağımsız Çalışma Zamanı ve Kaynak Yönetimi (`Runner` + `await toolset.close()`)

Ajanları `adk web` dışında özel FastAPI mikroservislerinde, Celery worker'larında veya CLI script'lerinde çalıştırırken `Runner` örneği oluşturulmalı ve `finally` bloğu içinde `await toolset.close()` çağrılarak alt süreçlerin (subprocess) ve ağ soketlerinin zarifçe kapatılması sağlanmalıdır:

```python
import asyncio
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, StdioServerParameters

async def run_standalone_mcp_agent():
    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "./data"],
            ),
            timeout=5,
        ),
        tool_filter=["list_directory", "read_file"],
    )

    agent = LlmAgent(
        model="gemini-2.5-flash",
        name="filesystem_assistant",
        instruction="Dosya yönetiminde yardımcı olun.",
        tools=[toolset],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="standalone_app", user_id="user_001")
    runner = Runner(app_name="standalone_app", agent=agent, session_service=session_service)

    try:
        user_message = types.Content(
            role="user",
            parts=[types.Part(text="Dizindeki dosyaları listeleyin.")],
        )
        async for event in runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
    finally:
        # Alt süreçleri ve ağ bağlantılarını zarifçe sonlandır
        print("\nMCP bağlantısı kapatılıyor...")
        await toolset.close()

if __name__ == "__main__":
    asyncio.run(run_standalone_mcp_agent())
```

---

## 12. Ad Çakışması ve İsim Alanı Yönetimi (`tool_name_prefix`)

Aynı ajana birden fazla MCP sunucusu bağlandığında, `query`, `search` veya `list` gibi genel fonksiyon isimleri çakışabilir. `tool_name_prefix` parametresi ile otomatik ad alanı (namespacing) atanır:

```python
postgres_toolset = McpToolset(
    connection_params=...,
    tool_name_prefix="pg_",  # pg_query, pg_list_tables üretir
)

github_toolset = McpToolset(
    connection_params=...,
    tool_name_prefix="gh_",  # gh_search_repositories, gh_create_issue üretir
)
```

---

## 13. Çift Yönlü Protokol Kancaları: Sampling ve Elicitation

Model Context Protocol çift yönlü iletişimi destekler. MCP sunucusu istemciden (ADK) işlem talep edebilir:
- **Sampling (`sampling_callback`)**: MCP sunucusunun ADK'dan bir LLM tamamlama/üretim adımı talep etmesini sağlar.
- **Elicitation (`elicitation_callback`)**: MCP sunucusunun bant dışı kimlik doğrulama veya kullanıcı etkileşimi istemesini sağlar.

```python
from mcp import SamplingCapability
from google.adk.tools.mcp_tool import McpToolset

async def handle_server_sampling(params):
    """Sunucu tarafından tetiklenen LLM üretim isteklerini işler."""
    return {
        "role": "assistant",
        "content": {"type": "text", "text": "ADK tarafından üretilen yanıt"},
    }

async def handle_server_elicitation(params):
    """Sunucudan gelen etkileşim veya kimlik doğrulama zorluklarını yönetir."""
    print(f"Elicitation talebi alındı: {params}")
    return {"action": "approved"}

toolset = McpToolset(
    connection_params=...,
    sampling_callback=handle_server_sampling,
    sampling_capabilities=SamplingCapability(),
    elicitation_callback=handle_server_elicitation,
)
```

---

## 14. Tanılama ve STDERR Hata Akışları (`errlog`)

Varsayılan olarak MCP subprocess hataları standart hataya (stderr) yazılır. Kök neden analizi için hata akışı harici bir log dosyasına veya tanılama tamponuna yönlendirilebilir:

```python
error_file = open("mcp_server_errors.log", "a")
try:
    toolset = McpToolset(connection_params=..., errlog=error_file)
    # Ajanı çalıştır...
finally:
    await toolset.close()
    error_file.close()
```

---

## 15. Zengin ve Etkileşimli UI Bileşenleri (`meta.ui.resourceUri`)

Standart MCP araçları düz metin veya JSON dönerken, ADK gelişmiş arayüzlerde interaktif görsel widget'lar (harita, grafik, hava durumu kartı veya interaktif formlar) çizilmesine olanak tanır.

```mermaid
sequenceDiagram
    autonumber
    participant Tool as MCP Server Tool
    participant ADK as ADK Framework
    participant UI as Client UI (adk web / Frontend)

    Tool-->>ADK: Sonuç + metadata döner (meta.ui.resourceUri = "ui://widgets/map")
    ADK->>ADK: meta.ui.resourceUri etiketini algılar
    ADK-->>UI: UI render sinyali ve Resource URI olayını yayar
    UI->>Tool: Resource URI üzerinden UI paketini çeker
    UI-->>UI: Sohbet arayüzünde interaktif widget'ı çizer
```

### Sunucu Tarafı Tanımı
```python
from mcp import types as mcp_types
from mcp.server.lowlevel import Server

app = Server("weather-mcp-server")

@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    """Aracı kaydeder ve UI render metadata'sını ekler."""
    return [
        mcp_types.Tool(
            name="get_weather",
            description="Şehir için hava durumu tahminini getirir.",
            inputSchema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            meta={"ui": {"resourceUri": "ui://widgets/weather-card"}},
        )
    ]

@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    """Aracı yürütür ve veri içeriği döner."""
    city = arguments.get("city", "Bilinmeyen")
    return [
        mcp_types.TextContent(type="text", text=f"{city} için hava durumu: 22°C Güneşli")
    ]
```
`adk web` veya özel frontend bu sinyali yakaladığında metin yerine doğrudan interaktif hava durumu kartını ekrana yansıtır.

