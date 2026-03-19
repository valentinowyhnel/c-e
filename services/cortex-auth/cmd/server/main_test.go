package server

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/cortexlabs/cortex-auth/internal/api"
)

func TestIssueAndValidateToken(t *testing.T) {
	_, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	router := newRouter(api.NewHandler(privateKey))

	issueBody := []byte(`{"subject":"user:dev","trust_score":90,"scopes":["read:graph"],"device_id":"dev-1","session_id":"sess-1","dpop_thumbprint":"thumb-1","principal_type":"human","mfa_verified":true}`)
	issueReq := httptest.NewRequest(http.MethodPost, "/v1/tokens/issue", bytes.NewReader(issueBody))
	issueRec := httptest.NewRecorder()
	router.ServeHTTP(issueRec, issueReq)
	if issueRec.Code != http.StatusOK {
		t.Fatalf("issue status = %d body = %s", issueRec.Code, issueRec.Body.String())
	}

	var issueResp map[string]string
	if err := json.NewDecoder(issueRec.Body).Decode(&issueResp); err != nil {
		t.Fatal(err)
	}

	validateBody := []byte(`{"token":"` + issueResp["token"] + `"}`)
	validateReq := httptest.NewRequest(http.MethodPost, "/v1/tokens/validate", bytes.NewReader(validateBody))
	validateRec := httptest.NewRecorder()
	router.ServeHTTP(validateRec, validateReq)
	if validateRec.Code != http.StatusOK {
		t.Fatalf("validate status = %d body = %s", validateRec.Code, validateRec.Body.String())
	}
}

func TestIssueTokenRejectsInvalidPrincipalType(t *testing.T) {
	_, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	router := newRouter(api.NewHandler(privateKey))

	body := []byte(`{"subject":"user:dev","trust_score":90,"scopes":["read:graph"],"device_id":"dev-1","session_id":"sess-1","dpop_thumbprint":"thumb-1","principal_type":"robot","mfa_verified":true}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/tokens/issue", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
}
