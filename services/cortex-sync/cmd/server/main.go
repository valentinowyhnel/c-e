package server

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.uber.org/zap"
)

type syncRequest struct {
	Source string `json:"source"`
	DryRun bool   `json:"dry_run"`
}

type syncJob struct {
	ID        string  `json:"id"`
	Status    string  `json:"status"`
	Mode      string  `json:"mode"`
	Source    string  `json:"source"`
	DryRun    bool    `json:"dry_run"`
	CreatedAt float64 `json:"created_at"`
}

type store interface {
	Save(context.Context, syncJob) error
	Get(context.Context, string) (syncJob, bool, error)
}

type memoryStore struct {
	mu   sync.RWMutex
	jobs map[string]syncJob
}

func (m *memoryStore) Save(_ context.Context, job syncJob) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.jobs[job.ID] = job
	return nil
}

func (m *memoryStore) Get(_ context.Context, id string) (syncJob, bool, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	job, ok := m.jobs[id]
	return job, ok, nil
}

type postgresStore struct {
	pool *pgxpool.Pool
}

func newPostgresStore(ctx context.Context, databaseURL string) (*postgresStore, error) {
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, err
	}
	_, err = pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS sync_jobs (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			mode TEXT NOT NULL,
			source TEXT NOT NULL,
			dry_run BOOLEAN NOT NULL,
			created_at DOUBLE PRECISION NOT NULL
		)
	`)
	if err != nil {
		pool.Close()
		return nil, err
	}
	return &postgresStore{pool: pool}, nil
}

func (p *postgresStore) Save(ctx context.Context, job syncJob) error {
	_, err := p.pool.Exec(ctx, `
		INSERT INTO sync_jobs (id, status, mode, source, dry_run, created_at)
		VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (id) DO UPDATE SET
			status = EXCLUDED.status,
			source = EXCLUDED.source,
			dry_run = EXCLUDED.dry_run
	`, job.ID, job.Status, job.Mode, job.Source, job.DryRun, job.CreatedAt)
	return err
}

func (p *postgresStore) Get(ctx context.Context, id string) (syncJob, bool, error) {
	row := p.pool.QueryRow(ctx, `SELECT id, status, mode, source, dry_run, created_at FROM sync_jobs WHERE id = $1`, id)
	var job syncJob
	if err := row.Scan(&job.ID, &job.Status, &job.Mode, &job.Source, &job.DryRun, &job.CreatedAt); err != nil {
		return syncJob{}, false, nil
	}
	return job, true, nil
}

// Run starts the cortex-sync HTTP service.
func Run() {
	logger, _ := zap.NewProduction()
	defer logger.Sync() //nolint:errcheck

	ctx := context.Background()
	var serviceStore store = newMemoryStore()
	if databaseURL := os.Getenv("DATABASE_URL"); databaseURL != "" {
		postgres, err := newPostgresStore(ctx, databaseURL)
		if err != nil {
			logger.Fatal("failed to init postgres store", zap.Error(err))
		}
		serviceStore = postgres
	}

	router := newRouter(serviceStore)

	logger.Info("starting cortex-sync", zap.String("addr", ":8080"))
	if err := http.ListenAndServe(":8080", router); err != nil {
		logger.Fatal("cortex-sync exited", zap.Error(err))
	}
}

func newMemoryStore() *memoryStore {
	return &memoryStore{jobs: map[string]syncJob{}}
}

func newRouter(serviceStore store) http.Handler {
	router := chi.NewRouter()
	router.Get("/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "cortex-sync"})
	})
	router.Post("/v1/sync/full", queueSync(serviceStore, "full"))
	router.Post("/v1/sync/delta", queueSync(serviceStore, "delta"))
	router.Get("/v1/sync/jobs/{jobID}", getJob(serviceStore))
	return router
}

func queueSync(serviceStore store, mode string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req syncRequest
		_ = json.NewDecoder(r.Body).Decode(&req)
		if req.Source == "" {
			req.Source = "ad"
		}

		job := syncJob{
			ID:        mode + "-" + time.Now().Format("20060102150405.000000000"),
			Status:    "queued",
			Mode:      mode,
			Source:    req.Source,
			DryRun:    req.DryRun,
			CreatedAt: float64(time.Now().Unix()),
		}

		if err := serviceStore.Save(r.Context(), job); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "sync_store_failed"})
			return
		}

		writeJSON(w, http.StatusAccepted, job)
	}
}

func getJob(serviceStore store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		jobID := chi.URLParam(r, "jobID")
		job, ok, err := serviceStore.Get(r.Context(), jobID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "sync_store_failed"})
			return
		}
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "job_not_found"})
			return
		}
		writeJSON(w, http.StatusOK, job)
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
