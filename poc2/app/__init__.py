"""POC package for the static coverage diagnostics workflow."""

import os
from pathlib import Path


def load_environment_from_dotenv() -> None:
    """Load project-level .env values before application code reads environment variables."""
    project_root = Path(__file__).resolve().parents[1]
    env_file = project_root / ".env"
    if not env_file.exists():
        return

    try:
        with env_file.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


load_environment_from_dotenv()
