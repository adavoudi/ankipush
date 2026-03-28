from aqt import mw, gui_hooks
from aqt.qt import QTimer, QAction, QDialog
import os
import threading
from . import logic


def _dismiss_dialogs():
    """Close any blocking dialogs (update check, etc.) so profile_did_open can fire."""
    for widget in mw.app.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible() and widget is not mw:
            print(f"[i] Auto-dismissing dialog: {widget.__class__.__name__}", flush=True)
            widget.reject()


def _load_profile():
    try:
        if not mw.isVisible():
            _dismiss_dialogs()
            mw.pm.load(mw.pm.profiles()[0])
            mw.loadProfile()
            mw.profileDiag.closeWithoutQuitting()
    except Exception as e:
        print(f"[!] Failed to load profile: {e}", flush=True)
        import sys
        sys.exit(1)


def _run_in_thread():
    def target():
        try:
            logic.run(mw)
        except logic.AnkiPushExit as e:
            os._exit(e.code)
    t = threading.Thread(target=target, daemon=True)
    t.start()


def _add_menu_item():
    action = QAction("Run ankipush", mw)
    action.triggered.connect(_run_in_thread)
    mw.form.menuTools.addAction(action)


def _on_profile_open():
    _add_menu_item()
    QTimer.singleShot(500, _run_in_thread)


gui_hooks.profile_did_open.append(_on_profile_open)

# Poll every 500ms to dismiss blocking dialogs and load the profile
def _poll():
    if mw.isVisible():
        return  # profile already loaded
    _dismiss_dialogs()
    _load_profile()
    if not mw.isVisible():
        QTimer.singleShot(500, _poll)

QTimer.singleShot(1000, _poll)
