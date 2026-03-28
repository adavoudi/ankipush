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

    # Extract media from the .apkg and register each file via add_file() so Anki
    # atomically writes the file, computes its SHA1, and marks it pending upload.
    import zipfile, json
    try:
        with zipfile.ZipFile(apkg_path) as zf:
            manifest = json.loads(zf.read("media").decode())
            mgr = mw.col.media()
            for zipped_name, real_name in manifest.items():
                data = zf.read(zipped_name)
                mgr.add_file(real_name, data)
                _print(f"[i] Registered media: {real_name}")
    except Exception as e:
        _print(f"[!] Media extraction error: {e}")

    # --- Sync push ---
    _print("[i] Syncing to AnkiWeb...")
    try:
        out = mw.col.sync_collection(auth, True)
        if out.new_endpoint:
            mw.pm.set_current_sync_url(out.new_endpoint)
            # Refresh auth with updated endpoint (fixes "missing original size" on first sync)
            auth = mw.pm.sync_auth()
        if out.required == out.NO_CHANGES or out.required == out.NORMAL_SYNC:
            _print("[i] Sync complete.")
        elif out.required == out.FULL_UPLOAD:
            _print("[i] Full upload required, uploading...")
            mw.col.close_for_full_sync()
            mw.col.full_upload_or_download(auth=auth, server_usn=None, upload=True)
            mw.reopen(after_full_sync=True)
            _print("[i] Full upload complete.")
        elif out.required == out.FULL_DOWNLOAD:
            _print("[i] Full download required, downloading...")
            mw.col.close_for_full_sync()
            mw.col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
            mw.reopen(after_full_sync=True)
            _print("[i] Full download complete.")
    except Exception as e:
        _print(f"[!] Sync push failed: {e}")
        _exit(1)

    # --- Media sync ---
    _print("[i] Syncing media to AnkiWeb...")
    try:
        media_auth = mw.pm.sync_auth()
        mw.col.sync_media(media_auth)  # spawns background thread, returns None immediately
        deadline = time.time() + 120
        while time.time() < deadline:
            status = mw.col.media_sync_status()
            if not status.active:
                break
            p = status.progress
            _print(f"[i] Media: +{p.added} -{p.removed} checked:{p.checked}")
            time.sleep(0.25)
        _print("[i] Media sync complete.")
    except Exception as e:
        _print(f"[!] Media sync error (non-fatal): {e}")

    _exit(0)
