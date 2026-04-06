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
