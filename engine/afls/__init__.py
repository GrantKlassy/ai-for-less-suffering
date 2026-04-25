from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

__version__ = "0.0.1"


def _load_repo_env() -> None:
    """Load the repo-root .env so `ANTHROPIC_API_KEY` surfaces without manual export.

    Walks up from the package for a directory containing `directives-ai/` (the
    repo-root marker `config.repo_root` uses), then loads `.env` there if
    present. Silent no-op outside the repo checkout so tests and installs
    elsewhere are unaffected.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "directives-ai").is_dir():
            env_path = candidate / ".env"
            if env_path.is_file():
                load_dotenv(env_path, override=False)
            return


_load_repo_env()
