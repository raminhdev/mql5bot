# AEGIS — PROGRESS.md

Session branch: `arena/01a06cb0-mql5bot`

current_release: A
current_phase: 1
current_file: none

next_3_steps:
- [ ] ea/MQL5/Include/Aegis/Core/Constants.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Errors.mqh
- [ ] ea/MQL5/Include/Aegis/Core/Version.mqh

unpushed: false

open_questions:
- PING.md is absent on this branch (bootstrap was on `arena/01a06c21-mql5bot`, never merged to main); TASKS.md marks it done per planning template. Confirm/restore before Phase 1 if it matters.
- Existing repo tree (`mql5/`, `python/mql5bot/`, `tests/`, `scripts/`, `requirements.txt`, `pyproject.toml`, `.github/workflows/ci.yml`) does NOT match SPEC §6 canonical layout (`ea/`, `factory/`, `schemas/`, `examples/`, `research/`). Confirm whether to keep / migrate / remove the legacy tree before Phase 1 (TASKS.md is derived from §6).
