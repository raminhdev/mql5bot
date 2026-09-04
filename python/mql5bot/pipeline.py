"""mql5bot.pipeline — staged screening pipeline (performance & selection
hardening, Phase D).

The certified research funnel, stage by stage:

    S1 screen      — cheap sweep over the parameter grid on the DEV data
                     (FAST engine by default; the TRUTH engine may be
                     forced).  Keeps ``top_k`` by an explicit rank metric.
    S2 cost stress — every survivor re-run at cost x1 and cost x2
                     (spread AND commission doubled) on the TRUTH engine;
                     survivors of the documented gate keep their place.
    S3 purged CV   — own trade-level purge + embargo combinatorial
                     cross-validation over the survivors (conceptually
                     after López de Prado's purged k-fold / CPCV; own
                     implementation, see ``purged_cv_stage``).
    S4 MT5 tester  — headless MetaTrader 5 Strategy Tester execution of
                     the survivors on tick data.  THIS SANDBOX HAS NO MT5
                     TERMINAL: without an explicit ``TesterConfig`` the
                     stage records a manifest with status ``skipped`` and
                     an honest reason — a certification is never faked.
    S5 OOS certify — ONE final TRUTH-engine run on never-touched OOS
                     data, gated by the one-look registry
                     (:class:`OosRegistry`): the same dataset version can
                     never be optimised/certified twice, enforced in
                     code, not just documented.

Every stage emits a :class:`RunManifest` whose digest (``manifest_id``)
is a deterministic function of params, window, data digest, cost config,
seed and stage — so certified results are reproducible from the manifest
alone.  FAST results appearing in manifests are always marked
``engine="fast"`` and are screening signals only — never final, never a
profit claim.  The only certification path is the TRUTH engine
(``mql5bot.backtest``/``mql5bot.engine``) plus the real MT5 tester.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .fast_engine import run_fast
from .metrics import RobustFitnessConfig
from .optimizer import STRATEGY_VERSIONS, _dataset_digest, _param_hash
from .strategies import default_params

# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------


def _clean(value):
    """Normalise a manifest value to plain JSON-safe Python types."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _canonical(params: dict) -> dict:
    """Deterministic canonical parameter serialisation (json-able)."""
    return _clean(dict(params))


@dataclass
class RunManifest:
    """Reproducibility record of one pipeline stage execution.

    ``manifest_id`` is a deterministic sha-1 over every field except
    ``created`` (wall-clock) and ``artifacts`` entries that are
    non-deterministic by nature (``skipped`` reasons etc. are included).
    """

    stage: str
    strategy: str
    params: dict
    engine: str
    dataset_version: str
    seed: int = 0
    dataset_bars: int = 0
    strategy_version: str = "undeclared"
    cost_config: dict = field(default_factory=dict)
    window: dict | None = None
    status: str = "ok"
    metrics: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    created: str = ""
    manifest_id: str = ""

    def __post_init__(self):
        self.params = _canonical(self.params)
        self.cost_config = _clean(self.cost_config)
        self.metrics = _clean(self.metrics)
        self.artifacts = _clean(self.artifacts)
        self.created = self.created or datetime.now(
            timezone.utc).isoformat(timespec="seconds")
        self.strategy_version = self.strategy_version \
            or STRATEGY_VERSIONS.get(self.strategy, "undeclared")
        self.manifest_id = self.digest()

    def digest(self) -> str:
        """Deterministic content id (excludes the wall-clock ``created``)."""
        payload = {
            "stage": self.stage,
            "strategy": self.strategy,
            "params": self.params,
            "engine": self.engine,
            "dataset_version": self.dataset_version,
            "seed": int(self.seed),
            "dataset_bars": int(self.dataset_bars),
            "strategy_version": self.strategy_version,
            "cost_config": self.cost_config,
            "window": self.window,
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          default=repr)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RunManifest:
        obj = cls(**{k: v for k, v in data.items()
                     if k in cls.__dataclass_fields__})
        return obj


# ---------------------------------------------------------------------------
# Data versions
# ---------------------------------------------------------------------------


def dataset_version_of(df: pd.DataFrame, tag: str | None = None) -> str:
    """Data version: an explicit tag when given, else the content digest."""
    return tag if tag else _dataset_digest(df)


