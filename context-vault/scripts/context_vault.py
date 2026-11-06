"""Context Vault command interface. JSON input and output; no shell-built user data."""

import argparse
import json
import os
from pathlib import Path
import sys

from vault import Vault, VaultError, load_json


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--vault", required=True)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("status")
    commands.add_parser("pending")
    commands.add_parser("maintain")
    for name in ("enrollment", "enroll", "recall", "capture", "source-add", "forget", "inspect", "allow-topic"):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True)
        if name == "enroll":
            command.add_argument("--mode", choices=("learn", "retrieve", "off"), required=True)
            command.add_argument("--confirmed", action="store_true")
        elif name == "recall":
            command.add_argument("--query", default="")
            command.add_argument("--limit", type=int, default=6)
        elif name == "capture":
            command.add_argument("--input", help="UTF-8 JSON file; omit to read JSON from stdin")
        elif name == "source-add":
            command.add_argument("--path", required=True)
            command.add_argument("--confirmed", action="store_true")
        elif name in {"forget", "inspect"}:
            command.add_argument("--id", required=True)
            if name == "forget":
                command.add_argument("--confirmed", action="store_true")
        elif name == "allow-topic":
            command.add_argument("--type", choices=("preference", "background", "context", "decision", "concept"), required=True)
            command.add_argument("--scope", required=True)
            command.add_argument("--title", required=True)
            command.add_argument("--confirmed", action="store_true")
    for name in ("source-read", "checkpoint", "fail"):
        command = commands.add_parser(name)
        command.add_argument("--source", required=True)
        if name == "checkpoint":
            command.add_argument("--start", type=int, required=True)
            command.add_argument("--through", type=int, required=True)
            command.add_argument("--token", required=True)
    command = commands.add_parser("processor")
    command.add_argument("--session", default=os.environ.get("CODEX_THREAD_ID"))
    return result


def execute(args):
    if args.command == "init":
        Vault.initialize(args.vault)
        return {"initialized": True, "vault": str(Path(args.vault).resolve())}
    vault = Vault(args.vault)
    if args.command == "status":
        return vault.status()
    if args.command == "enrollment":
        return vault.enrollment(args.project)
    if args.command == "enroll":
        return vault.enroll(args.project, args.mode, args.confirmed)
    if args.command == "recall":
        return vault.recall(args.project, args.query, args.limit)
    if args.command == "capture":
        payload = load_json(args.input) if args.input else json.load(sys.stdin)
        return vault.upsert(args.project, payload)
    if args.command == "source-add":
        return {"source": vault.source_add(args.project, args.path, confirmed=args.confirmed)}
    if args.command == "source-read":
        return vault.source_read(args.source)
    if args.command == "checkpoint":
        return vault.checkpoint(args.source, args.start, args.through, args.token)
    if args.command == "pending":
        return vault.pending()
    if args.command == "fail":
        vault.fail(args.source)
        return {"pending_retained": True}
    if args.command == "forget":
        return vault.forget(args.project, args.id, args.confirmed)
    if args.command == "inspect":
        return vault.inspect(args.project, args.id)
    if args.command == "allow-topic":
        return vault.allow_topic(args.project, args.type, args.scope, args.title, args.confirmed)
    if args.command == "maintain":
        return vault.maintain()
    if args.command == "processor":
        vault.processor(args.session)
        return {"processor_turn_excluded_from_learning": True}
    raise VaultError("Unsupported command")


def main():
    args = parser().parse_args()
    try:
        print(json.dumps(execute(args), ensure_ascii=False, allow_nan=False))
    except (VaultError, OSError, ValueError, KeyError, TypeError) as exc:
        # Exception strings from paths and parsers can contain source content.
        message = str(exc) if isinstance(exc, VaultError) else "Operation failed; inspect local configuration and input"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
