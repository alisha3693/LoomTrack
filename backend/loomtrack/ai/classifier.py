"""Supervisor issue note -> English translation and a reason category.

The Tamil note is translated to English by IndicTrans2 on this machine (ai/translate.py). The category is then
picked by the keyword rules below, from the note and its translation together. Until the translation models are
downloaded (or when they fail) the keyword rules alone give a first guess. Either way the original note is kept
beside the result and a merchandiser can override the category.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .. import config
from . import translate


@dataclass
class Classification:
    category: str
    translation: str | None
    confidence: float
    source: Literal["indictrans2", "keywords"]
    model: str | None = None


async def classify_note(note: str) -> Classification:
    """Translate with the local model and classify. Raises if the model fails (callers fall back to keywords)."""
    text = note.strip()
    if not text:
        return Classification("NO_ISSUE", None, 1.0, "keywords")
    if not config.ai_enabled() or not translate.has_tamil(text) or not translate.available():
        return classify_by_keywords(text)
    english = await translate.to_english(text)
    guess = classify_by_keywords(f"{text} {english or ''}")
    return Classification(guess.category, english, guess.confidence, "indictrans2", translate.MODEL_LABEL)


async def ai_status() -> dict:
    """{'mode': 'indictrans2' | 'keywords', ...}: what the office sees in the menu."""
    return translate.status()


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
