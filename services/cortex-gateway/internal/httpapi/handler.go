package httpapi

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type SentinelEvent struct {
	EventID               string             `json:"event_id"`
	MachineID             string             `json:"machine_id"`
	TenantID              string             `json:"tenant_id"`
	SessionLocalID        string             `json:"session_local_id"`
	EventType             string             `json:"event_type"`
	EventTime             string             `json:"event_time"`
	TraceID               string             `json:"trace_id"`
	PrivacyLevel          string             `json:"privacy_level"`
	ProcessLineageSummary string             `json:"process_lineage_summary"`
	FeatureVector         map[string]float64 `json:"feature_vector"`
	IntegrityFields       map[string]any     `json:"integrity_fields"`
	ConfidenceLocal       float64            `json:"confidence_local"`
}

type Handler struct {
	mu     sync.Mutex
	events []SentinelEvent
	logPath string
}

func NewHandler() *Handler {
	return &Handler{
		events:  make([]SentinelEvent, 0, 64),
		logPath: os.Getenv("CORTEX_GATEWAY_SENTINEL_EVENT_LOG"),
	}
}

func (h *Handler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", h.handleHealth)
	mux.HandleFunc("/v1/sentinel/events", h.handleSentinelEvents)
	return mux
}

func (h *Handler) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "cortex-gateway",
	})
}

func (h *Handler) handleSentinelEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method_not_allowed"})
		return
	}
	var event SentinelEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid_json"})
		return
	}
	if event.EventID == "" || event.MachineID == "" || event.TenantID == "" || event.EventType == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing_required_fields"})
		return
	}
	h.mu.Lock()
	h.events = append(h.events, event)
	depth := len(h.events)
	h.mu.Unlock()
	_ = h.appendAudit(event)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"accepted":        true,
		"event_id":        event.EventID,
		"machine_id":      event.MachineID,
		"received_at":     time.Now().UTC().Format(time.RFC3339),
		"queue_depth_hint": depth,
	})
}

func (h *Handler) appendAudit(event SentinelEvent) error {
	if h.logPath == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(h.logPath), 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(h.logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	defer f.Close()
	record := map[string]any{
		"event_type":   "sentinel_event_ingested",
		"recorded_at":  time.Now().UTC().Format(time.RFC3339),
		"event_id":     event.EventID,
		"machine_id":   event.MachineID,
		"tenant_id":    event.TenantID,
		"event_type_in": event.EventType,
		"trace_id":     event.TraceID,
	}
	return json.NewEncoder(f).Encode(record)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
