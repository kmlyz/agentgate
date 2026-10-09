---
name: google-agents-cli
description: >-
  Google Agents CLI (agents-cli) ve Agent Development Kit (ADK) ile kurumsal
  seviyede ajan iskeleleme (scaffolding), FastAPI/Playground çalıştırma,
  değerlendirme (eval) ve Cloud Run dağıtım iş akışları rehberi.
---

# Google Agents CLI (agents-cli) & ADK İş Akışı

Bu yetenek, Antigravity ve Google ADK ile üretim seviyesinde ajan geliştirmek için kullanılır.

## 1. Kurulum ve Başlangıç
- Agents CLI ve ilgili ajan yeteneklerini kurmak için:
  ```powershell
  uvx google-agents-cli setup
  ```
- Bu komut `agents-cli` komutunu, ADK Python paketlerini ve kodlama ajanları için gerekli becerileri sisteme entegre eder.

## 2. ADK Temel Primitifleri (Core Concepts)
ADK mimarisi 13 temel kavram üzerine kuruludur:
- **Agent:** Temel işçi birimi; akıl yürüten `LlmAgent` veya deterministik akış yöneticileri (`SequentialAgent`, `ParallelAgent`, `LoopAgent`).
- **Tool:** Ajanın dış dünyayla konuşmasını sağlayan yetenekler (`FunctionTool`, `AgentTool`, kod yürütme, API entegrasyonu). Gelişmiş senaryolarda çalışma zamanı tarafından enjekte edilen `ToolContext` (`state_delta` kalıcılığı, `actions: skip_summarization, transfer_to_agent, escalate`) ve modüler `Toolset` (`ToolFilter`) ile yönetilir; REST servisleri için OpenAPI v3.x spesifikasyonlarından otomatik araç üreten `OpenAPIToolset` (`RestApiTool`) desteklenir (`references/adk-custom-tools-guide.md`). Yerleşik araçlar (`BuiltInCodeExecutor`, `GoogleSearchTool`, `VertexAiSearchTool`) karşılıklı dışlama kuralına tabidir; klasik `sub_agents` listesine verilemez, mutlaka `AgentTool(agent=...)` ile sarmalanmalıdır (arama araçlarında `bypass_multi_tools_limit=True` bayrağı hariç - `references/adk-custom-tools-guide.md`). Araç yetkilendirmesinde `AuthScheme`/`AuthCredential`, Cloud IAM ID Token (`use_id_token` + `audience`), hazır belirteç (`external_access_token_key`) ve etkileşimli OAuth/OIDC akışı (`adk_request_credential`) uygulanır (`references/adk-auth-guide.md`). Harici açık araç ekosistemleri için Model Context Protocol istemcisi (`McpToolset`), ajanı tek satırda FastMCP sunucusu yapan `to_mcp_server`, bağımsız araçları sunan `adk_to_mcp_tool_type`, hiyerarşik `AgentTool` delegasyonu (bilişsel `tool_filter` odaklaması, `getstate`/`setstate` oturum kalıcılığı ve dinamik soket restorasyonu), üretim kalıpları (dinamik `header_provider`, `tool_name_prefix`, `progress_callback`, `sampling_callback`, `meta.ui.resourceUri`) ve Google Cloud Genmedia MCP ekosistemi (Imagen, Veo, Chirp, Lyria) desteklenir (`references/adk-mcp-guide.md`).
- **Callbacks:** Ajanın yürütme döngüsüne 3 seviyede (Agent, Model, Tool) müdahale eden 8 kanca (`before_agent_callback`/`after_agent_callback`, `before_model_callback`/`after_model_callback`/`on_model_error_callback`, `before_tool_callback`/`after_tool_callback`/`on_tool_error_callback`). Agent kancaları tüm `BaseAgent` türevlerinde, model ve araç kancaları yalnızca `LlmAgent` üzerinde geçerlidir. Python'da argümanlar keyword ile geçirildiğinden parametre isimleri birebir eşleşmelidir (`callback_context`, `tool`, `args`, `tool_context`, `tool_response`). 8 resmi tasarım kalıbı (Guardrails, iki fazlı önbellekleme, `tool_context.actions.skip_summarization=True`, `tool_context.request_credential`, `save_artifact`/`load_artifact`, hata bastırma) ve `Event.actions.state_delta` üzerinden otomatik durum kalıcılığı sunar; kancalar yürütme döngüsünde bloklayıcı/inline çalıştığından I/O işlemleri `async def` ile tanımlanmalıdır (`references/adk-callbacks-guide.md`).
- **Session & State vs. Memory:** Konuşma bağlamının 3 temel sütunu: `Session`, kullanıcı ile ajan arasındaki tekil aktif konuşma ipliğini (`id`, `app_name`, `user_id`, `events`, `state`, `last_update_time`) temsil eder; `State` (`session.state`), o oturuma veya tura özgü çalışma belleği / scratchpad verisidir; `Memory` ise geçmiş oturumları ve harici bilgi kaynaklarını kapsayan aranabilir semantik arşivdir (`BaseMemoryService`). Durum yönetiminde 4 kapsam öneki (`temp:` çağrıya özel geçici ve alt ajanlara miras, `user:` kullanıcılar geneli kalıcı, `app:` uygulama geneli küresel, öneksiz oturuma özel) kullanılır; Python'da `get_user_state(app_name, user_id)` ile oturum açılmadan okunabilir (`VertexAiSessionService` hariç). Ajan talimatlarına doğrudan durum enjeksiyonu `{key}` ve opsiyonel `{key?}` ile yapılır; JSON formatlı metinler için `InstructionProvider` (`ReadonlyContext`) ve `instructions_utils.inject_session_state` kullanılır. Yanıtlar tek satırda `output_key` ile durum belleğine kaydedilir; kanca ve araçlarda durum `context.state` üzerinden değiştirilerek `Event.actions.state_delta` üretilir; context dışında doğrudan `session.state['x']=y` ataması veritabanı kalıcılığını bozduğu için kesinlikle yasaktır. Oturum yaşam döngüsü `SessionService` tarafından yönetilir: yerel test için `InMemorySessionService`, ilişkisel veritabanları için zorunlu asenkron sürücülü (`sqlite+aiosqlite`, `postgresql+asyncpg`) ve 2 katmanlı kilitlemeli (in-process + satır düzeyi `SELECT ... FOR UPDATE`) `DatabaseSessionService`, bulut için `VertexAiSessionService`. Oturum bulunamadığında `SessionNotFoundError` fırlatılır; `Runner(auto_create_session=True)` ile otomatik oluşturma sağlanır. Hatalı turları geri almak veya alternatif dallanma yollarını denemek için oturum düzeyinde geri sarma (`runner.rewind_async(user_id, session_id, rewind_before_invocation_id)`) desteklenir; denetim logları korunurken sonraki LLM bağlamından filtrelenir. Veritabanı modernizasyonunda ADK Python v1.22.1+ ile eski pickle tabanlı `v0` şeması JSON tabanlı `v1` şemasına CLI üzerinden taşınır (`adk migrate session --source_db_url=... --dest_db_url=...` - `references/adk-sessions-guide.md`). Uzun vadeli hafıza `MemoryService` ile yönetilir: yerel test için `InMemoryMemoryService`, Agent Platform üzerinde LLM destekli hafıza konsolidasyonu (`enable_consolidation: True`) sunan `VertexAiMemoryBankService` (`--memory_service_uri="agentengine://<id>"`), Knowledge Engine üzerinde vektör benzerlik araması sunan `VertexAiRagMemoryService`. Ajanlar geçmişi hatırlamak için yerleşik `load_memory` aracını (`tools=[load_memory]`), özel araçlarda `tool_context.search_memory(query)` metodunu kullanır; tek bir ajanın hem konuşma hafızasını hem şirket dokümanlarını aynı anda taraması için Çift Bellek Servisi (Multi-Memory Pattern) mimarisi uygulanır (`references/adk-memory-guide.md`).
- **Artifact:** Oturum veya kullanıcıyla ilişkili adlandırılmış ve versiyonlanmış ikili veri yönetimi (`types.Part`/`Blob`). Oturum kapsamı (`session_id`) ve oturumlar arası kullanıcı kapsamı (`user:<filename>`) ayrımı sunar; modelin eseri ihtiyaç anında bağlamına çekmesi için yerleşik `LoadArtifactsTool` (`enable_spreadsheet_parsing=True`) ve bulut kalıcılığı için `GcsArtifactService` (`BaseArtifactService`) kullanılır (`references/adk-artifacts-guide.md`).
- **Event & Runner:** `Event` oturumda gerçekleşen her eylemin (kullanıcı girdisi, model yanıtı, araç kullanımı, durum değişimi, yetki devri) temel bilgi ve sinyal birimidir; `LlmResponse` yapısını genişletir (`author`, `invocation_id`, `id`, `timestamp`, `partial`, `turn_complete`, `actions: EventActions`). `EventActions`, durum değişikliklerini (`state_delta`), eser güncellemelerini (`artifact_delta`), orkestrasyon devrini (`transfer_to_agent`), döngü sonlandırmayı (`escalate`) ve özet atlamayı (`skip_summarization`) taşır. `Runner` olay döngüsünü ve servis koordinasyonunu yönetir; üretilen olayları `SessionService.append_event` metoduna teslim ederek deltaların `session.state`'e işlenmesini, oturum olay tarihçesine (`session.events`) yazılmasını ve dışarıya `yield` edilmesini sağlar. Olay akışında nihai kullanıcı yanıtları `event.is_final_response()`, araç çağrıları `event.get_function_calls()`, araç sonuçları ise `event.get_function_responses()` ile filtrelenir; çoklu araç yürütmelerinde `ToolContext.function_call_id` kullanılır (`references/adk-events-guide.md`).
- **Planning & Code Execution:** ReAct benzeri hedef ayrıştırma ve korumalı kod yürütme yetenekleri.
- **Skill & SkillToolset:** `agentskills.io` standardında 3 seviyeli (L1 Metadata frontmatter, L2 Instructions `SKILL.md`, L3 Resources: `references/`, `assets/`, `scripts/`) modüler yetenek kapsülleme mimarisi. Ajanın bağlam penceresini koruyarak yönergeleri ve betikleri kademeli (on-demand) yükleyen `SkillToolset` (`load_skill`, `load_skill_resource`, `run_skill_script`) ile yönetilir (`references/adk-skills-guide.md`).
- **App:** Tüm iş akışını kapsülleyen en üst düzey uygulama konteyneri (`App(name="...", root_agent=root_agent)`). Operasyonel altyapıyı bilişsel akıl yürütmeden ayırır; `on_startup`/`on_shutdown` yaşam döngüsü kancaları, `app:*` durum kapsamı, devam edebilirlik (`resumability_config`) ve merkezi eklentileri (`plugins`) yönetir (`references/adk-apps-guide.md`). Büyük statik talimatlar ve belgeler için Gemini 2.0+ yerel bağlam önbelleklemesi `ContextCacheConfig` (`min_tokens`, `ttl_seconds`, `cache_intervals`) ile `App` seviyesinde şeffaf olarak uygulanır; yanıt gecikmesini (TTFT) ve girdi token maliyetini minimize eder (`references/adk-context-caching-guide.md`). Uzun soluklu konuşmalarda model bağlam penceresini korumak ve maliyeti düşürmek için Bağlam Sıkıştırma (`EventsCompactionConfig`) uygulanır: iki strateji desteklenir — belirteç tabanlı sıkıştırma (`token_threshold` ve `event_retention_size`) ve kayan pencere sıkıştırması (`compaction_interval` ve `overlap_size`). Her ikisi de tanımlandığında belirteç tabanlı strateji önceliklidir; olay geçmişi özetlemesi `LlmEventSummarizer` ve özelleştirilebilir prompt şablonu ile yürütülür (`references/adk-context-compaction-guide.md`).
- **Plugin:** Tüm iş akışı ve `Runner`/`App` seviyesinde çalışan küresel modüler kod bileşeni (`BasePlugin`). 3 çalışma modu (Gözlemle/Observe, Müdahale et/Intervene, Değiştir/Amend) ve 10 yaşam döngüsü kancası (`on_user_message_callback`, `before_run_callback`, `on_event_callback`, `after_run_callback`, ajan/model/araç kancaları) sunar. Plugin kancaları yerel callback'lerden önce çalışır ve non-None dönüşlerde yerel kancaları atlatır (short-circuit). Zengin hazır eklenti ekosistemi (`Model Armor`, `BigQuery Analytics`, `Reflect and Retry Tools`, `Context Filter`, `Global Instruction`, `Save Files as Artifacts`, `Auto Tracing`) ile kurumsal güvenlik ve gözlemlenebilirlik sağlar (`references/adk-plugins-guide.md`).
- **Context:** Ajanın tek bir çağrı turu (invocation) boyunca ihtiyaç duyduğu durum, kimlik, servis ve yaşam döngüsü denetim paketini yöneten merkezi omurga. 4 uzmanlaşmış biçimi bulunur: Çekirdek ajan yürütmesinde servisleri ve erken sonlandırmayı yöneten `InvocationContext` (`ctx.end_invocation = True`); dinamik talimatlarda salt-okunur durum sağlayan `ReadonlyContext`; yaşam döngüsü ve model kancalarında yazılabilir durum ve artifact erişimi sunan `Context` (eski `CallbackContext`); ve araç fonksiyonlarında kimlik doğrulama (`request_credential`), bellek araması (`search_memory`), eser listeleme (`list_artifacts`) ve zengin UI bileşeni akıtma (`render_ui_widget`) sağlayan `ToolContext`. Durum yönetiminde `temp:`, `user:`, `app:` kapsam önekleri ve `Event.actions.state_delta` takibi kullanılır (`references/adk-context-guide.md`).

