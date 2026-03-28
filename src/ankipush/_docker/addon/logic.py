import os
import sys
import time


def run(mw):
    email = os.environ.get("ANKI_EMAIL")
    password = os.environ.get("ANKI_PASS")
    apkg_path = os.environ.get("ANKI_APKG_PATH", "/export/deck.apkg")

    # --- Auth ---
    if not email or not password:
        print("[!] ANKI_EMAIL or ANKI_PASS not set")
        sys.exit(1)

    if not mw.pm.sync_key():
        print(f"[i] Logging in as {email}...")
        endpoint = os.environ.get("ANKI_SYNC_ENDPOINT") or mw.pm.sync_endpoint()
        try:
            auth = mw.col.sync_login(
                username=email,
                password=password,
                endpoint=endpoint,
            )
            mw.pm.set_sync_key(auth.hkey)
            mw.pm.set_sync_username(email)
            print("[i] Login successful.")
        except Exception as e:
            if "auth" in str(e).lower() or "invalid" in str(e).lower():
                print(f"[!] Authentication failed: {e}")
            else:
                print(f"[!] Login error: {e}")
            sys.exit(1)
    else:
        print("[i] Existing session found, skipping login.")

    auth = mw.col.sync_auth()

    # --- Safety pull ---
    print("[i] Pulling existing collection from AnkiWeb...")
    try:
        mw.col.sync_collection(auth, True)
        print("[i] Pull complete.")
    except Exception as e:
        print(f"[!] Sync pull failed: {e}")
        sys.exit(1)

    # --- Import ---
    if not os.path.exists(apkg_path):
        print(f"[!] File not found: {apkg_path}")
        sys.exit(1)

    print(f"[i] Importing {os.path.basename(apkg_path)}...")
    try:
        try:
            mw.col.import_file(apkg_path)
        except AttributeError:
            mw.col.import_package(apkg_path)
        print("[i] Import complete.")
    except Exception as e:
        print(f"[!] Import failed: {e}")
        sys.exit(1)

    # --- Sync push ---
    print("[i] Syncing to AnkiWeb...")
    try:
        try:
            mw.col.sync_collection(auth, True)
        except Exception:
            mw.col.full_upload(auth)
        print("[i] Sync complete.")
    except Exception as e:
        print(f"[!] Sync push failed: {e}")
        sys.exit(1)

    # --- Media wait ---
    if hasattr(mw, "media_syncer"):
        print("[i] Waiting for media sync...")
        mw.media_syncer.start()
        while mw.media_syncer.is_syncing():
            time.sleep(1)
        print("[i] Media sync complete.")

    mw.close()
    sys.exit(0)
