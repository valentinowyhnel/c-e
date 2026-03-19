from __future__ import annotations

from dataclasses import asdict
from statistics import fmean
import uuid

from app.audit import AuditLogger
from app.collector import Collector
from app.config import RuntimeSettings
from app.cortex.client import CortexControlPlaneClient
from app.cortex.sync import CortexSyncCoordinator
from app.drift import DriftDetectorSuite
from app.features import FeatureBuilder
from app.health import HealthSnapshot
from app.learning_guard import LearningGuard
from app.metrics import MetricsRegistry
from app.models import AuthenticatedPeer, IngestDecision, LocalUpdate, ModelSnapshot, PipelineOutcome, stable_hash
from app.normalizer import EventNormalizer
from app.policy import ManifestSigner
from app.promotion import PromotionManager
from app.scoring import LocalScoringPipeline
from app.training import LocalTrainer
from app.transport.client import TransportClient
from app.transport.nats_bus import NATSJetStreamBus
from app.transport.queue import EncryptedWALQueue
from app.transport.security import SecureSessionGuard


class SentinelMachineService:
    def __init__(self, settings: RuntimeSettings, collector: Collector) -> None:
        self.settings = settings
        self.collector = collector
        self.normalizer = EventNormalizer()
        self.feature_builder = FeatureBuilder()
        self.drift = DriftDetectorSuite()
        self.scoring = LocalScoringPipeline(dimensions=14)
        self.trainer = LocalTrainer(settings.tenant_id, settings.machine_id, settings.machine_role)
        self.guard = LearningGuard()
        self.promoter = PromotionManager(settings.promotion_patience)
        self.manifest_signer = ManifestSigner("hmac-sha256", settings.queue_key)
        self.queue = EncryptedWALQueue(settings.queue_path, settings.queue_key)
        self.nats_bus = (
            NATSJetStreamBus(settings.nats_url, settings.nats_connect_timeout_seconds)
            if settings.enable_nats_bus
            else None
        )
        if self.nats_bus is not None:
            try:
                self.nats_bus.start()
            except Exception:
                self.nats_bus = None
        self.transport = TransportClient(self.queue, self.nats_bus)
        self.session_guard = SecureSessionGuard("spiffe://cortex/sentinel-machine/")
        self.audit = AuditLogger(settings.state_dir / "audit.log")
        self.metrics = MetricsRegistry()
        self.champion: ModelSnapshot | None = None
        self.shadow: ModelSnapshot | None = None
        self.control_plane = CortexControlPlaneClient(
            settings.cortex_ingest_url,
            settings.cortex_trust_url,
            settings.cortex_model_url,
            settings.cortex_internal_token,
        )
        self.sync = CortexSyncCoordinator(self.control_plane)

    def process_once(self) -> list[PipelineOutcome]:
        outcomes: list[PipelineOutcome] = []
        for raw_event in self.collector.collect():
            outcomes.append(self.process_raw_event(raw_event))
        return outcomes

    def process_raw_event(self, raw_event) -> PipelineOutcome:
        normalized = self.normalizer.normalize(raw_event)
        enriched = self.feature_builder.build(normalized)
        feature_mean = fmean(enriched.feature_vector.values())
        initial_drift = self.drift.evaluate(score=feature_mean, feature_mean=feature_mean)
        risk = self.scoring.score(enriched, initial_drift)
        drift_status = self.drift.evaluate(score=risk.score, feature_mean=feature_mean)
        self.trainer.observe(enriched)
        update = self._build_update(enriched, risk)
        guard_decision = self.guard.evaluate(
            update=update,
            machine_compromised=bool(enriched.feature_vector.get("tamper_flags")),
            labels_inconsistent=False,
            corroborated=self._is_corroborated(enriched.feature_vector),
            reference_degradation=max(0.0, risk.score - 0.92),
        )
        emitted = [
            self.transport.emit(
                "telemetry",
                {
                    "event_id": enriched.event_id,
                    "machine_id": enriched.machine_id,
                    "tenant_id": enriched.tenant_id,
                    "trace_id": enriched.trace_id,
                    "event_type": enriched.event_type,
                    "privacy_level": enriched.privacy_level,
                    "feature_vector": enriched.feature_vector,
                    "integrity_fields": enriched.integrity_fields,
                },
            ),
            self.transport.emit(
                "risk",
                {
                    "event_id": enriched.event_id,
                    "risk_score": risk.score,
                    "severity": risk.severity,
                    "confidence": risk.confidence,
                    "drift": asdict(drift_status),
                },
            ),
        ]
        if guard_decision.accepted and self.trainer.can_train(self.settings.min_training_support):
            self.shadow = self.trainer.train_shadow(self.champion)
            self.shadow.signed_manifest = self._sign_manifest(self.shadow)
            self.shadow.evaluation_report = self._evaluate_shadow(risk.score)
            promotion = self.promoter.evaluate(
                champion=self.champion,
                challenger=self.shadow,
                metrics=self.shadow.evaluation_report,
                signed_approval=True,
                poisoning_suspected=guard_decision.quarantined,
                drift_hard=drift_status.hard_drift,
            )
            self.audit.record("promotion_decision", {"model_id": self.shadow.model_id, "decision": asdict(promotion)})
            if promotion.approved:
                self.champion = self.shadow
        self.metrics.inc("events_processed_total")
        self.metrics.set("nats_bus_connected", 1.0 if self.nats_bus is not None else 0.0)
        self.metrics.inc("queue_flushed_total", float(self.transport.flush_pending()))
        self.metrics.set("backpressure_queue_depth", float(self.queue.depth()))
        self.metrics.set("model_confidence", risk.confidence - guard_decision.confidence_penalty)
        self.audit.record("security_decision", {"event_id": enriched.event_id, "severity": risk.severity, "risk_score": risk.score})
        return PipelineOutcome(
            normalized_event=enriched,
            drift_status=drift_status,
            risk=risk,
            update_decision=guard_decision,
            emitted_records=emitted,
        )

    def sync_outcome(self, outcome: PipelineOutcome) -> dict[str, object]:
        result = self.sync.sync_outcome(self, outcome)
        self.audit.record("control_plane_sync", result)
        return result

    def close(self) -> None:
        if self.nats_bus is not None:
            self.nats_bus.stop()

    def health(self) -> HealthSnapshot:
        queue_depth = self.queue.depth()
        cpu_overhead = min(self.settings.cpu_budget_percent, 0.4 + queue_depth / 10000.0)
        memory_overhead = min(self.settings.memory_budget_mb, 64.0 + queue_depth / 50.0)
        status = "ok" if queue_depth <= self.settings.max_queue_depth else "degraded"
        return HealthSnapshot(
            status=status,
            queue_depth=queue_depth,
            cpu_overhead=round(cpu_overhead, 4),
            memory_overhead_mb=round(memory_overhead, 4),
            drift_hard=False,
        )

    def ingest_remote_update(self, peer: AuthenticatedPeer, update: LocalUpdate) -> IngestDecision:
        auth = self.session_guard.authorize_peer(peer, self.settings.tenant_id)
        reasons = list(auth.reasons)
        expected_schema = stable_hash(sorted(self.trainer.memory.long_term[0].keys())) if self.trainer.memory.long_term else update.feature_schema_hash
        if update.feature_schema_hash != expected_schema:
            reasons.append("feature_schema_mismatch")
        if update.signed_by != peer.spiffe_id:
            reasons.append("signer_peer_mismatch")
        accepted = not reasons
        decision = IngestDecision(accepted=accepted, reasons=reasons)
        self.audit.record("remote_update_ingest", {"accepted": accepted, "reasons": reasons, "peer": peer.spiffe_id, "model_id": update.model_id})
        return decision

    def _build_update(self, event, risk) -> LocalUpdate:
        delta = {key: round(value * risk.score, 6) for key, value in event.feature_vector.items()}
        return LocalUpdate(
            model_id=self.champion.model_id if self.champion else "bootstrap",
            machine_id=self.settings.machine_id,
            tenant_id=self.settings.tenant_id,
            feature_schema_hash=stable_hash(sorted(event.feature_vector.keys())),
            metrics={"local_risk": risk.score, "confidence": risk.confidence},
            delta=delta,
            dataset_fingerprint=stable_hash([event.event_id, event.trace_id]),
            signed_by=self.settings.model_signing_key_id,
            suspicion_score=round(float(event.feature_vector.get("tamper_flags", 0.0)) * 0.5, 4),
            replay_nonce=str(uuid.uuid4()),
        )

    def _is_corroborated(self, vector: dict[str, float]) -> bool:
        supports = [
            vector.get("network_external", 0.0),
            vector.get("auth_elevated", 0.0),
            vector.get("file_sensitive", 0.0),
            vector.get("dns_rare", 0.0),
        ]
        return sum(1 for value in supports if value > 0.0) >= 2

    def _sign_manifest(self, snapshot: ModelSnapshot) -> dict[str, object]:
        body = {
            "model_id": snapshot.model_id,
            "parent_model_id": snapshot.parent_model_id,
            "tenant_scope": snapshot.tenant_scope,
            "machine_scope": snapshot.machine_scope,
            "training_window": snapshot.training_window,
            "feature_schema_hash": snapshot.feature_schema_hash,
        }
        manifest = self.manifest_signer.sign(body)
        manifest["signer"] = self.settings.model_signing_key_id
        return manifest

    def _evaluate_shadow(self, risk_score: float) -> dict[str, float]:
        return {
            "shadow_vs_champion_delta": round(max(0.0, 0.8 - risk_score), 4),
            "baseline_stability_score": 0.9 if self.trainer.memory.long_term else 0.0,
            "false_positive_rate_estimate": 0.04 if risk_score < 0.8 else 0.08,
            "update_acceptance_rate": 1.0,
        }
