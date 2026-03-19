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
