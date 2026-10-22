"""Command-line interface for cronpeek."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from .cron import Cron, explain, parse, validate as validate_expression


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.lower() == "now":
        return datetime.now()

    candidate = value
    if candidate[-1:] in ("Z", "z"):
        candidate = candidate[:-1] + "+00:00"
    candidate = candidate.replace(" ", "T")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"invalid datetime: {value!r}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cronpeek",
        description="Parse, validate, and inspect cron expressions.",
    )
    parser.add_argument("expression", help="cron expression to inspect")
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        help="number of times to display (default: 5)",
    )
    parser.add_argument(
        "--from",
        dest="from_time",
        help="starting time in ISO 8601 format (default: now)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        help="strftime format for displayed times",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="validate the expression and exit",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="explain each cron field and exit",
    )
    parser.add_argument(
        "--previous",
        action="store_true",
        help="show previous runs instead of upcoming runs",
    )

    args = parser.parse_args(argv)

    try:
        cron: Cron = parse(args.expression)
    except ValueError as exc:
        print(f"cronpeek: {exc}", file=sys.stderr)
        return 2

    if args.validate:
        try:
            validate_expression(args.expression)
        except ValueError as exc:
            print(f"cronpeek: {exc}", file=sys.stderr)
            return 2
        print("valid")
        return 0

    if args.explain:
        print(explain(cron))
        return 0

    if args.count < 0:
        print("cronpeek: count must not be negative", file=sys.stderr)
        return 2

    try:
        after = _parse_datetime(args.from_time)
    except ValueError as exc:
        print(f"cronpeek: {exc}", file=sys.stderr)
        return 2

    if args.previous:
        values = cron.previous(after, args.count)
    else:
        values = cron.next(after, args.count)

    output_format = args.output_format or "%Y-%m-%dT%H:%M:%S"
    try:
        for value in values:
            print(value.strftime(output_format))
    except ValueError as exc:
        print(f"cronpeek: invalid output format: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
