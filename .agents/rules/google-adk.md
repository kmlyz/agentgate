---
title: "Google ADK Standartları"
description: "Google Agent Development Kit (v2.x) mimarisi, dizin hiyerarşisi, araç ve iş akışı geliştirme kuralları"
type: rule
scope: project
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - rules
  - adk
  - python
  - architecture
---

# Google ADK (Agent Development Kit) Standartları

Bu kural seti Google ADK (v2.x) ile geliştirilen tüm ajanlar için geçerlidir.

## 1. Dizin ve Proje Yapısı
- Her ADK ajanı bağımsız bir alt klasör içinde yaşamalıdır:
  ```text
  <proje_kökü>/
  └── <ajan_klasörü>/       # örn: doc_agent/
      ├── __init__.py       # İçeriği mutlaka: from . import agent
      ├── agent.py          # Zorunlu ana orkestrasyon dosyası
      └── .env              # Ajan bazlı veya kök ortam değişkenleri
  ```
- **Windows Kodlama Kuralı:** PowerShell `echo ... >` UTF-16/null-bytes ürettiğinden, tüm dosyalar UTF-8 kodlamasıyla oluşturulmalıdır.

## 2. Giriş Noktası ve Tanımlama (`agent.py`)
- `agent.py` içinde ADK çalışma motorunun bağlandığı **tek ve zorunlu** nesne `root_agent` adında olmalıdır.
- `root_agent`, tekil bir `Agent` veya karmaşık/deterministik süreçler için bir `Workflow` (graf orkestratörü) olabilir.
- Sınıf importları:
  ```python
  from google.adk import Agent, Workflow, Event
  ```
- **Dinamik Şablonlar:** `instruction` metninde oturum durumundaki değişkenler `{var?}` formatında (hata vermemesi için `?` ile) veya artefaktlar `{artifact.var}` ile çağrılabilir.
- **Yapılandırılmış Girdi ve Çıktı:** Ajanın girdisi için `input_schema=InputPydanticModel`, garantili şemaya uygun JSON çıktısı için `output_schema=OutputPydanticModel` kullanılır.
- **Model Yapılandırması:** Sıcaklık ve token sınırları `generate_content_config=types.GenerateContentConfig(temperature=0.2)` ile kontrol edilir.
- **Ortak Kurallar:** Sistem genelindeki paylaşılan kurallar ve davranışlar için `GlobalInstructionPlugin` kullanılır.
- **Graf Tabanlı İş Akışları (`Workflow`):** `edges=[("START", saf_fonksiyon, agent, event_fonksiyon)]` ile deterministik kod düğümleri ve AI ajanları birleştirilir; her düğümün dönüşü bir sonrakine otomatik girdi olur.
- Standart Ajan Tanımlama:
  ```python
  root_agent = Agent(
      model="gemini-1.5-pro",  # veya gemini-flash-latest / gemini-2.0-flash
      name="doc_agent",
      description="Ajanın amacını özetleyen kısa açıklama.",
      instruction="Ajanın sistem talimatı. Oturum verisi: {user_role?}",
      tools=[tool_fonksiyon_1, tool_fonksiyon_2],
      output_schema=AnalysisResultSchema,  # Opsiyonel: Garantili Pydantic JSON çıktısı
  )
  ```
- Graf Tabanlı Akış Tanımlama:
  ```python
  root_agent = Workflow(
      name="doc_pipeline",
      edges=[("START", preprocess_file, analyzer_agent, notify_done)],
  )
  ```
- **Dinamik İş Akışları (`@node`, `ctx.run_node`):** Döngü (`while`/`for`) ve dallanmalar için fonksiyonlar `@node` ile sarmalanır; orkestratör içinde `await ctx.run_node(node, ...)` ile çalıştırılır. Duraklatmalı akışlarda `rerun_on_resume=True` ile tamamlanmış alt düğümler otomatik kontrol noktalarından (checkpoint) tekrarsız okunur.

## 3. Araç (Tool) Geliştirme Standartları
- **Fonksiyon Yapısı:** Standart Python fonksiyonları (paralel performans için `async def` tercih edilir).
- **Docstring Standardı:** ADK parametre şemasını Google-style docstring'den türetir (`Args:`, `Returns:` blokları zorunludur).
- **Dönüş Formatı:** Düz metin yerine yapılandırılmış `dict` dönmelidir:
  ```python
  def get_weather(city: str) -> dict:
      """Belirtilen şehir için güncel hava durumunu döner.

      Args:
          city (str): Hava durumu sorgulanacak şehir adı.

      Returns:
          dict: 'status' ('success' | 'error'), 'report' veya 'error_message'.
      """
      if not city:
          return {"status": "error", "error_message": "Şehir adı belirtilmedi."}
      return {"status": "success", "report": f"{city} için hava açık, 22C."}
  ```

## 4. Veri Taşıma ve Durum Yönetimi (State & Data Handling)
- **Graf Olay Ayrımı (`Event`):**
  - `Event(output=...)`: Sadece sıradaki graf düğümüne (`node_input`) veri aktarır. Bir düğüm tur başına yalnızca tek bir `output` yayabilir.
  - `Event(message=...)`: Doğrudan kullanıcıya/arayüze döner; sonraki düğüme iletilmez.
- **Durum Anahtarı Yaşam Döngüsü (State Prefixes):**
  - `temp:<anahtar>`: Yalnızca mevcut çağrı (turn) bittiğinde otomatik temizlenir.
  - `user:<anahtar>`: Kullanıcıya bağlı olup tüm oturumlarında paylaşılır.
  - `app:<anahtar>`: Tüm uygulama genelinde kalıcıdır.
  - *(önek yok)*: Oturum (session) boyunca kalıcıdır.
- **İnsan Onayı ve Müdahalesi (HITL):** Graf akışlarında kritik işlemler öncesi `from google.adk.events import RequestInput` ile `yield RequestInput(message=..., response_schema=...)` kullanılır. LLM çağırmadan deterministik olarak akışı duraklatır; kullanıcı yanıtı sıradaki düğüme aktarılır.
- **Hazır Şablon Ajanlar:** `SequentialAgent` veya `ParallelAgent` içinde ajan çıktısını bir sonrakine taşımak için `output_key="anahtar"` kullanılır ve sonraki ajanın talimatında `{anahtar}` ile okunur.

## 5. Yetkilendirme
- **Google AI Studio (Standart):** `GOOGLE_API_KEY` adıyla `.env` içinde tanımlanır.
- **Google Cloud Agent Platform (Enterprise/Vertex AI):** `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`, `GOOGLE_CLOUD_PROJECT` ve `GOOGLE_CLOUD_LOCATION` tanımlanır. Yerel geliştirme için `gcloud auth application-default login` kullanılır.

## 6. Çalıştırma Protokolü
- **Üst Dizin Kuralı:** Tüm ADK CLI komutları, ajan klasörünün **üst (parent) dizininden** çalıştırılmalıdır.
- **Terminal (CLI):** `adk run <ajan_klasörü>`
- **Web UI:** `adk web --port 8000` (Tarayıcı: `http://localhost:8000`)
- **Not:** `adk web` geliştirme ve hata ayıklama (tracing) içindir; üretim ortamı için kullanılmaz.
