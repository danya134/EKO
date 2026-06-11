"""
Точка входу для Render / production.
Gunicorn з подовженим timeout — генерація PDF з багатьма фото може тривати довше 30 с.
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    port = os.environ.get("PORT", "8000")
    workers = os.environ.get("WEB_CONCURRENCY", "1")
    timeout = os.environ.get("GUNICORN_TIMEOUT", "120")
    cmd = [
        sys.executable,
        "-m",
        "gunicorn",
        "core.wsgi:application",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        str(workers),
        "--timeout",
        str(timeout),
        "--graceful-timeout",
        str(timeout),
        "--worker-class",
        "sync",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
