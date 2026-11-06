from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import install_monitor
import thread_hopper_hook as monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.path = self.root / "rollout-test.jsonl"
        self.now = datetime.now(timezone.utc).timestamp()
        self.writes = 0
        self.event = {"session_id": "test-session", "hook_event_name": "PostToolUse",
                      "transcript_path": str(self.path)}

    def tearDown(self):
        self.directory.cleanup()

    def write_usage(self, fraction=.85, old=False):
        stamp = datetime.fromtimestamp(self.now - (1000 if old else 0), timezone.utc).isoformat()
        data = {"timestamp": stamp, "type": "event_msg", "payload": {"type": "token_count",
                "info": {"last_token_usage": {"input_tokens": int(fraction * 100000),
                         "cached_input_tokens": int(fraction * 90000)},
                         "model_context_window": 100000}}}
        self.path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        self.writes += 1
        os.utime(self.path, ns=(int(self.now * 1e9), int(self.now * 1e9) + self.writes * 1000000))

    def call(self, kind="PostToolUse", offset=0):
        return monitor.handle(dict(self.event, hook_event_name=kind), self.root, self.now + offset)

    def test_normal_usage_silent(self):
        self.write_usage(.4)
        self.assertIsNone(self.call())

    def test_warning_once_escalation_once(self):
        self.write_usage()
        result = self.call()
        self.assertIn("systemMessage", result)
        self.assertIn("hookSpecificOutput", result)
        self.assertNotIn("decision", result)
        self.assertNotIn("continue", result)
        self.assertIsNone(self.call(offset=1))
        self.write_usage(.94)
        self.assertIsNotNone(self.call(offset=2))
        self.assertIsNone(self.call(offset=3))

    def test_rearm_after_compaction(self):
        self.write_usage()
        self.call()
        self.write_usage(.2)
        self.assertIsNone(self.call())
        self.write_usage()
        self.assertIsNotNone(self.call())

    def test_collection_has_no_model_output(self):
        self.write_usage()
        self.assertIsNone(self.call("PostModelRequest"))
        self.assertIsNotNone(self.call("PostToolUse"))

    def test_snooze_defers_without_dropping_alert(self):
        self.write_usage()
        target = monitor.state_path(self.root, "test-session")
        monitor.atomic_json(target, {"snooze_until": self.now + 60})
        self.assertIsNone(self.call())
        self.assertIsNotNone(self.call(offset=61))

    def test_stale_missing_and_subagent_quiet(self):
        self.write_usage(old=True)
        self.assertIsNone(self.call())
        self.assertIsNone(monitor.handle(dict(self.event, transcript_path=None), self.root, self.now))
        self.write_usage()
        self.assertIsNone(monitor.handle(dict(self.event, agent_type="explorer"), self.root, self.now))

    def test_disabled_quiet(self):
        self.write_usage()
        monitor.atomic_json(self.root / "thread-hopper" / "config.json", {"enabled": False})
        self.assertIsNone(self.call())

    def test_stop_never_forces_continuation(self):
        self.write_usage()
        result = self.call("Stop")
        self.assertEqual(set(result), {"systemMessage"})
        result = self.call("UserPromptSubmit", 1)
        self.assertEqual(set(result), {"hookSpecificOutput"})
        self.assertIsNone(self.call("UserPromptSubmit", 2))

    def test_other_session_independent(self):
        self.write_usage()
        self.call()
        result = monitor.handle(dict(self.event, session_id="second"), self.root, self.now)
        self.assertIsNotNone(result)

    def test_busy_state_does_not_wait(self):
        self.write_usage()
        target = monitor.state_path(self.root, "test-session")
        with monitor.state_lock(target) as acquired:
            self.assertTrue(acquired)
            self.assertIsNone(self.call())

    def test_silent_cli_and_stop_json(self):
        self.write_usage(.2)
        script = str(Path(monitor.__file__))
        for kind, expected in (("PostModelRequest", ""), ("Stop", "{}")):
            result = subprocess.run([sys.executable, "-B", script, "--codex-home", str(self.root)],
                                    input=json.dumps(dict(self.event, hook_event_name=kind)),
                                    text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.strip(), expected)
            self.assertEqual(result.stderr, "")

    def test_error_never_breaks_stop(self):
        self.event["transcript_path"] = str(self.root / "missing.jsonl")
        result = subprocess.run([sys.executable, "-B", str(Path(monitor.__file__)),
                                 "--codex-home", str(self.root)],
                                input=json.dumps(dict(self.event, hook_event_name="Stop")),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})

    def test_status_is_read_only_before_first_hook(self):
        result = subprocess.run([sys.executable, "-B", str(Path(monitor.__file__)),
                                 "--codex-home", str(self.root), "--control", "status",
                                 "--session-id", "not-yet-seen"],
                                text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["monitor_status"], "not_observed")
        self.assertFalse((self.root / "thread-hopper").exists())

    def control(self, action, report=None):
        command = [sys.executable, "-B", str(Path(monitor.__file__)),
                   "--codex-home", str(self.root), "--session-id", "test-session",
                   "--control", action]
        if report is not None:
            incident = self.root / "incident.json"
            incident.write_text(json.dumps(report), encoding="utf-8")
            command += ["--incident-file", str(incident)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def report(self, incident_id="wrong-test-claim", basis="verified"):
        return self.control("report-reliability", {
            "incident_id": incident_id, "basis": basis,
            "summary": "Claimed a passing check without evidence",
            "evidence": "Task verification log contains a failing result"})

    def test_reliability_stay_preserves_future_context_warning(self):
        self.write_usage(.3)
        self.report()
        self.assertIn("systemMessage", self.call())
        self.control("dismiss-reliability")
        self.assertIsNone(self.call())
        self.write_usage(.85)
        result = self.call()
        self.assertIn("85%", result["systemMessage"])

    def test_context_snooze_does_not_suppress_reliability(self):
        self.write_usage(.85)
        self.control("snooze")
        self.report()
        result = self.call()
        self.assertIn("reliability", result["systemMessage"])
        self.assertNotIn("85%", result["systemMessage"])

    def test_reliability_suppression_does_not_reset_context_latch(self):
        self.write_usage(.85)
        self.call()
        before = self.control("status")["last_alert_level"]
        self.report()
        self.control("dismiss-reliability")
        self.assertEqual(self.control("status")["last_alert_level"], before)
        self.write_usage(.94)
        self.assertIn("94%", self.call()["systemMessage"])

    def test_same_incident_does_not_repeat_but_new_one_notifies(self):
        self.write_usage(.3)
        self.report()
        self.call()
        self.control("dismiss-reliability")
        self.report()
        self.assertIsNone(self.call())
        self.report("new-material-contradiction")
        self.assertIsNotNone(self.call())

    def test_updating_evidence_preserves_delivery(self):
        self.write_usage(.3)
        self.report(basis="user_reported")
        self.call()
        state = self.report(basis="verified")
        self.assertEqual(state["reliability"]["basis"], "verified")
        self.assertTrue(state["reliability"]["delivered"])
        self.assertIsNone(self.call())

    def test_reliability_does_not_need_fresh_usage_or_valid_path(self):
        self.write_usage(old=True)
        self.report()
        self.assertIsNotNone(self.call())
        self.control("dismiss-reliability")
        self.report("another-incident")
        self.path.unlink()
        self.assertIsNotNone(self.call())

    def test_report_basis_is_not_automatically_verified(self):
        self.write_usage(.3)
        self.report(basis="user_reported")
        result = self.call()
        self.assertIn("user-reported", result["systemMessage"])
        self.assertNotIn("Task verification log", json.dumps(result))
        self.assertNotIn("Claimed a passing", json.dumps(result))

    def test_startup_brief_once_and_after_compaction(self):
        self.write_usage(.3)
        self.assertIn("hookSpecificOutput", self.call("SessionStart"))
        self.assertIsNone(self.call("SessionStart"))
        event = dict(self.event, hook_event_name="SessionStart", source="compact")
        self.assertIn("hookSpecificOutput", monitor.handle(event, self.root, self.now))

    def test_concurrent_alerts_both_survive(self):
        self.write_usage(.85)
        self.report()
        result = self.call()
        self.assertIn("85%", result["systemMessage"])
        self.assertIn("reliability", result["systemMessage"])
        self.assertIsNone(self.call())

    def test_invalid_report_and_keyword_are_not_signals(self):
        with self.assertRaises(ValueError):
            monitor.reliability_report({"basis": "verified", "summary": "unsure"})
        self.write_usage(.3)
        event = dict(self.event, prompt="What does hallucination mean?")
        self.assertIsNone(monitor.handle(event, self.root, self.now))

    @unittest.skipUnless(os.name == "nt", "Windows hook-shell invocation")
    def test_windows_hook_command(self):
        self.write_usage(.2)
        command = (f'"{Path(sys.executable).as_posix()}" -B '
                   f'"{Path(monitor.__file__).as_posix()}" --codex-home "{self.root.as_posix()}"')
        result = subprocess.run(command, shell=True,
                                input=json.dumps(dict(self.event, hook_event_name="Stop")),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})


