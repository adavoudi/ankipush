from .runner import run_for_user


def sync_deck(email: str, password: str, apkg_path: str, data_dir: str = None) -> None:
    """Push an .apkg file into an AnkiWeb account headlessly via Docker."""
    run_for_user(email, password, apkg_path, data_dir)
