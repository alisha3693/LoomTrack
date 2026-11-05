"""Supervisor issue note → English reason category + translation.

Runs on a local open-source model through Ollama (free, no data leaves the
machine). When Ollama isn't reachable, a keyword classifier gives a first
guess instead. Either way the original note is kept beside the result and a
merchandiser can override the category.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .. import config
from ..domain.reasons import REASON_CODES


@dataclass
class Classification:
    category: str
    translation: str | None
    confidence: float
    source: Literal["ollama", "keywords"]
    model: str | None = None


ReasonCode = Literal[tuple(REASON_CODES)]  # type: ignore[valid-type]


class _Result(BaseModel):
    translation_en: str
    category: ReasonCode  # type: ignore[valid-type]
    confidence: float = Field(ge=0, le=1)


# Ollama constrains the model's output to this schema.
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "translation_en": {"type": "string"},
        "category": {"type": "string", "enum": REASON_CODES},
        "confidence": {"type": "number"},
    },
    "required": ["translation_en", "category", "confidence"],
}

# Definitions with floor vocabulary matter a lot for a small local model:
# without them Llama 3 8B got 4/6 sample notes right, with them 6/6.
_DEFINITIONS = """FABRIC_DELAY: fabric / cloth / dyeing not arrived or late
TRIMS_DELAY: trims or packing material late: buttons, zips, labels, tags, thread, elastic, cartons, polybags
MACHINE_BREAKDOWN: sewing or other machine broken, needle or motor problem, waiting for mechanic
LABOUR_SHORTAGE: workers absent, on leave, not enough operators
POWER_CUT: no electricity, current cut, EB cut, generator or diesel problem
QUALITY_REWORK: defects, shade variation, stains, alteration, rework, rejection
SUBCONTRACTOR_DELAY: outside print or wash unit slow for reasons other than the ones above
APPROVAL_PENDING: waiting for buyer approval or comments
ORDER_CHANGE: buyer changed style, quantity or sizes
NO_ISSUE: no problem reported
OTHER: a problem that fits none of the above"""

SYSTEM = f"""You read short notes from garment-factory floor supervisors in Tiruppur, India. Notes are Tamil, English or Tanglish and may contain speech-to-text errors.
1. translation_en: translate the note faithfully into plain English. Do not add facts.
2. category: the single root cause of the problem, using these definitions:
{_DEFINITIONS}
Pick the root cause, not where it happened: a power cut at the print unit is POWER_CUT.
Factory words: நூல் (nool) = sewing thread, never "book"; லைன் = production line; பீஸ் = pieces; ஷேட் = fabric shade / colour; கார்ட்டன் = carton; ஆபரேட்டர் = machine operator.
3. confidence: 0 to 1."""


async def classify_note(note: str) -> Classification:
    """Classify with the local model; raises if it is unreachable (callers fall back to keywords)."""
    text = note.strip()
    if not text:
        return Classification("NO_ISSUE", None, 1.0, "keywords")
    if not config.ai_enabled():
        return classify_by_keywords(text)

    body = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "format": _OUTPUT_SCHEMA,
        "options": {"temperature": 0},
        "keep_alive": "30m",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
    }
    # A cold model load can take ~20 s on a laptop GPU; later calls take ~4 s.
    async with httpx.AsyncClient(base_url=config.OLLAMA_URL, timeout=120) as client:
        res = await client.post("/api/chat", json=body)
        res.raise_for_status()
    parsed = _Result.model_validate(json.loads(res.json()["message"]["content"]))
    return Classification(parsed.category, parsed.translation_en.strip(), parsed.confidence, "ollama", config.OLLAMA_MODEL)


async def ai_status() -> dict:
    """Is the local model available? Shown in the office UI so nobody wonders why translations are missing."""
    if not config.ai_enabled():
        return {"mode": "keywords", "reason": "AI turned off (LOOMTRACK_AI=off)"}
    try:
        async with httpx.AsyncClient(base_url=config.OLLAMA_URL, timeout=3) as client:
            tags = (await client.get("/api/tags")).json()
        names = [m["name"] for m in tags.get("models", [])]
        wanted = config.OLLAMA_MODEL if ":" in config.OLLAMA_MODEL else f"{config.OLLAMA_MODEL}:latest"
        if wanted not in names:
            return {"mode": "keywords", "reason": f"Model {config.OLLAMA_MODEL} not pulled (ollama pull {config.OLLAMA_MODEL})"}
        return {"mode": "ollama", "model": config.OLLAMA_MODEL}
    except httpx.HTTPError:
        return {"mode": "keywords", "reason": f"Ollama not reachable at {config.OLLAMA_URL}"}


# --- Keyword fallback ---------------------------------------------------------
# Deterministic, offline, deliberately simple. Short English words that hide
# inside other words ("ok", "tag", "roll") are left out.

KEYWORDS: list[tuple[str, list[str]]] = [
    ("POWER_CUT", ["கரண்ட்", "மின்சாரம்", "மின்வெட்டு", "பவர்", "current illa", "power cut", "power", "eb cut", "generator", "ஜெனரேட்டர்", "டீசல்"]),
    ("MACHINE_BREAKDOWN", ["மெஷின்", "இயந்திர", "பழுது", "ரிப்பேர்", "machine", "repair", "breakdown", "needle", "ஊசி", "motor"]),
    ("LABOUR_SHORTAGE", ["ஆள்", "ஆட்கள்", "தொழிலாளர்", "லீவு", "விடுமுறை", "absent", "leave", "labour", "worker", "operators", "aal illa"]),
    ("FABRIC_DELAY", ["துணி", "fabric", "cloth", "dyeing", "டையிங்"]),
    ("TRIMS_DELAY", ["பட்டன்", "ஜிப்", "லேபிள்", "நூல்", "டேக்", "கார்ட்டன்", "button", "zip", "label", "thread", "trims", "elastic", "எலாஸ்டிக்", "carton", "polybag"]),
    ("SUBCONTRACTOR_DELAY", ["பிரிண்ட்", "பிரிண்டிங்", "வாஷிங்", "வெளி யூனிட்", "print", "printing", "washing", "wash", "subcontract", "job work", "ஜாப் வொர்க்"]),
    ("QUALITY_REWORK", ["ரீவொர்க்", "குறை", "தரம்", "கறை", "ஆல்டர்", "rework", "defect", "stain", "alter", "reject", "quality", "shade", "ஷேட்"]),
    ("APPROVAL_PENDING", ["அப்ரூவல்", "ஒப்புதல்", "approval", "approve", "comments pending"]),
    ("ORDER_CHANGE", ["மாற்றம்", "change", "revised", "qty change", "style change"]),
    ("NO_ISSUE", ["பிரச்சனை இல்லை", "சரியாக", "நன்றாக", "no issue", "no problem", "on track"]),
]


def classify_by_keywords(note: str) -> Classification:
    lower = note.lower()
    best: tuple[str, int] | None = None
    for code, words in KEYWORDS:
        hits = sum(1 for w in words if w.lower() in lower)
        if hits and (best is None or hits > best[1]):
            best = (code, hits)
    if best is None:
        return Classification("OTHER", None, 0.1, "keywords")
    return Classification(best[0], None, min(0.6, 0.3 + 0.15 * best[1]), "keywords")
