import pytest

from loomtrack.ai.classifier import classify_by_keywords


@pytest.mark.parametrize(
    "note, code",
    [
        ("இன்று 8 ஆட்கள் லீவு, அதனால் உற்பத்தி குறைவு", "LABOUR_SHORTAGE"),
        ("இரண்டு மெஷின் பழுது", "MACHINE_BREAKDOWN"),
        ("கரண்ட் இல்லை", "POWER_CUT"),
        ("ஷேட் வித்தியாசம், 300 பீஸ் ரீவொர்க்", "QUALITY_REWORK"),
        ("கார்ட்டன் பெட்டி இன்னும் வரவில்லை", "TRIMS_DELAY"),
        ("zip not arrived from supplier", "TRIMS_DELAY"),
        ("எல்லாம் சரியாக நடக்கிறது", "NO_ISSUE"),
    ],
)
def test_keywords(note, code):
    assert classify_by_keywords(note).category == code


def test_other_with_low_confidence_when_nothing_matches():
    c = classify_by_keywords("ஏதோ ஒன்று")
    assert c.category == "OTHER"
    assert c.confidence < 0.3


def test_never_claims_a_translation():
    assert classify_by_keywords("கரண்ட் இல்லை").translation is None
