import os
from unittest.mock import MagicMock, patch
from ankipush.runner import build_image, _DOCKER_DIR


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
        import pytest
        with pytest.raises(RuntimeError, match="build failed"):
            build_image()