## 3. Standart Kurumsal Proje Mimarisi
Gelişmiş ADK ve Agents CLI projeleri aşağıdaki hiyerarşiyi takip eder (`scaffold enhance` sonrası):
```text
<project-root>/
├── app/
│   ├── agent.py                # Ana ajan, root_agent ve app = App(...) tanımı
│   ├── agent_engine_app.py     # Agent Runtime (Agent Engine) giriş noktası
│   ├── fast_api_app.py         # Yerel REST/WebSocket API ve Cloud Run rotaları
│   └── app_utils/              # Oturum (session) ve artifact servisleri
├── tests/
│   ├── eval/                   # Başarı kriterleri ve değerlendirme veri setleri
│   ├── integration/            # Uçtan uca ajan entegrasyon testleri
│   └── unit/                   # Birim testler
├── .cloudbuild/                # Otomatik CI/CD boru hatları
├── deployment/                 # Terraform altyapı kodları (IaC)
├── pyproject.toml              # Proje ve uv bağımlılıkları (deployment_target)
├── agents-cli-manifest.yaml    # Agents CLI konfigürasyonu
├── Dockerfile                  # Dağıtım container imajı
├── GEMINI.md                   # Kodlama ajanları için proje yönergeleri
└── .env                        # GEMINI_API_KEY veya GCP proje ayarları
```

