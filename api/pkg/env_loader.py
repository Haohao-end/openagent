from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """Load environment variables from api/.env only."""
    api_env = Path(__file__).resolve().parents[1] / ".env"

    if api_env.exists():
        load_dotenv(dotenv_path=api_env, override=False)
        return

    # Fallback: keep support for already-exported shell environment variables.
    load_dotenv(override=False)
