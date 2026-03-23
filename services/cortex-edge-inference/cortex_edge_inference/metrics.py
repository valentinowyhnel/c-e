from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EdgeMetrics:
    inference_requests_total: int = 0
    inference_failures_total: int = 0
    trust_forward_total: int = 0
    trust_forward_failures_total: int = 0
    audit_events_total: int = 0
    audit_failures_total: int = 0

    def render(self) -> str:
        return "\n".join(
            [
                "# HELP cortex_edge_inference_requests_total Total inference requests.",
                "# TYPE cortex_edge_inference_requests_total counter",
                f"cortex_edge_inference_requests_total {self.inference_requests_total}",
                "# HELP cortex_edge_inference_failures_total Total inference failures.",
                "# TYPE cortex_edge_inference_failures_total counter",
                f"cortex_edge_inference_failures_total {self.inference_failures_total}",
                "# HELP cortex_edge_inference_trust_forward_total Total trust forwarding attempts.",
                "# TYPE cortex_edge_inference_trust_forward_total counter",
                f"cortex_edge_inference_trust_forward_total {self.trust_forward_total}",
                "# HELP cortex_edge_inference_trust_forward_failures_total Total trust forwarding failures.",
                "# TYPE cortex_edge_inference_trust_forward_failures_total counter",
                f"cortex_edge_inference_trust_forward_failures_total {self.trust_forward_failures_total}",
                "# HELP cortex_edge_inference_audit_events_total Total audit events sent.",
                "# TYPE cortex_edge_inference_audit_events_total counter",
                f"cortex_edge_inference_audit_events_total {self.audit_events_total}",
                "# HELP cortex_edge_inference_audit_failures_total Total audit failures.",
                "# TYPE cortex_edge_inference_audit_failures_total counter",
                f"cortex_edge_inference_audit_failures_total {self.audit_failures_total}",
                "",
            ]
        )