## 4. ADK İş Akışı (Workflow) Mimarisi Seçimi
Ajan geliştirirken problemin doğasına uygun iş akışı mimarisi seçilmelidir (`references/adk-workflows-overview.md`):
- **Graf Tabanlı (Graph Workflows):** Dallanma, döngü ve deterministik fonksiyon düğümleri gerektiren süreçler için (`references/graph-workflows.md`).
- **İşbirlikçi (Collaborative Workflows):** Koordinatör bir ajan ve `mode='task' | 'single_turn' | 'chat'` modlarında alt uzman takımları için (`references/agent-team-patterns.md`).
- **Şablon (Template Workflows):** Katı sıralı (`SequentialAgent`), paralel (`ParallelAgent`) veya döngüsel (`LoopAgent`) boru hatları için.
- **Dinamik (Dynamic Workflows):** Saf programatik Python/TypeScript kod akışı içinde esnek ajan orkestrasyonu için (`references/dynamic-workflows.md`).

## 5. Çalıştırma, Test ve Runtime Motoru
ADK ve Agents CLI çoklu çalıştırma ortamları sunar (`references/adk-runtime-guide.md`):
- **Geliştirici Web Arayüzü (Dev UI):**
  ```powershell
  agents-cli playground    # veya: adk web
  ```
  Tarayıcı üzerinden etkileşimli sohbet, oturum ve state incelemesi (`http://localhost:8080` veya `http://localhost:8000`).
