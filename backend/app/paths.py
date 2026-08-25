"""Runtime resource locations — monorepo and container-archive layouts.

Local dev runs from a monorepo checkout where backend/ sits beside
demo-store/ and fixtures/ (referenced as ``parents[3]`` from files inside
backend/app/…). Container deploys ship backend/ as the archive root, so those
directories land one level higher relative to this package instead. Hardcoding
the monorepo layout made fresh deploys crash on boot while hunting for a
fixture outside the image. resolve_dir() checks both layouts plus cwd, first
match wins; if nothing exists it returns the monorepo path so callers raise
their familiar "missing — run generate.py" errors locally.
"""
from pathlib import Path

_HERE = Path(__file__).resolve()  # …/backend/app/paths.py


def resolve_dir(name: str) -> Path:
    candidates = (
        _HERE.parents[2] / name,  # monorepo checkout: <repo>/<name>
        _HERE.parents[1] / name,  # container deploy: <archive-root>/<name>
        Path.cwd() / name,  # explicit cwd override (scripts)
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]
