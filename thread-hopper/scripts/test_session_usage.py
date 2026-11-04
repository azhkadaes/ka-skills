import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

import session_usage as usage


class CostTests(unittest.TestCase):
    def setUp(self):
        self.rates = {"input": 50, "cached": 2.5, "output": 250}
        self.case = {"name": "base", "strategies": {
            "stay": {"requests": [{"input": 100000, "cached": 100000, "repeat": 5}]},
            "restart": {"transition": [{"output": 2000}],
                        "requests": [{"input": 10000},
                                     {"input": 10000, "cached": 10000, "repeat": 4}]}}}
        self.data = {"unit": "credits", "billing": "subscription-proxy", "rates": self.rates,
                     "cases": [self.case, copy.deepcopy(self.case)]}
        self.data["cases"][1]["name"] = "conservative"

    def test_cached_cost(self):
        self.assertAlmostEqual(usage.request_cost({"input": 100000, "cached": 100000}, self.rates), .25)

    def test_break_even_five_requests(self):
        result = usage.compare(self.data)
        self.assertAlmostEqual(result["cases"][0]["costs"]["restart"], 1.1)
        self.assertFalse(result["recommend_restart"])  # 12% saving is below 20% margin.
        self.data["margin"] = 0.1
        self.assertTrue(usage.compare(self.data)["recommend_restart"])

    def test_short_horizon_stays(self):
        for case in self.data["cases"]:
            case["strategies"]["stay"]["requests"][0]["repeat"] = 1
            case["strategies"]["restart"]["requests"] = [{"input": 10000}]
        self.assertFalse(usage.compare(self.data)["recommend_restart"])

    def test_compaction_can_win(self):
        self.data["margin"] = 0
        self.data["cases"][1]["strategies"]["compact"] = {
            "requests": [{"input": 1000, "repeat": 5}]}
        self.assertFalse(usage.compare(self.data)["recommend_restart"])

    def test_single_case_not_recommendation(self):
        self.data["margin"] = 0
        self.data["cases"] = [self.case]
        self.assertFalse(usage.compare(self.data)["recommend_restart"])

    def test_cli_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.json"
            path.write_text(json.dumps(self.data), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(Path(usage.__file__)),
                                     "compare", "--scenario", str(path)],
                                    capture_output=True, text=True, check=True)
            self.assertAlmostEqual(json.loads(result.stdout)["cases"][0]["costs"]["stay"], 1.25)

    def test_writes_disjoint_from_input(self):
        result = usage.request_cost({"input": 12000, "cached": 4000, "writes": [
            {"tokens": 3000, "rate": 1.25}, {"tokens": 4000, "rate": 2.5}]},
            {"input": 1, "cached": .1, "output": 5})
        self.assertAlmostEqual(result, .01515)

    def test_invalid_counts(self):
        for request in ({"input": 5, "cached": 6}, {"input": -1}, {"input": True},
                        {"input": float("nan")}, {"repeat": 0}, {"input": 1.5}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                usage.request_cost(request, self.rates)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "rollout-test.jsonl"
        self.now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        self.info = {"last_token_usage": {"input_tokens": 109712, "cached_input_tokens": 104960,
                                         "output_tokens": 324, "reasoning_output_tokens": 17},
                     "total_token_usage": {"input_tokens": 1417789},
                     "model_context_window": 258400}

    def tearDown(self):
        self.directory.cleanup()

    def write(self, info=None, stamp="2026-11-04T12:00:00Z"):
        rows = [{"type": "turn_context", "payload": {"model": "gpt-6.1-sol"}},
                {"type": "event_msg", "timestamp": stamp,
                 "payload": {"type": "token_count", "info": info or self.info}}]
        self.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_last_request_not_lifetime(self):
        self.write()
        result = usage.snapshot(self.path, now=self.now)
        self.assertEqual(result["status"], "observed")
        self.assertAlmostEqual(result["last_input_window_fraction"], 109712 / 258400)
        self.assertAlmostEqual(result["cache_hit_fraction"], 104960 / 109712)
        self.assertFalse(result["context_pressure"])

    def test_partial_final_line(self):
        self.write()
        with self.path.open("a") as handle:
            handle.write('{"type":')
        self.assertEqual(usage.snapshot(self.path, now=self.now)["status"], "observed")

    def test_bounded_watch_emits_one_baseline(self):
        self.write()
        result = subprocess.run([sys.executable, "-B", str(Path(usage.__file__)), "watch",
                                 "--session", str(self.path), "--duration", "0.01", "--interval", "1"],
                                capture_output=True, text=True, check=True)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "baseline")

    def test_invalid_thread_does_not_search_other_chats(self):
        result = subprocess.run([sys.executable, "-B", str(Path(usage.__file__)), "snapshot",
                                 "--thread-id", "../other"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_stale_not_pressure(self):
        self.write(stamp="2026-11-04T11:00:00Z")
        result = usage.snapshot(self.path, now=self.now)
        self.assertEqual(result["status"], "stale")
        self.assertIsNone(result["context_pressure"])

    def test_missing_cache_not_zero(self):
        del self.info["last_token_usage"]["cached_input_tokens"]
        self.write()
        self.assertIsNone(usage.snapshot(self.path, now=self.now)["cache_hit_fraction"])

    def test_missing_and_invalid_usage(self):
        self.path.write_text("{}\n", encoding="utf-8")
        self.assertEqual(usage.snapshot(self.path, now=self.now)["status"], "unavailable")
        self.info["last_token_usage"]["cached_input_tokens"] = 999999
        self.write()
        self.assertEqual(usage.snapshot(self.path, now=self.now)["status"], "unavailable")

    def test_bounded_tail_and_no_transcript_output(self):
        self.write()
        original = self.path.read_bytes()
        self.path.write_bytes(original.split(b"\n", 1)[0] + b"\n" +
                              b'{"secret_conversation":"do not emit"}\n' * 100000 +
                              original.split(b"\n", 1)[1])
        result = usage.snapshot(self.path, now=self.now)
        self.assertEqual(result["model"], "gpt-6.1-sol")
        self.assertEqual(result["status"], "observed")
        self.assertNotIn("do not emit", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
