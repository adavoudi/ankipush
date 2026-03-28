# AnkiPushAddon — Implementation Plan

## Project Overview

A headless Anki automation system packaged as an installable Python library (`ankipush`). Other Python programs can install it via `pip` / `uv add` and call its public API to import `.apkg` files into a user's AnkiWeb account without any GUI.

The library:
1. Bundles the Dockerfile and Anki addon internally
2. Exposes a simple Python API: `from ankipush import sync_deck`
3. Runs Anki inside a Docker container (no GUI, no AnkiConnect)
4. Logs in to AnkiWeb programmatically using supplied credentials
5. Pulls the user's existing collection, imports a `.apkg` file, and syncs back to AnkiWeb
6. Maintains isolated data directories per user (keyed by email)

---

## Project Structure (Target)

```
AnkiPushAddon/
├── .gitignore
├── pyproject.toml                  # uv project + installable package definition
├── src/
│   └── ankipush/
│       ├── __init__.py             # Public API: sync_deck(email, password, apkg_path, data_dir)
│       ├── runner.py               # Docker SDK orchestration (internal)
│       ├── _docker/
│       │   ├── Dockerfile
│       │   ├── startup.sh
│       │   └── addon/
│       │       ├── __init__.py     # Anki addon: login, import, sync, exit
│       │       └── manifest.json
└── tests/
    ├── test_api.py
    ├── test_runner.py
    ├── test_addon_logic.py
    └── test_integration.py
```

---

## Milestone 1 — Project Scaffolding & Tooling

**Purpose:** Establish the installable Python library with `uv`, `src/` layout, virtualenv, and `.env` support so every subsequent milestone has a consistent, reproducible environment.

### Tasks
- [x] Create `pyproject.toml` using `uv` with `src` layout, package name `ankipush`, and dependencies: `docker`, `pytest` (dev)
- [x] Create `src/ankipush/__init__.py` with a stub `sync_deck(email, password, apkg_path, data_dir=None)` function that raises `NotImplementedError`
- [x] Add `.gitignore` entries for `__pycache__`, `.venv`, `dist/`
- [x] Verify `uv venv && uv sync` produces a working virtualenv with the package importable

### How to validate
- **Automated:** `pytest --collect-only` runs without import errors
- **Human:** Run `uv venv && uv sync`, then `source .venv/bin/activate && python -c "from ankipush import sync_deck; print('OK')"` — should print `OK`

## Milestone 2 — Docker Image: Remove AnkiConnect, Inject Custom Addon

**Purpose:** Produce a clean Docker image (bundled inside the library under `src/ankipush/_docker/`) that runs headless Anki with only our custom addon loaded, and no AnkiConnect.

### Tasks
- [x] Move `Dockerfile` and `startup.sh` into `src/ankipush/_docker/`
- [x] Rewrite `Dockerfile`: remove all AnkiConnect download/symlink/config steps; add `COPY addon /app/addon`
- [x] Rewrite `startup.sh`: remove AnkiConnect CORS logic; add `cp -r /app/addon /data/addons21/ankipush_addon` before launching `anki -b /data`
- [x] Create `src/ankipush/_docker/addon/manifest.json` with addon name and package fields
- [x] Create `src/ankipush/_docker/addon/__init__.py` as a stub (`print("[i] Addon loaded")`) so the image can be validated before full logic is added
- [x] In `runner.py`, use `importlib.resources` (or `__file__`) to locate the `_docker/` directory at runtime so the image builds correctly regardless of install location

### How to validate
- **Automated:** `pytest tests/test_runner.py::test_image_builds` — programmatically builds the image from the bundled Dockerfile and asserts no exception
- **Human:** Run `python -c "from ankipush import runner; runner.build_image()"` and confirm it completes; run `docker images` to see `ankipush` listed

---

## Milestone 3 — Anki Addon: Programmatic Login

**Purpose:** The addon reads `ANKI_EMAIL` and `ANKI_PASS` from environment variables and authenticates with AnkiWeb using the backend API, storing the session key — with no GUI dialogs.

### Tasks
- [x] In `anki_addon/__init__.py`, hook into `gui_hooks.profile_did_open`
- [x] Read `ANKI_EMAIL` and `ANKI_PASS` from `os.environ`; exit with code `1` and a clear error message if either is missing
- [x] Call `mw.col.sync_login(username, password, endpoint=mw.pm.sync_endpoint())` and store result via `mw.pm.set_sync_key()` and `mw.pm.set_sync_username()`
- [x] Skip login if `mw.pm.sync_key()` already exists (session reuse)
- [x] On `SyncError` with kind `AUTH`, print a clear error message and exit with code `1`
- [x] On any other exception, print the error and exit with code `1`

### How to validate
- **Automated:** `pytest tests/test_addon_logic.py::test_login_missing_env` — mock `os.environ` with no credentials, assert `sys.exit(1)` is raised
- **Automated:** `pytest tests/test_addon_logic.py::test_login_auth_error` — mock `mw.col.sync_login` to raise `SyncError(AUTH)`, assert `sys.exit(1)`
- **Human:** Run the container with wrong credentials (`ANKI_EMAIL=bad ANKI_PASS=bad`); container logs should show `[!] Authentication failed` and container exit code should be `1`

---

## Milestone 4 — Anki Addon: Safety Pull (Initial Sync Down)

**Purpose:** Before importing anything, pull the user's existing AnkiWeb collection into the local container database to prevent overwriting their data.

### Tasks
- [x] After successful login, call `mw.col.sync_collection(auth, True)` to perform an incremental sync (downloads existing data)
- [x] Handle the case where the local collection is empty/new (first run) — a full download is expected and should not be treated as an error
- [x] Log sync progress clearly: `[i] Pulling existing collection from AnkiWeb...` and `[i] Pull complete.`
- [x] On sync failure, print error and exit with code `1`

