#!/usr/bin/env python3
"""Launch the FROGENT web app with the Agent runtime."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.app.web_launcher import WebLaunchConfig, create_web_app  # noqa: E402


def main() -> None:
    config = WebLaunchConfig.from_env(PROJECT_ROOT)
    app = create_web_app(config)
    app.run(host=os.getenv("FROGENT_HOST", "127.0.0.1"),
            port=int(os.getenv("FROGENT_PORT", "5000")), threaded=True)


if __name__ == "__main__":
    main()
