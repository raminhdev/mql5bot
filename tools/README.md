# tools/ — AEGIS build & research tooling

Windows-side tooling for the AEGIS research / performance upgrade mission
(docs/SPEC.md §14/§17 DoD: compile with **0 errors / 0 warnings, log
attached**).  Everything here is invoked by the **owner** (or a Windows
runner) and its output is pasted back into the session — this sandbox has no
MetaEditor and no MetaTrader 5, so **no compile or backtest result may ever
be claimed without a real tool log** (HANDOFF §10).

## compile.ps1 — MetaEditor compile round-trip

Builds the mql5bot EA from the command line and produces one reproducible
compile log.

### Requirements

- Windows with MetaTrader 5 installed (any broker build; portable installs
  work too — see `-DataFolder`).
- Windows PowerShell 5.1+ (`powershell`, not only `pwsh`).
- The repo checked out (sources under `mql5/`).

### Owner flow (one round-trip)

```powershell
# from the repo root
powershell -ExecutionPolicy Bypass -File tools\compile.ps1 -Strict
```

The script:

1. Locates `metaeditor64.exe` — `-MetaEditorPath`, env `MQL5BOT_METAEDITOR`,
   then beside known terminal roots (registry `DataPath` / `origin.txt`
   portable entries), then `Program Files\MetaTrader*\`, Start-menu
   shortcuts, then `PATH`.
2. Resolves the MT5 **data folder** (the tree that contains `MQL5\`) —
   `-DataFolder`, env `MQL5BOT_DATA_FOLDER`, then the same known roots, then
   the newest `%APPDATA%\MetaQuotes\Terminal\<hash>\` that contains `MQL5`.
   Includes are resolved by MetaEditor inside that tree, which is why
   sources are installed there first (step 3).
3. Installs (copies) `mql5/Include|Experts|Scripts|Presets/Mql5Bot/*` into
   `<data>\MQL5\...` (skip with `-SkipInstall`).
4. Compiles every `*.mq5` under `Experts\Mql5Bot` and `Scripts\Mql5Bot`:
   `metaeditor64.exe /compile:"<file>" /log:"<file>.log"`, one invocation
   per file.
5. **Gates on real compiler output**: the produced `.ex5` must exist AND be
   newer than the compile start (an old `.ex5` from a previous build is not
   proof), and the compiler log is captured verbatim.  English severity
   tokens (`error` / `warning`) are counted when present; a non-English
   MetaEditor simply produces no tokens, so the `.ex5` freshness check is
   the authoritative signal and the raw log is always kept for human review.
6. Writes one combined reproducible log to
   `logs\compile-<UTC timestamp>.log` (host, versions, command lines,
   per-file verdicts, verbatim compiler logs, SHA-256 of every produced
   `.ex5`).  `logs/` is gitignored — nothing generated is committed.

### Parameters

| Parameter          | Meaning                                                        |
| ------------------ | -------------------------------------------------------------- |
| `-MetaEditorPath`  | Full path to `metaeditor64.exe` (auto-detected when omitted)   |
| `-DataFolder`      | MT5 data folder containing `MQL5\` (auto-detected when omitted)|
| `-Strict`          | Exit 3 when the compiler log contains any `warning` token      |
| `-SkipInstall`     | Don't copy repo sources; compile what is already in the data folder |
| `-RepoRoot`        | Repo root (default: `tools\..`)                                |
| `-OutDir`          | Combined-log directory (default `<RepoRoot>\logs`)             |

Environment fallbacks: `MQL5BOT_METAEDITOR`, `MQL5BOT_DATA_FOLDER`.

### Exit codes

| Code | Meaning                                                        |
| ---- | -------------------------------------------------------------- |
| 0    | PASS — every file compiled; 0 errors (warnings allowed unless `-Strict`) |
| 2    | FAIL — compile errors / `.ex5` not refreshed                   |
| 3    | FAIL — `-Strict` and warnings present                          |
| 1    | FAIL — `metaeditor64.exe` not found                            |
| 4    | FAIL — data folder not found / nothing to compile              |
| 5    | FAIL — script exception                                        |

### What to paste back into the session

The final `[compile] RESULT: ...` line(s) and the combined log path, e.g.:

```
[compile] Mql5Bot.mq5 : PASS (exit 0, ex5 fresh=True)
[compile] RESULT: PASS — 1 file(s) compiled clean
# combined log: C:\repo\logs\compile-20260904-120000.log
```

A green claim requires `RESULT: PASS` **plus** the log file (DoD item 1:
"log attached").  Anything less is `COMPILE NOT VERIFIED`.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `metaeditor64.exe not found` | Pass `-MetaEditorPath` explicitly. |
| `MT5 data folder not found` | Pass `-DataFolder` (a dedicated portable terminal folder works; it must contain `MQL5\`). |
| `FAIL ... ex5 fresh=False` with empty log | Another MetaEditor instance may hold the file open — close MetaEditor/GUI and re-run. |
| Warnings you disagree with | `-Strict` fails the run; review the warning lines in the combined log, fix the source, re-run. Non-English MetaEditor builds cannot report token counts — rely on the verbatim log. |
| Running on the Phase-2 dedicated portable terminal | `-MetaEditorPath <portable>\metaeditor64.exe -DataFolder <portable>` — compile and tester then share one data tree. |

## run_mt5_backtest.* — headless Strategy Tester (Phase 2, planned)

Batch backtest driver (`.set` render/parse, tester `.ini` generation,
portable-terminal launch, HTML report parsing, deterministic artifacts).
Documentation lands with the Phase-2 commit; `TASKS.md` tracks it.

## profile_research.py — performance profiling (Phase 18, planned)

Benchmark evidence for every optimization (see TASKS.md).
