// Package events fans visit changes out to connected clients.
//
// Changes are published with PostgreSQL NOTIFY inside the writing transaction (internal/store), so
// they're delivered only after a successful commit, and to every patient-flow instance, not only the
// one that made the change.
package events

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Hub broadcasts raw JSON event payloads to subscribers.
type Hub struct {
	mu   sync.Mutex
	subs map[chan []byte]struct{}
}

func NewHub() *Hub { return &Hub{subs: map[chan []byte]struct{}{}} }

// Subscribe returns a channel of events and a function to stop receiving them.
func (h *Hub) Subscribe() (<-chan []byte, func()) {
	ch := make(chan []byte, 16)
	h.mu.Lock()
	h.subs[ch] = struct{}{}
	h.mu.Unlock()
	return ch, func() {
		h.mu.Lock()
		if _, ok := h.subs[ch]; ok {
			delete(h.subs, ch)
			close(ch)
		}
		h.mu.Unlock()
	}
}

// Publish sends to every subscriber. A client too slow to keep up misses events rather than
// blocking everyone; clients refetch on each event anyway, so a missed one isn't fatal.
func (h *Hub) Publish(payload []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for ch := range h.subs {
		select {
		case ch <- payload:
		default:
		}
	}
}

func (h *Hub) Subscribers() int {
	h.mu.Lock()
	defer h.mu.Unlock()
	return len(h.subs)
}

// Listen forwards PostgreSQL notifications on channel to the hub until ctx ends, reconnecting with
// backoff if the connection drops.
func Listen(ctx context.Context, pool *pgxpool.Pool, channel string, hub *Hub, log *slog.Logger) {
	backoff := time.Second
	for ctx.Err() == nil {
		err := listenOnce(ctx, pool, channel, hub)
		if ctx.Err() != nil {
			return
		}
		log.Warn("event listener stopped; reconnecting", "error", err, "retry_in", backoff.String())
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		if backoff < 30*time.Second {
			backoff *= 2
		}
	}
}

func listenOnce(ctx context.Context, pool *pgxpool.Pool, channel string, hub *Hub) error {
	conn, err := pool.Acquire(ctx)
	if err != nil {
		return err
	}
	defer conn.Release()
	if _, err := conn.Exec(ctx, "LISTEN "+channel); err != nil {
		return err
	}
	for {
		n, err := conn.Conn().WaitForNotification(ctx)
		if err != nil {
			return err
		}
		hub.Publish([]byte(n.Payload))
	}
}
