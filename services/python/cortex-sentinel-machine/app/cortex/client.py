from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from app.cortex.contracts import build_ingest_payload, build_model_candidate_payload, build_trust_payload
from app.models import ModelSnapshot, PipelineOutcome


class CortexHTTPError(RuntimeError):
    pass


class CortexControlPlaneClient:
    def __init__(self, ingest_url: str, trust_url: str, model_url: str, internal_token: str) -> None:
        self.ingest_url = ingest_url.rstrip("/")
        self.trust_url = trust_url.rstrip("/")
        self.model_url = model_url.rstrip("/")
        self.internal_token = internal_token

    def push_event(self, outcome: PipelineOutcome) -> dict[str, object]:
        return self._post_json(f"{self.ingest_url}/v1/sentinel/events", build_ingest_payload(outcome), use_internal_token=False)

    def evaluate_trust(self, outcome: PipelineOutcome) -> dict[str, object]:
        return self._post_json(f"{self.trust_url}/trust/evaluate/v2", build_trust_payload(outcome), use_internal_token=True)

    def submit_model_candidate(self, snapshot: ModelSnapshot) -> dict[str, object]:
        return self._post_json(f"{self.model_url}/v1/model/promote", build_model_candidate_payload(snapshot), use_internal_token=True)

    def _post_json(self, url: str, payload: dict[str, object], *, use_internal_token: bool) -> dict[str, object]:
        headers = {"Content-Type": "application/json"}
        if use_internal_token:
            headers["x-cortex-internal-token"] = self.internal_token
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            raise CortexHTTPError(f"http_error:{exc.code}:{url}") from exc
        except URLError as exc:
            raise CortexHTTPError(f"url_error:{url}:{exc.reason}") from exc
