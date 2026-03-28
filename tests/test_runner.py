import os
import pytest
from unittest.mock import MagicMock, patch, call
from ankipush.runner import build_image, run_for_user, _DOCKER_DIR


def test_docker_dir_exists():
    assert os.path.isdir(_DOCKER_DIR)
    assert os.path.isfile(os.path.join(_DOCKER_DIR, "Dockerfile"))


def test_image_builds():
    mock_client = MagicMock()
    mock_client.build.return_value = iter([{"stream": "Step 1/1\n"}])
    with patch("ankipush.runner.docker.APIClient", return_value=mock_client):
        build_image()
    mock_client.build.assert_called_once_with(
        path=_DOCKER_DIR, tag="ankipush:latest", rm=True, decode=True
    )


def test_image_build_raises_on_error():
    mock_client = MagicMock()
    mock_client.build.return_value = iter([{"error": "build failed"}])
    with patch("ankipush.runner.docker.APIClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="build failed"):
            build_image()


def test_user_dirs_created(tmp_path):
    mock_client = MagicMock()
    container = MagicMock()
    container.logs.return_value = iter([b"done\n"])
    container.attrs = {"State": {"ExitCode": 0}}
    mock_client.containers.run.return_value = container

    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")

    with patch("ankipush.runner.docker.from_env", return_value=mock_client):
        run_for_user("user@example.com", "pass", str(apkg), data_dir=str(tmp_path))

    assert os.path.isdir(tmp_path / "user_example_com" / "anki-data")
    assert os.path.isdir(tmp_path / "user_example_com" / "export")


def test_container_cleanup_on_failure(tmp_path):
    mock_client = MagicMock()
    container = MagicMock()
    container.logs.side_effect = RuntimeError("crash")
    mock_client.containers.run.return_value = container

    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")

    with patch("ankipush.runner.docker.from_env", return_value=mock_client):
        with pytest.raises(RuntimeError):
            run_for_user("user@example.com", "pass", str(apkg), data_dir=str(tmp_path))

    container.remove.assert_called_once_with(force=True)


def test_raises_on_nonzero_exit(tmp_path):
    mock_client = MagicMock()
    container = MagicMock()
    container.logs.return_value = iter([b"[!] Authentication failed\n"])
    container.attrs = {"State": {"ExitCode": 1}}
    mock_client.containers.run.return_value = container

    apkg = tmp_path / "deck.apkg"
    apkg.write_bytes(b"fake")

    with patch("ankipush.runner.docker.from_env", return_value=mock_client):
        with pytest.raises(RuntimeError, match="exited with code 1"):
            run_for_user("user@example.com", "pass", str(apkg), data_dir=str(tmp_path))

