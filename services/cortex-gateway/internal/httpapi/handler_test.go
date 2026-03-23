package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestHealth(t *testing.T) {
	handler := NewHandler().Routes()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
}

func TestSentinelEventsAccepted(t *testing.T) {
	handler := NewHandler().Routes()
	body, _ := json.Marshal(map[string]any{
		"event_id": "evt-1",
		"machine_id": "machine-1",
		"tenant_id": "tenant-1",
		"event_type": "process_network_auth_combo",
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/sentinel/events", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", rec.Code)
	}
}

func TestSentinelEventsRejectMissingFields(t *testing.T) {
	handler := NewHandler().Routes()
	body := []byte(`{"event_id":"evt-1"}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/sentinel/events", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestSentinelEventsPersistAuditLog(t *testing.T) {
	root := filepath.Join(".", ".test-artifacts")
	if err := os.MkdirAll(root, 0o755); err != nil {
		t.Fatalf("mkdir failed: %v", err)
	}
	logPath := filepath.Join(root, "gateway-sentinel-events.jsonl")
	_ = os.Remove(logPath)
	t.Setenv("CORTEX_GATEWAY_SENTINEL_EVENT_LOG", logPath)

	handler := NewHandler().Routes()
	body, _ := json.Marshal(map[string]any{
		"event_id": "evt-2",
		"machine_id": "machine-2",
		"tenant_id": "tenant-2",
		"event_type": "windows_process_snapshot",
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/sentinel/events", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	data, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatalf("expected log file: %v", err)
	}
	if len(data) == 0 {
		t.Fatal("expected audit content")
	}
}

func TestMetaDecisionEventsAccepted(t *testing.T) {
	handler := NewHandler().Routes()
	body := []byte(`{
		"event_id":"mda-1",
		"entity_id":"machine-1",
		"entity_type":"machine",
		"trusted_output":{
			"weighted_scores":{"aggregate_risk":0.82},
			"agent_trust_scores":{"decision":0.63},
			"conflict_score":0.58,
			"selected_agents":["decision"],
			"deep_analysis_triggered":true,
			"reasoning_summary":"high conflict"
		},
		"deep_analysis_requests":[
			{"event_id":"mda-1","entity_id":"machine-1","agent_id":"decision","reasons":["agent_conflict"],"deadline_ms":150}
		],
		"degraded_mode":false,
		"timestamp":"2026-03-23T10:00:00Z"
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/meta-decision/events", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", rec.Code)
	}
}

func TestMetaDecisionEventsRejectMissingFields(t *testing.T) {
	handler := NewHandler().Routes()
	req := httptest.NewRequest(http.MethodPost, "/v1/meta-decision/events", bytes.NewReader([]byte(`{"event_id":"mda-2"}`)))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestMetaDecisionEventsPersistAuditLog(t *testing.T) {
	root := filepath.Join(".", ".test-artifacts")
	if err := os.MkdirAll(root, 0o755); err != nil {
		t.Fatalf("mkdir failed: %v", err)
	}
	logPath := filepath.Join(root, "gateway-meta-decision-events.jsonl")
	_ = os.Remove(logPath)
	t.Setenv("CORTEX_GATEWAY_SENTINEL_EVENT_LOG", logPath)

	handler := NewHandler().Routes()
	body := []byte(`{
		"event_id":"mda-3",
		"entity_id":"machine-3",
		"entity_type":"machine",
		"trusted_output":{
			"weighted_scores":{"aggregate_risk":0.91},
			"agent_trust_scores":{"decision":0.61},
			"conflict_score":0.66,
			"selected_agents":["decision","remediation"],
			"deep_analysis_triggered":true,
			"reasoning_summary":"critical asset"
		},
		"deep_analysis_requests":[
			{"event_id":"mda-3","entity_id":"machine-3","agent_id":"decision","reasons":["critical_asset"],"deadline_ms":150}
		],
		"degraded_mode":false,
		"timestamp":"2026-03-23T11:00:00Z"
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/meta-decision/events", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	data, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatalf("expected log file: %v", err)
	}
	if !bytes.Contains(data, []byte("meta_decision_event_ingested")) {
		t.Fatal("expected meta decision audit content")
	}
}