- **Terminal / CLI Runner:**
  ```powershell
  adk run my_agent --save_session --session_id test_session
  ```
  Terminalde doğrudan test, `--resume` veya `--replay` ile oturum tekrarı.
- **REST API Server:**
  ```powershell
  adk api_server
  ```
  FastAPI tabanlı REST sunucusu; `/run` (toplu yanıt), `/run_sse` (canlı SSE token streaming) ve Swagger UI (`/docs`).
- **Yürütme Mimarisi & Denetim:** Ajanlar olay döngüsü (Event Loop) ile çalışır; `RunConfig` (`max_llm_calls`) ile sınırlandırılabilir ve `ResumabilityConfig` ile kesintilere dayanıklı hale getirilebilir.

## 6. Değerlendirme, Optimizasyon & Dağıtım
- **Evals & Test:** Ajan yörüngesi (trajectory) ve nihai yanıt kalitesini ölçmek için `tests/eval/` altındaki `.test.json` veya `.evalset.json` veri setleri kullanılır (`references/adk-evaluation-guide.md`). Çok turlu serbest diyaloglar için Dinamik Kullanıcı Simülatörü (`ConversationScenario`, `user_persona`, `llm_audio`), harici araç izolasyonu için Ortam Simülatörü (`EnvironmentSimulationFactory`) ve özel Python metrik fonksiyonları (`custom_metrics`) desteklenir. Web UI (`adk web`), programatik `pytest`, CLI (`adk eval`) ve regresyon önleyici uyumluluk testleri (`adk conformance test`) ile çalıştırılır.
- **Optimizasyon (Prompt & Skill Tuning):** Değerlendirme skorlarına dayanarak ajan prompt ve yeteneklerini otomatik olarak evrimleştirmek için `adk optimize` CLI ve API motoru kullanılır (`references/adk-optimization-guide.md`). `LocalEvalSampler`, `GEPARootAgentPromptOptimizer`, `GEPARootAgentOptimizer` ve 4 aşamalı `SimplePromptOptimizer` desteklenir.