class InstallTests(unittest.TestCase):
    def test_fallback_preserves_guidance_and_is_idempotent(self):
        skill = Path(install_monitor.__file__).resolve().parents[1]
        original = b"\xef\xbb\xbf# Existing instructions\r\nKeep this exactly.\r\n"
        merged = install_monitor.merged_instructions(original, skill)
        self.assertTrue(merged.startswith(original))
        self.assertEqual(install_monitor.merged_instructions(merged, skill), merged)
        self.assertNotIn(b"{{SKILL_PATH}}", merged)
        removed = install_monitor.merged_instructions(merged, skill, True)
        self.assertTrue(removed.startswith(original))
        self.assertNotIn(install_monitor.START.encode(), removed)

    def test_fallback_updates_active_override_and_backs_up(self):
        skill = Path(install_monitor.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_bytes(b"normal guidance")
            override = root / "AGENTS.override.md"
            override.write_bytes(b"override guidance")
            preview = install_monitor.install_fallback(root, skill, dry_run=True)
            self.assertTrue(preview["changed"])
            self.assertEqual(override.read_bytes(), b"override guidance")
            install_monitor.install_fallback(root, skill)
            self.assertEqual((root / "AGENTS.md").read_bytes(), b"normal guidance")
            self.assertTrue(override.read_bytes().startswith(b"override guidance"))
            self.assertEqual(len(list((root / "thread-hopper" / "backups").iterdir())), 1)
            self.assertFalse(install_monitor.install_fallback(root, skill)["changed"])

    def test_fallback_refuses_incomplete_markers(self):
        with self.assertRaises(ValueError):
            install_monitor.merged_instructions(install_monitor.START.encode(), Path("."))

    def test_idempotent_merge_preserves_other_hooks(self):
        data = {"description": "existing", "hooks": {"PostToolUse": [{"matcher": "Bash",
                "hooks": [{"type": "command", "command": "other"}]}]}}
        merged = install_monitor.merged_hooks(data, "thread-hopper-command")
        self.assertEqual(install_monitor.merged_hooks(merged, "thread-hopper-command"), merged)
        self.assertEqual(merged["hooks"]["PostToolUse"][0], data["hooks"]["PostToolUse"][0])
        self.assertEqual(install_monitor.merged_hooks(merged, "thread-hopper-command", True), data)

    def test_only_stop_is_synchronous_and_none_block(self):
        hooks = install_monitor.merged_hooks({}, "monitor")["hooks"]
        for kind, groups in hooks.items():
            handler = groups[0]["hooks"][0]
            self.assertEqual(handler.get("async", False), kind != "Stop")
            self.assertNotIn("statusMessage", handler)
            self.assertLessEqual(handler["timeout"], 3)


if __name__ == "__main__":
    unittest.main()
