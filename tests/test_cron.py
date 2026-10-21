import unittest
from datetime import datetime

from cronpeek import parse, validate
from cronpeek.cron import explain


class ParseTests(unittest.TestCase):
    def test_basic_fields(self):
        job = parse("*/15 9-17 * * 1-5")
        self.assertTrue(job.matches(datetime(2025, 1, 6, 9, 0)))
        self.assertTrue(job.matches(datetime(2025, 1, 6, 9, 15)))
        self.assertFalse(job.matches(datetime(2025, 1, 6, 9, 7)))
        self.assertFalse(job.matches(datetime(2025, 1, 4, 9, 0)))

    def test_names(self):
        job = parse("0 0 1 jan mon")
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 0)))
        # 2025-01-06 is a Monday
        self.assertTrue(job.matches(datetime(2025, 1, 6, 0, 0)))

    def test_special_strings(self):
        job = parse("@daily")
        self.assertEqual(job.expression, "0 0 * * *")
        self.assertTrue(job.matches(datetime(2025, 3, 4, 0, 0)))

    def test_step_single_value(self):
        job = parse("5/10 * * * *")
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 5)))
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 15)))
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 55)))

    def test_list_and_range(self):
        job = parse("0,30 9,17 * * *")
        self.assertTrue(job.matches(datetime(2025, 1, 1, 9, 0)))
        self.assertTrue(job.matches(datetime(2025, 1, 1, 17, 30)))
        self.assertFalse(job.matches(datetime(2025, 1, 1, 10, 0)))

    def test_question_mark(self):
        job = parse("? * * * *")
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 0)))
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 59)))

    def test_weekday_sunday_conversion(self):
        job = parse("0 0 * * 0")
        # 2025-01-05 is a Sunday
        self.assertTrue(job.matches(datetime(2025, 1, 5, 0, 0)))
        self.assertFalse(job.matches(datetime(2025, 1, 6, 0, 0)))

    def test_vixie_or_semantics(self):
        job = parse("0 0 1 * 1")
        # day-of-month restricted and day-of-week restricted => OR
        self.assertTrue(job.matches(datetime(2025, 1, 1, 0, 0)))  # dom match
        # 2025-01-06 is Monday
        self.assertTrue(job.matches(datetime(2025, 1, 6, 0, 0)))  # dow match
        self.assertFalse(job.matches(datetime(2025, 1, 7, 0, 0)))

    def test_invalid_field_count(self):
        with self.assertRaises(ValueError):
            parse("* * *")

    def test_invalid_value(self):
        with self.assertRaises(ValueError):
            parse("60 * * * *")

    def test_invalid_step(self):
        with self.assertRaises(ValueError):
            parse("*/0 * * * *")

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            parse("10-5 * * * *")

    def test_reboot_rejected(self):
        with self.assertRaises(ValueError):
            parse("@reboot")

    def test_validate(self):
        self.assertTrue(validate("0 * * * *"))
        with self.assertRaises(ValueError):
            validate("bad")


class SchedulingTests(unittest.TestCase):
    def test_next(self):
        job = parse("0 * * * *")
        runs = job.next(datetime(2025, 1, 1, 0, 30), count=3)
        self.assertEqual(
            runs,
            [
                datetime(2025, 1, 1, 1, 0),
                datetime(2025, 1, 1, 2, 0),
                datetime(2025, 1, 1, 3, 0),
            ],
        )

    def test_next_zero(self):
        job = parse("* * * * *")
        self.assertEqual(job.next(datetime(2025, 1, 1, 0, 0), count=0), [])

    def test_previous(self):
        job = parse("0 * * * *")
        runs = job.previous(datetime(2025, 1, 1, 2, 30), count=3)
        self.assertEqual(
            runs,
            [
                datetime(2025, 1, 1, 2, 0),
                datetime(2025, 1, 1, 1, 0),
                datetime(2025, 1, 1, 0, 0),
            ],
        )

    def test_previous_strict(self):
        job = parse("0 * * * *")
        runs = job.previous(datetime(2025, 1, 1, 2, 0), count=1)
        self.assertEqual(runs, [datetime(2025, 1, 1, 1, 0)])

    def test_negative_count(self):
        job = parse("* * * * *")
        with self.assertRaises(ValueError):
            job.next(count=-1)
        with self.assertRaises(ValueError):
            job.previous(count=-1)


class ExplainTests(unittest.TestCase):
    def test_explain(self):
        job = parse("*/15 9-17 * * 1-5")
        text = explain(job)
        self.assertIn("minute: */15", text)
        self.assertIn("hour: 9-17", text)


class CliTests(unittest.TestCase):
    def test_validate_cli(self):
        from cronpeek.cli import main

        self.assertEqual(main(["0 * * * *", "--validate"]), 0)
        self.assertEqual(main(["bad", "--validate"]), 2)

    def test_next_cli(self):
        from cronpeek.cli import main
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["0 * * * *", "--count", "2", "--from", "2025-01-01T00:30"])
        self.assertEqual(rc, 0)
        self.assertEqual(
            buf.getvalue().strip().splitlines(),
            ["2025-01-01T01:00:00", "2025-01-01T02:00:00"],
        )

    def test_explain_cli(self):
        from cronpeek.cli import main
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["0 9 * * 1-5", "--explain"])
        self.assertEqual(rc, 0)
        self.assertIn("minute: 0", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
