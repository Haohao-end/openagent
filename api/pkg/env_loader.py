import os
from pathlib import Path

from dotenv import load_dotenv


def _configure_builtin_nltk_data() -> None:
    """Use the repository-bundled NLTK data for local Flask/Celery runs."""
    builtin_nltk_data = Path(__file__).resolve().parents[1] / "internal/core/unstructured/nltk_data"
    if builtin_nltk_data.exists():
        os.environ.setdefault("NLTK_DATA", str(builtin_nltk_data))


def load_project_env() -> None:
    """Load environment variables from api/.env only."""
    api_env = Path(__file__).resolve().parents[1] / ".env"

    if api_env.exists():
        load_dotenv(dotenv_path=api_env, override=False)
        _configure_builtin_nltk_data()
        return

    # Fallback: keep support for already-exported shell environment variables.
    load_dotenv(override=False)
    _configure_builtin_nltk_data()
