"""Bounded local Codex usage inspection and explicit cost forecasts. No network calls."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time

HEAD_BYTES = 65536
TAIL_BYTES = 2 * 1024 * 1024


def number(value, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value) or value < 0 or (integer and int(value) != value):
        raise ValueError(f"{name} must be finite and nonnegative" + (" integer" if integer else ""))
    return value


def fraction(value, name):
    value = number(value, name)
    if value > 1:
        raise ValueError(f"{name} must be between zero and one")
    return value


def resolve_session(args):
    if args.session:
        path = Path(args.session).expanduser().resolve(strict=True)
        if path.suffix != ".jsonl" or not path.name.startswith("rollout-"):
            raise ValueError("Expected an explicitly selected rollout-*.jsonl file")
        return path
    thread_id = args.thread_id
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", thread_id):
        raise ValueError("thread-id must be a UUID")
    root = Path(args.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    matches = []
    for folder in ("sessions", "archived_sessions"):
        matches.extend((root / folder).glob(f"**/rollout-*{thread_id}.jsonl"))
    if len(matches) != 1:
        raise ValueError(f"Expected one rollout for this thread; found {len(matches)}. Supply --session.")
    return matches[0].resolve()


def read_events(path):
    # Bound both I/O and returned metadata even for multi-gigabyte histories.
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if size <= HEAD_BYTES + TAIL_BYTES:
            chunks = [handle.read(HEAD_BYTES + TAIL_BYTES)]
        else:
            head = handle.read(HEAD_BYTES).rsplit(b"\n", 1)[0]
            handle.seek(size - TAIL_BYTES)
            tail = handle.read(TAIL_BYTES).split(b"\n", 1)[-1]
            chunks = [head, tail]
    for chunk in chunks:
        for line in chunk.splitlines():
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue  # An actively appended final line may be incomplete.
            if isinstance(event, dict):
                yield event


def snapshot(path, pressure=0.8, max_age=300, now=None):
    latest = None
    model = None
    for event in read_events(path):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if event.get("type") == "turn_context":
            model = payload.get("model")
        if event.get("type") == "event_msg" and payload.get("type") == "token_count":
            latest = (event.get("timestamp"), payload.get("info"))
    result = {"source": str(path), "model": model, "status": "unavailable"}
    if latest is None or not isinstance(latest[1], dict):
        result["reason"] = "No usable usage event in bounded scan"
        return result
    stamp, info = latest
    last = info.get("last_token_usage")
    if not isinstance(last, dict) or "input_tokens" not in last:
        result["reason"] = "Latest event has no last-request counters"
        return result
    try:
        input_tokens = number(last["input_tokens"], "input_tokens", True)
        cached = last.get("cached_input_tokens")
        if cached is not None:
            cached = number(cached, "cached_input_tokens", True)
            if cached > input_tokens:
                raise ValueError("cached_input_tokens exceeds input_tokens")
        window = info.get("model_context_window")
        if window is not None:
            window = number(window, "model_context_window", True)
            if not window:
                raise ValueError("model_context_window must be positive")
        timestamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Usage timestamp has no timezone")
        age = ((now or datetime.now(timezone.utc)) - timestamp).total_seconds()
        if age < -60:
            raise ValueError("Usage timestamp is in the future")
    except (ValueError, TypeError, AttributeError) as error:
        result["reason"] = str(error)
        return result
    fields = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens", "total_tokens")
    result.update({
        "status": "stale" if age > max_age else "observed",
        "timestamp": stamp,
        "age_seconds": round(max(0, age), 1),
        "last_request": {key: last[key] for key in fields if key in last},
        "model_context_window": window,
        "cache_hit_fraction": cached / input_tokens if cached is not None and input_tokens else None,
        "last_input_window_fraction": input_tokens / window if window else None,
        "context_pressure": input_tokens / window >= pressure if window and age <= max_age else None,
        "economics": "unknown until an explicit forecast is supplied",
    })
    return result


def request_cost(request, rates):
    inp = number(request.get("input", 0), "input", True)
    cached = number(request.get("cached", 0), "cached", True)
    output = number(request.get("output", 0), "output", True)
    repeat = number(request.get("repeat", 1), "repeat", True)
    if repeat < 1:
        raise ValueError("repeat must be positive")
    writes = request.get("writes", [])
    written = sum(number(w["tokens"], "write tokens", True) for w in writes)
    if cached + written > inp:
        raise ValueError("Cached and written tokens exceed total input")
    write_cost = sum(w["tokens"] * number(w["rate"], "write rate") for w in writes)
    cost = ((inp - cached - written) * rates["input"] + cached * rates["cached"]
            + write_cost + output * rates["output"]) * repeat / 1_000_000
    if not math.isfinite(cost):
        raise ValueError("Forecast cost overflow")
    return cost


def compare(data):
    billing = data["billing"]
    if billing not in ("api", "codex-credits", "subscription-proxy", "relative"):
        raise ValueError("Unknown billing mode")
    unit = data["unit"]
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("A cost unit is required")
    rates = {key: number(data["rates"][key], f"{key} rate")
             for key in ("input", "cached", "output")}
    margin = fraction(data.get("margin", 0.2), "margin")
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("At least one forecast case is required")
    results = []
    for case in cases:
        strategies = case["strategies"]
        if not {"stay", "restart"} <= strategies.keys():
            raise ValueError("Each case requires stay and restart strategies")
        if strategies.keys() - {"stay", "restart", "compact"}:
            raise ValueError("Unknown strategy")
        costs = {}
        for name, strategy in strategies.items():
            if not strategy.get("requests"):
                raise ValueError("Each strategy requires remaining task requests")
            costs[name] = sum(request_cost(r, rates) for r in
                              strategy.get("transition", []) + strategy["requests"])
        alternative = min((name for name in costs if name != "restart"), key=costs.get)
        baseline = costs[alternative]
        savings = baseline - costs["restart"]
        ratio = savings / baseline if baseline else 0
        results.append({"name": case["name"], "costs": costs,
                        "best_alternative": alternative,
                        "restart_savings": savings, "restart_savings_fraction": ratio,
                        "clears_margin": savings > 0 and ratio >= margin})
    warnings = []
    if any("compact" not in case["strategies"] for case in cases):
        warnings.append("Compaction is not modeled in every case")
    if billing == "subscription-proxy":
        warnings.append("Credit-rate proxy does not predict exact subscription allowance")
    if len(cases) < 2:
        warnings.append("Supply base and conservative cases before recommending a restart")
    return {"unit": unit, "billing": billing, "margin": margin, "cases": results,
            "recommend_restart": len(cases) >= 2 and all(r["clears_margin"] for r in results),
            "warnings": warnings,
            "forecast_only": "Assumptions and equivalent task outcomes require human/agent review"}


def load_forecast(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return compare(json.load(handle))


def emit(value):
    print(json.dumps(value, ensure_ascii=True, allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "watch"):
        command = subs.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--session")
        source.add_argument("--thread-id")
        command.add_argument("--codex-home")
        command.add_argument("--pressure", type=float, default=0.8)
        command.add_argument("--max-age", type=float, default=300)
        if name == "watch":
            command.add_argument("--interval", type=float, default=30)
            command.add_argument("--duration", type=float, default=600)
            command.add_argument("--scenario")
    command = subs.add_parser("compare")
    command.add_argument("--scenario", required=True)
    args = parser.parse_args()
    if args.command == "compare":
        emit(load_forecast(args.scenario))
        return
    fraction(args.pressure, "pressure")
    number(args.max_age, "max-age")
    path = resolve_session(args)
    if args.command == "snapshot":
        emit(snapshot(path, args.pressure, args.max_age))
        return
    if not 1 <= args.interval <= 3600 or not 0 < args.duration <= 86400:
        raise ValueError("interval must be 1–3600 seconds; duration must be 0–86400 seconds")
    deadline = time.monotonic() + args.duration
    previous = None
    signature = None
    measured = None
    economics = None
    while True:
        stat = path.stat()
        scenario_stat = Path(args.scenario).stat() if args.scenario else None
        current = (stat.st_size, stat.st_mtime_ns,
                   scenario_stat.st_mtime_ns if scenario_stat else None)
        if current != signature:
            measured = snapshot(path, args.pressure, args.max_age)
            economics = load_forecast(args.scenario) if args.scenario else None
            signature = current
        elif measured.get("status") == "observed":
            timestamp = datetime.fromisoformat(measured["timestamp"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - timestamp).total_seconds()
            measured["age_seconds"] = round(max(0, age), 1)
            if age > args.max_age:
                measured["status"] = "stale"
                measured["context_pressure"] = None
        state = (measured["status"], measured.get("context_pressure"),
                 economics["recommend_restart"] if economics else None)
        if state != previous:
            emit({"event": "baseline" if previous is None else "recommendation_changed",
                  "snapshot": measured, "forecast": economics})
            previous = state
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(args.interval, remaining))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        emit({"status": "error", "reason": str(error)})
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
