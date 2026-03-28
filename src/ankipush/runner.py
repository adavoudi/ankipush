import os
import re
import shutil
import docker

_DOCKER_DIR = os.path.join(os.path.dirname(__file__), "_docker")
_DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), ".ankipush", "users")


def build_image(tag: str = "ankipush:latest") -> None:
    client = docker.APIClient()
    for chunk in client.build(path=_DOCKER_DIR, tag=tag, rm=True, decode=True):
        if "stream" in chunk:
            print(chunk["stream"], end="", flush=True)
        elif "error" in chunk:
            raise RuntimeError(f"Docker build failed: {chunk['error']}")


def run_for_user(
    email: str,
    password: str,
    apkg_path: str,
    data_dir: str = None,
    image: str = "ankipush:latest",
) -> None:
    data_dir = data_dir or _DEFAULT_DATA_DIR
    safe_id = re.sub(r"[^a-zA-Z0-9]", "_", email)

    user_data = os.path.join(data_dir, safe_id, "anki-data")
    user_export = os.path.join(data_dir, safe_id, "export")
    os.makedirs(user_data, exist_ok=True)
    os.makedirs(user_export, exist_ok=True)

    dest = os.path.join(user_export, os.path.basename(apkg_path))
    shutil.copy2(apkg_path, dest)

    client = docker.from_env()
    container = client.containers.run(
        image=image,
        name=f"ankipush_{safe_id}",
        environment={
            "ANKI_EMAIL": email,
            "ANKI_PASS": password,
            "ANKI_APKG_PATH": f"/export/{os.path.basename(apkg_path)}",
        },
        volumes={
            user_data: {"bind": "/data", "mode": "rw"},
            user_export: {"bind": "/export", "mode": "rw"},
        },
        detach=True,
        remove=False,
    )
    try:
        for line in container.logs(stream=True):
            print(f"[{safe_id}] {line.decode().strip()}", flush=True)
        container.reload()
        exit_code = container.attrs["State"]["ExitCode"]
        if exit_code != 0:
            raise RuntimeError(f"ankipush container exited with code {exit_code}")
    finally:
        container.remove(force=True)

