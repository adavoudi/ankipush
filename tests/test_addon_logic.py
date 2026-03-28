import sys
import pytest
from unittest.mock import MagicMock, patch, call
from types import SimpleNamespace


def make_mw(sync_key=None, has_media_syncer=False):
    mw = MagicMock()
    mw.pm.sync_key.return_value = sync_key
    mw.col.sync_auth.return_value = MagicMock()
    if not has_media_syncer:
        del mw.media_syncer
    return mw


# We import logic directly — no aqt dependency
sys.path.insert(0, "src/ankipush/_docker/addon")
import logic


def test_login_missing_env(monkeypatch):
    monkeypatch.delenv("ANKI_EMAIL", raising=False)
    monkeypatch.delenv("ANKI_PASS", raising=False)
    with pytest.raises(SystemExit) as exc:
        logic.run(make_mw())
    assert exc.value.code == 1


def test_login_skipped_when_session_exists(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    monkeypatch.setenv("ANKI_APKG_PATH", "/nonexistent.apkg")
    mw = make_mw(sync_key="existing_key")
    with pytest.raises(SystemExit) as exc:
        logic.run(mw)
    mw.col.sync_login.assert_not_called()
    assert exc.value.code == 1  # exits on missing file, not auth


def test_login_auth_error(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "wrong")
    mw = make_mw()
    mw.col.sync_login.side_effect = Exception("invalid auth")
    with pytest.raises(SystemExit) as exc:
        logic.run(mw)
    assert exc.value.code == 1


def test_sync_pull_called_before_import(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_key="key")
    call_order = []
    mw.col.sync_collection.side_effect = lambda *a: call_order.append("sync")
    mw.col.import_file.side_effect = lambda *a: call_order.append("import")
    with pytest.raises(SystemExit):
        logic.run(mw)
    assert call_order.index("sync") < call_order.index("import")


def test_import_missing_file(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    monkeypatch.setenv("ANKI_APKG_PATH", "/does/not/exist.apkg")
    mw = make_mw(sync_key="key")
    with pytest.raises(SystemExit) as exc:
        logic.run(mw)
    assert exc.value.code == 1


def test_import_called_with_correct_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_key="key")
    with pytest.raises(SystemExit) as exc:
        logic.run(mw)
    mw.col.import_file.assert_called_once_with(str(apkg))
    assert exc.value.code == 0


def test_sync_push_called_after_import(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_key="key")
    call_order = []
    mw.col.sync_collection.side_effect = lambda *a: call_order.append("sync")
    mw.col.import_file.side_effect = lambda *a: call_order.append("import")
    with pytest.raises(SystemExit):
        logic.run(mw)
    # pull then import then push
    assert call_order == ["sync", "import", "sync"]


def test_media_wait_loop(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_key="key", has_media_syncer=True)
    is_syncing_results = [True, True, False]
    mw.media_syncer.is_syncing.side_effect = is_syncing_results
    with patch("logic.time.sleep"):
        with pytest.raises(SystemExit) as exc:
            logic.run(mw)
    assert mw.media_syncer.is_syncing.call_count == 3
    assert exc.value.code == 0
