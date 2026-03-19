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
