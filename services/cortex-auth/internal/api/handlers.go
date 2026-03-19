package api

import (
	"crypto/ed25519"
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/cortexlabs/cortex-auth/internal/auth"
)

type Handler struct {
	privateKey ed25519.PrivateKey
	publicKey  ed25519.PublicKey
	mu         sync.RWMutex
	sessions   map[string]sessionRecord
}

type issueTokenRequest struct {
	Subject        string   `json:"subject"`
	TrustScore     int      `json:"trust_score"`
	Scopes         []string `json:"scopes"`
	DeviceID       string   `json:"device_id"`
	SessionID      string   `json:"session_id"`
	DPoPThumbprint string   `json:"dpop_thumbprint"`
	PrincipalType  string   `json:"principal_type"`
	MFAVerified    bool     `json:"mfa_verified"`
}

type validateTokenRequest struct {
	Token string `json:"token"`
}

type errorResponse struct {
	Error string `json:"error"`
}

type sessionRecord struct {
	Subject       string
	TrustScore    int
	DeviceID      string
	SessionID     string
	PrincipalType string
	MFAVerified   bool
	UpdatedAt     int64
}

func NewHandler(privateKey ed25519.PrivateKey) *Handler {
	return &Handler{
		privateKey: privateKey,
		publicKey:  privateKey.Public().(ed25519.PublicKey),
		sessions:   map[string]sessionRecord{},
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, errorResponse{Error: message})
}

func (h *Handler) IssueToken(w http.ResponseWriter, r *http.Request) {
	var req issueTokenRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json")
		return
	}
	if strings.TrimSpace(req.Subject) == "" {
		writeError(w, http.StatusBadRequest, "subject_required")
		return
	}
	if strings.TrimSpace(req.SessionID) == "" {
		writeError(w, http.StatusBadRequest, "session_id_required")
		return
	}
	if strings.TrimSpace(req.DeviceID) == "" {
		writeError(w, http.StatusBadRequest, "device_id_required")
		return
	}
	if strings.TrimSpace(req.DPoPThumbprint) == "" {
		writeError(w, http.StatusBadRequest, "dpop_thumbprint_required")
		return
	}
	if req.PrincipalType != "human" && req.PrincipalType != "workload" && req.PrincipalType != "agent" {
		writeError(w, http.StatusBadRequest, "invalid_principal_type")
		return
	}

	token, err := auth.IssueCAPToken(auth.CAPClaims{
		Subject:        req.Subject,
		Issuer:         "cortex-auth",
		TrustScore:     req.TrustScore,
		Scopes:         req.Scopes,
		DeviceID:       req.DeviceID,
		SessionID:      req.SessionID,
		DPoPThumbprint: req.DPoPThumbprint,
		PrincipalType:  req.PrincipalType,
		MFAVerified:    req.MFAVerified,
	}, h.privateKey)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.recordSession(req)
	writeJSON(w, http.StatusOK, map[string]string{"token": token})
}

func (h *Handler) ValidateToken(w http.ResponseWriter, r *http.Request) {
	var req validateTokenRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json")
		return
	}
	if strings.TrimSpace(req.Token) == "" {
		writeError(w, http.StatusBadRequest, "token_required")
		return
	}

	claims, err := auth.ValidateCAPToken(req.Token, h.publicKey)
	if err != nil {
		writeError(w, http.StatusUnauthorized, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, claims)
}

func (h *Handler) recordSession(req issueTokenRequest) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.sessions[req.SessionID] = sessionRecord{
		Subject:       req.Subject,
		TrustScore:    req.TrustScore,
		DeviceID:      req.DeviceID,
		SessionID:     req.SessionID,
		PrincipalType: req.PrincipalType,
		MFAVerified:   req.MFAVerified,
		UpdatedAt:     time.Now().Unix(),
	}
}

func (h *Handler) SessionSummary(w http.ResponseWriter, _ *http.Request) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	uniqueUsers := map[string]struct{}{}
	uniqueDevices := map[string]struct{}{}
	usersLowTrust := map[string]struct{}{}
	humanSessions := 0
	workloadSessions := 0

	for _, session := range h.sessions {
		if session.Subject != "" {
			uniqueUsers[session.Subject] = struct{}{}
		}
		if session.DeviceID != "" {
			uniqueDevices[session.DeviceID] = struct{}{}
		}
		if session.TrustScore < 40 && session.Subject != "" {
			usersLowTrust[session.Subject] = struct{}{}
		}
		switch session.PrincipalType {
		case "human":
			humanSessions++
		case "workload", "agent":
			workloadSessions++
		}
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"active_sessions":   len(h.sessions),
		"users_low_trust":   len(usersLowTrust),
		"unique_users":      len(uniqueUsers),
		"unique_devices":    len(uniqueDevices),
		"human_sessions":    humanSessions,
		"workload_sessions": workloadSessions,
	})
}
