#!/usr/bin/env python3
"""Déjà — one-command, phase-by-phase verification gate.

Runs every layer's proof in a single board, from the ground up:

  Foundations  → interpreter, deps, .env keys, package imports, manifest, seed-data integrity
  Phase 1      → App Home / view unit tests
  Phase 2      → recall (RTS) resurfaces the seeded decision 3/3            [live]
  Phase 3      → judge → recall → reply end-to-end                          [live]
  Trigger      → LLM trigger-judgment runs under the Claude subscription    [live]
  Phase 4      → Block Kit memory card builders (unit)
  Phase 5      → MCP recall_memory tool (unit) + real stdio smoke           [smoke=live]
  Phase 6      → realistic seed data (unit) + live dry-run wiring           [dry-run=live]

Hermetic checks always run. Live checks need secrets in `.env`
(`SLACK_USER_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`) and a seeded workspace; without them — or with
`--no-live` — they SKIP instead of failing, so this is safe to run in tokenless CI.

Usage:
    python scripts/verify_all.py            # full gate (hermetic + any live proofs it can run)
    python scripts/verify_all.py --no-live  # hermetic only (no Slack/LLM calls)

Exit code is non-zero if anything FAILS (SKIPs never fail the gate).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))  # import demo tooling (seed_data, …)
sys.path.insert(0, str(REPO))  # import the deja package from the repo root

try:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env", override=False)
except Exception:  # noqa: BLE001 — dotenv is a foundation dep; its absence is caught below
    pass

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
ICON = {PASS: "✅", FAIL: "❌", SKIP: "⏭️ "}

NO_LIVE = "--no-live" in sys.argv[1:] or os.environ.get("DEJA_VERIFY_NO_LIVE") == "1"
HAS_SLACK = bool(os.environ.get("SLACK_USER_TOKEN")) and not NO_LIVE
HAS_CLAUDE = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")) and not NO_LIVE

_results: list[tuple[str, str, str, str]] = []  # (phase, name, status, detail)


def record(phase: str, name: str, status: str, detail: str = "") -> None:
    _results.append((phase, name, status, detail))


def _run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout
        )
        lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
        return p.returncode, (lines[-1] if lines else "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


def _pytest(phase: str, name: str, target: str) -> None:
    rc, tail = _run([sys.executable, "-m", "pytest", "-q", target], timeout=180)
    record(phase, name, PASS if rc == 0 else FAIL, tail)


def _script(
    phase: str, name: str, args: list[str], *, need: bool, timeout: int = 240
) -> None:
    if not need:
        reason = "--no-live" if NO_LIVE else "no token in .env"
        record(phase, name, SKIP, f"live check — {reason}")
        return
    rc, tail = _run([sys.executable, *args], timeout=timeout)
    record(phase, name, PASS if rc == 0 else FAIL, tail)


# ----------------------------------------------------------------- Foundations (always run)


def check_foundations() -> None:
    phase = "0 · Foundations"

    v = sys.version_info
    record(
        phase,
        "Python interpreter",
        PASS if v >= (3, 12) else SKIP,
        f"{v.major}.{v.minor}.{v.micro} (project targets >=3.12)",
    )

    missing = []
    for mod in (
        "slack_sdk",
        "slack_bolt",
        "dotenv",
        "mcp",
        "claude_agent_sdk",
        "aiohttp",
    ):
        try:
            __import__(mod)
        except Exception:  # noqa: BLE001
            missing.append(mod)
    record(
        phase,
        "Dependencies import",
        FAIL if missing else PASS,
        f"missing: {', '.join(missing)}"
        if missing
        else "slack_sdk, bolt, mcp, agent-sdk, …",
    )

    keys = {
        k: bool(os.environ.get(k))
        for k in ("SLACK_USER_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")
    }
    absent = [k for k, present in keys.items() if not present]
    record(
        phase,
        ".env secrets",
        PASS if not absent else SKIP,
        "all present"
        if not absent
        else f"absent: {', '.join(absent)} (live proofs will skip)",
    )

    broken = []
    for mod in (
        "deja.models",
        "deja.recall",
        "deja.memory",
        "deja.trigger",
        "deja.card",
        "deja.respond",
        "deja.thread",
        "deja.mcp_server",
    ):
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001
            broken.append(f"{mod} ({type(e).__name__})")
    record(
        phase,
        "deja package imports",
        FAIL if broken else PASS,
        "; ".join(broken) if broken else "all 8 modules import",
    )

    try:
        json.loads((REPO / "manifest.json").read_text())
        record(phase, "manifest.json valid", PASS, "parses as JSON")
    except Exception as e:  # noqa: BLE001
        record(phase, "manifest.json valid", FAIL, f"{type(e).__name__}: {e}")

    try:
        from seed_arcs import ALL_THREADS, ARCS
        from seed_data import is_decision

        markers = [t.marker for t in ALL_THREADS]
        inconclusive = {
            "RFC / design-doc process"
        }  # the one arc that is decision-free by design
        problems = []
        if len(markers) != len(set(markers)):
            problems.append("duplicate markers")
        for name, threads in ARCS.items():
            has = any(is_decision(r.text) for t in threads for r in t.replies)
            if has == (name in inconclusive):
                problems.append(f"{name} decision/inconclusive mismatch")
        if len({t.channel for t in ALL_THREADS}) < 4:
            problems.append("<4 channels")
        record(
            phase,
            "seed-data integrity",
            FAIL if problems else PASS,
            "; ".join(problems)
            if problems
            else f"{len(ALL_THREADS)} arc threads / "
            f"{len({t.channel for t in ALL_THREADS})} channels, markers unique, decisions consistent",
        )
    except Exception as e:  # noqa: BLE001
        record(phase, "seed-data integrity", FAIL, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------------------- all checks


def main() -> int:
    started = time.time()
    print(f"\n  Déjà verification gate {'(hermetic only)' if NO_LIVE else ''}\n")

    check_foundations()

    _pytest("1 · App Home", "view / home unit tests", "tests/test_app_home_opened.py")

    _script(
        "2 · Recall (RTS)",
        "recall resurfaces decision 3/3",
        ["scripts/prove_recall.py"],
        need=HAS_SLACK,
    )
    _script(
        "3 · Judge→Recall→Reply",
        "end-to-end pipeline",
        ["scripts/verify_pipeline.py"],
        need=HAS_SLACK and HAS_CLAUDE,
    )
    _script(
        "Trigger · LLM auth",
        "trigger-judgment under subscription",
        ["scripts/verify_trigger.py"],
        need=HAS_CLAUDE,
    )

    _pytest(
        "4 · Block Kit card",
        "memory-card builders (unit)",
        "tests/test_view_builders.py",
    )

    _pytest("5 · MCP tool", "recall_memory logic (unit)", "tests/test_mcp_tool.py")
    _script(
        "5 · MCP stdio",
        "real MCP client over stdio",
        ["scripts/mcp_smoke.py"],
        need=HAS_SLACK,
    )

    _pytest("6 · Seed data", "realistic seed (unit)", "tests/test_seed_data.py")
    _script(
        "6 · Seed dry-run",
        "live channel wiring (posts nothing)",
        ["scripts/seed_deja.py", "--dry-run"],
        need=HAS_SLACK,
        timeout=120,
    )

    # ---- board
    tally = {PASS: 0, FAIL: 0, SKIP: 0}
    last_phase = None
    for phase, name, status, detail in _results:
        if phase != last_phase:
            print(f"  {phase}")
            last_phase = phase
        tally[status] += 1
        detail = f"  — {detail}" if detail else ""
        print(f"    {ICON[status]} {status}  {name}{detail}")

    dur = time.time() - started
    print(
        f"\n  {tally[PASS]} passed · {tally[FAIL]} failed · {tally[SKIP]} skipped "
        f"· {dur:.1f}s"
    )
    if tally[FAIL]:
        print("  GATE: ❌ FAIL\n")
        return 1
    if tally[SKIP]:
        print(
            "  GATE: ✅ PASS (some live proofs skipped — run with secrets for the full gate)\n"
        )
    else:
        print("  GATE: ✅ PASS — all phases green\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
