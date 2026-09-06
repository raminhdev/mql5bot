"""mql5bot.factory.cli — operator CLI for the Strategy Factory
(mission §55/§56).  Local-first; subcommands:

    interpret    NL text → draft spec + interpretation report (§10)
    register     draft/canonical JSON → factory DB (immutable version)
    record-run   append a validation run (metrics are measured, §13)
    advance      audited lifecycle transition (evidence + actor
                 required; the store refuses unevidenced promotions)
    status       strategies, versions, states
    meta-feed    emit Meta StrategyMetaInput rows (certification only,
                 §36-§39) for the existing allocation pipeline

Nothing here trades, contacts a broker, or widens authority; the DB
default lives next to the repo (local-first, §73).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..dsl import parse_spec
from .adapter import meta_input
from .claims import extract_claims
from .interpreter import TemplateInterpreter
from .providers import ResearchMaterial
from .store import FactoryStore, StoreError

DB_ENV = "AEGIS_FACTORY_DB"


def _db(args) -> FactoryStore:
    import os
    return FactoryStore(os.environ.get(DB_ENV, args.db))


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_interpret(args) -> int:
    text = _read_text(args.infile)
    mat = ResearchMaterial("USER_TEXT", Path(args.infile).stem, text,
                           author=args.author or None)
    interp = TemplateInterpreter()
    r = interp.interpret(mat, autonomous_research=args.autonomous)
    r.claims.extend(extract_claims(text))
    out = {"draft": r.draft,
           "restatement": r.restatement,
           "claims": r.claims,
           "ambiguities": r.ambiguities,
           "unsupported": r.unsupported,
           "assumptions": r.assumptions,
           "confidence": r.confidence,
           "needs_review": r.needs_review,
           "next": "review ambiguities; then `factory register`"}
    print(json.dumps(out, ensure_ascii=False, indent=2,
                     sort_keys=True))
    return 1 if r.needs_review else 0


def cmd_register(args) -> int:
    doc = json.loads(_read_text(args.draft))
    spec = parse_spec(doc)
    store = _db(args)
    version_id, created = store.register_strategy(
        spec, created_by=args.actor,
        source={"type": "USER_TEXT"},
        original_text=_read_text(args.source) if args.source else None,
        claims=extract_claims(_read_text(args.source))
        if args.source else None)
    print(json.dumps({"strategy_id": spec.strategy_id,
                      "version": spec.version,
                      "spec_hash": spec.spec_hash,
                      "version_row_id": version_id,
                      "created": created}))
    return 0


def cmd_record_run(args) -> int:
    store = _db(args)
    metrics = json.loads(_read_text(args.metrics)) \
        if args.metrics else {}
    run_id = store.record_run(
        args.strategy, args.version, run_type=args.run_type,
        status=args.status, spec_hash=args.spec_hash,
        metrics=metrics, dataset_hash=args.dataset_hash,
        config_hash=args.config_hash, gate_version=args.gate_version,
        code_commit=args.code_commit)
    print(json.dumps({"run_id": run_id}))
    return 0


def cmd_advance(args) -> int:
    store = _db(args)
    try:
        new_state = store.transition(
            args.strategy, args.version, args.to,
            evidence_refs=tuple(args.evidence), actor=args.actor,
            reason=args.reason, human_approval=args.human_approved)
    except StoreError as e:
        print(json.dumps({"refused": str(e)}))
        return 2
    print(json.dumps({"strategy_id": args.strategy,
                      "state": new_state}))
    return 0


def cmd_status(args) -> int:
    store = _db(args)
    rows = store.list_strategies(state=args.state)
    print(json.dumps(rows, ensure_ascii=False, indent=2,
                     sort_keys=True, default=str))
    return 0


def cmd_meta_feed(args) -> int:
    """Certification-only feed for the EXISTING Meta layer (§70)."""
    store = _db(args)
    rows = store.list_strategies()
    feed = []
    for row in rows:
        feed.append(meta_input(
            strategy_id=row["strategy_id"], symbol="EURUSD",
            signal=0,                    # runtime supplies signals
            regime="UNKNOWN",
            lifecycle_state=row["state"],
            strategy_version=str(row["version"]),
        ).__dict__)
    print(json.dumps(feed, ensure_ascii=False, indent=2,
                     sort_keys=True, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mql5bot-factory",
        description="AEGIS Strategy Factory (research only — never "
                    "executes, never trades)")
    p.add_argument("--db", default="factory.db",
                   help=f"factory DB path (or ${DB_ENV})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("interpret", help="NL text → draft spec")
    sp.add_argument("infile")
    sp.add_argument("--author")
    sp.add_argument("--autonomous", action="store_true",
                    help="carry explicit parameter RANGES instead of "
                         "ambiguities (research mode only)")
    sp.set_defaults(func=cmd_interpret)

    sp = sub.add_parser("register", help="register a draft/canonical spec")
    sp.add_argument("draft")
    sp.add_argument("--actor", required=True)
    sp.add_argument("--source", help="original text file (provenance)")
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("record-run", help="append a validation run")
    sp.add_argument("strategy")
    sp.add_argument("--version", type=int, required=True)
    sp.add_argument("--run-type", required=True)
    sp.add_argument("--status", required=True,
                    choices=["PASS", "FAIL", "ERROR"])
    sp.add_argument("--spec-hash", required=True)
    sp.add_argument("--metrics", help="JSON file of measured metrics")
    sp.add_argument("--dataset-hash", default="")
    sp.add_argument("--config-hash", default="")
    sp.add_argument("--gate-version", default="")
    sp.add_argument("--code-commit", default="")
    sp.set_defaults(func=cmd_record_run)

    sp = sub.add_parser("advance", help="audited lifecycle transition")
    sp.add_argument("strategy")
    sp.add_argument("--version", type=int, required=True)
    sp.add_argument("--to", required=True)
    sp.add_argument("--actor", required=True)
    sp.add_argument("--reason", default="")
    sp.add_argument("--evidence", nargs="*", default=[],
                    help="validation run ids (required for promotions)")
    sp.add_argument("--human-approved", action="store_true",
                    help="audited human approval (required for DEMO+)")
    sp.set_defaults(func=cmd_advance)

    sp = sub.add_parser("status", help="list strategies and states")
    sp.add_argument("--state")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("meta-feed", help="certification feed for Meta")
    sp.set_defaults(func=cmd_meta_feed)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
