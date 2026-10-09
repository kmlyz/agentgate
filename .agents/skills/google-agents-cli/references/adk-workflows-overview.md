---
title: "ADK Workflows Overview"
description: "Overview of multi-agent and multi-node workflow architectures in Google ADK"
category: workflows
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - workflows
  - multi-agent
  - collaboration
  - orchestration
---

# Google ADK Çoklu Ajan ve Düğüm İş Akışları (Workflows Overview)

Kaynak: `https://adk.dev/workflows/index.md`  
Destek: Python v0.1.0+, TypeScript v0.2.0+ (ADK 2.0+ Graph desteği), Go v0.1.0+, Java v0.1.0+, Kotlin v0.1.0+

---

## 1. Neden İş Akışları (Workflows)?

Monolitik (tekil ve devasa) ajanlar karmaşıklaştıkça geliştirilmesi, değerlendirilmesi ve sürdürülmesi zorlaşır. ADK, birden çok ajanı ve çalıştırılabilir düğümü **Agent Workflows** çatısı altında birleştirerek 3 temel avantaj sağlar:

1. **Öngörülebilirlik (Predictability):** Şablonlu mantık veya graf tabanlı yürütme ile kontrol akışını denetim altında tutma.
2. **Güvenilirlik (Reliability):** Görevlerin tutarlı bir sıra ve modelde çalışmasını garanti etme.
3. **Yapı ve Ayrışma (Structure):** Ajanları ve yürütülebilir düğümleri ayrıştırarak görev sorumluluklarını ve veri bağlamını (context window) sınırlandırma.

---

## 2. ADK İş Akışı Tipleri Karşılaştırması

ADK uygulamalarında iş akışı oluşturmak için 4 ana yöntem mevcuttur:

| İş Akışı Tipi | Sürüm | Temel Sınıflar / Yapı | Karakteristik ve Uygun Senaryolar |
| :--- | :--- | :--- | :--- |
| **Graph-based Workflows** | ADK 2.0+ | `Graph`, `AgentNode`, `FunctionNode`, `Route` | Karar dallanmaları, döngüler ve deterministik fonksiyon düğümleri içeren esnek yürütme grafları. |
| **Dynamic Workflows** | ADK 2.0+ | Python/TS kod blokları (`if`, `while`, `try-except`) | Saf programatik kod mantığı ile ajanların ve fonksiyonların yürütüldüğü serbest akışlar. |
| **Collaborative Workflows** | ADK 2.0+ | `LlmAgent` + `sub_agents` + `mode` | Koordinatör ajanın dinamik görev dağıttığı ve alt ajanların modlarına göre otomatik geri döndüğü çoklu ajan takımları. |
| **Template Workflows** | Tüm sürümler | `SequentialAgent`, `ParallelAgent`, `LoopAgent` | `BaseAgent` tabanlı sabit, sıralı, paralel veya döngüsel hazır şablonlar. |
| **Agent Routing (Deneysel)** | Experimental | `router` fonksiyonları | Çalışma anında model/ajan seçimi (A/B testing, fallback, auto-routing). |

---

## 3. İşbirlikçi Ajan Modları (Collaboration Modes)

Koordinatör bir ebeveyn ajan (`sub_agents`) altında çalışan alt ajanlar için 3 farklı çalışma modu tanımlanabilir:

> [!WARNING]
> `mode` parametresi **yalnızca alt ajanlar (subagents)** içindir. Asla bir kök (root) ajana `mode` parametresi atanmamalıdır.

| Özellik \ Mod | `chat` (Varsayılan) | `task` | `single_turn` |
| :--- | :--- | :--- | :--- |
| **Human in the Loop** | Tam etkileşim | Yalnızca netleştirme soruları | İzin verilmez |
| **Kullanıcı Etkileşimi** | Kullanıcı serbestçe sohbet eder | Ajan gerekirse soru sorar | Kullanıcı etkileşimi yoktur |
| **Kontrol Akışı** | Manuel devir yapılana kadar kontrol ajandadır | Görev bitene kadar kontrol ajandadır | Görev biter bitmez anında döner |
| **Paralel Yürütme** | Desteklenmez | Desteklenmez | Birden çok görev paralel çalışabilir |
| **Ebeveyne Dönüş** | Manuel (`transfer_to_agent`) | Otomatik (`finish_task`) | Otomatik (çıktı/sonuç ile) |

