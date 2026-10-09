---
title: "Multi-Language Setup"
description: "Setting up Google ADK across Python, TypeScript, Go, Java, and Kotlin"
category: architecture
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - multi-language
  - python
  - typescript
  - go
  - java
  - kotlin
  - architecture
---

# Google ADK Çoklu Dil Kurulum Referansı

Google ADK'nın resmi olarak desteklediği diller ve paket bağımlılıkları:

## 1. Python
- Paket: `google-adk`
- Kurulum: `uv add google-adk` veya `pip install google-adk`

## 2. Node.js / TypeScript
- Paketler: `@google/adk`, `@google/adk-devtools`
- Kurulum: `npm install @google/adk @google/adk-devtools`

## 3. Go (Go 1.25+)
- Paket: `google.golang.org/adk/v2` (v1.x için `@v1`)
- Kurulum: `go get google.golang.org/adk/v2`

## 4. Java (Maven & Gradle)
- Paketler: `com.google.adk:google-adk:1.11.0`, `com.google.adk:google-adk-dev:1.11.0`
- Özellik: SpringBoot gömülü dev server desteği.

## 5. Kotlin (JVM & KSP)
- Paketler: 
  - `com.google.adk:google-adk-kotlin-core:1.3.0`
  - `com.google.adk:google-adk-kotlin-processor:1.3.0` (KSP ile `@Tool` kod üretimi)
