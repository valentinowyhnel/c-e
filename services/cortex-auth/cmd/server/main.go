package server

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"net/http"

	"github.com/cortexlabs/cortex-auth/internal/api"
	"github.com/go-chi/chi/v5"
	"go.uber.org/zap"
)

// Run starts the cortex-auth HTTP API.
func Run() {
	logger, _ := zap.NewProduction()
	defer logger.Sync() //nolint:errcheck

	_, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		logger.Fatal("failed to generate dev signing key", zap.Error(err))
	}

	router := newRouter(api.NewHandler(privateKey))

	logger.Info("starting cortex-auth", zap.String("addr", ":8080"))
	if err := http.ListenAndServe(":8080", router); err != nil {
		logger.Fatal("cortex-auth exited", zap.Error(err))
	}
}

func newRouter(handler *api.Handler) http.Handler {
	router := chi.NewRouter()
	router.Get("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"service": "cortex-auth",
		})
	})
	router.Post("/v1/tokens/issue", handler.IssueToken)
	router.Post("/v1/tokens/validate", handler.ValidateToken)
	router.Get("/v1/sessions/summary", handler.SessionSummary)
	return router
}