- **Dağıtım (Deploy):** ADK ajanları 4 ana hedef ortama dağıtılabilir (`references/adk-deployment-guide.md`):
  - **Cloud Run:** Python, TypeScript, Go (`adkgo`) ve Java için sunucusuz konteyner dağıtımı; durum kalıcılığı (`--session_service_uri`, `--artifact_service_uri`) ve REST/Web UI testi.
  - **Agent Runtime (Agent Platform):** `agents-cli deploy` ile tam yönetilen kurumsal ajan motoru. Dağıtım sonrası REST (`async_create_session`, `async_stream_query`) ve Vertex AI Python SDK ile test edilir.
  - **GKE (Kubernetes):** Python (`adk deploy gke`) ve Go (distroless container) dağıtımı; Workload Identity bağlaması, LoadBalancer/ClusterIP servisleri ve diller arası REST uyumu.
  - **Docker & Container:** Şirket içi (on-premise) veya GCP dışı ortamlar için bağımsız konteyner paketleme.
  - **MCP Araçları ile Dağıtım:** `agent.py` içinde ajan ve `McpToolset` kesinlikle **senkron** başlatılmalıdır (asenkron fabrikalar dağıtımda çalışmaz). 3 desen desteklenir: Python+Node.js içeren Self-Contained Stdio Dockerfile, `StreamableHTTPSessionManager(stateless=True)` ile bağımsız Cloud Run servisi veya GKE Pod Sidecar deseni (`references/adk-mcp-guide.md`).


## 7. Gözlemlenebilirlik (Observability)
Ajanların iç durumu, akıl yürütme adımları ve araç yürütmelerini izlemek için yerleşik gözlemlenebilirlik araçları kullanılır (`references/adk-observability-guide.md`):
- **3 Temel Sütun:** Yapılandırılmış Loglama (`LoggingPlugin` konsol, `DebugLoggingPlugin` YAML dökümü), GenAI Metrikleri (`gen_ai.*` ve `adk.experimental.*` toplam token/süre ölçümü) ve Dağıtık İzleme (OpenTelemetry / OTLP: `invoke_agent`, `execute_tool`, Cloud Trace).
- **Telemetri ve Güvenlik:** `TelemetryConfig.captureMessageContent` veya çağrı bazlı `RunConfig.telemetry` ile istem/yanıt takibi (üretimde PII maskeleme kurallarına dikkat edilmelidir).
- **Kurumsal Altyapı:** `agents-cli infra single-project` ile GCP audit ve telemetri kaynaklarının otomatik provizyonu.

## 8. Güvenlik ve Emniyet (Safety & Security)
Ajanların güvenli, deterministik ve kurumsal politikalara uyumlu çalışması için çok katmanlı savunma stratejisi uygulanır (`references/adk-safety-security-guide.md`):
- **Kimlik & Yetki:** Agent-Auth (PoLP servis hesapları), User-Auth (OAuth kullanıcı delegasyonu) ve Araç Kimlik Doğrulama Mimarisi (`AuthScheme`, `AuthCredential`, IAM ID Token ile zorunlu `audience` eşleşmesi, `adk_request_credential` etkileşimli 3LO akışı ve `external_access_token_key` - `references/adk-auth-guide.md`).
- **Güvenlik Bariyerleri (Guardrails):** `ToolContext` üzerinden In-Tool politikaları, Gemini güvenlik filtreleri (`SafetySetting`), `before_tool_callback` parametre doğrulaması ve kurumsal eklentiler (`Gemini as a Judge`, `Model Armor`, `PII Redaction`).
- **Yalıtım:** Sandboxed kod yürütme, hermetik ortamlar ve tarayıcıda model çıktılarının zorunlu HTML/JS kaçırılması (escaping).
