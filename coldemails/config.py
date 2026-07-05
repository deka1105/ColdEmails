"""Environment loading. Campaign configs live in ``campaigns.py``."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def env(key: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val
