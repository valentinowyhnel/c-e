package server

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetEntityByID(t *testing.T) {
	router := newRouter()
	req := httptest.NewRequest(http.MethodGet, "/v1/graph/entities/user:dev", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
}

func TestSearchRequiresQuery(t *testing.T) {
	router := newRouter()
	req := httptest.NewRequest(http.MethodGet, "/v1/graph/search", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
}
