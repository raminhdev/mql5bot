"""Certification status model (Phase 3 hardening, Blocker 7).

SOFTWARE_PASS / EMPIRICAL_VALIDATION_PENDING / VERIFIED / FAILED are
distinct; MT5 NOT VERIFIED is a separate dimension; "tool executed
successfully" never becomes "strategy verified".
"""

from mql5bot.certify import CertifyConfig, render_report, run_certification
from mql5bot.status import (
    EMPIRICAL_VALIDATION_PENDING,
    FAILED,
    MT5_NOT_VERIFIED,
    MT5_VERIFIED,
    NOT_ELIGIBLE,
    SOFTWARE_PASS,
    VERIFIED,
    certify_status_model,
    pipeline_certification_status,
)

# ---------------------------------------------------------------------------
# Pipeline transitions
# ---------------------------------------------------------------------------


def test_zero_survivors_is_not_eligible_never_certified():
    sec = pipeline_certification_status(
        s2_survivors=0, cv_status="skipped", oos_ran=False,
        oos_status="blocked")
    assert sec["status"] == NOT_ELIGIBLE
    assert sec["reason"] == "NO_VALID_SURVIVOR"
    assert sec["status"] != VERIFIED


def test_full_python_funnel_is_empirical_pending_mt5_not_verified():
    sec = pipeline_certification_status(
        s2_survivors=2, cv_status="ok", oos_ran=True, oos_status="ok")
    assert sec["status"] == EMPIRICAL_VALIDATION_PENDING
    assert sec["mt5_status"] == MT5_NOT_VERIFIED


def test_cv_failure_is_failed_not_pending():
    sec = pipeline_certification_status(
        s2_survivors=2, cv_status="error", oos_ran=False,
        oos_status="not_requested")
    assert sec["status"] == FAILED
    assert "purged_cv" in sec["reason"]


def test_oos_failure_is_failed():
    sec = pipeline_certification_status(
        s2_survivors=1, cv_status="ok", oos_ran=True, oos_status="blocked")
    assert sec["status"] == FAILED


def test_software_pass_is_always_recorded_and_never_a_claim():
    for kwargs in (
        {"s2_survivors": 0, "cv_status": "skipped", "oos_ran": False,
         "oos_status": "blocked"},
        {"s2_survivors": 2, "cv_status": "ok", "oos_ran": True,
         "oos_status": "ok"},
    ):
        sec = pipeline_certification_status(**kwargs)
        assert sec["software_status"] == SOFTWARE_PASS


def test_sandbox_cannot_reach_verified():
    """The sandbox has no MT5 terminal: with mt5_status NOT VERIFIED the
    pipeline status is capped at EMPIRICAL_VALIDATION_PENDING for every
    combination of the other flags."""
    for kwargs in (
        {"s2_survivors": 2, "cv_status": "ok", "oos_ran": False,
         "oos_status": "not_requested"},
        {"s2_survivors": 2, "cv_status": "ok", "oos_ran": True,
         "oos_status": "ok"},
        {"s2_survivors": 5, "cv_status": "ok", "oos_ran": True,
         "oos_status": "ok"},
    ):
        sec = pipeline_certification_status(**kwargs)
        assert sec["status"] in (EMPIRICAL_VALIDATION_PENDING, FAILED,
                                 NOT_ELIGIBLE)
        assert sec["status"] != VERIFIED


# ---------------------------------------------------------------------------
# Certification ladder mapping
# ---------------------------------------------------------------------------


def test_certify_mapping():
    assert certify_status_model(VERIFIED, 6, 6) == {
        "status": VERIFIED, "mt5_status": MT5_VERIFIED, "reason": ""}
    # a leg ran and failed -> FAILED (with MT5 still not verified)
    assert certify_status_model("NOT VERIFIED", 6, 4)["status"] == FAILED
    # nothing required ran -> EMPIRICAL_VALIDATION_PENDING, honest reason
    pending = certify_status_model("NOT VERIFIED", 0, 0)
    assert pending["status"] == EMPIRICAL_VALIDATION_PENDING
    assert pending["mt5_status"] == MT5_NOT_VERIFIED
    assert "did not run" in pending["reason"]


class _Outcome:
    def __init__(self, ok: bool, report=None, error: str = ""):
        self.ok = ok
        self.report = report
        self.error = error
        self.run_id = "rid"


def test_run_certification_without_terminal_is_pending_not_verified(
        tmp_path):
    """No MT5 runner: every required leg is 'did not run' -> the report
    is EMPIRICAL_VALIDATION_PENDING with MT5 NOT VERIFIED.  A successful
    Python cross-check leg never upgrades the verdict."""
    cfg = CertifyConfig(strategy="AegisScalper", ea="AegisScalper.ex5",
                        symbol="EURUSD", timeframe="M1", manifest_id="")
    report = run_certification(cfg, run_tester=None)
    assert report["verdict"]["status"] == "NOT VERIFIED"
    sm = report["status_model"]
    assert sm["status"] == EMPIRICAL_VALIDATION_PENDING
    assert sm["mt5_status"] == MT5_NOT_VERIFIED
    text = render_report(report)
    assert "EMPIRICAL_VALIDATION_PENDING" in text
    assert "NOT VERIFIED" in text
    assert "## VERDICT: VERIFIED" not in text


def test_run_certification_failed_leg_is_failed(tmp_path):
    """A required MT5 leg that RAN and failed -> FAILED (not pending,
    not verified)."""
    cfg = CertifyConfig(strategy="AegisScalper", ea="AegisScalper.ex5",
                        symbol="EURUSD", timeframe="M1", manifest_id="")
    report = run_certification(
        cfg, run_tester=lambda tc: _Outcome(False, None, "boom"))
    sm = report["status_model"]
    assert sm["status"] == FAILED
    assert sm["mt5_status"] == MT5_NOT_VERIFIED
