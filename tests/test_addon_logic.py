import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "src/ankipush/_docker/addon")
import logic
from logic import AnkiPushExit


def make_mw(sync_auth=None, has_media_syncer=False):
    mw = MagicMock()
    mw.pm.sync_auth.return_value = sync_auth
    # media_sync_status returns inactive by default so poll loop exits immediately
    media_status = MagicMock()
    media_status.active = False
    mw.col.media_sync_status.return_value = media_status
    # taskman.run_in_background calls on_done immediately
    def fake_run_in_background(fn, on_done):
        on_done(None)
    mw.taskman.run_in_background.side_effect = fake_run_in_background
    return mw


def test_login_missing_env(monkeypatch):
    monkeypatch.delenv("ANKI_EMAIL", raising=False)
    monkeypatch.delenv("ANKI_PASS", raising=False)
    mw = make_mw()
    with pytest.raises(AnkiPushExit) as exc:
        logic.run(mw)
    assert exc.value.code == 1


def test_login_skipped_when_session_exists(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    monkeypatch.setenv("ANKI_APKG_PATH", "/nonexistent.apkg")
    mw = make_mw(sync_auth=MagicMock())
    with pytest.raises(AnkiPushExit) as exc:
        logic.run(mw)
    mw.col.sync_login.assert_not_called()
    assert exc.value.code == 1


def test_login_auth_error(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "wrong")
    mw = make_mw()
    mw.col.sync_login.side_effect = Exception("invalid auth")
    with pytest.raises(AnkiPushExit) as exc:
        logic.run(mw)
    assert exc.value.code == 1


def test_sync_pull_called_before_import(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_auth=MagicMock())
    call_order = []
    mw.col.sync_collection.side_effect = lambda *a: call_order.append("sync")
    mock_importer = MagicMock()
    mock_importer.run.side_effect = lambda: call_order.append("import")
    with patch("logic.AnkiPackageImporter", return_value=mock_importer):
        with pytest.raises(AnkiPushExit):
            logic.run(mw)
    assert call_order.index("sync") < call_order.index("import")


def test_import_missing_file(monkeypatch):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    monkeypatch.setenv("ANKI_APKG_PATH", "/does/not/exist.apkg")
    mw = make_mw(sync_auth=MagicMock())
    with pytest.raises(AnkiPushExit) as exc:
        logic.run(mw)
    assert exc.value.code == 1


def test_import_called_with_correct_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_auth=MagicMock())
    mock_importer = MagicMock()
    with patch("logic.AnkiPackageImporter", return_value=mock_importer) as mock_cls:
        with pytest.raises(AnkiPushExit) as exc:
            logic.run(mw)
    mock_cls.assert_called_once_with(mw.col, str(apkg))
    mock_importer.run.assert_called_once()
    assert exc.value.code == 0


def test_sync_push_called_after_import(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_auth=MagicMock())
    call_order = []
    sync_out = MagicMock()
    sync_out.NO_CHANGES = "NO_CHANGES"
    sync_out.NORMAL_SYNC = "NORMAL_SYNC"
    sync_out.FULL_UPLOAD = "FULL_UPLOAD"
    sync_out.FULL_DOWNLOAD = "FULL_DOWNLOAD"
    sync_out.required = "NO_CHANGES"
    sync_out.new_endpoint = None
    mw.col.sync_collection.side_effect = lambda *a: (call_order.append("sync"), sync_out)[1]
    mock_importer = MagicMock()
    mock_importer.run.side_effect = lambda: call_order.append("import")
    with patch("logic.AnkiPackageImporter", return_value=mock_importer):
        with pytest.raises(AnkiPushExit):
            logic.run(mw)
    assert call_order == ["sync", "import", "sync"]


def test_exits_zero_on_success(monkeypatch, tmp_path):
    monkeypatch.setenv("ANKI_EMAIL", "a@b.com")
    monkeypatch.setenv("ANKI_PASS", "pass")
    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")
    monkeypatch.setenv("ANKI_APKG_PATH", str(apkg))
    mw = make_mw(sync_auth=MagicMock())
    sync_out = MagicMock()
    sync_out.NO_CHANGES = "NO_CHANGES"
    sync_out.required = "NO_CHANGES"
    sync_out.new_endpoint = None
    mw.col.sync_collection.return_value = sync_out
    mock_importer = MagicMock()
    with patch("logic.AnkiPackageImporter", return_value=mock_importer):
        with pytest.raises(AnkiPushExit) as exc:
            logic.run(mw)
    assert exc.value.code == 0