### How to validate
- **Automated:** `pytest tests/test_addon_logic.py::test_sync_pull_called` — mock `mw.col.sync_collection`, assert it is called before any import
- **Human:** Run the container with valid credentials and no `.apkg` file; logs should show the pull step completing, then an error about the missing `.apkg` — confirming pull ran first

---

## Milestone 5 — Anki Addon: Import `.apkg`

**Purpose:** Import the deck package from the path specified by `ANKI_APKG_PATH` into the local Anki collection.

### Tasks
- [x] Read `ANKI_APKG_PATH` from `os.environ`; default to `/export/deck.apkg` if not set
- [x] Check that the file exists; if not, print a clear error and exit with code `1`
- [x] Call `mw.col.import_file(apkg_path)` (or `import_package` if the Anki 25.x API differs — handle both with a try/fallback)
- [x] Log `[i] Importing <filename>...` and `[i] Import complete.`
- [x] On import failure, print error and exit with code `1`

### How to validate
- **Automated:** `pytest tests/test_addon_logic.py::test_import_missing_file` — mock `os.path.exists` to return `False`, assert `sys.exit(1)`
- **Automated:** `pytest tests/test_addon_logic.py::test_import_called` — mock `mw.col.import_file`, assert it is called with the correct path
- **Human:** Drop a valid `.apkg` into `users/<user_id>/export/`, run the container; logs should show `[i] Import complete.`

---

## Milestone 6 — Anki Addon: Sync Push & Media Wait

**Purpose:** After import, push the merged collection back to AnkiWeb and wait for background media sync to finish before shutting down.

### Tasks
- [x] After import, call `mw.col.sync_collection(auth, True)` for an incremental push
- [x] If the collection requires a full sync (schema changed), call `mw.col.full_upload(auth)` instead
- [x] After database sync, check `mw.media_syncer` existence; if present, call `.start()` and loop with `time.sleep(1)` until `is_syncing()` returns `False`
- [x] Log `[i] Syncing to AnkiWeb...`, `[i] Sync complete.`, `[i] Waiting for media sync...`, `[i] Media sync complete.`
- [x] Call `mw.close()` then `sys.exit(0)` for a graceful shutdown

### How to validate
- **Automated:** `pytest tests/test_addon_logic.py::test_sync_push_called` — mock sync functions, assert push is called after import
- **Automated:** `pytest tests/test_addon_logic.py::test_media_wait_loop` — mock `is_syncing()` to return `True` twice then `False`, assert loop ran 3 times
- **Human:** Run the full flow end-to-end with a valid `.apkg`; container should exit with code `0` and the deck should appear in AnkiWeb

---

## Milestone 7 — Host Orchestration & Public API

**Purpose:** Implement `runner.py` (internal Docker SDK logic) and wire it to the public `sync_deck()` API so callers can import and use the library with a single function call.

### Tasks
- [x] Implement `runner.py` with `run_for_user(email, password, apkg_path, data_dir)` using the Docker SDK
- [x] Sanitize email to a safe directory name (e.g., `user@example.com` → `user_example_com`)
- [x] Create `<data_dir>/<safe_user_id>/anki-data/` and `<data_dir>/<safe_user_id>/export/` if they don't exist
- [x] Copy the `.apkg` file into the user's `export/` directory before launching the container
- [x] Mount user-specific directories as Docker volumes (`/data` and `/export`)
- [x] Pass credentials as container environment variables (never written to disk)
- [x] Stream container logs line-by-line, yielding or printing with a `[<user_id>]` prefix
- [x] After container exits, read `ExitCode`; return `True` on `0`, raise an exception with the last log lines on non-zero
- [x] Always remove the container in a `finally` block
- [x] Implement `sync_deck(email, password, apkg_path, data_dir=None)` in `src/ankipush/__init__.py` that calls `runner.run_for_user()`; `data_dir` defaults to `~/.ankipush/users`

### How to validate
- **Automated:** `pytest tests/test_runner.py::test_user_dirs_created` — mock Docker client, assert correct directories are created for a given email
- **Automated:** `pytest tests/test_runner.py::test_container_cleanup_on_failure` — mock container to raise an exception, assert `container.remove()` is still called
- **Automated:** `pytest tests/test_api.py::test_sync_deck_signature` — assert `sync_deck` is importable and has the correct signature
- **Human:** In a fresh virtualenv, run `pip install -e .`, then call `from ankipush import sync_deck` in a Python script with a populated `.env` — confirm it runs without import errors

---

## Milestone 8 — End-to-End Integration Test

**Purpose:** Validate the complete pipeline works together as an installed library: build image → run container → import deck → sync to AnkiWeb → clean exit.

### Tasks
- [ ] Create `tests/test_integration.py` (skipped unless `RUN_INTEGRATION=1` env var is set)
- [ ] Test: call `sync_deck(email, password, apkg_path)` with valid credentials and a real `.apkg`, assert it returns without raising
- [ ] Test: call with invalid credentials, assert it raises an exception containing `Authentication failed`
- [ ] Test: call with a non-existent `.apkg` path, assert it raises an exception containing the missing file path

### How to validate
- **Automated:** `RUN_INTEGRATION=1 pytest tests/test_integration.py` — requires Docker daemon and valid AnkiWeb credentials in `.env`
- **Human:** In a separate project, run `pip install git+https://github.com/<your-repo>`, then call `sync_deck(...)` and confirm the deck appears in AnkiWeb

---

## Definition of Done

A milestone is complete when:
1. All its tasks are ticked `[x]`
2. All associated automated tests pass (`uv run pytest`)
3. The human validation step has been performed and confirmed
