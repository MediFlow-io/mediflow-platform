package events

import "testing"

func TestHubBroadcastsAndUnsubscribes(t *testing.T) {
	h := NewHub()
	a, stopA := h.Subscribe()
	b, stopB := h.Subscribe()
	h.Publish([]byte(`{"visitId":1}`))
	if string(<-a) != `{"visitId":1}` || string(<-b) != `{"visitId":1}` {
		t.Fatal("both subscribers should receive the event")
	}
	stopA()
	stopA() // idempotent
	if h.Subscribers() != 1 {
		t.Fatalf("want 1 subscriber, got %d", h.Subscribers())
	}
	if _, open := <-a; open {
		t.Fatal("unsubscribed channel should be closed")
	}
	stopB()
}

func TestSlowSubscriberDoesNotBlockPublish(t *testing.T) {
	h := NewHub()
	_, stop := h.Subscribe()
	defer stop()
	for i := 0; i < 100; i++ { // buffer is 16; publish must never block
		h.Publish([]byte("x"))
	}
}
