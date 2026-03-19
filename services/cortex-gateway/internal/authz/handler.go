package authz

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"strings"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	typev3 "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	statuspb "google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc/codes"
)

type Handler struct{}

func NewHandler() *Handler {
	return &Handler{}
}

func (h *Handler) Check(_ context.Context, req *authv3.CheckRequest) (*authv3.CheckResponse, error) {
	headers := req.GetAttributes().GetRequest().GetHttp().GetHeaders()
	authHeader := headers["authorization"]
	if authHeader == "" {
		return deny("missing authorization header"), nil
	}
	if !strings.HasPrefix(authHeader, "Bearer ") {
		return deny("invalid authorization format"), nil
	}

	token := strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
	if token == "" {
		return deny("empty bearer token"), nil
	}
	if !isStructuredToken(token) {
		return deny("invalid token"), nil
	}

	return &authv3.CheckResponse{
		Status: &statuspb.Status{Code: int32(codes.OK)},
		HttpResponse: &authv3.CheckResponse_OkResponse{
			OkResponse: &authv3.OkHttpResponse{
				Headers: []*corev3.HeaderValueOption{
					header("x-cortex-user-id", "user:dev"),
					header("x-cortex-trust-score", "80"),
					header("x-cortex-scopes", "read:graph"),
					header("x-cortex-session-id", "session-dev"),
				},
			},
		},
	}, nil
}

func isStructuredToken(token string) bool {
	parts := strings.Split(token, ".")
	if len(parts) != 2 {
		return false
	}

	payload, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return false
	}

	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		return false
	}

	subject, ok := claims["sub"].(string)
	return ok && strings.TrimSpace(subject) != ""
}

func deny(reason string) *authv3.CheckResponse {
	return &authv3.CheckResponse{
		Status: &statuspb.Status{
			Code:    int32(codes.PermissionDenied),
			Message: reason,
		},
		HttpResponse: &authv3.CheckResponse_DeniedResponse{
			DeniedResponse: &authv3.DeniedHttpResponse{
				Status: &typev3.HttpStatus{Code: typev3.StatusCode_Forbidden},
				Body:   reason,
			},
		},
	}
}

func header(key, value string) *corev3.HeaderValueOption {
	return &corev3.HeaderValueOption{
		Header: &corev3.HeaderValue{
			Key:   key,
			Value: value,
		},
	}
}
