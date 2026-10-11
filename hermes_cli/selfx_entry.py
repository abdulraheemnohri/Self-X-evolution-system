"""Self-X product entry point.

Self-X owns its default data directory and user-facing command while retaining
the Hermes implementation namespace as a temporary internal compatibility layer.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_home() -> None:
    # Explicit Self-X setting wins. HERMES_HOME remains accepted for existing
    # deployments and installer stages that still use the legacy internal name.
    configured = os.environ.get("SELF_X_HOME") or os.environ.get("HERMES_HOME")
    if configured:
        home = Path(configured).expanduser()
    elif os.name == "nt":
        home = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Self-X"
    else:
        home = Path.home() / ".selfx"
    resolved = str(home.resolve())
    os.environ["SELF_X_HOME"] = resolved
    os.environ["HERMES_HOME"] = resolved


def main() -> int | None:
    """Start the shared agent runtime with Self-X identity and storage."""
    _configure_home()
    if sys.argv:
        sys.argv[0] = "self-x"
    # Import only after configuring HERMES_HOME: legacy modules cache it at import.
    from hermes_cli.main import main as runtime_main

    return runtime_main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