### Bağlam İzolasyonu (Context Isolation)
- `task` ve `single_turn` modundaki ajanlar **kendi izole oturum dallarında (branch)** çalışır.
- Paralel çalışan ajanlar birbirlerinin olaylarını veya bağlamlarını görmez; yalnızca kendi dallarını görür.
- Görevler bittiğinde ebeveyn ajan toplanan sonuçları alır.

### Örnek (Python):
```python
from google.adk.agents import Agent

# single_turn: Kullanıcı ile konuşmaz, tek adımda görevi tamamlar ve döner
weather_agent = Agent(
    name="weather_checker",
    model="gemini-flash-latest",
    mode="single_turn",
    description="Checks the weather for a given city.",
    instruction="Use the get_weather tool and return the forecast.",
    tools=[get_weather],
)

# task: Gerektiğinde kullanıcıya soru sorar, iş bitince finish_task ile koordinatöre döner
flight_agent = Agent(
    name="flight_booker",
    model="gemini-flash-latest",
    mode="task",
    description="Searches for and books flights.",
    instruction="Help the user find and book flights. Ask clarifying questions if needed.",
    tools=[search_flights, book_flight],
)

# Root Koordinatör: Alt ajanları otomatik araç olarak görür
root_coordinator = Agent(
    name="travel_planner",
    model="gemini-1.5-pro",
    description="Coordinator agent for planning trips.",
    instruction="Help the user plan travel. Delegate to weather_checker and flight_booker.",
    sub_agents=[weather_agent, flight_agent],
)
```

---

## 4. Yaygın Çoklu Ajan İş Akışı Desenleri (Workflow Patterns)

1. **Coordinator and Dispatcher:** Merkezi bir koordinatör, istekleri uzman alt ajanlara yönlendirir (`sub_agents` ve `transfer_to_agent`).
2. **Sequential Pipeline:** Bir ajanın çıktısının diğer ajanın girdisi olduğu ardışık boru hattı (`SequentialAgent` veya `Graph`).
3. **Parallel Fan-out and Gather:** Aynı anda bağımsız çalışan ajanlar ve sonuçların toplanması (`ParallelAgent` veya `single_turn` paralel görevler).
4. **Hierarchical Task Decomposition:** Karmaşık bir görevin alt parçalara bölünerek alt koordinatörler tarafından yönetilmesi.
5. **Generate and Review (Üretici - Denetçi):** Bir ajanın içerik/kod ürettiği, diğer ajanın değerlendirip onayladığı veya geri bildirim verdiği desen.
6. **Iterative Refinement:** Hedef kalite ölçütlerine ulaşılana kadar çalışan döngüsel akış (`LoopAgent` veya koşullu `Graph` döngüsü).
7. **Human-in-the-Loop (HITL):**
   - **External Tool:** Onay için dış sisteme/kullanıcıya çağrı yapan onay aracı.
   - **SecurityPlugin & PolicyEngine (TypeScript önerilen):** Kritik araç çağrılarını intercept edip kullanıcı onayına (`PolicyOutcome.CONFIRM`) sunan kurumsal yapı.

---

## 5. Mimari Karar Matrisi: Hangi İş Akışını Seçmeliyim?

| Senaryo Gereksinimi | Önerilen Mimari |
| :--- | :--- |
| Deterministik veri dönüşümü + LLM adımları + koşullu yönlendirme | **Graph-based Workflow** (`/graphs/`) |
| Geleneksel Python kod akışı (döngüler, API çağrıları) içinde ajan çalıştırma | **Dynamic Workflow** (`/graphs/dynamic/`) |
| Kullanıcıyla sohbet eden ve gerektiğinde uzmanlara başvuran bir asistan | **Collaborative Workflow** (`/workflows/collaboration/`) |
| Sırasıyla A -> B -> C çalışan katı boru hatları | **SequentialAgent** (`/agents/workflow-agents/`) |
| Çok adımlı analizlerde bağımsız veri toplama | **ParallelAgent** (`/agents/workflow-agents/`) |
