import os
import subprocess
from pathlib import Path


def _write_fake_nginx(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_nginx = bin_dir / "nginx"
    fake_nginx.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_nginx.chmod(0o755)
    return bin_dir


def _run_entrypoint(tmp_path: Path, *, https_enabled: bool) -> str:
    project_root = Path(__file__).resolve().parents[4]
    conf_dir = tmp_path / "conf.d"
    ssl_dir = tmp_path / "ssl"
    conf_dir.mkdir()
    ssl_dir.mkdir()

    if https_enabled:
        (ssl_dir / "server.crt").write_text("cert", encoding="utf-8")
        (ssl_dir / "server.key").write_text("key", encoding="utf-8")

    fake_bin_dir = _write_fake_nginx(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin_dir}{os.pathsep}{env['PATH']}",
            "NGINX_CONF_DIR": str(conf_dir),
            "NGINX_SSL_DIR": str(ssl_dir),
            "NGINX_ENABLE_HTTPS": "true" if https_enabled else "false",
            "NGINX_DOMAIN_NAME": "openllm.cloud",
            "API_UPSTREAM_HOST": "llmops-api",
            "API_UPSTREAM_PORT": "5001",
            "UI_UPSTREAM_HOST": "llmops-ui",
            "UI_UPSTREAM_PORT": "3000",
        }
    )

    subprocess.run(
        ["bash", str(project_root / "docker" / "nginx" / "entrypoint.sh")],
        check=True,
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
    )

    return (conf_dir / "default.conf").read_text(encoding="utf-8")


def test_nginx_entrypoint_should_generate_socketio_proxy_with_upgrade_headers_in_http_mode(tmp_path):
    config = _run_entrypoint(tmp_path, https_enabled=False)

    assert "map $http_upgrade $connection_upgrade {" in config
    assert config.index("location /api/socket.io/ {") < config.index("location /api/ {")
    assert "location /api/socket.io/ {" in config
    assert "proxy_pass http://llmops-api:5001/socket.io/;" in config
    assert "include /etc/nginx/proxy.conf;" in config
    assert "proxy_set_header Upgrade $http_upgrade;" in config
    assert "proxy_set_header Connection $connection_upgrade;" in config
    assert "location /api/ {" in config
    assert "proxy_pass http://llmops-api:5001/;" in config


def test_nginx_entrypoint_should_generate_socketio_proxy_in_https_mode(tmp_path):
    config = _run_entrypoint(tmp_path, https_enabled=True)

    assert "listen 443 ssl;" in config
    assert "ssl_certificate /etc/ssl/server.crt;" in config
    assert "ssl_certificate_key /etc/ssl/server.key;" in config
    assert config.index("location /api/socket.io/ {") < config.index("location /api/ {")
    assert "location /api/socket.io/ {" in config
    assert "proxy_pass http://llmops-api:5001/socket.io/;" in config
    assert "proxy_set_header Upgrade $http_upgrade;" in config
    assert "proxy_set_header Connection $connection_upgrade;" in config
    assert "location /api/ {" in config
