"""Core cron parsing and scheduling logic for cronpeek."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional


MAX_SEARCH_MINUTES = 5 * 366 * 24 * 60

SPECIAL_STRINGS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

MONTH_NAMES = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}

DAY_NAMES = {
    "SUN": 0, "SUNDAY": 0,
    "MON": 1, "MONDAY": 1,
    "TUE": 2, "TUESDAY": 2,
    "WED": 3, "WEDNESDAY": 3,
    "THU": 4, "THURSDAY": 4,
    "FRI": 5, "FRIDAY": 5,
    "SAT": 6, "SATURDAY": 6,
}


class CronField:
    """A parsed cron field."""

    def __init__(self, values: set[int], raw: str, restricted: bool):
        self.values = set(values)
        self.raw = raw
        self.restricted = restricted


class Cron:
    """A parsed cron expression."""

    def __init__(self, expression: str, fields: list[CronField]):
        self.expression = expression
        self.fields = fields
        self.minute = fields[0]
        self.hour = fields[1]
        self.day_of_month = fields[2]
        self.month = fields[3]
        self.day_of_week = fields[4]

    def matches(self, dt: datetime) -> bool:
        if dt.minute not in self.minute.values:
            return False
        if dt.hour not in self.hour.values:
            return False
        if dt.month not in self.month.values:
            return False
        if dt.day not in self.day_of_month.values:
            dom_match = False
        else:
            dom_match = True

        # cron uses 0=Sunday..6=Saturday
        cron_dow = (dt.weekday() + 1) % 7
        dow_match = cron_dow in self.day_of_week.values

        if self.day_of_month.restricted and self.day_of_week.restricted:
            day_ok = dom_match or dow_match
        else:
            day_ok = dom_match and dow_match
        return day_ok

    def _matches(self, dt: datetime) -> bool:
        return self.matches(dt)

    def next(self, start: Optional[datetime] = None, count: int = 5) -> list[datetime]:
        if count < 0:
            raise ValueError("count must not be negative")
        if count == 0:
            return []
        if start is None:
            start = datetime.now()

        result: list[datetime] = []
        candidate = start.replace(second=0, microsecond=0)
        if candidate <= start:
            candidate = candidate + timedelta(minutes=1)

        gap = 0
        while len(result) < count:
            if self._matches(candidate):
                result.append(candidate)
                gap = 0
            candidate = candidate + timedelta(minutes=1)
            gap += 1
            if gap > MAX_SEARCH_MINUTES:
                break
        return result

    def previous(self, start: Optional[datetime] = None, count: int = 5) -> list[datetime]:
        if count < 0:
            raise ValueError("count must not be negative")
        if count == 0:
            return []
        if start is None:
            start = datetime.now()

        result: list[datetime] = []
        candidate = start.replace(second=0, microsecond=0)
        if candidate >= start:
            candidate = candidate - timedelta(minutes=1)

        gap = 0
        while len(result) < count:
            if self._matches(candidate):
                result.append(candidate)
                gap = 0
            candidate = candidate - timedelta(minutes=1)
            gap += 1
            if gap > MAX_SEARCH_MINUTES:
                break
        return result

    def between(
        self,
        start: datetime,
        end: datetime,
        inclusive: bool = True,
    ) -> list[datetime]:
        if start > end:
            raise ValueError("start must not be after end")

        result: list[datetime] = []
        candidate = start.replace(second=0, microsecond=0)
        while candidate <= end:
            if candidate >= start and self._matches(candidate):
                if inclusive or candidate < end:
                    result.append(candidate)
            candidate = candidate + timedelta(minutes=1)
        return result


def _to_number(
    token: str,
    names: Optional[dict[str, int]],
    min_val: int,
    max_val: int,
) -> int:
    token = token.strip()
    if names is not None and token.upper() in names:
        value = names[token.upper()]
    else:
        try:
            value = int(token)
        except ValueError:
            raise ValueError(f"invalid value: {token!r}")
    if value < min_val or value > max_val:
        raise ValueError(f"value out of range: {value}")
    return value


def _parse_field(
    text: str,
    min_val: int,
    max_val: int,
    names: Optional[dict[str, int]] = None,
    normalize: Optional[Callable[[int], int]] = None,
) -> CronField:
    text = text.strip()
    if not text:
        raise ValueError("empty cron field")

    restricted = text not in ("*", "?")
    values: set[int] = set()

    for part in text.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty list item in cron field")

        step = 1
        base = part
        if "/" in part:
            base, step_str = part.split("/", 1)
            base = base.strip()
            try:
                step = int(step_str.strip())
            except ValueError:
                raise ValueError(f"invalid step: {step_str!r}")
            if step <= 0:
                raise ValueError("step must be positive")

        if base == "*":
            lo, hi = min_val, max_val
        elif base == "?":
            lo, hi = min_val, max_val
        elif "-" in base:
            left, right = base.split("-", 1)
            lo = _to_number(left, names, min_val, max_val)
            hi = _to_number(right, names, min_val, max_val)
            if lo > hi:
                raise ValueError(f"invalid range: {base!r}")
        else:
            value = _to_number(base, names, min_val, max_val)
            if "/" in part and step > 1:
                lo, hi = value, max_val
            else:
                lo = hi = value

        for value in range(lo, hi + 1, step):
            if value < min_val or value > max_val:
                continue
            if normalize is not None:
                value = normalize(value)
            values.add(value)

    if not values:
        raise ValueError("cron field has no values")
    return CronField(values, text, restricted)


def parse(expression: str) -> Cron:
    if not isinstance(expression, str):
        raise ValueError("cron expression must be a string")
    expr = expression.strip()
    if not expr:
        raise ValueError("empty cron expression")

    lowered = expr.lower()
    if lowered == "@reboot":
        raise ValueError("@reboot is not supported")
    if lowered in SPECIAL_STRINGS:
        expr = SPECIAL_STRINGS[lowered]

    tokens = expr.split()
    if len(tokens) != 5:
        raise ValueError("cron expression must have exactly 5 fields")

    minute = _parse_field(tokens[0], 0, 59)
    hour = _parse_field(tokens[1], 0, 23)
    day_of_month = _parse_field(tokens[2], 1, 31)
    month = _parse_field(tokens[3], 1, 12, MONTH_NAMES)
    day_of_week = _parse_field(
        tokens[4],
        0,
        7,
        DAY_NAMES,
        normalize=lambda value: 0 if value == 7 else value,
    )

    normalized = " ".join(tokens)
    return Cron(normalized, [minute, hour, day_of_month, month, day_of_week])


def validate(expression: str) -> bool:
    parse(expression)
    return True


def explain(cron: Cron) -> str:
    names = ["minute", "hour", "day of month", "month", "day of week"]
    lines = [f"expression: {cron.expression}"]
    for name, field in zip(names, cron.fields):
        lines.append(f"{name}: {field.raw}")
    return "\n".join(lines)
