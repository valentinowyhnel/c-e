package main

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/nats-io/nats.go"
)

type criticalSignal struct {
	Topic     string                 `json:"topic"`
	Source    string                 `json:"source"`
	Type      string                 `json:"type"`
	Value     float64                `json:"value"`
	Labels    map[string]any         `json:"labels"`
	Severity  int                    `json:"severity"`
	Timestamp int64                  `json:"timestamp"`
}

func main() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = "nats://cortex-nats:4222"
	}

	nc, err := nats.Connect(natsURL)
	if err != nil {
		slog.Error("nats connect failed", "err", err)
		os.Exit(1)
	}
	defer nc.Close()

	js, err := nc.JetStream()
	if err != nil {
		slog.Error("jetstream init failed", "err", err)
		os.Exit(1)
	}

	http.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"status":"ok","service":"cortex-nats-bridge"}`))
	})

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "read body failed", http.StatusBadRequest)
			return
		}
		defer r.Body.Close()

		topic := pathToTopic(r.URL.Path)
		if _, err := js.Publish(topic, body); err != nil {
			http.Error(w, "publish failed", http.StatusBadGateway)
			return
		}

		for _, signal := range extractCriticalSignals(body, r.URL.Path) {
			data, _ := json.Marshal(signal)
			_, _ = js.Publish(signal.Topic, data)
		}

		w.WriteHeader(http.StatusOK)
	})

	slog.Info("nats bridge started", "port", "8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		slog.Error("http server failed", "err", err)
		os.Exit(1)
	}
}

func pathToTopic(path string) string {
	switch path {
	case "/v1/metrics":
		return "cortex.telemetry.metrics"
	case "/v1/traces":
		return "cortex.telemetry.traces"
	case "/v1/logs":
		return "cortex.telemetry.logs"
	default:
		return "cortex.telemetry.raw"
	}
}

func extractCriticalSignals(body []byte, path string) []criticalSignal {
	payload := strings.ToLower(string(body))
	signals := []criticalSignal{}
	now := time.Now().Unix()

	switch {
	case path == "/v1/metrics" && strings.Contains(payload, "latency"):
		signals = append(signals, criticalSignal{
			Topic:     "cortex.obs.anomalies",
			Source:    "otel-collector",
			Type:      "latency",
			Value:     900,
			Severity:  3,
			Timestamp: now,
			Labels:    map[string]any{"path": path},
		})
	case path == "/v1/logs" && strings.Contains(payload, "error"):
		signals = append(signals, criticalSignal{
			Topic:     "cortex.obs.patterns",
			Source:    "otel-collector",
			Type:      "error_rate",
			Value:     1,
			Severity:  2,
			Timestamp: now,
			Labels:    map[string]any{"path": path},
		})
	}

	return signals
}
