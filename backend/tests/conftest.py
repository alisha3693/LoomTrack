import pytest

from loomtrack.ai import translate


@pytest.fixture(autouse=True)
def no_translation_models(monkeypatch):
    """Tests never load the real translation models (slow, and they need a GPU or a lot of patience).
    A test that wants a translator replaces `translate.available` and `translate._run` itself."""
    monkeypatch.setattr(translate, "available", lambda: False)
