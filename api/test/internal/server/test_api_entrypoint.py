import os
import subprocess
from pathlib import Path


def _write_capture_command(tmp_path: Path, command_name: str) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    command_path = bin_dir / command_name
    command_path.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$0 $*\" > \"$CAPTURE_FILE\"\n",
        encoding="utf-8",
    )
    command_path.chmod(0o755)


def _run_api_entrypoint(tmp_path: Path, *, extra_env: dict[str, str] | None = None) -> str:
    project_root = Path(__file__).resolve().parents[4]
    bin_dir = tmp_path / "bin"
    capture_file = tmp_path / "capture.txt"

    for command_name in ("gunicorn", "flask", "celery"):
        _write_capture_command(tmp_path, command_name)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "CAPTURE_FILE": str(capture_file),
            "MODE": "api",
            "MIGRATION_ENABLED": "false",
            "FLASK_ENV": "production",
            "SQLALCHEMY_DATABASE_URI": "postgresql://postgres:pwd@localhost:5432/llmops",
            "REDIS_HOST": "localhost",
            "REDIS_PORT": "6379",
            "JWT_SECRET_KEY": "secret",
        }
    )
    if extra_env:
        env.update(extra_env)

    subprocess.run(
        ["bash", str(project_root / "api" / "docker" / "entrypoint.sh")],
        check=True,
        cwd=project_root / "api",
        env=env,
        capture_output=True,
        text=True,
    )

    return capture_file.read_text(encoding="utf-8").strip()


def test_api_entrypoint_should_default_to_single_gunicorn_worker_for_socketio_compatibility(tmp_path):
    command = _run_api_entrypoint(tmp_path)

    assert "gunicorn" in command
    assert "--workers 1" in command
    assert "--worker-class gthread" in command


def test_api_entrypoint_should_force_single_gunicorn_worker_when_gthread_is_explicitly_scaled_out(tmp_path):
    command = _run_api_entrypoint(
        tmp_path,
        extra_env={
            "SERVER_WORKER_AMOUNT": "4",
            "SERVER_WORKER_CLASS": "gthread",
        },
    )

    assert "gunicorn" in command
    assert "--workers 1" in command
    assert "--worker-class gthread" in command
