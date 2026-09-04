# Aegis — Decisions Log

Every meaningful architectural deviation from `docs/SPEC.md` and every
significant trade-off is recorded here with its rationale. When uncertain
about a financial rule, the more conservative option wins and is documented.

Format: newest on top. `[SPEC]` entries record SPEC-mandated decisions that
were already made and must not be silently reverted.

---

## 2026-09-04 — Keep the committed Mql5Bot tree in place while Aegis releases land (DEV)

**Decision.** The canonical layout in SPEC §6 (`ea/MQL5/...`, `factory/...`,
`schemas/`, `research/`, docs set) is the destination architecture, but this
repository already contains a working, tested, two-language stack under
`mql5/`, `python/`, `tests/`. We will NOT rename/move/restructure that tree as
a first step: restructuring without a compile-capable environment would
destroy working functionality for zero behavioural gain (audit §1, §7).

**Rationale.** Release work is incremental and evidence-based. The Mql5Bot EA
becomes the Release-A seed: its files grow into SPEC §8 behaviour, and new
canonical models are first implemented in Python where they can be unit-tested
in this sandbox, then ported to MQL5 in compile-verified sessions (audit §17).
SPEC §8 class/file names (e.g. `SymbolSpec.mqh`) will be used for new MQL5
files when they are added, inside the existing `mql5/Include/Mql5Bot/` tree.

**Cost.** The layout differs from SPEC §6 until a later consolidation release;
`docs/IMPLEMENTATION_AUDIT.md` §1 maps current paths. The SPEC §6 layout
remains the target for a dedicated, separately planned refactor that keeps
`git history` intact and is verified by the MQL5 unit-test harness.

## 2026-09-04 — Python-first canonical risk/identity models (DEV)

**Decision.** Release-A's "injected `SSymbolSpec` risk math", "volume/price
normalisation", and "FNV-1a magic derivation" are implemented first as pure,
dependency-light Python modules in `python/mql5bot/` (canonical model +
synthetic-spec tests), and the MQL5 port must match them. The existing
`CRiskManager`/`CTradeManager` code is left running untouched until the port
lands in a compile-verified session.

**Rationale.** SPEC §14 requires PositionSizer tests on synthetic broker specs
(EURUSD 5-digit, USDJPY, XAUUSD, US30-like, BTCUSD-like; clamping; insufficient
margin). MetaEditor is unavailable in this environment, so MQL5 changes cannot
be compile-verified here; the Python twin is the verifiable specification of
the arithmetic. This mirrors the existing, working strategy-parity approach
(README "Strategy ↔ backtest parity") and extends it to risk code. Keeping the
old EA untouched avoids regressions (task rule: never destroy working
functionality).

**Cost.** A short window where the live EA's internal math and the canonical
Python model are not yet byte-identical; the EA remains demo-only per its own
documentation, and the port task is tracked in the audit's order list (§17.2).

## 2026-09-04 — SPEC.md §19 (external references) reconciliation (DOC)

**Decision.** The committed `docs/SPEC.md` ends at §18 "OUTPUT STYLE".
HANDOFF.md §4.17 refers to "SPEC §19" for the external-repository policy
(paper_trading_view, BTC multi-horizon builder, MT5 docker/data-bridge,
AutoTradeSignal/core, highcharts). Policy is applied as written in HANDOFF §4
and in the work-session brief: reference-only, no third-party trading code
imported, no Highcharts, no Selenium in the core. When SPEC.md is next
edited, fold this section in as its final numbered section.

## 2026-09-04 — Version naming (DOC)

**Decision.** The committed code labels itself Mql5Bot "1.0.0"
(`Config.mqh`, `Mql5Bot.mq5`, `CHANGELOG.md`). Aegis `v1.0.0` per SPEC §5.6 is
the end of Release E. The code's own version string keeps tracking the
committed EA codebase; Aegis release tags (`A-ea-core` … `v1.0.0`) are
separate and follow SPEC.

---

## 2026-09-04 — Engine state hardening (never soften a halt or pause)

