import inspect
from ankipush import sync_deck


def test_sync_deck_signature():
    sig = inspect.signature(sync_deck)
    assert list(sig.parameters) == ["email", "password", "apkg_path", "data_dir"]
    assert sig.parameters["data_dir"].default is None


def test_sync_deck_delegates_to_runner(tmp_path):
    from unittest.mock import patch
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    with patch("ankipush.run_for_user") as mock_run:
        sync_deck("a@b.com", "pass", str(apkg), str(tmp_path))
    mock_run.assert_called_once_with("a@b.com", "pass", str(apkg), str(tmp_path))
