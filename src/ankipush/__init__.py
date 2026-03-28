from .runner import run_for_user, build_image
import docker


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
