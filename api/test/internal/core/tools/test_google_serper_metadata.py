from pathlib import Path

import yaml


def test_google_serper_descriptions_are_english():
    provider_dir = (
        Path(__file__).resolve().parents[4]
        / "internal/core/tools/builtin_tools/providers/google"
    )
    catalog = yaml.safe_load((provider_dir / "google_serper.yaml").read_text())
    implementation = (provider_dir / "google_serper.py").read_text()

    assert catalog["description"] == "Search the web with Google Serper using a search query."
    assert 'Field(description="The search query to look up on the web.")' in implementation
    assert 'description="Search the web with Google Serper using a search query."' in implementation
