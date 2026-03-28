from .runner import run_for_user, build_image
import asyncio
import docker
from functools import partial


def _ensure_image(tag: str = "ankipush:latest") -> None:
    client = docker.from_env()
    try:
        client.images.get(tag)
    except docker.errors.ImageNotFound:
        print(f"[ankipush] Image '{tag}' not found, building...", flush=True)
        build_image(tag)


def sync_deck(email: str, password: str, apkg_path: str, data_dir: str = None) -> None:
    """Push an .apkg file into an AnkiWeb account headlessly via Docker."""
    _ensure_image()
    run_for_user(email, password, apkg_path, data_dir)


async def async_sync_deck(email: str, password: str, apkg_path: str, data_dir: str = None) -> None:
    """Async version of sync_deck — runs in a thread executor so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(sync_deck, email, password, apkg_path, data_dir))
