"""M3 ML Anomaly Detection

Per-window traffic and performance features, Isolation Forest scoring on the
0-1 scale (above ~0.5 = unusual), and explanations of which features stand out.

Owner: Affan. Phase: 4.
"""
from .episodes import episodes, classify, TYPES
from .detector import (FEATURES, TRAFFIC_FEATURES, PERF_FEATURES, window_features,
                       AnomalyDetector, detect)

__all__ = ["episodes", "classify", "TYPES", "FEATURES", "TRAFFIC_FEATURES", "PERF_FEATURES", "window_features", "AnomalyDetector",
           "detect"]
