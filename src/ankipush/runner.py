import os
import docker

_DOCKER_DIR = os.path.join(os.path.dirname(__file__), "_docker")


def build_image(tag: str = "ankipush:latest") -> None:
    client = docker.APIClient()
    for chunk in client.build(path=_DOCKER_DIR, tag=tag, rm=True, decode=True):
        if "stream" in chunk:
            print(chunk["stream"], end="", flush=True)
        elif "error" in chunk:
            raise RuntimeError(f"Docker build failed: {chunk['error']}")
