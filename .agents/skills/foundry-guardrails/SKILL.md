---
name: foundry-guardrails
description: AgentGate içinde ve dışa aktarılacak ajanlarda deterministik güvenlik katmanı, tip güvenli araç tasarımı, Pydantic şemaları ve Human-in-the-Loop onay kapısı standartları.
---

# Foundry Guardrails: Deterministik Araç ve Güvenlik Tasarım Rehberi

Bu kılavuz, ajanların harici API'lara erişiminde deterministik sınırları korumak, serbest metin kaçaklarını önlemek ve tip güvenli araçlar üretmek için kullanılmalıdır.

## 1. Çekirdek İlkeler

1. **Serbest Metin Yasağı:** Model serbest `string` girdisi alarak cümle kurmamalıdır.
2. **Teklif Deseni (Propose Pattern):** Eylem doğrudan icra edilmez; yapılandırılmış parametrelerle teklif edilir (`propose_*`).
3. **Deterministik Şablonlama:** Metinler kod seviyesinde (`string.format` veya f-string) birleştirilir.
4. **İnsan Onayı (HITL):** Kritik işlemler operatör onayına kadar `PENDING_APPROVAL` durumunda tutulur.

## 2. Tip Güvenli Şema Deseni (Pydantic v2)

### Doğru Kalıp (Pattern)
```python
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    FEAT = "feat"
    FIX = "fix"
    CHORE = "chore"


class ProposeActionInput(BaseModel):
    action_type: ActionType = Field(..., description="Eylem türü")
    scope: str = Field(
        ...,
        description="Hedef modül (küçük harf, boşluksuz, azami 15 karakter)",
        pattern=r"^[a-z0-9_-]{1,15}$",
    )
    summary: str = Field(
        ...,
        description="Özet açıklama (küçük harfle başlar, nokta ile bitmez, azami 50 karakter)",
        pattern=r"^[a-z0-9].{1,50}$",
    )

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        v = v.strip()
        if v.endswith("."):
            raise ValueError("Özet nokta (.) ile bitemez.")
        banned_phrases = ["ai generated", "model updated", "otomatik"]
        if any(p in v.lower() for p in banned_phrases):
            raise ValueError("Özet yapay zeka jargonu veya laf kalabalığı içeremez.")
        return v
```

### Hatalı Kalıp (Anti-Pattern)
```python
# YANLIŞ: Serbest metin kabul eder, model kontrolsüz metin ve halüsinasyon üretebilir.
class DangerousActionInput(BaseModel):
    message: str = Field(..., description="Commit mesajınızı yazın")  # YASAK!
```

## 3. Deterministik Şablonlama ve İcra

Metin birleştirme iş mantığı kodda yer alır:
```python
def render_action_message(proposal: ProposeActionInput) -> str:
    return f"{proposal.action_type.value}({proposal.scope}): {proposal.summary}"
```

## 4. Kendi Kendini İyileştirme (Self-Healing Loop)

Model doğrulama hatası aldığında Pydantic'ten dönen `ValidationError` doğrudan modele döndürülür:
```text
Hata: 1 validation error for ProposeActionInput
summary: Özet nokta (.) ile bitemez.
```
Model bu geri bildirim sayesinde parametresini düzeltir ve tekrar dener. Harici sisteme hiçbir hatalı veri sızmaz.
