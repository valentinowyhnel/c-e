package httpapi

import (
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	metadecisionv1 "github.com/cortexlabs/proto/meta_decision/v1"
	"google.golang.org/protobuf/encoding/protojson"
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
	mu                 sync.Mutex
	events             []SentinelEvent
	metaDecisionEvents []*metadecisionv1.MetaDecisionEvent
	logPath            string
}

func NewHandler() *Handler {
	return &Handler{
		events:             make([]SentinelEvent, 0, 64),
		metaDecisionEvents: make([]*metadecisionv1.MetaDecisionEvent, 0, 32),
		logPath:            os.Getenv("CORTEX_GATEWAY_SENTINEL_EVENT_LOG"),
	}
}

func (h *Handler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", h.handleHealth)
	mux.HandleFunc("/v1/sentinel/events", h.handleSentinelEvents)
	mux.HandleFunc("/v1/meta-decision/events", h.handleMetaDecisionEvents)
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

func (h *Handler) handleMetaDecisionEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method_not_allowed"})
		return
	}
	body, err := readRequestBody(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid_json"})
		return
	}
	var event metadecisionv1.MetaDecisionEvent
	if err := protojson.Unmarshal(body, &event); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid_meta_decision_event"})
		return
	}
	if event.GetEventId() == "" || event.GetEntityId() == "" || event.GetEntityType() == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing_required_fields"})
		return
	}
	h.mu.Lock()
	h.metaDecisionEvents = append(h.metaDecisionEvents, &event)
	depth := len(h.metaDecisionEvents)
	h.mu.Unlock()
	_ = h.appendMetaDecisionAudit(&event)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"accepted":         true,
		"event_id":         event.GetEventId(),
		"entity_id":        event.GetEntityId(),
		"received_at":      time.Now().UTC().Format(time.RFC3339),
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

func (h *Handler) appendMetaDecisionAudit(event *metadecisionv1.MetaDecisionEvent) error {
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
	trustedOutput := event.GetTrustedOutput()
	deepAnalysisTriggered := false
	selectedAgents := []string{}
	if trustedOutput != nil {
		deepAnalysisTriggered = trustedOutput.GetDeepAnalysisTriggered()
		selectedAgents = trustedOutput.GetSelectedAgents()
	}
	record := map[string]any{
		"event_type":                  "meta_decision_event_ingested",
		"recorded_at":                 time.Now().UTC().Format(time.RFC3339),
		"meta_decision_event_id":      event.GetEventId(),
		"entity_id":                   event.GetEntityId(),
		"entity_type":                 event.GetEntityType(),
		"deep_analysis_triggered":     deepAnalysisTriggered,
		"selected_agents":             selectedAgents,
		"deep_analysis_request_count": len(event.GetDeepAnalysisRequests()),
	}
	return json.NewEncoder(f).Encode(record)
}

func readRequestBody(r *http.Request) ([]byte, error) {
	defer r.Body.Close()
	return io.ReadAll(r.Body)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
