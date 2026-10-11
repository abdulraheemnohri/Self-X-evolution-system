"""Read-only Self-X identity and diagnostics primitives."""
from __future__ import annotations
import importlib
import os
import platform
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class Capability:
    name: str
    status: str
    detail: str

@dataclass(frozen=True)
class Finding:
    id: str
    category: str
    severity: str
    summary: str
    evidence: str
    suggested_action: str
    timestamp: float

def collect_identity(*, enabled_tools: Iterable[str] = (), optional_imports: Iterable[str] = ("yaml", "httpx", "fastapi", "rich")) -> dict:
    """Describe runtime facts without invoking an LLM or changing system state."""
    caps = [
        Capability("python", "available", platform.python_version()),
        Capability("platform", "available", platform.platform()),
    ]
    for name in optional_imports:
        try:
            mod = importlib.import_module(name)
            caps.append(Capability("python:" + name, "available", str(getattr(mod, "__version__", "installed"))))
        except Exception as exc:
            caps.append(Capability("python:" + name, "unavailable", type(exc).__name__))
    caps.extend(Capability("tool:" + name, "configured", "Reported by caller") for name in sorted(set(enabled_tools)))
    secret_words = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "PRIVATE", "AUTH")
    safe_env_names = sorted(k for k in os.environ if not any(word in k.upper() for word in secret_words))
    return {
        "schema_version": 1,
        "collected_at": time.time(),
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "environment_variable_names": safe_env_names,
        "capabilities": [asdict(cap) for cap in caps],
        "secrets_included": False,
    }

def run_diagnostics(*, paths: Iterable[str | Path] = (), min_free_bytes: int = 100 * 1024 * 1024,
                    optional_imports: Iterable[str] = ("yaml", "httpx", "fastapi", "rich")) -> list[Finding]:
    """Run read-only dependency, path, writability, and free-space checks."""
    findings: list[Finding] = []
    now = time.time()
    for name in optional_imports:
        try:
            importlib.import_module(name)
        except Exception as exc:
            findings.append(Finding("dependency-" + name, "dependency", "MEDIUM",
                f"Optional dependency '{name}' is unavailable", type(exc).__name__,
                f"Install {name} only if a feature that needs it is enabled.", now))
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.exists():
            findings.append(Finding("path-missing-" + (path.name or "root"), "filesystem", "MEDIUM",
                f"Expected path is missing: {path.name or str(path)}", "Path does not exist",
                "Confirm the configured path before creating or changing it.", now))
            continue
        if path.is_dir() and not os.access(path, os.W_OK):
            findings.append(Finding("path-not-writable-" + path.name, "filesystem", "HIGH",
                f"Directory is not writable: {path.name}", "Current process lacks write access",
                "Review ownership and permissions before changing them.", now))
        try:
            usage = shutil.disk_usage(path if path.is_dir() else path.parent)
            if usage.free < min_free_bytes:
                findings.append(Finding("disk-low-" + (path.name or "root"), "resources",
                    "HIGH" if usage.free < min_free_bytes // 4 else "MEDIUM", "Low free disk space",
                    f"{usage.free} bytes free; threshold {min_free_bytes}",
                    "Review disk usage and remove only files confirmed safe to delete.", now))
        except OSError as exc:
            findings.append(Finding("disk-check-" + (path.name or "root"), "resources", "LOW",
                "Disk usage could not be checked", type(exc).__name__,
                "Check whether the path is mounted and accessible.", now))
    return findings
