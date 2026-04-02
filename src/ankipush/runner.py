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

    # Seed prefs21.db and User 1 profile if not present so Anki skips the first-run setup wizard
    prefs_dst = os.path.join(user_data, "prefs21.db")
    if not os.path.exists(prefs_dst):
        prefs_src = os.path.join(_DOCKER_DIR, "data", "prefs21.db")
        shutil.copy2(prefs_src, prefs_dst)
    user1_dst = os.path.join(user_data, "User 1")
    if not os.path.exists(user1_dst):
        user1_src = os.path.join(_DOCKER_DIR, "data", "User 1")
        shutil.copytree(user1_src, user1_dst)

    # Recursively grant full permissions so the container (running as root) can write freely
    for root, dirs, files in os.walk(user_data):
        os.chmod(root, 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o666)
    os.chmod(user_export, 0o777)

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
            **({} if not os.environ.get("ANKI_SYNC_ENDPOINT") else {"ANKI_SYNC_ENDPOINT": os.environ["ANKI_SYNC_ENDPOINT"]}),
        },
        volumes={
            user_data: {"bind": "/data", "mode": "rw"},
            user_export: {"bind": "/export", "mode": "rw"},
        },
        detach=True,
        remove=False,
    )
    try:
        for line in container.logs(stream=True, stdout=True, stderr=True):
            print(f"[{safe_id}] {line.decode().strip()}", flush=True)
        container.reload()
        exit_code = container.attrs["State"]["ExitCode"]
        if exit_code != 0:
            raise RuntimeError(f"ankipush container exited with code {exit_code}")
    finally:
        container.remove(force=True)

