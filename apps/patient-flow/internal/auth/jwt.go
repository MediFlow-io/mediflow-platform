package auth

// Package auth verifies RS256 access tokens issued by the Django core API.
//
// Copied from apps/gateway/jwt.go (the gateway is a separate module). Keep the two in sync, or move
// both to a shared module when a third Go service needs it.
// Public keys come from Django's JWKS endpoint, so the gateway never holds a
// signing secret. Standard library only, to keep the gateway dependency-free.

import (
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

var ErrInvalidToken = errors.New("invalid token")

// Claims are the fields MediFlow services rely on. user_id is a string.
type Claims struct {
	UserID    string          `json:"user_id"`
	Role      string          `json:"role"`
	Name      string          `json:"name"`
	TokenType string          `json:"token_type"`
	Issuer    string          `json:"iss"`
	Audience  json.RawMessage `json:"aud"`
	ExpiresAt float64         `json:"exp"`
	NotBefore float64         `json:"nbf"`
}

type jwk struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	N   string `json:"n"`
	E   string `json:"e"`
}

type Verifier struct {
	jwksURL  string
	issuer   string
	audience string
	client   *http.Client
	now      func() time.Time

	mu        sync.RWMutex
	keys      map[string]*rsa.PublicKey
	fetchedAt time.Time
}

// NewVerifier fetches signing keys from jwksURL and checks iss/aud when they are non-empty.
func NewVerifier(jwksURL, issuer, audience string, client *http.Client) *Verifier {
	return &Verifier{jwksURL: jwksURL, issuer: issuer, audience: audience, client: client, now: time.Now}
}

// minRefetch stops a flood of tokens with unknown kids from hammering Django.
const minRefetch = time.Minute

func (v *Verifier) refreshKeys(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, v.jwksURL, nil)
	if err != nil {
		return err
	}
	resp, err := v.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("jwks: unexpected status %d", resp.StatusCode)
	}
	var set struct {
		Keys []jwk `json:"keys"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&set); err != nil {
		return fmt.Errorf("jwks: %w", err)
	}
	keys := make(map[string]*rsa.PublicKey, len(set.Keys))
	for _, k := range set.Keys {
		if k.Kty != "RSA" {
			continue
		}
		n, errN := base64.RawURLEncoding.DecodeString(k.N)
		e, errE := base64.RawURLEncoding.DecodeString(k.E)
		if errN != nil || errE != nil {
			continue
		}
		keys[k.Kid] = &rsa.PublicKey{N: new(big.Int).SetBytes(n), E: int(new(big.Int).SetBytes(e).Int64())}
	}
	if len(keys) == 0 {
		return errors.New("jwks: no usable RSA keys")
	}
	v.mu.Lock()
	v.keys, v.fetchedAt = keys, v.now()
	v.mu.Unlock()
	return nil
}

// candidateKeys returns the key matching kid, or every key when the token has no kid.
func (v *Verifier) candidateKeys(ctx context.Context, kid string) []*rsa.PublicKey {
	lookup := func() []*rsa.PublicKey {
		v.mu.RLock()
		defer v.mu.RUnlock()
		if kid != "" {
			if k, ok := v.keys[kid]; ok {
				return []*rsa.PublicKey{k}
			}
			return nil
		}
		all := make([]*rsa.PublicKey, 0, len(v.keys))
		for _, k := range v.keys {
			all = append(all, k)
		}
		return all
	}
	if keys := lookup(); len(keys) > 0 {
		return keys
	}
	v.mu.RLock()
	stale := v.now().Sub(v.fetchedAt) >= minRefetch || v.keys == nil
	v.mu.RUnlock()
	if stale {
		_ = v.refreshKeys(ctx) // a failed fetch leaves no candidates, so the token is rejected
	}
	return lookup()
}

// Verify checks signature, algorithm, expiry, issuer, audience and that it is an access token.
func (v *Verifier) Verify(ctx context.Context, token string) (*Claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, ErrInvalidToken
	}
	var header struct {
		Alg string `json:"alg"`
		Kid string `json:"kid"`
	}
	if err := decodeSegment(parts[0], &header); err != nil || header.Alg != "RS256" {
		return nil, ErrInvalidToken
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return nil, ErrInvalidToken
	}
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	verified := false
	for _, key := range v.candidateKeys(ctx, header.Kid) {
		if rsa.VerifyPKCS1v15(key, crypto.SHA256, digest[:], sig) == nil {
			verified = true
			break
		}
	}
	if !verified {
		return nil, ErrInvalidToken
	}

	var claims Claims
	if err := decodeSegment(parts[1], &claims); err != nil {
		return nil, ErrInvalidToken
	}
	now := float64(v.now().Unix())
	switch {
	case claims.TokenType != "access",
		claims.ExpiresAt == 0 || now >= claims.ExpiresAt,
		claims.NotBefore != 0 && now < claims.NotBefore,
		v.issuer != "" && claims.Issuer != v.issuer,
		v.audience != "" && !audienceContains(claims.Audience, v.audience):
		return nil, ErrInvalidToken
	}
	return &claims, nil
}

func decodeSegment(segment string, out any) error {
	raw, err := base64.RawURLEncoding.DecodeString(segment)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, out)
}

// audienceContains accepts aud as a single string or an array, per RFC 7519.
func audienceContains(raw json.RawMessage, want string) bool {
	var single string
	if json.Unmarshal(raw, &single) == nil {
		return single == want
	}
	var many []string
	if json.Unmarshal(raw, &many) == nil {
		for _, a := range many {
			if a == want {
				return true
			}
		}
	}
	return false
}