**Decision.** `ENGINE_NO_NEW_TRADES` (daily-loss breach) is the *soft* pause
and `ENGINE_HALT` (drawdown kill switch, SL-guard escalation, manual trip)
is the *hard* stop. Only a day rollover clears the daily-loss pause; the
kill switch is cleared ONLY by an explicit one-shot reset (input
`InpResetKillSwitch` + GlobalVariable `reset_ack` edge — see state-store
commit) — never by equity recovery and never by a rollover. A daily-loss
breach while a guard pause or the halt is active must NOT soften that state
(the EA only applies the daily pause from `ENGINE_NORMAL`). Mirrored in
`python/mql5bot/failsafe.py`.

## 2026-09-04 — Cold-state persistence: strict text, delete-then-write

**Decision.** Internal EA state files (`AEGIS_STATE v1` ticket registry,
`MAGICMAP v1`) stay strict line-based text until the EA↔Factory JSON
contract ships (a reviewed JSON writer lands with that contract). Saves are
delete-then-write because `FileOpen(FILE_WRITE|FILE_READ)` does not
truncate — stale tail rows would resurrect removed tickets/ids on load.
Reads are strict: a corrupt header quarantines the file aside (never
applied partially); malformed rows are skipped. Hot state (kill switch,
reason, day key, day-start equity, equity peak) rides GlobalVariables so a
restart always restores it; management flags (`partialDone`, `beDone`) are
persisted per `POSITION_IDENTIFIER` in the cold registry — never in the
position comment (brokers overwrite comments).

---

## Earlier decisions carried from HANDOFF.md §4 (kept; [SPEC]-consistent)

1. **[SPEC §3.1]** Signal/Risk separation: strategies emit signals only;
   meta-layer and Risk Engine veto; Factory never trades (files only).
2. **[SPEC §3.2]** Every position always has an SL; failure to set SL → close +
   CRITICAL + alert.
3. **[SPEC §3.3, §3.10]** Query broker specs at runtime; all risk math on an
   injected `SSymbolSpec` struct (unit-testable with synthetic specs).
4. **[SPEC §3.9]** Stable identity: Magic = FNV-1a hash of `strategy_id` into a
   reserved range, persisted in a registry; never index-based.
5. **[SPEC §3.8]** Attribution/management state persisted by
   `POSITION_IDENTIFIER` in files, NOT in the position comment (brokers
   overwrite comments).
6. **[SPEC §3.4]** No `Sleep()`; retries via a `RetryQueue` processed in
   OnTimer with backoff.
7. **[SPEC §9]** Strategy Tester: DSL specs delivered as one bundle via
   `#property tester_file`; WebRequest/Calendar skipped in tester.
8. **[SPEC §2]** Releases A→E gated by DoD; release N+1 starts only after N is
   tagged. Compiled AND DSL copies of the 4 reference strategies with a
   bar-by-bar parity test (golden test of the DSL engine).
9. **[SPEC §12.2]** Combination default = `weighted_netting` (one book position
   per symbol; opposite signals netted; pro-rata attribution).
10. **[SPEC §12.2]** Weights = gate × regime_fit × performance × correlation ×
    drift factors; adaptive part clamped [0.25, 1.5], ≤ ±15 %/day; hard zeros
    allowed; daily cadence; ≤10 meta parameters.
11. **[SPEC §10.4]** Gate 3 demo = ≥ 4 weeks AND ≥ 30 trades (low-frequency
    exception: ≥ 8 weeks AND ≥ 15 trades, flagged). OOS budget: one look per
    strategy version.
12. **[SPEC §8.C]** Kelly sizing capped ≤ 0.25 Kelly, off by default;
    martingale forbidden; grid/averaging off by default and hard-capped.
13. **[SPEC §8.H]** Two separate Telegram bot tokens (EA vs Factory).
14. **[SPEC §4]** Factory: Python 3.11+, FastAPI, SQLAlchemy+Alembic, SQLite,
    Jinja2+HTMX (no JS framework), binds 127.0.0.1, password from env; MQL5
    compile is local-only (PowerShell), GitHub CI is Python-only.
15. **[SPEC §8.A]** Server GMT offset estimated from
    `TimeCurrent() − TimeGMT()` when connected, persisted.
16. External repos: read-only inspiration; no third-party trading code; no
    Highcharts (licensing) — if interactive charting is ever needed,
    TradingView lightweight-charts only, recorded here first.

## Open questions

- None blocking. (Owner-side compile logs for MQL5 batches are required before
  those batches are considered done — see audit §17.)
