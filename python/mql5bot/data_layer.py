"""mql5bot.data_layer — production research data layer (mission
Phase 6).

Every dataset carries its full identity (instrument, timeframe,
timezone, source, source/download timestamps, content SHA-256, schema
version, quality status) and is AUDITED before use:

* duplicate timestamps
* timestamp disorder
* impossible OHLC (high < max(open, close), low > min(open, close))
* non-positive prices
* session gaps (> 3× the median bar spacing)
* weekend/session artifacts (reported, never repaired)

Cleaning is EXPLICIT: :func:`clean_ohlcv` returns the repaired frame
TOGETHER with a change log — data is never silently repaired.  Every
research run can name its exact dataset content hash (the same digest
the RunManifest records).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_SCHEMA_VERSION = "1"
REQUIRED_COLUMNS = ("open", "high", "low", "close")


# ---- identity --------------------------------------------------------------


@dataclass
class DatasetIdentity:
    """Immutable provenance of one dataset version."""

    instrument: str
    timeframe: str
    timezone_name: str
    source: str
    source_timestamp: str        # provider's last-bar timestamp (UTC ISO)
    download_timestamp: str
    sha256: str
    bars: int
    schema_version: str = DATA_SCHEMA_VERSION
    quality: str = "UNKNOWN"     # OK | WARNINGS | CORRUPT
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def content_digest(frame: pd.DataFrame) -> str:
    """Deterministic content hash of an OHLCV frame (canonical JSON of
    values; index included as ISO timestamps)."""
    payload = {
        "columns": list(frame.columns),
        "index": [str(i) for i in frame.index],
        "values": np.round(frame.to_numpy(dtype=float), 10).tolist(),
    }
    blob = json.dumps(payload, sort_keys=True,
                      separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


# ---- audit -----------------------------------------------------------------


def audit_ohlcv(df: pd.DataFrame, *, max_gap_factor: float = 3.0
                ) -> dict:
    """Audit one OHLCV frame.  Returns
    ``{"identity-ish": ..., "quality": OK|WARNINGS|CORRUPT,
    "findings": [{type, detail}...]}``.  Never mutates the input and
    never repairs anything."""
    findings: list[dict] = []
    if len(df) == 0:
        return {"quality": "CORRUPT", "bars": 0,
                "findings": [{"type": "empty", "detail": "no bars"}]}

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return {"quality": "CORRUPT", "bars": len(df),
                "findings": [{"type": "missing_columns",
                              "detail": missing}]}

    if df.index.has_duplicates:
        dupes = df.index[df.index.duplicated()].unique()
        findings.append({"type": "duplicate_timestamp",
                         "detail": [str(d) for d in dupes[:5]],
                         "count": int(df.index.duplicated().sum())})
    if not df.index.is_monotonic_increasing:
        findings.append({"type": "timestamp_disorder",
                         "detail": "index not ascending"})

    px = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    bad = ~np.isfinite(px)
    if bad.any():
        findings.append({"type": "nonfinite_price",
                         "count": int(bad.sum())})
    nonpos = (px[np.isfinite(px)] <= 0.0)
    if nonpos.any():
        findings.append({"type": "nonpositive_price",
                         "count": int(nonpos.sum())})
    imposs = ((df["high"] < df[["open", "close"]].max(axis=1))
              | (df["low"] > df[["open", "close"]].min(axis=1))
              | (df["high"] < df["low"]))
    if imposs.any():
        findings.append({"type": "impossible_ohlc",
                         "count": int(imposs.sum()),
                         "detail": [str(i) for i in
                                    df.index[imposs][:5]]})

    if len(df) >= 3:
        gaps = np.diff(df.index.view(np.int64))
        median_gap = float(np.median(gaps))
        if median_gap > 0:
            thresh = median_gap * max_gap_factor
            big = gaps > thresh
            if big.any():
                findings.append({
                    "type": "gap", "count": int(big.sum()),
                    "detail": f"{int(big.sum())} gaps > "
                              f"{max_gap_factor}x median spacing",
                    "largest_bars": int(gaps.max() / median_gap)})

    quality = "OK"
    if findings:
        hard = {"duplicate_timestamp", "timestamp_disorder",
                "impossible_ohlc", "nonpositive_price", "nonfinite_price",
                "missing_columns", "empty"}
        quality = "CORRUPT" if any(f["type"] in hard for f in findings) \
            else "WARNINGS"
    return {"quality": quality, "bars": len(df), "findings": findings}


def clean_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """EXPLICIT cleaning: returns (frame, change_log).  Only safe,
    lossless-or-documented operations are performed: sort by timestamp,
    drop duplicate timestamps (keep first), drop bars with non-positive
    or non-finite prices, clamp impossible high/low into consistency.
    Every change is logged — a caller can always reconstruct what was
    removed.  Gaps are REPORTED by audit, never filled."""
    changes: list[dict] = []
    out = df.copy()

    if not out.index.is_monotonic_increasing:
        out = out.sort_index()
        changes.append({"op": "sort_index", "rows": len(out)})
    if out.index.has_duplicates:
        n = int(out.index.duplicated().sum())
        out = out[~out.index.duplicated(keep="first")]
        changes.append({"op": "drop_duplicate_timestamps", "rows": n})
    px = out[["open", "high", "low", "close"]].to_numpy(dtype=float)
    bad = ~np.isfinite(px).all(axis=1) | (px <= 0.0).any(axis=1)
    if bad.any():
        n = int(bad.sum())
        out = out[~bad]
        changes.append({"op": "drop_invalid_price_bars", "rows": n})
    imposs = (out["high"] < out[["open", "close"]].max(axis=1)) \
        | (out["low"] > out[["open", "close"]].min(axis=1))
    if imposs.any():
        n = int(imposs.sum())
        hi = out[["open", "close"]].max(axis=1)
        lo = out[["open", "close"]].min(axis=1)
        out.loc[imposs, "high"] = np.maximum(out.loc[imposs, "high"], hi)
        out.loc[imposs, "low"] = np.minimum(out.loc[imposs, "low"], lo)
        changes.append({"op": "clamp_impossible_high_low", "rows": n})
    return out, changes


def register_dataset(frame: pd.DataFrame, *, instrument: str,
                     timeframe: str, tz: str, source: str,
                     source_timestamp: str | None = None,
                     download_timestamp: str | None = None) -> dict:
    """Audit + identity a dataset.  Returns the registration record
    (identity + audit).  CORRUPT datasets are returned with
    quality=CORRUPT — the caller must refuse to backtest them."""
    audit = audit_ohlcv(frame)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    identity = DatasetIdentity(
        instrument=instrument, timeframe=timeframe, timezone_name=tz,
        source=source,
        source_timestamp=source_timestamp
        or str(frame.index[-1]),
        download_timestamp=download_timestamp or now,
        sha256=content_digest(frame), bars=len(frame),
        quality=audit["quality"], notes=[f["type"] for f in
                                         audit["findings"]])
    return {"identity": identity.to_dict(), "audit": audit}


# ---- committed REAL data ----------------------------------------------------


def load_real_vix(repo_root: Path) -> tuple[pd.DataFrame, str]:
    """Load the committed REAL CBOE VIX daily series (DataHub mirror)
    and its content digest.  Raises if the provenance manifest digest
    does not match the file bytes."""
    path = Path(repo_root) / "tests/data/real/vix_daily.csv"
    blob = path.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    manifest = json.loads(
        (path.parent / "manifest.json").read_text())
    recorded = manifest["sources"]["vix_daily"]["sha256"]
    if digest != recorded:
        raise ValueError(
            f"dataset digest mismatch: file {digest[:12]} vs manifest "
            f"{recorded[:12]} — refusing to use unverified data")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")[["open", "high", "low", "close"]] \
        .astype(float).sort_index()
    return df, digest
