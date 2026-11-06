"""Behavioral checks use synthetic sources and disposable vaults only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hook import handle
from install import hook_command, install, merge_hooks
from vault import BEGIN, END, WORKER_MARKER, Vault, VaultError, atomic_json, digest, load_json, pack_note, split_note


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="context-vault-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / "Alpha"
        self.b = self.root / "Beta"
        self.a.mkdir()
        self.b.mkdir()
        self.v = Vault.initialize(self.root / "Vault")
        self.project = self.v.enroll(self.a, "learn", confirmed=True)
        self.doc = self.a / "selected.md"
        self.doc.write_text("Use PostgreSQL for this project.\n", encoding="utf-8")
        self.sid = self.v.source_add(self.a, self.doc, confirmed=True)
        self.chunk = self.v.source_read(self.sid)
        self.ref = self.chunk["messages"][0]["evidence"]
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.config = {"enabled": True, "vault": str(self.v.root), "transcript_roots": [str(self.sessions)]}

    def capture(self, **changes):
        item = {"title": "Database choice", "type": "decision", "scope": self.project["id"],
                "text": "This project uses PostgreSQL.", "basis": "stated", "status": "active",
                "sensitivity": "ordinary", "evidence": [self.ref]}
        item.update(changes)
        return self.v.upsert(self.a, item)

    def event(self, kind="UserPromptSubmit", cwd=None, session="synthetic-chat", **extra):
        return {"hook_event_name": kind, "cwd": str(cwd or self.a), "session_id": session,
                "turn_id": "turn-one", "prompt": "Which database?", **extra}

    def transcript(self, messages):
        path = self.sessions / "rollout-synthetic.jsonl"
        lines = [{"type": "session_meta", "payload": {"id": "synthetic-chat", "cwd": str(self.a)}}]
        lines += [{"type": "event_msg", "payload": {"type": "user_message" if role == "user" else "agent_message", "message": text}}
                  for role, text in messages]
        path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="synthetic-chat", transcript_roots=[self.sessions])
        return path, sid

    def test_unknown_gate_precedes_note_scan(self):
        with patch.object(self.v, "_scan", side_effect=AssertionError("read before consent")):
            with self.assertRaises(VaultError):
                self.v.recall(self.b, "database")

    def test_unknown_cannot_capture_or_register_source(self):
        with self.assertRaises(VaultError):
            self.v.source_add(self.b, self.doc, confirmed=True)

    def test_enrollment_requires_explicit_choice(self):
        with self.assertRaises(VaultError):
            self.v.enroll(self.b, "learn")
        self.assertEqual(self.v.enrollment(self.b)["mode"], "unknown")

    def test_enrollment_persists_across_instances(self):
        self.assertEqual(Vault(self.v.root).enrollment(self.a)["mode"], "learn")

    def test_retrieval_only_reads_but_cannot_learn(self):
        self.capture()
        self.v.enroll(self.a, "retrieve", confirmed=True)
        self.assertEqual(len(self.v.recall(self.a, "database")), 1)
        with self.assertRaises(VaultError):
            self.capture(title="New fact")
        self.assertFalse(self.v.pending())

    def test_off_disables_recall(self):
        self.v.enroll(self.a, "off", confirmed=True)
        with self.assertRaises(VaultError):
            self.v.recall(self.a)

    def test_cannot_enroll_vault_or_parent(self):
        for root in (self.v.root, self.root):
            with self.assertRaises(VaultError):
                self.v.enroll(root, "learn", confirmed=True)

    def test_projects_are_scoped_but_global_preferences_travel(self):
        self.capture()
        self.capture(title="Explanation style", type="preference", scope="global", text="Explain examples.")
        self.v.enroll(self.b, "retrieve", confirmed=True)
        notes = self.v.recall(self.b)
        self.assertEqual([x["title"] for x in notes], ["Explanation style"])

    def test_project_decision_cannot_be_global(self):
        with self.assertRaises(VaultError):
            self.capture(scope="global")

    def test_no_source_is_selected_implicitly(self):
        with self.assertRaises(VaultError):
            self.v.source_add(self.a, self.doc)

    def test_generated_notes_cannot_become_sources(self):
        saved = self.capture()
        with self.assertRaises(VaultError):
            self.v.source_add(self.a, self.v.root / saved["path"], confirmed=True)

    def test_evidence_cannot_cross_projects(self):
        other = self.v.enroll(self.b, "learn", confirmed=True)
        source = self.b / "notes.md"
        source.write_text("Beta source", encoding="utf-8")
        sid = self.v.source_add(self.b, source, confirmed=True)
        ref = self.v.source_read(sid)["messages"][0]["evidence"]
        with self.assertRaises(VaultError):
            self.capture(evidence=[ref])

    def test_tampered_evidence_is_rejected(self):
        with self.assertRaises(VaultError):
            self.capture(evidence=[{**self.ref, "token": "bad"}])

    def test_changed_source_is_rejected_before_save(self):
        self.doc.write_text("Use another database", encoding="utf-8")
        with self.assertRaises(VaultError):
            self.capture()
        self.assertFalse(self.v.recall(self.a))

    def test_unproven_inference_cannot_be_active(self):
        with self.assertRaises(VaultError):
            self.capture(basis="inferred")
        self.capture(basis="inferred", status="tentative")
        self.assertEqual(self.v.recall(self.a)[0]["status"], "tentative")

    def test_correction_updates_current_record_and_retains_history(self):
        first = self.capture()
        self.capture(id=first["id"], expected_revision=first["revision"], text="We now use SQLite.")
        notes = self.v.recall(self.a)
        self.assertEqual(len(notes), 1)
        self.assertIn("SQLite", notes[0]["text"])
        self.assertEqual(len(list((self.v.system / "history" / first["id"]).glob("*.md"))), 1)

    def test_stale_correction_cannot_clobber_newer_write(self):
        first = self.capture()
        self.capture(id=first["id"], expected_revision=first["revision"], text="Latest correction")
        with self.assertRaises(VaultError):
            self.capture(id=first["id"], expected_revision=first["revision"], text="Stale correction")

    def test_inference_cannot_overwrite_explicit_record(self):
        first = self.capture()
        with self.assertRaises(VaultError):
            self.capture(id=first["id"], expected_revision=first["revision"], basis="inferred", status="tentative")

    def test_same_topic_does_not_create_duplicate(self):
        first = self.capture()
        with self.assertRaises(VaultError):
            self.capture()
        self.assertEqual(len(self.v.recall(self.a)), 1)
        self.assertEqual(self.v.recall(self.a)[0]["id"], first["id"])

    def test_alias_matches_existing_topic(self):
        first = self.capture(aliases=["DB selection"])
        second = self.capture(title="DB selection", expected_revision=first["revision"])
        self.assertEqual(first["id"], second["id"])

    def test_previous_title_is_preserved_as_alias_after_a_rename(self):
        first = self.capture(aliases=["DB selection"])
        self.capture(id=first["id"], title="Chosen database", expected_revision=first["revision"])
        meta = self.v.inspect(self.a, first["id"])["properties"]
        self.assertIn("Database choice", meta["aliases"])
        self.assertIn("DB selection", meta["aliases"])

    def test_human_prose_outside_markers_is_preserved(self):
        first = self.capture()
        path = self.v.root / first["path"]
        with path.open("ab") as handle:
            handle.write(b"\n## My explanation\n\nKeep my exact words.\r\n")
        current = self.v.recall(self.a)[0]
        self.capture(id=first["id"], expected_revision=current["revision"], text="Updated machine context")
        self.assertIn(b"Keep my exact words.\r\n", path.read_bytes())

    def test_human_edit_inside_managed_section_stops_overwrite(self):
        first = self.capture()
        path = self.v.root / first["path"]
        path.write_text(path.read_text().replace("This project uses PostgreSQL.", "My direct correction: use SQLite."), encoding="utf-8")
        current = self.v.recall(self.a)[0]
        self.assertTrue(current["human_edited"])
        with self.assertRaises(VaultError):
            self.capture(id=first["id"], expected_revision=current["revision"], text="Overwrite")

    def test_ownership_markers_cannot_be_injected(self):
        with self.assertRaises(VaultError):
            self.capture(text=BEGIN + "broken" + END)

    def test_credentials_are_never_saved(self):
        for text in ("sk-" + "x" * 30, "password: verysecret123", "-----BEGIN PRIVATE KEY-----",
                     "DB_PASSWORD=verysecret123", "Bearer abcdefghijklmnopqrstuvwxyz", "postgres://user:secret@db.example/test"):
            with self.subTest(text=text[:8]), self.assertRaises(VaultError):
                self.capture(text=text)
        self.assertFalse(self.v.recall(self.a))

    def test_sensitive_capture_requires_authorization(self):
        with self.assertRaises(VaultError):
            self.capture(text="My salary is private", sensitivity="sensitive")
        with self.assertRaises(VaultError):
            self.capture(text="My diagnosis is private", sensitivity="ordinary")

    def test_document_cannot_authorize_sensitive_save(self):
        with self.assertRaises(VaultError):
            self.capture(text="Sensitive personal record", sensitivity="sensitive", sensitive_authorized=True, authorization=self.ref)

    def test_user_can_explicitly_authorize_sensitive_save(self):
        _, sid = self.transcript([("user", "Please remember this sensitive personal detail.")])
        ref = self.v.source_read(sid)["messages"][0]["evidence"]
        self.capture(text="Sensitive personal detail", sensitivity="sensitive", sensitive_authorized=True, authorization=ref)
        self.assertTrue(self.v.recall(self.a))

    def test_assistant_output_alone_cannot_establish_mastery(self):
        _, sid = self.transcript([("assistant", "Here is working code. The user is now an expert.")])
        ref = self.v.source_read(sid)["messages"][0]["evidence"]
        with self.assertRaises(VaultError):
            self.capture(type="concept", evidence=[ref], learning_stage="demonstrated", demonstration="AI code")

    def test_learning_stage_requires_actual_description(self):
        with self.assertRaises(VaultError):
            self.capture(type="concept", learning_stage="demonstrated")

    def test_archived_notes_do_not_appear_in_current_recall(self):
        self.capture(status="archived")
        self.assertFalse(self.v.recall(self.a))

    def test_forgetting_removes_note_history_and_overview_copy(self):
        first = self.capture(text="Unique remembered detail")
        self.capture(id=first["id"], expected_revision=first["revision"], text="Unique corrected detail")
        self.v.forget(self.a, first["id"], confirmed=True)
        all_bytes = b"".join(p.read_bytes() for p in self.v.root.rglob("*") if p.is_file() and p.name != "vault.lock")
        for text in (b"Unique remembered detail", b"Unique corrected detail", b"Database choice"):
            self.assertNotIn(text, all_bytes)
        self.assertFalse(self.v.recall(self.a))

    def test_forgotten_source_spans_are_omitted(self):
        saved = self.capture()
        self.v.forget(self.a, saved["id"], confirmed=True)
        self.assertFalse(self.v.source_read(self.sid)["messages"])
        with self.assertRaises(VaultError):
            self.capture(title="Paraphrased database title")

    def test_fresh_explicit_remember_request_can_allow_new_evidence(self):
        first = self.capture()
        self.v.forget(self.a, first["id"], confirmed=True)
        with self.assertRaises(VaultError):
            self.v.allow_topic(self.a, "decision", self.project["id"], "Database choice")
        self.v.allow_topic(self.a, "decision", self.project["id"], "Database choice", confirmed=True)
        new_doc = self.a / "fresh.md"
        new_doc.write_text("Remember the new database choice: SQLite.", encoding="utf-8")
        source = self.v.source_add(self.a, new_doc, confirmed=True)
        ref = self.v.source_read(source)["messages"][0]["evidence"]
        self.capture(text="The new choice is SQLite.", evidence=[ref])
        self.assertFalse(self.v.source_read(self.sid)["messages"])
        self.assertIn("SQLite", self.v.recall(self.a)[0]["text"])

    def test_inspect_checks_source_changes(self):
        first = self.capture()
        self.assertTrue(self.v.inspect(self.a, first["id"])["sources"][0]["unchanged"])
        self.doc.write_text("New owning source", encoding="utf-8")
        self.assertFalse(self.v.inspect(self.a, first["id"])["sources"][0]["unchanged"])

    def test_inspect_cannot_expose_another_projects_note(self):
        first = self.capture()
        self.v.enroll(self.b, "retrieve", confirmed=True)
        with self.assertRaises(VaultError):
            self.v.inspect(self.b, first["id"])

    def test_home_and_evidence_links_have_real_targets(self):
        from urllib.parse import unquote
        import re
        for target in re.findall(r"\]\((.*?)\)", (self.v.root / "Home.md").read_text()):
            self.assertTrue((self.v.root / unquote(target)).is_file())
        saved = self.capture()
        note = self.v.root / saved["path"]
        for target in re.findall(r"\]\((.*?)\)", note.read_text()):
            self.assertTrue((note.parent / unquote(target)).is_file())

    def test_forgetting_requires_explicit_request(self):
        first = self.capture()
        with self.assertRaises(VaultError):
            self.v.forget(self.a, first["id"])

    def test_interrupted_deletion_is_not_recalled(self):
        first = self.capture()
        with patch.object(self.v, "_finish_delete", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.v.forget(self.a, first["id"], confirmed=True)
        self.assertFalse(self.v.recall(self.a))
        self.v.maintain()
        self.assertFalse((self.v.root / first["path"]).exists())

    def test_checkpoint_cannot_skip_unread_data(self):
        with self.assertRaises(VaultError):
            self.v.checkpoint(self.sid, 0, self.chunk["through"] + 1, self.chunk["checkpoint"])

    def test_new_data_remains_pending_after_earlier_checkpoint(self):
        with self.doc.open("a", encoding="utf-8") as handle:
            handle.write("New context\n")
        self.v.checkpoint(self.sid, 0, self.chunk["through"], self.chunk["checkpoint"])
        self.assertTrue(self.v.pending())
        self.assertIn("New context", self.v.source_read(self.sid)["messages"][0]["text"])

    def test_processed_prefix_rewrite_is_not_silently_skipped(self):
        self.v.checkpoint(self.sid, 0, self.chunk["through"], self.chunk["checkpoint"])
        self.doc.write_text("Changed history\n", encoding="utf-8")
        with self.assertRaises(VaultError):
            self.v.source_read(self.sid)

    def test_same_size_document_rewrite_is_detected(self):
        self.v.checkpoint(self.sid, 0, self.chunk["through"], self.chunk["checkpoint"])
        original = self.doc.read_text()
        self.doc.write_text(original.replace("PostgreSQL", "ABCDEFGHIJ"), encoding="utf-8")
        self.assertIn(self.sid, [x["id"] for x in self.v.pending()])

    def test_explicit_document_reselection_recovers_rewritten_history(self):
        self.v.checkpoint(self.sid, 0, self.chunk["through"], self.chunk["checkpoint"])
        self.doc.write_text("New document version", encoding="utf-8")
        sid = self.v.source_add(self.a, self.doc, confirmed=True)
        self.assertEqual(sid, self.sid)
        self.assertIn("New document version", self.v.source_read(sid)["messages"][0]["text"])

    def test_unknown_message_after_known_metadata_is_not_acknowledged(self):
        path = self.sessions / "rollout-new-schema.jsonl"
        path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "new", "cwd": str(self.a)}}) + "\n" +
                        json.dumps({"type": "event_msg", "payload": {"type": "user_message_v2", "message": "Do not drop me"}}) + "\n", encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="new", transcript_roots=[self.sessions])
        with self.assertRaises(VaultError):
            self.v.source_read(sid)
        self.assertEqual(self.v._state()["sources"][sid]["cursor"], 0)

    def test_known_message_subtype_with_unknown_shape_is_rejected(self):
        path = self.sessions / "rollout-invalid-message.jsonl"
        for payload in ({"type": "user_message", "message": {"text": "Not a supported string"}},
                        {"type": "agent_message", "message": None}):
            path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "shape-test", "cwd": str(self.a)}}) + "\n" +
                            json.dumps({"type": "event_msg", "payload": payload}) + "\n", encoding="utf-8")
            sid = self.v.source_add(self.a, path, kind="chat", session="shape-test", transcript_roots=[self.sessions])
            with self.assertRaises(VaultError):
                self.v.source_read(sid)

    def test_unknown_response_content_shape_is_rejected(self):
        path = self.sessions / "rollout-invalid-response.jsonl"
        path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "shape-test", "cwd": str(self.a)}}) + "\n" +
                        json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": {"value": "Unsupported"}}]}}) + "\n", encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="shape-test", transcript_roots=[self.sessions])
        with self.assertRaises(VaultError):
            self.v.source_read(sid)

    def test_unchanged_source_can_acknowledge_a_zero_length_checkpoint(self):
        self.v.checkpoint(self.sid, 0, self.chunk["through"], self.chunk["checkpoint"])
        self.v.source_add(self.a, self.doc, confirmed=True)
        empty = self.v.source_read(self.sid)
        self.assertTrue(empty["unchanged"])
        self.v.checkpoint(self.sid, empty["start"], empty["through"], empty["checkpoint"])
        self.assertFalse(self.v.pending())

    def test_large_metadata_does_not_consume_message_budget(self):
        path = self.sessions / "rollout-large-metadata.jsonl"
        path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "large-metadata", "cwd": str(self.a), "instructions": "x" * 150000}}) + "\n" +
                        json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "A useful short fact"}}) + "\n", encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="large-metadata", transcript_roots=[self.sessions])
        chunk = self.v.source_read(sid)
        self.assertEqual([x["text"] for x in chunk["messages"]], ["A useful short fact"])
        self.v.checkpoint(sid, chunk["start"], chunk["through"], chunk["checkpoint"])

    def test_large_chat_is_chunked_by_text_budget_without_losing_messages(self):
        _, sid = self.transcript([("user", "a" * 40000), ("user", "b" * 40000)])
        first = self.v.source_read(sid)
        self.assertEqual(len(first["messages"]), 1)
        self.v.checkpoint(sid, first["start"], first["through"], first["checkpoint"])
        second = self.v.source_read(sid)
        self.assertEqual(second["messages"][0]["text"], "b" * 40000)

    def test_current_host_metadata_and_encrypted_assistant_items_are_supported(self):
        path = self.sessions / "rollout-host-shapes.jsonl"
        rows = [{"type": "session_meta", "payload": {"id": "host-shapes", "cwd": str(self.a)}}]
        rows += [{"type": kind, "payload": {}} for kind in ("inter_agent_communication_metadata", "token_usage_record", "world_state")]
        rows += [{"type": "event_msg", "payload": {"type": "thread_settings_applied"}},
                 {"type": "response_item", "payload": {"type": "additional_tools"}},
                 {"type": "response_item", "payload": {"type": "agent_message", "content": [
                     {"type": "text", "text": "Visible assistant context"},
                     {"type": "encrypted_text", "encrypted_content": "Never expose encrypted metadata"}]}},
                 {"type": "event_msg", "payload": {"type": "user_message", "message": "Actual user context"}}]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="host-shapes", transcript_roots=[self.sessions])
        result = self.v.source_read(sid)
        self.assertEqual([x["role"] for x in result["messages"]], ["assistant", "user"])
        self.assertNotIn("Never expose", json.dumps(result))

    def test_manual_overview_edit_is_preserved_and_reported(self):
        self.capture()
        overview = next((self.v.root / "Projects").glob("*/Overview.md"))
        original = overview.read_text()
        overview.write_text(original.replace(END, "My own overview explanation\n" + END), encoding="utf-8")
        result = self.v.maintain()
        self.assertIn("My own overview explanation", overview.read_text())
        self.assertIn(overview.relative_to(self.v.root).as_posix(), result["protected_overviews"])

    def test_forgetting_reports_protected_derived_copy(self):
        first = self.capture()
        overview = next((self.v.root / "Projects").glob("*/Overview.md"))
        overview.write_text(overview.read_text().replace(END, "My own explanation\n" + END), encoding="utf-8")
        result = self.v.forget(self.a, first["id"], confirmed=True)
        self.assertFalse(result["complete"])
        self.assertTrue(result["protected_overviews"])
        self.assertFalse(self.v.recall(self.a))

    def test_failure_preserves_pending_and_backs_off(self):
        self.v.fail(self.sid)
        self.assertFalse(self.v.pending())
        state = self.v._state()
        self.assertTrue(state["sources"][self.sid]["pending"])
        self.assertIn(self.sid, self.v.status()["errors"])

    def test_transcript_outside_allowed_root_is_rejected(self):
        with self.assertRaises(VaultError):
            self.v.source_add(self.a, self.doc, kind="chat", session="x", transcript_roots=[self.sessions])

    def test_transcript_metadata_prevents_cross_project_source_pairing(self):
        path = self.sessions / "rollout-other-project.jsonl"
        path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "other-session", "cwd": str(self.b)}}) + "\n" +
                        json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "Private other project content"}}) + "\n", encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="other-session", transcript_roots=[self.sessions])
        with self.assertRaisesRegex(VaultError, "different project"):
            self.v.source_read(sid)

    def test_transcript_metadata_prevents_wrong_session_pairing(self):
        path, _ = self.transcript([("user", "Original chat")])
        state = self.v._state()
        source = next(x for x in state["sources"].values() if x["kind"] == "chat")
        source["session"] = "wrong-session"
        self.v._save(state)
        with self.assertRaisesRegex(VaultError, "different session"):
            self.v.source_read(source["id"])

    def test_unknown_transcript_schema_is_not_acknowledged(self):
        path = self.sessions / "rollout-unknown.jsonl"
        path.write_text('{"new_schema": true}\n', encoding="utf-8")
        sid = self.v.source_add(self.a, path, kind="chat", session="new", transcript_roots=[self.sessions])
        with self.assertRaises(VaultError):
            self.v.source_read(sid)
        self.assertEqual(self.v._state()["sources"][sid]["cursor"], 0)

    def test_source_read_labels_roles_and_redacts_credentials(self):
        _, sid = self.transcript([("user", "api_key: abcdefghijklmnopqrstuvwxyz"), ("assistant", "Generated explanation")])
        result = self.v.source_read(sid)
        self.assertEqual([x["role"] for x in result["messages"]], ["user", "assistant"])
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", result["messages"][0]["text"])

    def test_processor_turn_is_excluded_without_disabling_later_user_messages(self):
        path, sid = self.transcript([("user", WORKER_MARKER + " maintain notes"), ("assistant", "Generated processor output")])
        handle(self.event(prompt=WORKER_MARKER + " maintain notes"), self.config)
        self.v.processor("synthetic-chat")
        chunk = self.v.source_read(sid)
        self.assertFalse(chunk["messages"])
        self.v.checkpoint(sid, chunk["start"], chunk["through"], chunk["checkpoint"])
        self.assertEqual(handle(self.event("Stop", transcript_path=str(path)), self.config), {})
        self.assertNotIn(sid, [x["id"] for x in self.v.pending()])
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "My next ordinary project decision"}}) + "\n")
        handle(self.event(prompt="My next ordinary project decision", turn_id="turn-two"), self.config)
        self.assertEqual(self.v.source_read(sid)["messages"][0]["text"], "My next ordinary project decision")

    def test_processor_cannot_guess_or_permanently_disable_a_session(self):
        with self.assertRaises(VaultError):
            self.v.processor("unobserved-session")

    def test_unknown_project_hook_asks_choices_without_retrieval(self):
        with patch.object(Vault, "recall", side_effect=AssertionError("premature recall")):
            output = handle(self.event(cwd=self.b), self.config)
        text = output["hookSpecificOutput"]["additionalContext"]
        for choice in ("A.", "B.", "C.", "explicit selection"):
            self.assertIn(choice, text)

    def test_hook_automatically_recalls_without_skill_mention(self):
        self.capture()
        output = handle(self.event(), self.config)
        self.assertIn("PostgreSQL", output["hookSpecificOutput"]["additionalContext"])

    def test_stop_queues_only_source_pointer(self):
        path, sid = self.transcript([("user", "A synthetic durable preference")])
        handle(self.event("Stop", transcript_path=str(path)), self.config)
        state = self.v.state_file.read_text()
        self.assertNotIn("A synthetic durable preference", state)
        self.assertIn(sid, [x["id"] for x in self.v.pending()])

    def test_retrieval_only_hook_cannot_queue_capture(self):
        path, _ = self.transcript([("user", "Later context")])
        self.v.enroll(self.a, "retrieve", confirmed=True)
        with patch.object(Vault, "source_add", side_effect=AssertionError("capture in read-only")):
            self.assertEqual(handle(self.event("Stop", transcript_path=str(path)), self.config), {})

    def test_invalid_properties_and_duplicate_id_are_rejected(self):
        with self.assertRaises(VaultError):
            split_note("---\nscope: global\nscope: other\n---\nBody")
        with self.assertRaises(VaultError):
            split_note("---\nid: {nested: value}\n---\nBody")

    def test_obsidian_date_properties_are_supported(self):
        meta, _ = split_note("---\nverified: 2026-11-05\n---\nBody")
        self.assertEqual(meta["verified"], "2026-11-05")

    def test_manual_move_is_reconciled_without_rewriting_prose(self):
        first = self.capture()
        original = self.v.root / first["path"]
        destination = original.with_name("My chosen filename.md")
        original.rename(destination)
        self.v.maintain()
        self.assertEqual(self.v.recall(self.a)[0]["path"], destination.relative_to(self.v.root).as_posix())

    def test_cli_json_round_trip(self):
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("context_vault.py")),
                                 "--vault", str(self.v.root), "enrollment", "--project", str(self.a)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "learn")

    def test_installer_dry_run_has_no_side_effects(self):
        home = self.root / "fake-codex"
        destination = self.root / "new-vault"
        output = install(destination, home, dry_run=True)
        self.assertTrue(output["dry_run"])
        self.assertFalse(home.exists())
        self.assertFalse(destination.exists())

    def test_installer_preserves_other_hooks_and_is_idempotent(self):
        old = {"description": "user config", "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "unrelated"}]}]}}
        once = merge_hooks(old, "our-command")
        self.assertEqual(once, merge_hooks(once, "our-command"))
        removed = merge_hooks(once, "our-command", remove=True)
        self.assertEqual(removed, old)

    def test_installer_preserves_non_command_handlers(self):
        data = {"hooks": {"SessionStart": [{"hooks": [{"type": "mcp_tool", "server": "example", "tool": "hello"}]}]}}
        updated = merge_hooks(data, "ours")
        self.assertEqual(updated["hooks"]["SessionStart"][0], data["hooks"]["SessionStart"][0])
        self.assertEqual(merge_hooks(updated, "ours", remove=True), data)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell launcher check")
    def test_registered_launcher_executes_through_powershell(self):
        config = self.root / "hook-config.json"
        atomic_json(config, self.config)
        command = hook_command(sys.executable, Path(__file__).with_name("hook.py").resolve(), config, windows=True)
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                input=json.dumps({"hook_event_name": "ContextVaultDiagnostic"}),
                                capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})

    def test_windows_unsupported_launcher_paths_fail_explicitly(self):
        with self.assertRaises(VaultError):
            hook_command("C:/Program Files/Python/python.exe", "C:/skill/hook.py", "C:/config.json", windows=True)

    def test_typed_boolean_options_cannot_be_faked_by_strings(self):
        for field in ("verified", "unclassified", "sensitive_authorized"):
            with self.subTest(field=field), self.assertRaises(VaultError):
                self.capture(**{field: "false"})

    def test_install_and_remove_are_scoped_to_fake_home(self):
        home = self.root / "fake-home"
        home.mkdir()
        old = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "unrelated"}]}]}}
        atomic_json(home / "hooks.json", old)
        target = self.root / "installed-vault"
        result = install(target, home)
        self.assertTrue(Path(result["skill"]).joinpath("SKILL.md").exists())
        self.assertEqual(load_json(home / "context-vault" / "config.json")["enabled"], True)
        install(target, home, remove=True)
        self.assertEqual(load_json(home / "hooks.json"), old)
        self.assertTrue(target.exists())

    def test_concurrent_distinct_captures_preserve_all_records(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: self.capture(title=f"Concurrent item {i}"), range(4)))
        self.assertEqual(len({x["id"] for x in results}), 4)
        self.assertEqual(len(self.v.recall(self.a, limit=12)), 4)


if __name__ == "__main__":
    unittest.main()
