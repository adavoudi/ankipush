from ankipush import sync_deck
import pytest

def test_sync_deck_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        sync_deck("a@b.com", "pass", "/tmp/deck.apkg")

def test_sync_deck_signature():
    import inspect
    sig = inspect.signature(sync_deck)
    assert list(sig.parameters) == ["email", "password", "apkg_path", "data_dir"]
    assert sig.parameters["data_dir"].default is None