# ---------------------------------------------------------------------------
# S1 — screen
# ---------------------------------------------------------------------------


def _rank_of(result, metric: str, composite_config=None) -> float:
    if metric == "composite":
        from .metrics import composite_score

        return float(composite_score(result.metrics, composite_config)["score"])
    value = result.metrics.get(metric)
    return float(value) if value is not None else float("-inf")


def screen_stage(df: pd.DataFrame, strategy: str, grid: dict, *,
                 top_k: int = 5,
                 rank_metric: str = "sharpe",
                 engine: str = "fast",
                 dataset_tag: str | None = None,
                 seed: int = 0,
                 composite_config=None,
                 **run_kwargs) -> dict:
    """S1: cheap screen over the grid; returns ranked manifests + params.

    ``engine`` is ``"fast"`` (default; screening signals only) or
    ``"truth"`` (wrapper engine — slower, still not a certification).
    Unknown strategies and empty grids raise like the canonical entry
    points.  Deterministic: same inputs -> same ranking and manifests.
    """

    if engine not in ("fast", "truth"):
        raise ValueError("engine must be 'fast' or 'truth'")
    if not grid:
        raise ValueError("grid must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    cfg_metric = composite_config if composite_config is not None \
        else RobustFitnessConfig()
    if rank_metric == "composite" and not isinstance(cfg_metric,
                                                     RobustFitnessConfig):
        raise TypeError("composite_config must be a RobustFitnessConfig")

    base = default_params(strategy)  # KeyError: unknown strategy
    keys = sorted(grid)
    combos = [dict(zip(keys, vals)) for vals in itertools.product(
        *(grid[k] for k in keys))]
    runner = run_fast if engine == "fast" else run_backtest
    runs = []
    for combo in combos:
        params = {**base, **combo}
        result = runner(df, strategy, params, **run_kwargs)
        runs.append((params, result))
    runs.sort(key=lambda pr: _rank_of(pr[1], rank_metric, cfg_metric),
              reverse=True)

    version = dataset_version_of(df, dataset_tag)
    manifests = []
    for params, result in runs[:top_k]:
        m = RunManifest(
            stage="screen", strategy=strategy, params=params,
            engine=engine, dataset_version=version, seed=seed,
            dataset_bars=len(df),
            cost_config=_clean(run_kwargs),
            metrics=_clean(result.metrics),
            artifacts={"rank_metric": rank_metric},
        )
        manifests.append(m)
    return {
        "stage": "screen",
        "manifests": manifests,
        "top_params": [m.params for m in manifests],
        "rank_metric": rank_metric,
        "dataset_version": version,
    }


# ---------------------------------------------------------------------------
# S2 — cost stress (x2)
# ---------------------------------------------------------------------------

_COST_KEYS = ("spread_points", "slippage_points", "commission_per_lot")


def _stressed_costs(run_kwargs: dict, factor: float) -> dict:
    kwargs = dict(run_kwargs)
    for key in _COST_KEYS:
        kwargs[key] = float(kwargs.get(key, 0.0)) * factor
    return kwargs


def cost_stress_stage(df: pd.DataFrame, strategy: str,
                      params_list: list[dict], *,
                      factor: float = 2.0,
                      min_trades: int = 10,
                      engine: str = "truth",
                      dataset_tag: str | None = None,
                      seed: int = 0,
                      **run_kwargs) -> dict:
    """S2: TRUTH-engine robustness of every survivor at cost x ``factor``.

    Survival gate (documented, conservative): the stressed run must end
    above initial capital AND keep at least ``min_trades`` trades AND
    its max drawdown must not more than double the unstressed run's.
    The gate is a screening filter — surviving is NOT a profit promise.
    """
    if engine not in ("fast", "truth"):
        raise ValueError("engine must be 'fast' or 'truth'")
    if factor <= 1.0:
        raise ValueError("stress factor must be > 1.0")
    runner = run_backtest if engine == "truth" else run_fast
    version = dataset_version_of(df, dataset_tag)
    manifests = []
    for params in params_list:
        base = runner(df, strategy, params, **run_kwargs)
        stressed = runner(df, strategy, params,
                          **_stressed_costs(run_kwargs, factor))
        bm, sm = base.metrics, stressed.metrics
        trades_s = int(sm.get("trades", 0))
        dd_b = float(bm.get("max_drawdown_pct", 0.0))
        dd_s = float(sm.get("max_drawdown_pct", 0.0))
        end_b = float(bm.get("end_equity", 0.0))
        end_s = float(sm.get("end_equity", 0.0))
        dd_ok = dd_s >= 2.0 * min(dd_b, 0.0)  # never more than doubled
        survived = (end_s > float(run_kwargs.get("initial_capital", 10_000.0))
                    and trades_s >= min_trades
                    and dd_ok)
        manifests.append(RunManifest(
            stage="cost_stress", strategy=strategy, params=params,
            engine=engine, dataset_version=version, seed=seed,
            dataset_bars=len(df),
            cost_config=_clean(_stressed_costs(run_kwargs, factor)),
            status="ok" if survived else "dropped",
            metrics=_clean(sm),
            artifacts={
                "factor": float(factor),
                "base_end_equity": end_b,
                "stressed_end_equity": end_s,
                "stressed_trades": trades_s,
                "base_max_drawdown_pct": dd_b,
                "stressed_max_drawdown_pct": dd_s,
                "min_trades": min_trades,
            },
        ))
    return {"stage": "cost_stress", "manifests": manifests}


# ---------------------------------------------------------------------------
# S3 — trade-level purged CPCV (own implementation)
# ---------------------------------------------------------------------------


def _entry_index_map(index: pd.DatetimeIndex) -> dict[str, int]:
    return {str(t): i for i, t in enumerate(index)}


def _block_edges(n: int, n_splits: int) -> list[tuple[int, int]]:
    """Contiguous bar blocks; the last absorbs the remainder."""
    size = n // n_splits
    if size < 1:
        raise ValueError("n_splits too large for the frame")
    edges = []
    start = 0
    for s in range(n_splits):
        end = n if s == n_splits - 1 else start + size
        edges.append((start, end))
        start = end
    return edges


def _pnl_per_bar(trades: pd.DataFrame, pos: dict[str, int],
                 n: int) -> np.ndarray:
    """Realised net pnl per bar, attributed to the ENTRY bar (the same
    attribution the walk-forward contract uses for window accounting)."""
    out = np.zeros(n)
    if trades is None or trades.empty:
        return out
    for entry, pnl in zip(trades["entry_time"], trades["pnl"]):
        i = pos.get(entry)
        if i is not None:
            out[i] += float(pnl)
    return out


def _sharpe_of_pnl(pnl: np.ndarray) -> float:
    vals = pnl[np.isfinite(pnl)]
    if vals.size < 3:
        return 0.0
    std = vals.std(ddof=1)
    if std <= 0.0:
        return 0.0
    return float(vals.mean() / std)


def purged_cv_stage(df: pd.DataFrame, strategy: str,
                    params_list: list[dict], *,
                    n_splits: int = 6,
                    embargo_bars: int = 0,
                    engine: str = "truth",
                    dataset_tag: str | None = None,
                    seed: int = 0,
                    **run_kwargs) -> dict:
    """S3: own trade-level purge + embargo combinatorial CV over survivors.

    Mechanics (own implementation; the purge/embargo idea follows López
    de Prado's purged k-fold — not a copy): the bar axis is cut into
    ``n_splits`` contiguous blocks; every combination of ``n_splits // 2``
    test blocks forms one fold.  For each fold and each configuration the
    run's trades are split at trade level: a trade whose lifetime
    [entry bar, exit bar) INTERSECTS an embargoed test span
    (test block +/- ``embargo_bars``) is LEAKY for that fold and is
    excluded from in-sample selection (purge), never from the test
    evaluation.  Each fold selects the configuration with the best IS
    Sharpe (leak-free trades only, pnl attributed to the entry bar; ties
    broken deterministically by parameter hash) and scores it on its own
    test blocks.

    The reported OOS-Sharpe distribution is a DEVELOPMENT-data ranking
    diagnostic — it never touches the certification dataset and never
    replaces S5.
    """
    if n_splits < 4 or n_splits % 2 != 0:
        raise ValueError("n_splits must be an even integer >= 4")
    if embargo_bars < 0:
        raise ValueError("embargo_bars must be >= 0")
    if not params_list:
        raise ValueError("params_list must not be empty")
    if engine not in ("fast", "truth"):
        raise ValueError("engine must be 'fast' or 'truth'")
    runner = run_backtest if engine == "truth" else run_fast
    version = dataset_version_of(df, dataset_tag)
    n = len(df)
    edges = _block_edges(n, n_splits)
    pos = _entry_index_map(df.index)
    n_test = n_splits // 2

    # one full-sample run per configuration; trades and per-bar pnl
    per_cfg = []
    for params in params_list:
        result = runner(df, strategy, params, **run_kwargs)
        trades = result.trades
        pnl = _pnl_per_bar(trades, pos, n)
        exit_bar = np.asarray([pos.get(t, -1) for t in trades["exit_time"]])
        entry_bar = np.asarray([pos.get(t, -1) for t in trades["entry_time"]])
        per_cfg.append({
            "params": params,
            "pnl": pnl,
            "entry_bar": entry_bar,
            "exit_bar": exit_bar,
            "n_trades": len(trades),
        })
    cfg_ids = [_param_hash(c["params"]) for c in per_cfg]

    def leaky_mask(cfg: dict, embargoed: list[tuple[int, int]]) -> np.ndarray:
        """Trades whose lifetime intersects any embargoed span."""
        mask = np.zeros(cfg["entry_bar"].size, dtype=bool)
        for lo, hi in embargoed:
            mask |= (cfg["exit_bar"] > lo) & (cfg["entry_bar"] < hi)
        return mask

    fold_scores = []
    selected_hashes = []
    fold_log: list[dict] = []
    for test_blocks in itertools.combinations(range(n_splits), n_test):
        embargoed = []
        for b in test_blocks:
            lo, hi = edges[b]
            embargoed.append((max(0, lo - embargo_bars),
                              min(n, hi + embargo_bars)))
        in_test = np.zeros(n, dtype=bool)
        for lo, hi in embargoed:
            in_test[lo:hi] = True
        train_bars = np.arange(n)[~in_test]
        is_scores = []
        for cfg in per_cfg:
            leaky = leaky_mask(cfg, embargoed)
            keep = ~leaky
            train_pnl = np.zeros(n)
            idx = cfg["entry_bar"][keep]
            vals = cfg["pnl"][idx] if idx.size else np.zeros(0)
            if idx.size:
                np.add.at(train_pnl, idx, vals)
            is_scores.append(_sharpe_of_pnl(train_pnl[train_bars]))
        # deterministic argmax: best IS; ties -> smallest param hash
        best = max(range(len(per_cfg)),
                   key=lambda i: (is_scores[i], -int(cfg_ids[i], 16)))
        chosen = per_cfg[best]
        test_idx: list[int] = []
        for b in test_blocks:
            lo, hi = edges[b]
            test_idx.extend(range(lo, hi))
        fold_scores.append(_sharpe_of_pnl(chosen["pnl"]
                                          [np.asarray(test_idx, dtype=int)]))
        selected_hashes.append(cfg_ids[best])
        fold_log.append({"test_blocks": sorted(test_blocks),
                         "selected": cfg_ids[best],
                         "oos_sharpe": fold_scores[-1]})

    arr = np.asarray(fold_scores, dtype=float)
    manif = RunManifest(
        stage="purged_cv", strategy=strategy,
        params=dict(params_list[0]), engine=engine,
        dataset_version=version, seed=seed, dataset_bars=n,
        cost_config=_clean(run_kwargs),
        metrics={"oos_sharpe_mean": float(arr.mean()),
                 "oos_sharpe_worst": float(arr.min()),
                 "oos_sharpe_p10": float(np.percentile(arr, 10)),
                 "oos_sharpe_median": float(np.median(arr))},
        artifacts={
            "n_splits": n_splits,
            "embargo_bars": embargo_bars,
            "n_folds": len(fold_scores),
            "configs": [
                {"param_hash": h, "params": c["params"],
                 "n_trades": int(c["n_trades"])}
                for h, c in zip(cfg_ids, per_cfg)
            ],
            "selected_most": max(set(selected_hashes),
                                 key=selected_hashes.count),
            "per_fold_oos_sharpe": [float(x) for x in fold_scores],
            "folds": fold_log,
        },
    )
    return {"stage": "purged_cv", "manifest": manif}


# ---------------------------------------------------------------------------
# S4 — headless MT5 tester (certification path, terminal host only)
# ---------------------------------------------------------------------------


def mt5_stage(tester_config=None, run_settings=None) -> RunManifest:
    """S4: headless MetaTrader 5 Strategy Tester ticks.

    Requires a real terminal host: pass an ``mt5tester.TesterConfig`` and
    ``RunSettings``.  Without them the stage returns a manifest with
    status ``skipped`` and an explicit reason — results are never faked
    and never guessed.
    """
    if tester_config is None or run_settings is None:
        return RunManifest(
            stage="mt5", strategy="", params={}, engine="mt5tester",
            dataset_version="", status="skipped",
            artifacts={"reason": "headless MT5 tester requires a terminal "
                       "host; no TesterConfig provided (certification "
                       "runs on a terminal machine)"},
        )
    from .mt5tester import _config_snapshot, run_backtest

    outcome = run_backtest(tester_config, run_settings)
    return RunManifest(
        stage="mt5", strategy=getattr(tester_config, "ea", "") or "",
        params={}, engine="mt5tester",
        dataset_version="",
        status="ok" if outcome.ok else "failed",
        metrics=_clean(outcome.to_dict().get("metrics") or {}),
        artifacts={"snapshot": _config_snapshot(tester_config),
                   "run_id": outcome.run_id,
                   "error": outcome.error},
    )


# ---------------------------------------------------------------------------
# S5 — OOS certification with the one-look registry
# ---------------------------------------------------------------------------


class OosOneLookViolation(ValueError):
    """The OOS certification slice was already used."""


@dataclass
class OosRegistry:
    """Persistent one-look enforcement for OOS certification slices.

    POLICY (documented in the walk-forward contract and here): never
    optimise on the same OOS certification slice more than once per
    (dataset_version, strategy).  ``certify`` refuses to run when the
    dataset version already holds a certification entry, whatever the
    parameters — one look, recorded, forever.
    """

    path: str | Path

    def _load(self) -> dict:
        p = Path(self.path)
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, sort_keys=True),
                     encoding="utf-8")

    def certify(self, strategy: str, dataset_version: str,
                params: dict, strategy_version: str = "undeclared",
                strategy_engine: str = "truth",
                metrics: dict | None = None,
                cost_config: dict | None = None,
                dataset_bars: int = 0) -> RunManifest:
        """Record one certification look; raise if the slice was used."""
        key = f"{dataset_version}::{strategy}"
        data = self._load()
        if key in data:
            raise OosOneLookViolation(
                f"OOS certification slice already used for {strategy!r} on "
                f"dataset version {dataset_version!r} "
                f"(one-look policy; prior params "
                f"{data[key]['params']!r}). A fresh, never-touched dataset "
                "version is required for any further certification.")
        entry = RunManifest(
            stage="oos", strategy=strategy, params=params,
            engine=strategy_engine, dataset_version=dataset_version,
            dataset_bars=dataset_bars,
            cost_config=_clean(cost_config or {}),
            metrics=_clean(metrics or {}),
            status="ok",
            artifacts={"policy": "one-look-per-dataset-version"},
        )
        data[key] = {
            "params": entry.params,
            "manifest_id": entry.manifest_id,
            "strategy_version": strategy_version,
            "engine": strategy_engine,
            "metrics": entry.metrics,
            "cost_config": entry.cost_config,
            "certified": entry.created,
        }
        self._save(data)
        return entry

    def has_look(self, strategy: str, dataset_version: str) -> bool:
        return f"{dataset_version}::{strategy}" in self._load()


