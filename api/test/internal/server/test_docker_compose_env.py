from pathlib import Path


def test_docker_compose_should_not_interpolate_postgres_credentials_into_sqlalchemy_uri():
    compose_path = Path(__file__).resolve().parents[4] / "docker" / "docker-compose.yaml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "SQLALCHEMY_DATABASE_URI: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@llmops-db:5432/${POSTGRES_DB}?client_encoding=utf8" not in compose_text
    assert "SQLALCHEMY_DATABASE_URI:" not in compose_text


def test_docker_compose_should_keep_api_env_file_as_single_source_of_truth():
    compose_path = Path(__file__).resolve().parents[4] / "docker" / "docker-compose.yaml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "env_file:" in compose_text
    assert "../api/.env" in compose_text


def test_docker_compose_should_not_require_ui_build_env_file():
    compose_path = Path(__file__).resolve().parents[4] / "docker" / "docker-compose.yaml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert ".ui-build.env" not in compose_text
    assert "context: .." in compose_text
    assert "dockerfile: ui/Dockerfile" in compose_text


def test_ui_dockerfile_should_read_vite_api_prefix_from_api_env():
    dockerfile_path = Path(__file__).resolve().parents[4] / "ui" / "Dockerfile"
    dockerfile_text = dockerfile_path.read_text(encoding="utf-8")

    assert "COPY api/.env* /app/api/" in dockerfile_text
    assert "read-dotenv-value.mjs /app/api/.env VITE_API_PREFIX" in dockerfile_text


def test_api_env_example_should_document_vite_api_prefix():
    env_example_path = Path(__file__).resolve().parents[4] / "api" / ".env.example"
    env_example_text = env_example_path.read_text(encoding="utf-8")

    assert "VITE_API_PREFIX=" in env_example_text
