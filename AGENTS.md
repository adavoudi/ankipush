# Project Overview

`ankipush` is an installable Python library that headlessly imports `.apkg` Anki deck files into an
AnkiWeb account (or a self-hosted sync server) without any GUI. It spins up a containerised Anki
instance via Docker, logs in programmatically, pulls the user's existing collection, imports the
deck, syncs the merged result back, and exits — all from a single `sync_deck()` call. It is
designed to be embedded in automation pipelines, content-generation tools, or any Python program
that needs to push flashcard decks to Anki users at scale.

---

## Repository Structure

```
ankipush/
├── src/ankipush/               # Installable library (public API)
│   ├── __init__.py             # sync_deck(), async_sync_deck(), build_image() exports
│   ├── runner.py               # Docker SDK orchestration: build image, run container per user
│   └── _docker/                # Files bundled inside the library and copied into the image
│       ├── Dockerfile          # Headless Anki image (Debian, Qt VNC, no AnkiConnect)
│       ├── startup.sh          # Container entrypoint: injects addon, launches Anki
│       ├── data/               # Pre-seeded Anki profile (skips first-run wizard)
│       └── addon/              # Anki addon loaded inside the container
│           ├── __init__.py     # Qt hooks: auto-loads profile, dismisses dialogs, runs logic
│           ├── logic.py        # Pure Python: login → pull → import → sync → media sync → exit
│           └── manifest.json   # Anki addon metadata
├── tests/
│   ├── test_api.py             # Unit tests for public API (sync_deck, async_sync_deck)
│   ├── test_runner.py          # Unit tests for Docker orchestration (runner.py)
│   ├── test_addon_logic.py     # Unit tests for addon logic (no Anki install required)
│   ├── test_integration.py     # Integration tests against a local self-hosted sync server
│   ├── conftest.py             # Pytest fixtures: sync server lifecycle, shared_datadir
│   ├── data/                   # .apkg fixtures generated with genanki
│   └── syncserver/             # Docker Compose + Dockerfile for the test sync server
├── pyproject.toml              # uv project definition, dependencies, pytest config
├── Makefile                    # Developer shortcuts
├── plan.md                     # Implementation milestones (living document)
├── README.md                   # User-facing documentation
├── discussion.md               # Design discussion log
└── images/                     # Screenshots used in docs/tests
```

---

## Build & Development Commands

```bash
# Create virtualenv and install all dependencies (including dev)
make install
# equivalent: uv venv && uv sync --extra dev

# Activate the virtualenv (auto-activated if direnv is installed)
source .venv/bin/activate

# Run unit tests
make test
# equivalent: uv run pytest

# Build the Docker image (required before first use; ~3 min on first run)
make build-image
# equivalent: uv run python -c "from ankipush import build_image; build_image()"

# Run integration tests (requires Docker + running sync server)
make test-integration
# equivalent: RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v -s

# Build the distributable wheel
make build
# equivalent: uv build

# Clean build artifacts and virtualenv
make clean
```

---

## Code Style & Conventions

- **Formatter:** No formatter is enforced yet. Follow PEP 8 manually.
  > TODO: add `ruff` to dev dependencies and configure in `pyproject.toml`.
- **Naming:** `snake_case` for functions/variables, `PascalCase` for exceptions and classes.
- **Private symbols:** prefix with `_` (e.g. `_print`, `_exit`, `_ensure_image`).
- **Imports:** stdlib → third-party → local, one blank line between groups.
- **Commit messages:** imperative mood, lowercase, ≤ 72 chars.
  - Examples: `fix media sync: use taskman.run_in_background`, `add async_sync_deck() wrapper`
- **No type annotations required** in addon code (runs inside Anki's Python 3.9 environment).
  Host-side code (`runner.py`, `__init__.py`) should use type hints.
- **Tests:** one test file per module; test names describe the behaviour, not the implementation.

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────────────┐
│  Caller (Python program)                                     │
│                                                              │
│  from ankipush import sync_deck                              │
│  sync_deck(email, password, apkg_path)                       │
└────────────────────┬────────────────────────────────────────┘
                     │ calls
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ankipush/__init__.py                                        │
│  • _ensure_image() — builds Docker image if missing         │
│  • run_for_user()  — delegates to runner.py                 │
└────────────────────┬────────────────────────────────────────┘
                     │ calls
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ankipush/runner.py                                          │
│  • Seeds per-user data dir (~/.ankipush/users/<safe_email>/) │
│  • Copies .apkg into user's export/ dir                     │
│  • Launches Docker container (ankipush:latest)              │
│  • Streams container logs to stdout in real-time            │
│  • Raises RuntimeError on non-zero exit code                │
└────────────────────┬────────────────────────────────────────┘
                     │ Docker run
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker container (ankipush:latest)                          │
│  startup.sh → injects addon → anki -b /data                 │
│                                                              │
│  addon/__init__.py                                           │
│  • Hooks profile_did_open                                    │
│  • Polls every 500ms to dismiss blocking dialogs            │
│  • Runs logic.run(mw) in a background thread                │
│                                                              │
│  addon/logic.py                                              │
│  1. Auth   — sync_login() or reuse cached session           │
│  2. Pull   — sync_collection() download                     │
│  3. Import — AnkiPackageImporter.run()                      │
│  4. Media  — col.media().add_file() for each bundled file   │
│  5. Push   — sync_collection() upload (or full_upload)      │
│  6. Media  — col.sync_media() + poll media_sync_status()    │
│  7. Exit   — os._exit(code)                                 │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- The addon runs inside Anki's Qt event loop. All blocking work runs in a `threading.Thread` to
  avoid freezing the event loop; collection operations that require the Qt thread use
  `mw.taskman.run_in_background`.
- `AnkiPushExit` is a custom exception used inside `logic.py` so unit tests can catch it cleanly.
  The addon's `__init__.py` catches it and calls `os._exit(code)` to terminate the process.
- Per-user data isolation: each email maps to a sanitised directory name under `data_dir`. The
  pre-seeded `prefs21.db` and `User 1/` profile are copied on first run to skip Anki's setup wizard.
- The sync endpoint can be overridden via `ANKI_SYNC_ENDPOINT` env var for self-hosted servers.
- Media files are registered via `col.media().add_file(name, data)` after import, not by writing
  to disk directly. This atomically writes the file, computes its SHA1, and marks it as pending
  upload in Anki's media sync DB. `col.sync_media(auth)` is then called directly (it spawns its
  own background thread); progress is polled via `col.media_sync_status()` until `active` is false.