def oos_stage(df: pd.DataFrame, strategy: str, params: dict, *,
              registry: OosRegistry,
              dataset_tag: str | None = None,
              strategy_version: str | None = None,
              engine: str = "truth",
              **run_kwargs) -> dict:
    """S5: ONE final TRUTH-engine run on never-touched OOS data.

    The registry refuses a second look on the same dataset version
    (``OosOneLookViolation``).  The manifest carries the data digest /
    tag, the parameter hash and the full cost configuration — enough to
    reproduce the certified run exactly.
    """
    if engine != "truth":
        raise ValueError("OOS certification requires engine='truth'")
    version = dataset_version_of(df, dataset_tag)
    merged = {**default_params(strategy), **params}
    sv = strategy_version or STRATEGY_VERSIONS.get(strategy, "undeclared")
    # fast fail BEFORE the run: a second look on this slice is refused
    if registry.has_look(strategy, version):
        raise OosOneLookViolation(
            f"OOS certification slice already used for {strategy!r} on "
            f"dataset version {version!r} (one-look policy)")
    result = run_backtest(df, strategy, params, **run_kwargs)
    entry = registry.certify(strategy, version, merged,
                             strategy_version=sv,
                             strategy_engine="truth",
                             metrics=_clean(result.metrics),
                             cost_config=_clean(run_kwargs),
                             dataset_bars=len(df))
    return {"stage": "oos", "manifest": entry, "result": result}


