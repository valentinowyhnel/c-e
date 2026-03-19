from dataclasses import dataclass


@dataclass
class AnomalyClassification:
    is_anomalous: bool
    anomaly_type: str
    severity: int
    confidence: float
    evidence: list[str]
    suggested_action: str


class AnomalyEngine:
    async def classify_threshold(self, value: float, baseline: float, metric: str) -> AnomalyClassification:
        ratio = value / baseline if baseline > 0 else value
        is_anomalous = ratio >= 5 or value >= 1000
        anomaly_type = "latency" if "latency" in metric else "behavioral"
        severity = 4 if ratio >= 10 else 3 if is_anomalous else 1
        return AnomalyClassification(
            is_anomalous=is_anomalous,
            anomaly_type=anomaly_type if is_anomalous else "none",
            severity=severity,
            confidence=0.95 if is_anomalous else 0.3,
            evidence=[f"value={value}", f"baseline={baseline}"],
            suggested_action="restart_pod" if is_anomalous else "none",
        )
