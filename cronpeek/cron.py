"""Core cron expression parsing and matching logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Optional, Set


MONTH_NAMES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

WEEKDAY_NAMES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}

SPECIAL_EXPRESSIONS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_MAX_SEARCH_MINUTES = 5 * 366 * 24 * 60


@dataclass(frozen=True)
class CronField:
    """A single cron field."""

    values: frozenset[int]
    restricted: bool
    text: str = field(default="*", compare=False)

    def matches(self, value: int) -> bool:
        return value in self.values


def _parse_value(token: str, minimum: int, maximum: int, names: Optional[dict[str, int]]) -> int:
    token = token.strip()
    if names is not None and token.lower() in names:
        value = names[token.lower()]
    else:
        try:
            value = int(token, 10)
        except ValueError as exc:
            raise ValueError(f"invalid value {token!r}") from exc
    if value < minimum or value > maximum:
        raise ValueError(
            f"value {value} is outside the allowed range {minimum}-{maximum}"
        )
    return value


def _parse_field(
    text: str,
    minimum: int,
    maximum: int,
    names: Optional[dict[str, int]],
    normalize: Optional[callable] = None,
) -> CronField:
    text = text.strip()
    if not text:
        raise ValueError("empty cron field")

    restricted = text not in ("*", "?")
    values: Set[int] = set()

    for segment in text.split(","):
        segment = segment.strip()
        if not segment:
            raise ValueError("empty cron field segment")

        if "/" in segment:
            base, step_text = segment.split("/", 1)
            try:
                step = int(step_text, 10)
            except ValueError as exc:
                raise ValueError(f"invalid step {step_text!r}") from exc
            if step <= 0:
                raise ValueError("cron step must be positive")
        else:
            base = segment
            step = 1

        base = base.strip()
        if base in ("*", "?"):
            low, high = minimum, maximum
        elif "-" in base:
            left, right = base.split("-", 1)
            low = _parse_value(left, minimum, maximum, names)
            high = _parse_value(right, minimum, maximum, names)
            if low > high:
                raise ValueError(f"invalid range {base!r}")
        else:
            low = high = _parse_value(base, minimum, maximum, names)
            if "/" in segment and "-" not in base and base not in ("*", "?"):
                high = maximum

        for value in range(low, high + 1, step):
            if minimum <= value <= maximum:
                values.add(value)

    if normalize is not None:
        values = {normalize(value) for value in values}

    if not values:
        raise ValueError("cron field has no values")
    if any(value < minimum or value > maximum for value in values):
        raise ValueError("cron field value out of range")

    return CronField(frozenset(values), restricted, text=text)


@dataclass(frozen=True)
class Cron:
    """A parsed cron expression."""

    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField
    expression: str

    def matches(self, value: datetime) -> bool:
        """Return whether ``value`` is a scheduled time."""
        if not self.minute.matches(value.minute):
            return False
        if not self.hour.matches(value.hour):
            return False
        if not self.month.matches(value.month):
            return False

        day_of_month_match = self.day_of_month.matches(value.day)
        cron_weekday = (value.weekday() + 1) % 7
        day_of_week_match = self.day_of_week.matches(cron_weekday)

        if self.day_of_month.restricted and self.day_of_week.restricted:
            return day_of_month_match or day_of_week_match
        return day_of_month_match and day_of_week_match

    def next(self, after: Optional[datetime] = None, count: int = 1) -> list[datetime]:
        """Return the next ``count`` runs strictly after ``after``."""
        if count < 0:
            raise ValueError("count must not be negative")
        if after is None:
            after = datetime.now()
        if count == 0:
            return []

        current = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        result: list[datetime] = []
        for _ in range(_MAX_SEARCH_MINUTES):
            if self.matches(current):
                result.append(current)
                if len(result) == count:
                    break
            current += timedelta(minutes=1)
        return result

    def previous(
        self, after: Optional[datetime] = None, count: int = 1
    ) -> list[datetime]:
        """Return the most recent ``count`` runs strictly before ``after``."""
        if count < 0:
            raise ValueError("count must not be negative")
        if after is None:
            after = datetime.now()
        if count == 0:
            return []

        current = after.replace(second=0, microsecond=0)
        if current >= after:
            current -= timedelta(minutes=1)

        result: list[datetime] = []
        for _ in range(_MAX_SEARCH_MINUTES):
            if self.matches(current):
                result.append(current)
                if len(result) == count:
                    break
            current -= timedelta(minutes=1)
        return result


def parse(expression: str) -> Cron:
    """Parse a cron expression into a :class:`Cron` object."""
    expression = expression.strip()
    if not expression:
        raise ValueError("cron expression must not be empty")

    lowered = expression.lower()
    if lowered == "@reboot":
        raise ValueError("@reboot is not a schedulable cron expression")
    if lowered in SPECIAL_EXPRESSIONS:
        expression = SPECIAL_EXPRESSIONS[lowered]

    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron expression must have exactly five fields")

    minute_text, hour_text, day_text, month_text, weekday_text = fields

    minute = _parse_field(minute_text, 0, 59, None)
    hour = _parse_field(hour_text, 0, 23, None)
    day_of_month = _parse_field(day_text, 1, 31, None)
    month = _parse_field(month_text, 1, 12, MONTH_NAMES)
    day_of_week = _parse_field(
        weekday_text,
        0,
        7,
        WEEKDAY_NAMES,
        normalize=lambda value: 0 if value == 7 else value,
    )

    return Cron(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month=month,
        day_of_week=day_of_week,
        expression=expression,
    )


def validate(expression: str) -> bool:
    """Return ``True`` if ``expression`` is a valid cron expression."""
    parse(expression)
    return True


def describe_field(field: CronField, minimum: int, maximum: int) -> str:
    """Return a compact human-readable description of a field."""
    if not field.restricted:
        return "*"
    values = sorted(field.values)
    if values == list(range(minimum, maximum + 1)):
        return "*"
    if len(values) <= 12:
        return ",".join(str(value) for value in values)
    return f"{len(values)} values"


def explain(cron: Cron) -> str:
    """Return a multi-line explanation of a parsed cron expression."""
    lines = [
        f"expression: {cron.expression}",
        f"minute: {cron.minute.text}",
        f"hour: {cron.hour.text}",
        f"day of month: {cron.day_of_month.text}",
        f"month: {cron.month.text}",
        f"day of week: {cron.day_of_week.text}",
    ]
    return "\n".join(lines)
