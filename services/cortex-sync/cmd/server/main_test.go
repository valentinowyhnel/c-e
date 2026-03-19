package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestQueueAndGetSyncJob(t *testing.T) {
	router := newRouter(newMemoryStore())

	req := httptest.NewRequest(http.MethodPost, "/v1/sync/full", bytes.NewReader([]byte(`{"source":"ad","dry_run":true}`)))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("queue status = %d body = %s", rec.Code, rec.Body.String())
	}

	var job map[string]any
	if err := json.NewDecoder(rec.Body).Decode(&job); err != nil {
		t.Fatal(err)
	}

	getReq := httptest.NewRequest(http.MethodGet, "/v1/sync/jobs/"+job["id"].(string), nil)
	getRec := httptest.NewRecorder()
	router.ServeHTTP(getRec, getReq)
	if getRec.Code != http.StatusOK {
		t.Fatalf("get status = %d body = %s", getRec.Code, getRec.Body.String())
	}
}

func TestSyncSummaryReflectsQueuedAndSuccessfulJobs(t *testing.T) {
	store := newMemoryStore()
	if err := store.Save(t.Context(), syncJob{
		ID:        "delta-1",
		Status:    "queued",
		Mode:      "delta",
		Source:    "ad",
		DryRun:    true,
		CreatedAt: 1710000000,
	}); err != nil {
		t.Fatal(err)
	}
	if err := store.Save(t.Context(), syncJob{
		ID:        "full-1",
		Status:    "success",
		Mode:      "full",
		Source:    "ad",
		DryRun:    false,
		CreatedAt: 1710000300,
	}); err != nil {
		t.Fatal(err)
	}

	router := newRouter(store)
	req := httptest.NewRequest(http.MethodGet, "/v1/sync/summary", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("summary status = %d body = %s", rec.Code, rec.Body.String())
	}

	var payload map[string]any
	if err := json.NewDecoder(rec.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if payload["delta_pending"].(float64) != 1 {
		t.Fatalf("delta_pending = %v", payload["delta_pending"])
	}
	if payload["queued_jobs"].(float64) != 1 {
		t.Fatalf("queued_jobs = %v", payload["queued_jobs"])
	}
	if payload["last_success"] == "" {
		t.Fatal("expected last_success to be populated")
	}
}
