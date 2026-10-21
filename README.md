# cronpeek

`cronpeek` is a dependency-free Python CLI and library for working with
cron expressions. It can validate expressions, explain their fields,
and calculate upcoming or previous execution times.

## Features

- Standard five-field cron expressions: minute, hour, day of month,
  month, and day of week.
- Ranges, steps, lists, wildcards, and `?`.
- Month and weekday names, including `SUN`..`SAT` and `JAN`..`DEC`.
- Common special strings such as `@daily`, `@hourly`, and `@weekly`.
- Vixie-cron style day-of-month/day-of-week OR semantics when both
  fields are restricted.
- No third-party runtime dependencies.

## Installation

```bash
python -m pip install -e .
```

Python 3.9 or newer is required.

## Command-line usage

Validate an expression:

```bash
cronpeek "*/15 9-17 * * 1-5" --validate
```

Show the next five runs from now:

```bash
cronpeek "*/15 9-17 * * 1-5" --count 5
```

Show the next runs from a specific time:

```bash
cronpeek "0 12 * * 1" --count 3 --from "2025-01-01T00:00:00"
```

Show previous runs:

```bash
cronpeek "0 0 * * *" --previous --count 3 --from "2025-01-02T00:00:00"
```

Explain the fields:

```bash
cronpeek "0 9 * * 1-5" --explain
```

Custom output format:

```bash
cronpeek "0 * * * *" --count 2 --format "%Y-%m-%d %H:%M"
```

## Library usage

```python
from datetime import datetime
from cronpeek import parse

job = parse("*/15 9-17 * * 1-5")
print(job.matches(datetime(2025, 1, 6, 9, 30)))

for run in job.next(datetime(2025, 1, 1, 0, 0), count=3):
    print(run)
```

## Development

Run the tests with:

```bash
python -m unittest discover -s tests
```
