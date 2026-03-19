package auth

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

// CAPClaims models Cortex Authentication Protocol claims.
type CAPClaims struct {
	Subject        string   `json:"sub"`
	Issuer         string   `json:"iss"`
	IssuedAt       int64    `json:"iat"`
	ExpiresAt      int64    `json:"exp"`
	JWTID          string   `json:"jti"`
	TrustScore     int      `json:"trust_score"`
	Scopes         []string `json:"scopes"`
	DeviceID       string   `json:"device_id"`
	SessionID      string   `json:"session_id"`
	DPoPThumbprint string   `json:"dpop_thumbprint"`
	PrincipalType  string   `json:"principal_type"`
	MFAVerified    bool     `json:"mfa_verified"`
}

func IssueCAPToken(claims CAPClaims, privateKey ed25519.PrivateKey) (string, error) {
	claims.IssuedAt = time.Now().Unix()
	claims.ExpiresAt = time.Now().Add(time.Hour).Unix()
	claims.JWTID = uuid.New().String()

	if claims.Subject == "" {
		return "", fmt.Errorf("subject is required")
	}
	if claims.TrustScore < 0 || claims.TrustScore > 100 {
		return "", fmt.Errorf("invalid trust score: %d", claims.TrustScore)
	}
	if claims.DPoPThumbprint == "" {
		return "", fmt.Errorf("DPoP thumbprint is required")
	}
	if claims.PrincipalType == "" {
		return "", fmt.Errorf("principal type is required")
	}

	payload, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}

	signature := ed25519.Sign(privateKey, payload)
	return encode(payload) + "." + encode(signature), nil
}

func ValidateCAPToken(token string, publicKey ed25519.PublicKey) (*CAPClaims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 2 {
		return nil, fmt.Errorf("invalid token format")
	}

	payload, err := decode(parts[0])
	if err != nil {
		return nil, fmt.Errorf("invalid payload encoding: %w", err)
	}
	signature, err := decode(parts[1])
	if err != nil {
		return nil, fmt.Errorf("invalid signature encoding: %w", err)
	}

	if !ed25519.Verify(publicKey, payload, signature) {
		return nil, fmt.Errorf("invalid signature")
	}

	var claims CAPClaims
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil, err
	}
	if claims.ExpiresAt < time.Now().Unix() {
		return nil, fmt.Errorf("token expired")
	}

	return &claims, nil
}

func encode(b []byte) string {
	return base64.RawURLEncoding.EncodeToString(b)
}

func decode(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(s)
}
