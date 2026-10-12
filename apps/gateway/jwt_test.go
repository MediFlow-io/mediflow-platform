package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

var testKey, _ = rsa.GenerateKey(rand.Reader, 2048)

func b64(data []byte) string { return base64.RawURLEncoding.EncodeToString(data) }

func sign(t *testing.T, key *rsa.PrivateKey, header, claims map[string]any) string {
	t.Helper()
	h, _ := json.Marshal(header)
	c, _ := json.Marshal(claims)
	input := b64(h) + "." + b64(c)
	digest := sha256.Sum256([]byte(input))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	return input + "." + b64(sig)
}

func validClaims() map[string]any {
	return map[string]any{
		"user_id": "7", "role": "doctor", "token_type": "access",
		"iss": "mediflow-core", "aud": "mediflow",
		"exp": time.Now().Add(5 * time.Minute).Unix(),
	}
}

func jwksServer(t *testing.T, key *rsa.PublicKey) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{"keys": []map[string]string{{
			"kty": "RSA", "kid": "k1", "alg": "RS256",
			"n": b64(key.N.Bytes()), "e": b64(big.NewInt(int64(key.E)).Bytes()),
		}}})
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newTestVerifier(t *testing.T) *verifier {
	srv := jwksServer(t, &testKey.PublicKey)
	return newVerifier(srv.URL, "mediflow-core", "mediflow", srv.Client())
}

func TestVerifyAcceptsValidToken(t *testing.T) {
	v := newTestVerifier(t)
	token := sign(t, testKey, map[string]any{"alg": "RS256", "typ": "JWT"}, validClaims())
	claims, err := v.Verify(context.Background(), token)
	if err != nil {
		t.Fatalf("expected valid token, got %v", err)
	}
	if claims.UserID != "7" || claims.Role != "doctor" {
		t.Fatalf("unexpected claims: %+v", claims)
	}
}

func TestVerifyRejectsBadTokens(t *testing.T) {
	v := newTestVerifier(t)
	otherKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	rs256 := map[string]any{"alg": "RS256"}
	with := func(key string, value any) map[string]any {
		c := validClaims()
		c[key] = value
		return c
	}
	cases := map[string]string{
		"wrong signer":  sign(t, otherKey, rs256, validClaims()),
		"expired":       sign(t, testKey, rs256, with("exp", time.Now().Add(-time.Minute).Unix())),
		"refresh token": sign(t, testKey, rs256, with("token_type", "refresh")),
		"wrong issuer":  sign(t, testKey, rs256, with("iss", "someone-else")),
		"wrong aud":     sign(t, testKey, rs256, with("aud", []string{"other"})),
		"alg none":      sign(t, testKey, map[string]any{"alg": "none"}, validClaims()),
		"unknown kid":   sign(t, testKey, map[string]any{"alg": "RS256", "kid": "nope"}, validClaims()),
		"garbage":       "not.a.jwt",
	}
	for name, token := range cases {
		if _, err := v.Verify(context.Background(), token); err == nil {
			t.Errorf("%s: expected rejection", name)
		}
	}
}

func TestRequireAuthEnforcesTokenAndRole(t *testing.T) {
	v := newTestVerifier(t)
	ok := func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) }
	adminOnly := requireAuth(v, []string{"admin"}, ok)
	anyUser := requireAuth(v, nil, ok)
	doctor := sign(t, testKey, map[string]any{"alg": "RS256"}, validClaims())

	cases := []struct {
		name    string
		handler http.HandlerFunc
		auth    string
		want    int
	}{
		{"no token", anyUser, "", http.StatusUnauthorized},
		{"valid token", anyUser, "Bearer " + doctor, http.StatusOK},
		{"wrong role", adminOnly, "Bearer " + doctor, http.StatusForbidden},
		{"not bearer", anyUser, "Basic " + doctor, http.StatusUnauthorized},
	}
	for _, tc := range cases {
		req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader("{}"))
		if tc.auth != "" {
			req.Header.Set("Authorization", tc.auth)
		}
		rec := httptest.NewRecorder()
		tc.handler(rec, req)
		if rec.Code != tc.want {
			t.Errorf("%s: got %d, want %d", tc.name, rec.Code, tc.want)
		}
	}
}
