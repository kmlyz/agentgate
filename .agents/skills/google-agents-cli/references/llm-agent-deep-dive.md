---
title: "LlmAgent Deep Dive"
description: "Advanced configuration for LlmAgent, dynamic templates, Pydantic schemas, and global plugins"
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - llm-agent
  - pydantic
  - schemas
  - generation-config
  - architecture
---

# Google ADK LlmAgent Derinlemesine Yapılandırma Kılavuzu

`google.adk.agents.Agent` (`LlmAgent`) sınıfının gelişmiş parametreleri ve kullanım kalıpları:

## 1. Dinamik Şablon Değişkenleri (`instruction`)
Ajan talimatlarında oturum durumundan veya artefaktlardan veri çekmek için:
- `{var}`: `session.state["var"]` değerini şablona enjekte eder. Değişken yoksa hata verir.
- `{var?}`: Değişken yoksa hatayı yoksayar ve boş bırakır (tavsiye edilen güvenli kullanım).
- `{artifact.report}`: `report` adlı artefaktın metin içeriğini talimata dahil eder.

## 2. Pydantic ile Yapılandırılmış Girdi ve Çıktı (`input_schema`, `output_schema`)
Ajanın girdisini ve çıktısını garantili şemaya zorlamak için:
- **`input_schema`**: Ajana gönderilen kullanıcı mesajının bu şemaya uygun bir JSON dizesi olmasını zorunlu kılar.
- **`output_schema`**: Ajanın nihai yanıtının garantili bir JSON dizesi olmasını sağlar.

```python
from pydantic import BaseModel, Field
from google.adk.agents import Agent


class DocumentQueryInput(BaseModel):
    document_id: str = Field(description="Sorgulanacak belgenin benzersiz kimliği")
    query: str = Field(description="Kullanıcının belge hakkındaki sorusu")


class DocumentAnalysisResult(BaseModel):
    summary: str = Field(description="Dökümanın kısa ve özeti")
    key_findings: list[str] = Field(description="Önemli bulguların maddeleri")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Güven skoru")


root_agent = Agent(
    name="structured_doc_agent",
    model="gemini-1.5-pro",
    instruction="Analyze the given document query and populate the required output schema.",
    input_schema=DocumentQueryInput,
    output_schema=DocumentAnalysisResult,
    tools=[search_documents],
)
```

## 3. Model Üretim & Yeniden Deneme Parametreleri (`generate_content_config`)
```python
from google.genai import types

generation_config = types.GenerateContentConfig(
    temperature=0.1,  # Deterministik ve olgusal yanıtlar için düşük sıcaklık
    max_output_tokens=2048,
    safety_settings=[
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        )
    ],
    # 429 RESOURCE_EXHAUSTED durumunda otomatik yeniden deneme (retry):
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(initial_delay=1.0, attempts=3)
    ),
)
```
Detaylı Gemini model parametreleri, Interactions API ve araç dönüştürme için bkz: [`gemini-models-and-interactions.md`](gemini-models-and-interactions.md).

## 4. Sistem Genelinde Varsayılan Model Belirleme
```python
from google.adk.agents import Agent

# Tüm ajanlar için varsayılan modeli tek satırda tanımlama
Agent.set_default_model("gemini-1.5-pro")
```

## 5. Küresel Talimatlar (`GlobalInstructionPlugin`)
Tüm alt ajanlarda paylaşılan ortak sistem kuralları veya kişilik tanımlamak için artık eski `global_instruction` yerine `GlobalInstructionPlugin` kullanılır.

