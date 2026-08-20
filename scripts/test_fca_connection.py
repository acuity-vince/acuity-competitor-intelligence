"""Verify FCA API credentials without printing or exporting secrets."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.regulators.fca import FCAClient  # noqa: E402


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_local_env(REPO_ROOT / ".env")
    email = os.getenv("FCA_API_EMAIL", "")
    api_key = os.getenv("FCA_API_KEY", "")
    if not email or not api_key:
        print("FCA connection: credentials missing")
        return 2

    client = FCAClient(email, api_key)
    results = client.search_firms("IG Markets Limited")
    print("FCA connection: authenticated")
    print(f"Search results: {len(results)}")
    for result in results[:3]:
        print(
            "Result: "
            f"name={result.name!r}, frn={result.frn!r}, "
            f"status={result.status!r}, type={result.result_type!r}"
        )
    if results:
        print(f"First result fields: {sorted(results[0].raw.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
