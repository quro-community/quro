from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(env_file: Path | None = None) -> None:
    candidates = (
        [env_file]
        if env_file
        else [
            Path.cwd() / ".env",
            Path(__file__).parent.parent / ".env",
        ]
    )
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                with candidate.open(encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val
            except OSError:
                pass
            break


_load_dotenv()

QURO_DB_URL = os.environ.get("QURO_DB_URL", "postgresql://localhost:5432/quro")
