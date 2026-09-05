"""mql5bot.versions — semantic versions of the research identity.

These constants participate in the OOS certification identity
(:class:`mql5bot.pipeline.OosRegistry`): a certification recorded under
one identity is NOT reusable under another.  Bump a version whenever the
corresponding SEMANTICS change — never to obtain a fresh certification
look on the same data (that is refused outright; see the one-look
policy).
"""

from __future__ import annotations

# Canonical research engine semantics (mql5bot.engine / backtest wrapper
# / fast engine equivalence contract).
ENGINE_VERSION = "1.0.0"

# Cost model semantics (mql5bot.costs: fills, spread/slippage/
# commission accounting conventions).
COST_MODEL_VERSION = "1.0.0"

# Signal/feature semantics (mql5bot.strategies + mql5bot.indicators:
# what a signal value means on a closed bar).
FEATURE_VERSION = "1.0.0"

# Certification protocol / registry identity schema (this file's
# identity contract; schema 2 = content-digest identity, see
# docs/CERTIFICATION.md and docs/CV_STATE_CONTRACT.md).
CERTIFICATION_PROTOCOL_VERSION = "2.0.0"
