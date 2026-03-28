import os
import sys
import time

try:
    from anki.importing import AnkiPackageImporter
except ImportError:
    AnkiPackageImporter = None  # not available outside Anki environment


class AnkiPushExit(Exception):
    def __init__(self, code):
        self.code = code


_stderr = None


def _print(msg):
    global _stderr
    if _stderr is None:
        try:
            _stderr = os.fdopen(os.dup(2), 'w', buffering=1)
        except Exception:
            _stderr = sys.stderr
    _stderr.write(msg + "\n")


def run(mw):
    def _exit(code):
        _print(f"[i] Exiting with code {code}")
        raise AnkiPushExit(code)

    email = os.environ.get("ANKI_EMAIL")
    password = os.environ.get("ANKI_PASS")
    apkg_path = os.environ.get("ANKI_APKG_PATH", "/export/deck.apkg")

    # --- Auth ---
    if not email or not password:
        _print("[!] ANKI_EMAIL or ANKI_PASS not set")
        _exit(1)

    if not mw.pm.sync_auth():
        _print(f"[i] Logging in as {email}...")
        custom_endpoint = os.environ.get("ANKI_SYNC_ENDPOINT")
        if custom_endpoint:
            _print(f"[i] Using custom sync endpoint: {custom_endpoint}")
            mw.pm.set_custom_sync_url(custom_endpoint)
        endpoint = mw.pm.sync_endpoint()
        try:
            auth = mw.col.sync_login(
                username=email,
                password=password,
                endpoint=endpoint,
            )
            mw.pm.set_sync_key(auth.hkey)
            mw.pm.set_sync_username(email)
            _print("[i] Login successful.")
        except Exception as e:
            if "auth" in str(e).lower() or "invalid" in str(e).lower():
                _print(f"[!] Authentication failed: {e}")
            else:
                _print(f"[!] Login error: {e}")
            _exit(1)
    else:
        _print("[i] Existing session found, skipping login.")

    auth = mw.pm.sync_auth()

    # --- Safety pull ---
    _print("[i] Pulling existing collection from AnkiWeb...")
    try:
        mw.col.sync_collection(auth, True)
        _print("[i] Pull complete.")
    except Exception as e:
        _print(f"[!] Sync pull failed: {e}")
        _exit(1)

    # --- Import ---
    if not os.path.exists(apkg_path):
        _print(f"[!] File not found: {apkg_path}")
        _exit(1)

    _print(f"[i] Importing {os.path.basename(apkg_path)}...")
    try:
        importer = AnkiPackageImporter(mw.col, apkg_path)
        importer.run()
        _print("[i] Import complete.")
    except Exception as e:
        _print(f"[!] Import failed: {e}")
        _exit(1)

    # --- Sync push ---
    _print("[i] Syncing to AnkiWeb...")
    try:
        out = mw.col.sync_collection(auth, True)
        if out.new_endpoint:
            mw.pm.set_current_sync_url(out.new_endpoint)
        if out.required == out.NO_CHANGES or out.required == out.NORMAL_SYNC:
            _print("[i] Sync complete.")
        elif out.required == out.FULL_UPLOAD:
            _print("[i] Full upload required, uploading...")
            mw.col.full_upload_or_download(auth=auth, server_usn=None, upload=True)
            _print("[i] Full upload complete.")
        elif out.required == out.FULL_DOWNLOAD:
            _print("[i] Full download required, downloading...")
            mw.col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
            _print("[i] Full download complete.")
    except Exception as e:
        _print(f"[!] Sync push failed: {e}")
        _exit(1)

    # Media sync not supported in headless mode

    _exit(0)