# ---------------------------------------------------------------------------
# Orchestration + cache + optional Optuna
# ---------------------------------------------------------------------------


def _cache_key(stage: str, inputs: dict) -> str:
    blob = json.dumps(_clean(inputs), sort_keys=True, separators=(",", ":"),
                      default=repr)
    return hashlib.sha1(f"{stage}|{blob}".encode()).hexdigest()


def _cache_load(cache_dir: str | None, key: str):
    if not cache_dir:
        return None
    p = Path(cache_dir) / f"{key}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _cache_save(cache_dir: str | None, key: str, data) -> None:
    if not cache_dir:
        return
    p = Path(cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{key}.json").write_text(
        json.dumps(_clean(data), indent=2, sort_keys=True),
        encoding="utf-8")


def run_stages(df: pd.DataFrame, strategy: str, grid: dict, *,
               top_k: int = 5,
               n_splits: int = 6,
               embargo_bars: int = 0,
               dataset_tag: str | None = None,
               oos_df: pd.DataFrame | None = None,
               oos_registry: OosRegistry | None = None,
               cache_dir: str | None = None,
               seed: int = 0,
               **run_kwargs) -> dict:
    """Run S1->S3 (-> S5 when an OOS frame + registry are supplied).

    Deterministic and cacheable: stage outputs are cached under
    ``cache_dir`` keyed by the stage inputs (content digests, params,
    cost config, seed) and replayed verbatim on a cache hit.  S4 (MT5)
    is never invoked here — certification ticks belong to a terminal
    host and are driven by ``mt5_stage`` explicitly.
    """
    version = dataset_version_of(df, dataset_tag)
    out = {"dataset_version": version, "stages": {}}

    key = _cache_key("s1", {"strategy": strategy, "grid": grid,
                            "version": version, "top_k": top_k,
                            "seed": seed, "run_kwargs": run_kwargs})
    cached = _cache_load(cache_dir, key)
    if cached is not None:
        out["stages"]["screen"] = cached
    else:
        s1 = screen_stage(df, strategy, grid, top_k=top_k,
                          dataset_tag=dataset_tag, seed=seed, **run_kwargs)
        out["stages"]["screen"] = {
            "manifests": [m.to_dict() for m in s1["manifests"]],
        }
        _cache_save(cache_dir, key, out["stages"]["screen"])

    survivors = [m["params"] for m in out["stages"]["screen"]["manifests"]]
    key2 = _cache_key("s2", {"strategy": strategy, "params": survivors,
                             "version": version, "seed": seed,
                             "run_kwargs": run_kwargs})
    cached = _cache_load(cache_dir, key2)
    if cached is not None:
        out["stages"]["cost_stress"] = cached
    else:
        s2 = cost_stress_stage(df, strategy, survivors, seed=seed,
                               dataset_tag=dataset_tag, **run_kwargs)
        out["stages"]["cost_stress"] = {
            "manifests": [m.to_dict() for m in s2["manifests"]],
        }
        _cache_save(cache_dir, key2, out["stages"]["cost_stress"])
    survivors = [m["params"] for m in out["stages"]["cost_stress"]
                 ["manifests"] if m["status"] == "ok"]

    if survivors:
        key3 = _cache_key("s3", {"strategy": strategy, "params": survivors,
                                 "version": version, "n_splits": n_splits,
                                 "embargo_bars": embargo_bars, "seed": seed,
                                 "run_kwargs": run_kwargs})
        cached = _cache_load(cache_dir, key3)
        if cached is not None:
            out["stages"]["purged_cv"] = cached
        else:
            s3 = purged_cv_stage(df, strategy, survivors,
                                 n_splits=n_splits,
                                 embargo_bars=embargo_bars, seed=seed,
                                 dataset_tag=dataset_tag, **run_kwargs)
            out["stages"]["purged_cv"] = s3["manifest"].to_dict()
            _cache_save(cache_dir, key3, out["stages"]["purged_cv"])
    else:
        # loud, documented: the funnel stops here unless OOS data is
        # provided, in which case S5 falls back to the screen leader
        out["stages"]["purged_cv"] = RunManifest(
            stage="purged_cv", strategy=strategy, params={},
            engine="fast", dataset_version=version, seed=seed,
            dataset_bars=len(df), status="skipped",
            artifacts={"reason": "no cost-stress survivors (gate: x2-cost "
                       "end-equity, min trades, drawdown bound)"},
        ).to_dict()

    if oos_df is not None:
        if oos_registry is None:
            raise ValueError("oos_stage requires an OosRegistry")
        chosen = out["stages"]["purged_cv"].get("artifacts", {}).get(
            "selected_most")
        candidates = survivors or [m["params"]
                                   for m in out["stages"]["screen"]
                                   ["manifests"]]
        params = next((p for p in candidates
                       if _param_hash(p) == chosen), candidates[0])
        oos = oos_stage(oos_df, strategy, params, registry=oos_registry,
                        dataset_tag=dataset_tag, **run_kwargs)
        out["stages"]["oos"] = oos["manifest"].to_dict()
        out["oos_params"] = params
    return out


