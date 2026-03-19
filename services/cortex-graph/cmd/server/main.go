package server

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"go.uber.org/zap"
)

var overview = map[string]any{
	"nodes": []map[string]any{
		{"id": "user:dev", "type": "User", "displayName": "Dev User"},
		{"id": "group:admins", "type": "Group", "displayName": "Admins"},
		{"id": "resource:neo4j", "type": "Resource", "displayName": "Neo4j Cluster"},
	},
	"edges": []map[string]any{
		{"source": "user:dev", "target": "group:admins", "type": "MEMBER_OF"},
		{"source": "group:admins", "target": "resource:neo4j", "type": "ACCESS"},
	},
}

// Run starts the graph API.
func Run() {
	logger, _ := zap.NewProduction()
	defer logger.Sync() //nolint:errcheck

	router := newRouter()

	logger.Info("starting cortex-graph", zap.String("addr", ":8080"))
	if err := http.ListenAndServe(":8080", router); err != nil {
		logger.Fatal("cortex-graph exited", zap.Error(err))
	}
}

func newRouter() http.Handler {
	router := chi.NewRouter()
	router.Get("/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "ok",
			"service": "cortex-graph",
		})
	})
	router.Get("/v1/graph/overview", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, overview)
	})
	router.Get("/v1/graph/entities/{entityID}", func(w http.ResponseWriter, r *http.Request) {
		entityID := chi.URLParam(r, "entityID")
		for _, node := range overview["nodes"].([]map[string]any) {
			if node["id"] == entityID {
				writeJSON(w, http.StatusOK, node)
				return
			}
		}
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "entity_not_found"})
	})
	router.Get("/v1/graph/search", func(w http.ResponseWriter, r *http.Request) {
		query := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("q")))
		if query == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query_required"})
			return
		}
		results := make([]map[string]any, 0)
		for _, node := range overview["nodes"].([]map[string]any) {
			id := strings.ToLower(node["id"].(string))
			name := strings.ToLower(node["displayName"].(string))
			if strings.Contains(id, query) || strings.Contains(name, query) {
				results = append(results, node)
			}
		}
		writeJSON(w, http.StatusOK, map[string]any{"results": results, "count": len(results)})
	})
	return router
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
