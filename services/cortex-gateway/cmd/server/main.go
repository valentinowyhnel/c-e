package server

import (
	"context"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	"github.com/cortexlabs/cortex-gateway/internal/authz"
	"github.com/cortexlabs/cortex-gateway/internal/httpapi"
	"go.uber.org/zap"
	"google.golang.org/grpc"
)

// Run starts the gateway HTTP and gRPC servers.
func Run() {
	logger, _ := zap.NewProduction()
	defer logger.Sync() //nolint:errcheck

	grpcListener, err := net.Listen("tcp", ":9001")
	if err != nil {
		logger.Fatal("failed to listen for grpc", zap.Error(err))
	}

	grpcServer := grpc.NewServer()
	authv3.RegisterAuthorizationServer(grpcServer, authz.NewHandler())
	httpHandler := httpapi.NewHandler()

	httpServer := &http.Server{
		Addr: ":8080",
		Handler:           httpHandler.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logger.Info("starting cortex-gateway grpc", zap.String("addr", ":9001"))
		if err := grpcServer.Serve(grpcListener); err != nil {
			logger.Fatal("grpc server failed", zap.Error(err))
		}
	}()

	go func() {
		logger.Info("starting cortex-gateway http", zap.String("addr", ":8080"))
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("http server failed", zap.Error(err))
		}
	}()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	<-ctx.Done()

	grpcServer.GracefulStop()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(shutdownCtx)
}
