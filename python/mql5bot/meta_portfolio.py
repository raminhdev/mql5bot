"""mql5bot.meta_portfolio — the canonical Meta portfolio engine
(meta-production mission, Phases 3-10).

This is the engine the mission mandates: strategy signals on ONE shared
account → Meta decision at time t (inputs available at t only) → weights
→ the canonical :class:`engine.PortfolioEngine` mechanics (netting or
hedging, shared equity, real fills, costs, Risk-Engine sizing, exposure
caps) → PnL, attribution, constraints.

It replaces the equity-curve blend of :mod:`meta_replay` (which remains
only as a diagnostic approximation): here BOTH policies (META and
EQUAL_WEIGHT) run the SAME portfolio mechanics over the SAME event
stream, differing ONLY in the weighting policy — the correct META vs
EQUAL_WEIGHT comparison.

Causality contract (Phases 4/8):
* rebalance timestamps are a fixed grid known in advance;
* the decision at rebalance ``t`` uses ONLY bars with
  ``index < t`` (strictly before the bar whose open the weight takes
  effect on): expanding per-strategy trade statistics, correlation of
  returns, and the layer's runtime state (prior weights);
* runtime state (prior allocation) carries across rebalances and across
  the DEV→OOS boundary; research knowledge (future OOS performance,
  future correlations, future regimes/drift) never does;
* every decision carries its ``as_of`` in the journal.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .engine import CostConfig, Instrument, PortfolioEngine, RunConfig
from .meta_layer import MetaConfig, MetaLayer, MetaPolicy, StrategyMetaInput
from .meta_oos import StrategySpec

TRADING_DAYS = 252


# ---- as-of statistics (strictly exclusive: index < t) ----------------------


def as_of_stats_exclusive(df: pd.DataFrame, specs: list[StrategySpec],
                          as_of: pd.Timestamp,
                          instrument: dict | None = None
                          ) -> tuple[dict, pd.DataFrame]:
    """Per-strategy (mean per-trade pct return, n trades) and per-bar
    returns from runs over ``[start, as_of)`` ONLY — the bar whose open
    the weight takes effect on is NEVER part of the statistics."""
    instrument = instrument or {}
    window = df.loc[df.index < as_of]
    stats: dict[str, tuple[float, int]] = {}
    rets: dict[str, pd.Series] = {}
    for spec in sorted(specs, key=lambda s: s.name):
        res = run_backtest(window, spec.engine_strategy, spec.params,
                           **instrument)
        pnl = res.trades["pnl_pct"] if len(res.trades) else \
            pd.Series(dtype=float)
        stats[spec.name] = (float(pnl.mean()) if len(pnl) else 0.0, len(pnl))
        rets[spec.name] = res.equity.pct_change().fillna(0.0)
    return stats, pd.DataFrame(rets)


# ---- rebalance grid ---------------------------------------------------------


def rebalance_grid(index: pd.DatetimeIndex, *, first_bar: int,
                   every_days: int = 1) -> list[pd.Timestamp]:
    """First bar of every ``every_days``-th calendar day from ``first_bar``
    on — a fixed grid, independent of any outcome."""
    out: list[pd.Timestamp] = []
    days = sorted({ts.date() for ts in index[first_bar:]})
    for d in days[::max(1, every_days)]:
        for ts in index[first_bar:]:
            if ts.date() == d:
                out.append(ts)
                break
    return out


# ---- immutable decision snapshot (Phase 2) ----------------------------------


@dataclass(frozen=True)
class MetaSnapshot:
    """Everything a decision at ``as_of`` may consume — and nothing else.

    Frozen: attributes refuse re-binding; the stats mapping and the
    returns/specs containers are defensively copied at construction, so
    hostile mutation of the caller's objects cannot reach a decision
    made from this snapshot.
    """

    as_of: pd.Timestamp
    stats: dict
    returns: pd.DataFrame
    specs: tuple

    def __post_init__(self):
        object.__setattr__(self, "as_of", pd.Timestamp(self.as_of))
        object.__setattr__(self, "stats",
                           types.MappingProxyType(dict(self.stats)))
        object.__setattr__(self, "returns", self.returns.copy(deep=True))
        object.__setattr__(self, "specs", tuple(self.specs))


# ---- decision inputs (identical for both policies) --------------------------


def _strategy_inputs(specs: list[StrategySpec], label: str,
                     certified: set[str] | None = None
                     ) -> list[StrategyMetaInput]:
    """Certification inputs for research replay: VERIFIED states with a
    neutral regime and no drift — the weighting policy is the ONLY
    difference under test here.  When ``certified`` is provided, specs
    outside it are UNCERTIFIED (hard zero at every decision)."""
    out = []
    for s in sorted(specs, key=lambda s: s.name):
        state = "VERIFIED" if certified is None or s.name in certified \
            else "UNCERTIFIED"
        out.append(StrategyMetaInput(
            s.name, label, 0, "TREND_UP",
            frozenset({"TREND_UP"}), frozenset({"TREND_UP"}),
            frozenset(), state, drift_available=True,
            drift_score=0.0, strategy_version=s.version))
    return out


# ---- results -----------------------------------------------------------------


@dataclass
class PolicyRun:
    policy: str
    equity: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    events: list = field(default_factory=list)
    weights: list[dict] = field(default_factory=list)   # decision journal
    metrics: dict = field(default_factory=dict)
    attribution: pd.DataFrame = field(
        default_factory=pd.DataFrame)                   # per-strategy PnL


@dataclass
class MetaPortfolioResult:
    meta: PolicyRun
    equal_weight: PolicyRun
    rebalance_dates: list = field(default_factory=list)
    comparison: dict = field(default_factory=dict)


# ---- the engine --------------------------------------------------------------


class MetaPortfolioEngine:
    """Runs META and EQUAL_WEIGHT portfolios with identical mechanics.

    One shared account per policy: all strategies trade the same df on
    the same symbol under one :class:`RunConfig` (netting or hedging),
    one capital base, one cost model, one Risk Engine; only the
    allocation schedule (the weights) differs.
    """

    def __init__(self, df: pd.DataFrame, specs: list[StrategySpec], *,
                 config: MetaConfig | None = None,
                 instrument: dict | None = None,
                 mode: str = "netting",
                 initial_capital: float = 10_000.0,
                 risk_percent: float = 1.0,
                 every_days: int = 1,
                 min_history_bars: int = 250,
                 label: str = "SYNTH",
                 initial_weights: dict[str, float] | None = None,
                 certified: set[str] | None = None):
        self.df = df
        self.specs = sorted(specs, key=lambda s: s.name)
        self.config = config or MetaConfig()
        # certification surface under test: when provided, specs outside
        # the set are UNCERTIFIED at every decision (hard zero)
        self.certified = certified
        self.instrument = dict(instrument or {})
        self.mode = mode
        self.initial_capital = initial_capital
        self.risk_percent = risk_percent
        self.every_days = every_days
        self.min_history = min_history_bars
        self.label = label
        self.initial_weights = dict(initial_weights or {})
        self.rebalances = rebalance_grid(df.index, first_bar=min_history_bars,
                                         every_days=every_days)

    # -- decisions ---------------------------------------------------------

    def snapshot(self, t: pd.Timestamp) -> MetaSnapshot:
        """The immutable input snapshot for a decision at ``t`` (strictly
        pre-``t`` statistics — the bar whose open the weight takes effect
        on is never part of the inputs)."""
        stats, hist_rets = as_of_stats_exclusive(
            self.df, self.specs, t, instrument=self.instrument)
        return MetaSnapshot(as_of=t, stats=stats, returns=hist_rets,
                            specs=tuple(self.specs))

    def decide_weights(self, t: pd.Timestamp, policy: MetaPolicy,
                       layer: MetaLayer) -> tuple[dict[str, float], dict]:
        """Causal weights at ``t`` from the immutable snapshot."""
        snap = self.snapshot(t)
        inputs = _strategy_inputs(list(snap.specs), self.label,
                                  self.certified)
        corr = snap.returns if policy is MetaPolicy.META \
            and not snap.returns.empty else None
        d = layer.decide(inputs, as_of=snap.as_of.to_pydatetime(),
                         returns=corr,
                         oos_stats=dict(snap.stats))
        w = {x.strategy_id: x.final_weight for x in d.weights}
        journal = {"as_of": str(t), "policy": policy.value,
                   "n_trades_prior": {k: v[1]
                                      for k, v in snap.stats.items()},
                   **{f"w::{k}": v for k, v in sorted(w.items())}}
        return w, journal

    def _schedules(self, weights_seq: list[tuple[pd.Timestamp, dict]]
                   ) -> dict[str, tuple]:
        sched: dict[str, list] = {s.name: [] for s in self.specs}
        for t, w in weights_seq:
            for s in self.specs:
                sched[s.name].append((t, float(w.get(s.name, 0.0))))
        return {k: tuple(v) for k, v in sched.items()}

    # -- the run -----------------------------------------------------------

    def run_policy(self, policy: MetaPolicy,
                   layer: MetaLayer) -> PolicyRun:
        weights_seq: list[tuple[pd.Timestamp, dict]] = []
        journals: list[dict] = []
        for t in self.rebalances:
            w, journal = self.decide_weights(t, policy, layer)
            weights_seq.append((t, w))
            journals.append(journal)
        sched = self._schedules(weights_seq)
        costs = CostConfig(symbol="GEN", **{
            k: v for k, v in self.instrument.items()
            if k in CostConfig.__dataclass_fields__})
        from .symbolspec import SymbolSpec
        spec = SymbolSpec(
            name="GEN",
            point=float(self.instrument.get("point", 1e-5)),
            tick_size=float(self.instrument.get("point", 1e-5)),
            tick_value_loss=float(self.instrument.get("point", 1e-5))
            * float(self.instrument.get("contract_size", 100_000.0)),
            contract_size=float(self.instrument.get("contract_size",
                                                    100_000.0)),
            currency_profit="USD", currency_deposit="USD")
        instruments = [
            Instrument(symbol="GEN", strategy=s.engine_strategy or s.name,
                       df=self.df, costs=costs, spec=spec,
                       profit_to_deposit=1.0, params=s.params,
                       allocation_schedule=sched[s.name])
            for s in self.specs]
        cfg = RunConfig(initial_capital=self.initial_capital,
                        mode=self.mode,
                        risk_value=self.risk_percent,
                        warmup_bars=self.min_history)
        res = PortfolioEngine(cfg).run(instruments)
        run = PolicyRun(policy=policy.value, equity=res.equity,
                        trades=res.trades, events=res.events,
                        weights=journals)
        run.metrics = self._metrics(run)
        run.attribution = self._attribution(run)
        return run

    # -- metrics / attribution (Phase 10) -----------------------------------

    def _metrics(self, run: PolicyRun) -> dict:
        """Full canonical report (net, CAGR, Sharpe, Sortino, Calmar, maxDD,
        DD duration, PF, expectancy, recovery, CVaR, exposure, turnover,
        concentration) via :func:`metrics.compute_metrics`, plus realized
        cross-strategy correlation of the period."""
        from .metrics import compute_metrics
        idx = run.equity.index
        if len(idx) > 2:
            step = float(np.median(np.diff(idx.values).astype("timedelta64[s]")
                                   .astype(float)))
            ppy = 365 * 24 * 3600 / step if step > 0 else 24 * TRADING_DAYS
        else:
            ppy = 24 * TRADING_DAYS
        m = compute_metrics(run.equity, run.trades, periods_per_year=ppy)
        m["n_trades"] = len(run.trades)
        m["realized_corr_mean"] = self._realized_corr(run)
        return m

    def _realized_corr(self, run: PolicyRun) -> float:
        """Mean pairwise realized correlation of per-strategy daily PnL."""
        t = run.trades
        if not len(t) or t["strategy"].nunique() < 2:
            return float("nan")
        piv = t.assign(day=pd.to_datetime(t["exit_time"]).dt.date) \
            .pivot_table(index="day", columns="strategy", values="pnl",
                         aggfunc="sum").fillna(0.0)
        corr = piv.corr().to_numpy()
        mask = ~np.eye(len(corr), dtype=bool)
        return float(np.nanmean(corr[mask])) if mask.any() else float("nan")

    @staticmethod
    def _attribution(run: PolicyRun) -> pd.DataFrame:
        if not len(run.trades):
            return pd.DataFrame(columns=["strategy", "pnl", "trades"])
        g = run.trades.groupby("strategy")["pnl"].agg(["sum", "count"])
        g.columns = ["pnl", "trades"]
        return g.reset_index().sort_values("strategy")

    # -- full comparison ----------------------------------------------------

    def meta_layer(self) -> MetaLayer:
        """The META layer for this engine (public so tests/replay can drive
        single decisions through the identical path)."""
        return MetaLayer(self.config,
                         state=None if not self.initial_weights
                         else self._seeded_state())

    def run(self) -> MetaPortfolioResult:
        meta_layer = self.meta_layer()
        ew_layer = MetaLayer(_ew_config(self.config))
        meta = self.run_policy(MetaPolicy.META, meta_layer)
        ew = self.run_policy(MetaPolicy.EQUAL_WEIGHT, ew_layer)
        out = MetaPortfolioResult(meta=meta, equal_weight=ew,
                                  rebalance_dates=self.rebalances)
        out.comparison = compare_policies(meta, ew)
        return out

    def _seeded_state(self):
        from .meta_layer import MetaState
        return MetaState(config_hash=self.config.config_hash,
                         weights=dict(self.initial_weights))


def _ew_config(config: MetaConfig) -> MetaConfig:
    return MetaConfig(policy=MetaPolicy.EQUAL_WEIGHT,
                      mode=config.mode,
                      vote_threshold=config.vote_threshold,
                      max_strategy_weight=config.max_strategy_weight,
                      gross_exposure_cap=config.gross_exposure_cap,
                      max_weight_change=config.max_weight_change,
                      max_positions=config.max_positions)


# ---- statistical comparison (Phase 25) --------------------------------------


def compare_policies(meta: PolicyRun, ew: PolicyRun) -> dict:
    from .meta_replay import block_bootstrap_sharpe_diff, probabilistic_sharpe
    mr, er = meta.equity, ew.equity   # both helpers pct_change() internally
    out: dict = {"net_meta": float(meta.metrics.get("net_profit", 0.0)),
                 "net_ew": float(ew.metrics.get("net_profit", 0.0)),
                 "sharpe_meta": float(meta.metrics.get("sharpe", 0.0)),
                 "sharpe_ew": float(ew.metrics.get("sharpe", 0.0)),
                 "maxdd_meta": float(meta.metrics.get("max_drawdown_pct", 0.0) or 0.0),
                 "maxdd_ew": float(ew.metrics.get("max_drawdown_pct", 0.0) or 0.0),
                 "trades_meta": int(meta.metrics.get("n_trades", 0)),
                 "trades_ew": int(ew.metrics.get("n_trades", 0))}
    if len(mr) > 30 and len(er) > 30:
        try:
            boot = block_bootstrap_sharpe_diff(mr, er)
            out["bootstrap"] = boot
            out["psr_meta_gt_ew"] = probabilistic_sharpe(mr, er)
        except Exception:  # noqa: BLE001 — never fake significance
            out["bootstrap"] = None
    return out


def main(days: int = 365, seed: int = 5) -> int:
    from .data import generate_ohlc
    df = generate_ohlc(days=days, seed=seed)
    specs = [StrategySpec("bollinger_reversal", {}),
             StrategySpec("ema_crossover", {"fast": 10, "slow": 50}),
             StrategySpec("macd_momentum", {})]
    eng = MetaPortfolioEngine(df, specs, min_history_bars=480,
                              every_days=2, label="SYNTH")
    res = eng.run()
    for run, name in ((res.meta, "META"), (res.equal_weight, "EQUAL_WEIGHT")):
        print(f"{name}: net={run.metrics['net_profit']:.2f} "
              f"sharpe={run.metrics['sharpe']:.3f} "
              f"trades={run.metrics['n_trades']}")
    print("comparison:", {k: v for k, v in res.comparison.items()
                          if k in ("net_meta", "net_ew", "psr_meta_gt_ew")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
