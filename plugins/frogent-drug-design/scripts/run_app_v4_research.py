#!/usr/bin/env python3
"""Launch the read-only app_v4 source with the FROGENT research manager."""

import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.app_v4_launcher import AppV4LaunchConfig, create_app_v4_research  # noqa: E402


def main() -> None:
    source = PROJECT_ROOT / "sources" / "frogent"
    config = AppV4LaunchConfig.from_env(PLUGIN_ROOT, source)
    app = create_app_v4_research(config)
    app.run(host=os.getenv("FROGENT_HOST", "127.0.0.1"),
            port=int(os.getenv("FROGENT_PORT", "5000")), threaded=True)


if __name__ == "__main__":
    main()
