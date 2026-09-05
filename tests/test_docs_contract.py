"""Documentation-contract pins (Phase 3 gate).

The MT5 round-trip is a TEN-step owner sequence with exactly five
certification states, and the degradation band is informational only.
These are contract documents: tests fail if the contract silently
changes.
"""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

TEN_STEPS = [
    "compile",
    "compile log",
    "baseline tester",
    "raw report",
    "parse",
    "Every Tick run",
    "Every Tick based on real ticks run",
    "compare Python vs MT5",
    "archive manifest",
    "assign certification state",
]

FIVE_STATES = [
    "SOFTWARE_PASS",
    "EMPIRICAL_VALIDATION_PENDING",
    "VERIFIED",
    "FAILED",
    "NOT_ELIGIBLE",
]


def test_mt5_roundtrip_documents_exactly_ten_steps():
    text = (DOCS / "MT5_ROUNDTRIP.md").read_text(encoding="utf-8")
    for i, step in enumerate(TEN_STEPS, start=1):
        assert f"| {i} | **{step}** |" in text, f"step {i} ({step}) missing"
    assert "| 11 |" not in text


def test_mt5_roundtrip_documents_exactly_five_states():
    text = (DOCS / "MT5_ROUNDTRIP.md").read_text(encoding="utf-8")
    for state in FIVE_STATES:
        assert f"`{state}`" in text, f"state {state} missing"


def test_degradation_band_is_informational_only_everywhere():
    cert = (DOCS / "CERTIFICATION.md").read_text(encoding="utf-8")
    mt5 = (DOCS / "MT5_ROUNDTRIP.md").read_text(encoding="utf-8")
    for name, text in (("CERTIFICATION", cert), ("MT5_ROUNDTRIP", mt5)):
        assert "INFORMATIVE ONLY" in text or "informational only" in text \
            or "INFORMATIONAL ONLY" in text, \
            f"{name}: the never-a-gate rule must be stated"
        assert "never gates the" in text or "NEVER a pass/fail" in text, \
            f"{name}: the never-gates wording must be present"
    # the reference band may be stated, but never as a verdict criterion
    assert "30-50" in cert or "30–50" in cert


def test_wfa_cpcv_review_matrix_present():
    text = (DOCS / "WFA_CPCV_REVIEW.md").read_text(encoding="utf-8")
    assert "STATE CARRY" in text and "KNOWLEDGE CARRY" in text
    # the 11-row comparison matrix (header + 10 data rows min)
    rows = [ln for ln in text.splitlines()
            if ln.startswith("|") and "---" not in ln]
    assert len(rows) >= 12  # header + >=11 matrix rows


def test_benchmark_fast_never_claims_fully_vectorized():
    text = (DOCS / "BENCHMARK_FAST.md").read_text(encoding="utf-8")
    assert "fully vectorized" not in text.lower()
    assert "fully-vectorized" not in text.lower()
    assert "NO MEASURABLE SPEEDUP" in text  # claim-discipline wording kept
    engine = Path(__file__).resolve().parents[1] / "python" / "mql5bot" \
        / "fast_engine.py"
    assert "fully vectorized" not in engine.read_text(encoding="utf-8") \
        .lower()
