from __future__ import annotations

from pathlib import Path


def test_meta_decision_proto_and_generator_exist() -> None:
    proto = Path("proto/meta_decision/v1/meta_decision.proto")
    generator = Path("scripts/generate_meta_decision_proto_stubs.py")
    go_generator = Path("scripts/generate_meta_decision_go_stubs.py")
    assert proto.exists() is True
    assert generator.exists() is True
    assert go_generator.exists() is True


def test_meta_decision_proto_declares_core_messages() -> None:
    body = Path("proto/meta_decision/v1/meta_decision.proto").read_text(encoding="utf-8")
    for token in (
        "message AgentSignal",
        "message DeepAnalysisRequest",
        "message TrustedAgentOutput",
        "message MetaDecisionAssessmentRequest",
        "message MetaDecisionEvent",
    ):
        assert token in body


def test_generated_proto_artifacts_exist() -> None:
    assert Path("proto/meta_decision/v1/meta_decision_pb2.py").exists() is True
    assert Path("proto/meta_decision/v1/meta_decision_pb2_grpc.py").exists() is True
    assert Path("proto/meta_decision/v1/meta_decision.pb.go").exists() is True
