# ankipush

A Python library that headlessly imports `.apkg` deck files into an AnkiWeb account via Docker. No GUI required.

## Requirements

- Python 3.10+
- Docker (running)

## Installation

```bash
pip install git+https://github.com/adavoudi/ankipush.git
```

## Setup

Build the Docker image once before first use (takes ~3 minutes):

```python
from ankipush import build_image

build_image()
```

Or from the command line if you have the repo cloned:

```bash
make build-image
```

> `sync_deck()` will also auto-build the image on first call if it hasn't been built yet.

## Usage

```python
from ankipush import sync_deck

sync_deck(
    email="you@example.com",
    password="yourpassword",
    apkg_path="/path/to/deck.apkg",
)
```

### Async usage

```python
from ankipush import async_sync_deck

await async_sync_deck(
    email="you@example.com",
    password="yourpassword",
    apkg_path="/path/to/deck.apkg",
)
```

### Optional: custom data directory

By default, user data is stored in `~/.ankipush/users/`. You can override this:

```python
sync_deck(
    email="you@example.com",
    password="yourpassword",
    apkg_path="/path/to/deck.apkg",
    data_dir="/custom/path",
)
```

Each user gets an isolated subdirectory keyed by their email, so multiple accounts can be used safely.

## Media files

`.apkg` files with audio or image media are fully supported. Media files bundled in the package are automatically extracted and synced to AnkiWeb alongside the cards.

Use `[sound:filename.mp3]` in card fields for audio and `<img src="filename.png">` for images, and include the files in `genanki.Package.media_files`:

```python
import genanki

model = genanki.Model(...)
note = genanki.Note(model=model, fields=["[sound:audio.mp3]<img src=\"image.png\">", "back"])
deck = genanki.Deck(...)
deck.add_note(note)

package = genanki.Package(deck)
package.media_files = ["/path/to/audio.mp3", "/path/to/image.png"]
package.write_to_file("deck.apkg")
```

## How it works

1. Starts a headless Anki instance in Docker
2. Logs in to AnkiWeb (or a custom sync server) using the provided credentials
3. Pulls the user's existing collection to avoid data loss
4. Imports the `.apkg` file and registers any bundled media files for sync
5. Syncs the merged collection back to AnkiWeb
6. Syncs media files to AnkiWeb
7. Exits and cleans up the container

## Custom sync server

To use a self-hosted Anki sync server instead of AnkiWeb:

```python
import os
os.environ["ANKI_SYNC_ENDPOINT"] = "http://your-server:8080/"

from ankipush import sync_deck
sync_deck("user", "pass", "deck.apkg")
```

## Development

```bash
git clone https://github.com/your-username/ankipush.git
cd ankipush
make install       # create venv and install deps
make test          # run unit tests
make test-integration  # run integration tests (requires Docker)
```
