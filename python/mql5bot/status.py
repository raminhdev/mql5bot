"""mql5bot.status — certification status model (Phase 3 hardening).

The research funnel must never blur the line between "software executed
successfully" and "the strategy is validated".  Every pipeline and
certification result carries an explicit status from this model:

===============================  ======================================
Status                           Meaning
===============================  ======================================
``SOFTWARE_PASS``                every software stage executed exactly
                                 as specified (manifests, gates, cache,
                                 determinism).  Makes NO claim about
                                 any strategy's performance.
``EMPIRICAL_VALIDATION_PENDING`` the development-funnel empirical gates
                                 (S2 cost stress, S3 fold-isolated CV,
                                 S5 one-look OOS) ran and passed, but
                                 the MT5 real-tick certification ladder
                                 has NOT run.  MT5 status stays
                                 ``NOT VERIFIED``.
``VERIFIED``                     the full ladder — including a real MT5
                                 Strategy Tester run on the terminal
                                 host with every required leg ok and
                                 every gate passed — succeeded.  Only
                                 ``certify.run_certification`` can
                                 produce this, and only from a real
                                 terminal run.
``FAILED``                       a required gate failed (a leg ran and
                                 did not pass, or a funnel gate dropped
                                 the candidate for cause).
``NOT_ELIGIBLE``                 the funnel was blocked BEFORE
                                 certification could be considered
                                 (e.g. ``NO_VALID_SURVIVOR``).
``NOT VERIFIED`` (MT5)           the MT5-specific state: the tester has
                                 not run (or has not passed).  This is
                                 deliberately a SEPARATE dimension from
                                 the pipeline status: "the tool did not
                                 run" is not "the tool failed", and
                                 neither is ever a PASS.
===============================  ======================================

Hard rules (tested):

* ``VERIFIED`` is unreachable from the sandbox: no MT5 terminal exists
  here, therefore every sandbox result is at best
  ``EMPIRICAL_VALIDATION_PENDING`` with MT5 ``NOT VERIFIED``.
* "tool executed successfully" (a manifest with ``status == "ok"``) is
  a SOFTWARE fact; it never implies ``VERIFIED``.
* a funnel blocked with ``NO_VALID_SURVIVOR`` never reaches
  certification and never becomes an OOS candidate.
"""

from __future__ import annotations

SOFTWARE_PASS = "SOFTWARE_PASS"
EMPIRICAL_VALIDATION_PENDING = "EMPIRICAL_VALIDATION_PENDING"
VERIFIED = "VERIFIED"
FAILED = "FAILED"
NOT_ELIGIBLE = "NOT_ELIGIBLE"

# MT5 dimension (deliberately separate from the statuses above)
MT5_NOT_VERIFIED = "NOT VERIFIED"
MT5_VERIFIED = "VERIFIED"

NO_VALID_SURVIVOR = "NO_VALID_SURVIVOR"


def pipeline_certification_status(
    *,
    s2_survivors: int,
    cv_status: str,
    oos_ran: bool,
    oos_status: str,
    mt5_status: str = MT5_NOT_VERIFIED,
) -> dict:
    """Certification status of a ``run_stages`` result (Blocker 5 + 7).

    ``NO VALID SURVIVOR`` never becomes an OOS candidate: the funnel is
    ``NOT_ELIGIBLE`` and S5 is blocked for diagnostics only.  A
    sandbox pipeline (MT5 never run) can reach at most
    ``EMPIRICAL_VALIDATION_PENDING``.
    """
    section = {
        "software_status": SOFTWARE_PASS,
        "mt5_status": mt5_status,
        "status": None,
        "reason": "",
    }
    if s2_survivors == 0:
        section.update({
            "status": NOT_ELIGIBLE,
            "reason": NO_VALID_SURVIVOR,
        })
        return section
    if cv_status != "ok":
        section.update({
            "status": FAILED,
            "reason": f"purged_cv status={cv_status!r}",
        })
        return section
    if oos_ran and oos_status != "ok":
        section.update({
            "status": FAILED,
            "reason": f"oos status={oos_status!r}",
        })
        return section
    if mt5_status != MT5_VERIFIED:
        section.update({
            "status": EMPIRICAL_VALIDATION_PENDING,
            "reason": ("MT5 real-tick certification has not run "
                       "(terminal host required)") if oos_ran
                      else "one-look OOS certification not yet used; "
                           "MT5 real-tick certification has not run",
        })
        return section
    section.update({"status": VERIFIED, "reason": ""})
    return section


def certify_status_model(verdict_status: str, required_ran: int,
                         required_ok: int) -> dict:
    """Status-model section for a ``certify.run_certification`` report.

    Maps the ladder verdict onto the explicit model: a passing verdict is
    ``VERIFIED`` (MT5 ``VERIFIED``); a failing verdict with at least one
    required leg that RAN is ``FAILED``; when nothing required ran (no
    terminal host) the report is ``EMPIRICAL_VALIDATION_PENDING`` with
    MT5 ``NOT VERIFIED`` — "did not run" is honest and is never a pass.
    """
    if verdict_status == VERIFIED:
        return {"status": VERIFIED, "mt5_status": MT5_VERIFIED,
                "reason": ""}
    if required_ran > 0 and required_ran > required_ok:
        return {"status": FAILED, "mt5_status": MT5_NOT_VERIFIED,
                "reason": f"{required_ran - required_ok} required leg(s) "
                          "ran and failed"}
    return {"status": EMPIRICAL_VALIDATION_PENDING,
            "mt5_status": MT5_NOT_VERIFIED,
            "reason": "required MT5 legs did not run (terminal host "
                      "required)"}
