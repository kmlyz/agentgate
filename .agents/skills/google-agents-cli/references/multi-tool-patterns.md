---
title: "Multi-Tool Patterns"
description: "Designing single agents that orchestrate multiple autonomous tools effectively"
category: integrations
doc_type: guide
status: active
version: "2.0"
last_updated: "2026-10-04"
author: "Antigravity Engineering"
tags:
  - adk
  - multi-tool
  - tool-calling
  - agent-design
  - integrations
---

# Google ADK Multi-Tool Agent Tasarım Şablonu

Bu doküman, Google ADK ile çoklu araç (multi-tool) kullanan ajanların resmi referans kodunu ve yapılandırmasını içerir.

## 1. Klasör ve Modül Yapısı
```text
parent_directory/
└── multi_tool_agent/
    ├── __init__.py       # from . import agent
    ├── agent.py          # root_agent ve araç tanımları
    └── .env              # GOOGLE_API_KEY
```

## 2. `__init__.py`
```python
from . import agent
```

## 3. `agent.py` Örnek Uygulaması
```python
import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent


def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status ('success' | 'error') and report or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": "The weather in New York is sunny with a temperature of 25C.",
        }
    return {
        "status": "error",
        "error_message": f"Weather information for '{city}' is not available.",
    }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status ('success' | 'error') and formatted time report or error msg.
    """
    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": f"Sorry, timezone info not available for '{city}'.",
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f"The current time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    return {"status": "success", "report": report}


root_agent = Agent(
    name="weather_time_agent",
    model="gemini-flash-latest",
    description="Agent to answer questions about the time and weather in a city.",
    instruction="You are a helpful agent who can answer user questions about the time and weather in a city.",
    tools=[get_weather, get_current_time],
)
```

## 4. Çalıştırma
```powershell
# Parent dizinden:
adk web --port 8000
# veya CLI:
adk run multi_tool_agent
```