---

## Testing Strategy

### Unit tests (`make test`)

Run without Docker or network access. All Anki internals are mocked via `unittest.mock`.

| File | What it tests |
|---|---|
| `test_api.py` | Public API signatures, `_ensure_image`, async wrapper |
| `test_runner.py` | Directory creation, container lifecycle, error propagation |
| `test_addon_logic.py` | Full `logic.run()` flow: auth, pull, import, sync, media, exit codes |

### Integration tests (`make test-integration`)

Require Docker. Skipped unless `RUN_INTEGRATION=1` is set.

- Spins up a real Anki sync server (`tests/syncserver/`) via Docker Compose.
- Runs `sync_deck()` against it with `testuser:testpass`.
- Covers: happy path, bad credentials, missing file, second-run merge, multi-deck, card updates,
  full upload on first sync.

```bash
RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v -s
```

### CI

> TODO: add a GitHub Actions workflow that runs `make test` on every push and
> `make test-integration` on PRs targeting `master`.

---

## Security & Compliance

- **Credentials** are passed as Docker environment variables at runtime and never written to disk.
  They are not logged (only the email prefix appears in log lines).
- **Per-user data isolation:** each user's Anki collection lives in a separate directory keyed by
  their sanitised email. Containers cannot access other users' data.
- **No secrets in source:** `ANKI_EMAIL` and `ANKI_PASS` must be supplied by the caller; the
  library has no credential storage.
- **Docker image:** built from `debian:12.4-slim`; no AnkiConnect, no exposed ports in production
  runs. The VNC platform (`QT_QPA_PLATFORM=vnc`) is used only to satisfy Qt's display requirement;
  port 5900 is not published unless explicitly mapped by the caller.
- **Dependency scanning:** > TODO: add `uv audit` or `pip-audit` to CI.
- **License:** > TODO: add a LICENSE file. The Anki desktop client is AGPL-3.0; verify
  compatibility with your intended use.

---

## Agent Guardrails

Automated agents (coding assistants, CI bots) working in this repo **must not**:

- Modify `src/ankipush/_docker/data/` — the pre-seeded SQLite profile is hand-crafted and
  fragile; changes will break the first-run wizard bypass.
- Remove or weaken the `finally: container.remove(force=True)` block in `runner.py` — this
  prevents zombie containers.
- Add `print()` calls to `logic.py` that bypass `_print()` — all output must go through the
  stderr-backed writer so it appears in Docker logs.
- Change `os._exit(code)` in `addon/__init__.py` to `sys.exit()` — `sys.exit` does not terminate
  the Qt event loop from a background thread.
- Run integration tests without `RUN_INTEGRATION=1` — they start Docker containers and hit the
  network.
- Commit `test_real.py` or `*.apkg` files created during manual testing (both are gitignored).
- Wrap `col.sync_media(auth)` in `taskman.run_in_background` — `sync_media` already spawns its
  own background thread and returns `None` immediately; wrapping it again breaks progress polling.
- Write media files directly to `collection.media` on disk — always use `col.media().add_file(name, data)`
  so Anki atomically registers the file in its sync DB and marks it pending upload.

---

## Extensibility Hooks

| Hook | How to use |
|---|---|
| `ANKI_SYNC_ENDPOINT` | Set to `http://host:port/` to use a self-hosted sync server instead of AnkiWeb |
| `data_dir` parameter | Override the default `~/.ankipush/users/` storage location per call |
| `image` parameter in `run_for_user()` | Pass a custom Docker image tag to use a modified Anki build |
| `build_image(tag=...)` | Build the image under a custom tag for multi-version testing |
| `async_sync_deck()` | Drop-in async wrapper for use in `asyncio`-based applications |

To add new behaviour to the in-container flow, edit `src/ankipush/_docker/addon/logic.py` and
add steps between the existing phases (auth → pull → import → push → media → exit).

---

## Further Reading

- `README.md` — user-facing installation and usage guide
- [Anki sync protocol notes](https://forums.ankiweb.net/t/is-there-any-supported-way-to-authenticate-ankiweb-login-without-using-the-gui/67637)
- [genanki](https://github.com/kerrickstaley/genanki) — used to generate `.apkg` test fixtures
- [Anki self-hosted sync server docs](https://docs.ankiweb.net/sync-server.html)
