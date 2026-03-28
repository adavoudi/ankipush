import inspect
import asyncio
from ankipush import sync_deck, async_sync_deck


def test_sync_deck_signature():
    sig = inspect.signature(sync_deck)
    assert list(sig.parameters) == ["email", "password", "apkg_path", "data_dir"]
    assert sig.parameters["data_dir"].default is None


def test_sync_deck_delegates_to_runner(tmp_path):
    from unittest.mock import patch, MagicMock
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    mock_client = MagicMock()
    mock_client.images.get.return_value = MagicMock()  # image exists
    with patch("ankipush.docker.from_env", return_value=mock_client):
        with patch("ankipush.run_for_user") as mock_run:
            sync_deck("a@b.com", "pass", str(apkg), str(tmp_path))
    mock_run.assert_called_once_with("a@b.com", "pass", str(apkg), str(tmp_path))


def test_async_sync_deck_signature():
    sig = inspect.signature(async_sync_deck)
    assert list(sig.parameters) == ["email", "password", "apkg_path", "data_dir"]
    assert asyncio.iscoroutinefunction(async_sync_deck)


def test_async_sync_deck_delegates_to_sync_deck(tmp_path):
    from unittest.mock import patch, MagicMock
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    with patch("ankipush.sync_deck") as mock_sync:
        asyncio.run(async_sync_deck("a@b.com", "pass", str(apkg), str(tmp_path)))
    mock_sync.assert_called_once_with("a@b.com", "pass", str(apkg), str(tmp_path))
