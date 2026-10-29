"""M3 ML Anomaly Detection with Isolation Forest.

Traffic is cut into fixed time windows. Each window becomes one row of features:

  Traffic features (from the proposal)
    pps               packets per second
    avg_pkt_size      average packet size (bytes)
    connections       distinct conversations (5-tuples) active in the window
    avg_conn_duration average time those conversations were active in the window (s)
    dst_ports         distinct destination ports contacted
    tcp_udp_ratio     TCP packets / (UDP packets + 1)
    bytes_per_sec     traffic rate
  Performance features (so congestion is visible too)
    latency_ms, loss_pct, retransmissions

Isolation Forest builds many random trees that keep splitting the data. A window
that looks like the others needs many splits to isolate; an unusual one is
isolated in few splits and gets a high score. It is unsupervised: it learns from
normal traffic and needs no labelled attacks.

Anomaly score is reported on the 0-1 scale of the original Isolation Forest paper
(Liu et al., 2008): about 0.5 or below is normal, values approaching 1 are anomalous.
scikit-learn's score_samples() returns the negative of this score, so we flip the sign.

A second check runs next to the forest: how far each feature is from its normal value,
in units of normal spread (a robust z-score). Isolation Forest only splits on values it
saw during training, so if loss was always 0 in normal traffic it can never isolate a
window with loss. The deviation check catches that case, and also tells the Copilot
which features made the window unusual.

A window is anomalous when its deviation is >= 6, or when the forest score is above the
threshold AND some feature deviates by >= 4. The threshold is the 99th percentile of the
baseline's own scores + 0.03 + 0.25/sqrt(baseline windows), so short baselines are stricter.
Tested on synthetic traffic (10 seeds): all injected events found; under 0.5% of normal
windows flagged.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

TRAFFIC_FEATURES = ["pps", "avg_pkt_size", "connections", "avg_conn_duration", "dst_ports",
                    "tcp_udp_ratio", "bytes_per_sec"]
PERF_FEATURES = ["latency_ms", "loss_pct", "retransmissions"]
FEATURES = TRAFFIC_FEATURES + PERF_FEATURES

# Smallest change in each feature that counts as "one unit of spread". Without this, a
# feature that is always 0 in normal traffic (loss) would make any tiny value look extreme.
MIN_SPREAD = {"throughput_mbps": 0.05, "jitter_ms": 1.0, "pps": 2.0, "avg_pkt_size": 20.0, "connections": 2.0, "avg_conn_duration": 0.05,
              "dst_ports": 2.0, "tcp_udp_ratio": 1.0, "bytes_per_sec": 2000.0,
              "latency_ms": 3.0, "loss_pct": 0.5, "retransmissions": 1.0}


def window_features(df: pd.DataFrame, window: float = 2.0,
                    metrics: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row of features per time window. `metrics` (from window_metrics with the same
    window) adds the performance features; without it they are computed here."""
    from netmind.analyzer.traffic import add_flow_ids
    if df.empty:
        return pd.DataFrame(columns=["t", "window_start"] + FEATURES)
    t0 = df["ts"].min()
    d = add_flow_ids(df)
    d["w"] = ((d["ts"] - t0) // window).astype(int)
    rows = []
    for k in range(int(d["w"].max()) + 1):
        p = d[d["w"] == k]
        n = len(p)
        if n:
            span = p.groupby("flow")["ts"].agg(lambda s: s.max() - s.min())
            tcp = int((p["proto"] == "TCP").sum())
            udp = int((p["proto"] == "UDP").sum())
        rows.append({
            "t": round(k * window, 3), "window_start": round(float(t0 + k * window), 3),
            "pps": n / window,
            "avg_pkt_size": float(p["length"].mean()) if n else 0.0,
            "connections": int(p["flow"].nunique()) if n else 0,
            "avg_conn_duration": float(span.mean()) if n else 0.0,
            "dst_ports": int(p.loc[p["dport"] > 0, "dport"].nunique()) if n else 0,
            "tcp_udp_ratio": tcp / (udp + 1) if n else 0.0,
            "bytes_per_sec": float(p["length"].sum()) / window,
        })
    feats = pd.DataFrame(rows)
    if metrics is None:
        from netmind.performance.metrics import window_metrics
        metrics = window_metrics(df, window)
    m = metrics[["t"] + PERF_FEATURES].copy()
    feats = feats.merge(m, on="t", how="left")
    return feats


def _clean(X: pd.DataFrame, features: list[str], fill: dict | None = None) -> pd.DataFrame:
    """Keeps the feature columns as numbers and fills gaps."""
    X = X[features].astype(float).copy()
    if fill:
        X = X.fillna(fill)
    return X.fillna(0.0)


class AnomalyDetector:
    """Isolation Forest wrapped with scaling, a 0-1 score and per-feature explanations."""

    def __init__(self, features: list[str] | None = None, n_estimators: int = 200,
                 contamination: str | float = "auto", random_state: int = 42,
                 z_threshold: float = 6.0, z_support: float = 4.0):
        """Sets up the 200-tree Isolation Forest and the z thresholds (6 and 4)"""
        self.features = list(features or FEATURES)
        self.model = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                                     random_state=random_state)
        self.scaler = StandardScaler()
        self.baseline: dict = {}
        self.threshold = 0.5
        self.z_threshold = z_threshold
        self.z_support = z_support

    # log1p tames heavy-tailed counts (a flood has 100x the normal packet rate)
    @staticmethod
    def _tf(X: pd.DataFrame) -> np.ndarray:
        """log(1 + x) of each feature so huge values don't dominate."""
        return np.log1p(np.clip(X.to_numpy(dtype=float), 0, None))

    def fit(self, feats: pd.DataFrame) -> "AnomalyDetector":
        """Learns normal: scales, trains the forest, sets the threshold, median and MAD."""
        X = _clean(feats, self.features)
        med = X.median()
        self.fill = med.to_dict()
        Z = self.scaler.fit_transform(self._tf(X))
        self.model.fit(Z)
        train_scores = -self.model.score_samples(Z)
        # A window must score clearly above anything seen in normal traffic. The margin grows
        # when the baseline is short, because a forest built on a few windows is noisy.
        self.threshold = float(max(0.5, np.quantile(train_scores, 0.99) + 0.03
                                   + 0.25 / np.sqrt(len(X))))
        spread = (X - med).abs().median() * 1.4826  # MAD, scaled to match a std-dev
        floor = pd.Series({f: max(MIN_SPREAD.get(f, 1e-3), 0.1 * abs(med[f])) for f in X.columns})
        self.baseline = {"median": med.to_dict(),
                         "spread": spread.where(spread > floor, floor).to_dict(),
                         "train_windows": int(len(X))}
        return self

    def deviations(self, X: pd.DataFrame) -> pd.DataFrame:
        """Robust z-score of every feature: (x - median) / spread."""
        med = pd.Series(self.baseline["median"])[self.features]
        spr = pd.Series(self.baseline["spread"])[self.features]
        return (X[self.features] - med) / spr

    def score(self, feats: pd.DataFrame) -> pd.DataFrame:
        """Adds anomaly_score (0-1), is_anomaly and the features that stand out most."""
        X = _clean(feats, self.features, getattr(self, "fill", None))
        Z = self.scaler.transform(self._tf(X))
        s = -self.model.score_samples(Z)
        out = feats[[c for c in ("t", "window_start") if c in feats.columns]].copy()
        z = self.deviations(X).abs().max(axis=1).to_numpy()
        out["anomaly_score"] = np.round(s, 4)
        out["max_deviation"] = np.round(z, 1)
        # Flag a window when the deviation is large on its own, or when the forest finds it
        # unusual AND at least one feature is clearly away from normal (>= z_support). The
        # second condition stops the forest flagging windows that are only mildly different.
        out["is_anomaly"] = ((s > self.threshold) & (z >= self.z_support)) | (z >= self.z_threshold)
        out["top_features"] = [json.dumps(self.explain_row(X.iloc[i]))
                               for i in range(len(X))]
        return out

    def explain_row(self, row: pd.Series, k: int = 3) -> list[dict]:
        """Features furthest from normal, as robust z-scores (distance from the training median)."""
        med, spr = self.baseline["median"], self.baseline["spread"]
        items = []
        for f in self.features:
            z = (row[f] - med[f]) / spr[f]
            items.append({"feature": f, "value": round(float(row[f]), 3),
                          "normal": round(float(med[f]), 3), "z": round(float(z), 1)})
        items.sort(key=lambda x: -abs(x["z"]))
        return [i for i in items[:k] if abs(i["z"]) >= 3]

    def save(self, path: str | Path) -> None:
        """Saves the trained detector with joblib."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> "AnomalyDetector":
        """Loads a saved detector."""
        return joblib.load(path)


# A baseline needs at least this many windows (16 s of traffic with 2 s windows). With fewer,
# "normal" cannot be learned, so detection is skipped instead of reporting "no anomalies".
MIN_TRAIN_WINDOWS = 8


class InsufficientDataError(ValueError):
    """Not enough traffic to learn a normal baseline."""


def baseline(feats: pd.DataFrame, train_until: float | None = None,
             train_fraction: float = 0.3) -> pd.DataFrame:
    """The windows used as the normal baseline: the first `train_until` seconds, or by
    default the first 30% of windows (at least MIN_TRAIN_WINDOWS)."""
    if train_until is None:
        return feats.iloc[:max(MIN_TRAIN_WINDOWS, int(len(feats) * train_fraction))]
    return feats[feats["t"] < train_until]


def detect(feats: pd.DataFrame, train_until: float | None = None,
           train_fraction: float = 0.3, features: list[str] | None = None,
           model: AnomalyDetector | None = None) -> tuple[pd.DataFrame, AnomalyDetector]:
    """Train on the start of the capture (assumed normal) unless a trained model is given,
    then score every window.

    train_until: seconds from the start of the capture to use as normal baseline.
    Raises InsufficientDataError when the baseline has fewer than MIN_TRAIN_WINDOWS windows.
    """
    if model is None:
        base = baseline(feats, train_until, train_fraction)
        if len(base) < MIN_TRAIN_WINDOWS:
            raise InsufficientDataError(
                f"only {len(base)} time window(s) available for the normal baseline; at least "
                f"{MIN_TRAIN_WINDOWS} are needed (capture longer, e.g. 60 s or more)")
        model = AnomalyDetector(features).fit(base)
    return model.score(feats), model
