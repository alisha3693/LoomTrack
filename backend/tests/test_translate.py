"""Tamil and English on this machine: a glossary for step names, IndicTrans2 for everything else, and a plain
fallback (no translation, keyword matching) whenever the models are not there."""
import asyncio

import pytest

from loomtrack import config
from loomtrack.ai import classifier, translate
from test_api import env  # noqa: F401


def test_known_words_come_from_the_glossary_in_order():
    assert translate.from_glossary("Embroidery") == "எம்ப்ராய்டரி"
    assert translate.from_glossary("Finishing & checking") == "ஃபினிஷிங் & செக்கிங்"
    assert translate.from_glossary("final inspection") == "இறுதி ஆய்வு"


def test_a_name_with_an_unknown_word_is_left_to_the_model():
    assert translate.from_glossary("Heat transfer") is None
    assert translate.from_glossary("Cutting 2") is None


@pytest.fixture
def models_ready(monkeypatch):
    """Pretend the downloaded models answer, so the wiring can be tested without them."""
    monkeypatch.setattr(translate, "available", lambda: True)
    said = []

    async def fake_run(direction, text):
        said.append((direction, text))
        return {"ta-en": "Two machines are broken, the mechanic has come", "en-ta": "வெப்ப பரிமாற்றம்"}[direction]

    monkeypatch.setattr(translate, "_run", fake_run)
    return said


def test_the_glossary_answers_without_asking_the_model(models_ready):
    assert asyncio.run(translate.suggest_tamil("Packing")) == {"ta": "பேக்கிங்", "source": "glossary"}
    assert models_ready == []


def test_a_model_answer_is_used_when_it_is_tamil(models_ready):
    assert asyncio.run(translate.suggest_tamil("Heat transfer")) == {"ta": "வெப்ப பரிமாற்றம்", "source": "model"}
    assert models_ready == [("en-ta", "Heat transfer")]


def test_an_answer_that_is_not_tamil_or_a_failure_gives_no_suggestion(monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: True)

    async def english(direction, text):
        return "Heat transfer"

    async def broken(direction, text):
        raise RuntimeError("out of memory")

    monkeypatch.setattr(translate, "_run", english)
    assert asyncio.run(translate.suggest_tamil("Heat transfer")) == {"ta": None, "source": None}
    monkeypatch.setattr(translate, "_run", broken)
    assert asyncio.run(translate.suggest_tamil("Heat transfer")) == {"ta": None, "source": None}


def test_without_the_models_nothing_is_translated(monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: False)
    assert asyncio.run(translate.to_english("துணி இன்னும் வரவில்லை")) is None
    assert asyncio.run(translate.to_tamil("Packing is done")) is None
    assert asyncio.run(translate.suggest_tamil("Heat transfer")) == {"ta": None, "source": None}


def test_text_with_no_tamil_is_not_sent_to_the_tamil_to_english_model(models_ready):
    assert asyncio.run(translate.to_english("generator diesel finished")) is None
    assert models_ready == []


def test_a_note_is_translated_then_classified_from_both_texts(models_ready):
    r = asyncio.run(classifier.classify_note("இரண்டு மெஷின் பழுது, மெக்கானிக் வந்தார்"))
    assert (r.category, r.translation, r.source) == ("MACHINE_BREAKDOWN", "Two machines are broken, the mechanic has come", "indictrans2")
    assert r.confidence <= 0.6, "keyword rules decide the category, so it is only ever a guess"


def test_an_english_or_empty_note_skips_the_translator_and_without_models_keywords_decide(monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: False)
    r = asyncio.run(classifier.classify_note("மெஷின் பழுது"))
    assert (r.category, r.translation, r.source) == ("MACHINE_BREAKDOWN", None, "keywords")
    assert asyncio.run(classifier.classify_note("  ")).category == "NO_ISSUE"


def test_the_status_says_why_it_is_not_translating(monkeypatch):
    monkeypatch.setenv("LOOMTRACK_AI", "off")
    assert translate.status(fresh=True)["mode"] == "keywords" and "off" in translate.status(fresh=True)["reason"]
    monkeypatch.setenv("LOOMTRACK_AI", "on")
    monkeypatch.setattr(translate, "libraries_installed", lambda: False)
    assert "not installed" in translate.status(fresh=True)["reason"]
    monkeypatch.setattr(translate, "libraries_installed", lambda: True)
    monkeypatch.setattr(translate, "downloaded", lambda d: False)
    assert "not downloaded" in translate.status(fresh=True)["reason"]
    monkeypatch.setattr(translate, "downloaded", lambda d: True)
    monkeypatch.setattr(translate, "device", lambda: "cuda")
    assert translate.status(fresh=True) == {"mode": "indictrans2", "model": "IndicTrans2", "device": "cuda"}


def test_the_device_setting_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("LOOMTRACK_TRANSLATE_DEVICE", "cpu")
    assert config.translate_device() == "cpu"
    monkeypatch.setenv("LOOMTRACK_TRANSLATE_DEVICE", "tpu")
    assert config.translate_device() == "auto"


def _save(env, steps, name):
    return env["client"].post("/api/m/templates", headers=env["merch"], json={"name": name, "steps": steps})


def _tamil_of(env, template_id, name_en):
    t = next(t for t in env["client"].get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == template_id)
    return next(s["nameTa"] for s in t["steps"] if s["nameEn"] == name_en)


def test_a_new_step_gets_its_tamil_name_when_the_template_is_saved(env, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: True)

    async def fake_run(direction, text):
        return "வெப்ப பரிமாற்றம்"

    monkeypatch.setattr(translate, "_run", fake_run)
    r = _save(env, [
        {"kind": "stage", "nameEn": "Embroidery", "process": "embroidery", "startOffset": 30, "endOffset": 20},        # in the glossary
        {"kind": "stage", "nameEn": "Heat transfer T", "process": "pressing", "startOffset": 19, "endOffset": 10},    # not: the model
    ], "Tamil names A")
    assert r.status_code == 201, r.text
    assert _tamil_of(env, r.json()["id"], "Embroidery") == "எம்ப்ராய்டரி"
    assert _tamil_of(env, r.json()["id"], "Heat transfer T") == "வெப்ப பரிமாற்றம்"


def test_with_no_translator_a_new_step_keeps_its_english_name(env, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: False)
    r = _save(env, [{"kind": "stage", "nameEn": "Heat press Q", "process": "pressing", "startOffset": 30, "endOffset": 20}], "Tamil names C")
    assert r.status_code == 201, r.text
    assert _tamil_of(env, r.json()["id"], "Heat press Q") == "Heat press Q"


def test_a_tamil_name_typed_by_hand_is_ignored_and_renaming_translates_again(env, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda: False)
    r = _save(env, [{"kind": "stage", "nameEn": "Sewing Z2", "nameTa": "typed by hand", "process": "x", "startOffset": 30, "endOffset": 20}], "Tamil names D")
    assert r.status_code == 201
    assert _tamil_of(env, r.json()["id"], "Sewing Z2") == "Sewing Z2"
    t = next(t for t in env["client"].get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == r.json()["id"])
    code = next(s["code"] for s in t["steps"] if s["nameEn"] == "Sewing Z2")
    assert env["client"].patch(f"/api/m/steps/{code}", headers=env["merch"], json={"nameEn": "Packing X"}).status_code == 200
    assert _tamil_of(env, r.json()["id"], "Packing X") == "Packing X"          # no glossary word 'X', no model: English stays