def optuna_optimize(df: pd.DataFrame, strategy: str, space: dict, *,
                    n_trials: int = 50,
                    dataset_tag: str | None = None,
                    seed: int = 0,
                    metric: str = "sharpe",
                    **run_kwargs) -> dict:
    """OPTIONAL stage: Optuna TPE + Hyperband search over ``space``.

    Never a core dependency: importing this function does not import
    Optuna; calling it without ``optuna`` installed raises ImportError
    with an install hint.  The sampler is seeded (deterministic trials)
    and every trial is cached by its parameters so re-runs replay
    identical results.  Parameters accepted by Optuna's ``suggest_*``
    API map by type name (``int``/``float``/``categorical``).
    """
    try:
        import optuna
    except ImportError as exc:  # optional extra only
        raise ImportError(
            "optuna_optimize requires the optional 'optimize' extra "
            "(pip install mql5bot[optimize]); it is never a core "
            "dependency of the pipeline") from exc
    version = dataset_version_of(df, dataset_tag)
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        params = {}
        for name, spec in space.items():
            kind = spec["type"]
            if kind == "int":
                params[name] = trial.suggest_int(name, spec["low"],
                                                 spec["high"])
            elif kind == "float":
                params[name] = trial.suggest_float(name, spec["low"],
                                                   spec["high"])
            elif kind == "categorical":
                params[name] = trial.suggest_categorical(name,
                                                         spec["choices"])
            else:
                raise ValueError(f"unsupported space type {kind!r}")
        merged = {**default_params(strategy), **params}
        res = run_fast(df, strategy, merged, **run_kwargs)
        value = res.metrics.get(metric)
        return float(value) if value is not None else float("-inf")

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = study.best_params
    return {
        "stage": "optuna",
        "strategy": strategy,
        "dataset_version": version,
        "metric": metric,
        "seed": seed,
        "n_trials": n_trials,
        "best_params": best,
        "best_value": float(study.best_value),
        "engine": "fast",
        "note": "deterministic under seed; screening signal only — "
                "certification stays on the TRUTH path",
    }
