"""Fail if any module of the package is below the per-file coverage minimum.

`[tool.coverage.report] fail_under` only checks the total; this also holds every
file to the minimum. Run after pytest (which writes .coverage):

    python tools/check_coverage.py            # default minimum: 85
    python tools/check_coverage.py --min 90
"""

from __future__ import annotations

import argparse
import io
import sys

import coverage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min", type=float, default=85.0)
    args = parser.parse_args(argv)

    cov = coverage.Coverage()
    cov.load()
    data = cov.get_data()
    failures = []
    for path in sorted(data.measured_files()):
        # Same number as `coverage report` for this file (statements and branches).
        pct = cov.report(morfs=[path], file=io.StringIO())
        if pct < args.min:
            failures.append((pct, path))
    for pct, path in failures:
        print(f"{pct:5.1f}%  {path}")
    if failures:
        print(f"{len(failures)} file(s) below {args.min:.0f}% coverage")
        return 1
    print(f"all {len(data.measured_files())} files have at least {args.min:.0f}% coverage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
