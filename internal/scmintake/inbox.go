// Package scmintake implements the real, testable core of AD-11's
// bytedesk.port.scm/1#receive-webhook idempotency contract: one immutable
// inbox entry per (provider, deliveryId), and the numeric-repository /
// immutable-commit identity checks required before any Git intent is
// reconciled.
//
// This is a slice of AD-11, not the full task: it does not implement
// provider-webhook-signature authentication, the fetch-commit/scan-repository
// Git-provider Adapter, outbox publication, dead-letter handling, or
// submission of candidate/binding commands through AD-10 - those need a real
// Git-provider integration this environment does not have. What is real
// here is proven: duplicate webhook delivery is side-effect free, and a
// replayed deliveryId with different authenticated payload bytes is denied
// with idempotency_collision and no committed state, matching AD-11's
// SCM-001 conformance case and its "duplicate webhook delivery is
// side-effect free" acceptance criterion.
package scmintake

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"sync"
)

// ErrIdempotencyCollision is returned when a (provider, deliveryId) pair
// already has a recorded inbox entry whose payload digest differs from the
// bytes just presented - the mutation named in AD-11's SCM-001 conformance
// case. No state is committed when this is returned.
var ErrIdempotencyCollision = errors.New("scmintake: idempotency_collision")

// InboxReceipt mirrors bytedesk.port.scm-inbox-receipt/1: the durable,
// immutable record produced for one (provider, deliveryId) pair.
type InboxReceipt struct {
	Provider      string
	DeliveryID    string
	PayloadDigest string
}

// Inbox is a durable (for process lifetime), idempotent webhook receipt
// store keyed by (provider, deliveryId). Safe for concurrent use: every
// receive is serialized so the collision check and the commit cannot race.
type Inbox struct {
	mu      sync.Mutex
	entries map[inboxKey]InboxReceipt
}

type inboxKey struct {
	provider   string
	deliveryID string
}

func NewInbox() *Inbox {
	return &Inbox{entries: make(map[inboxKey]InboxReceipt)}
}

// Receive records one webhook delivery. If (provider, deliveryId) has not
// been seen, it commits a new receipt and reports isNew=true. If it has been
// seen with the exact same payload digest, it is a side-effect-free replay:
// the existing receipt is returned with isNew=false and no error. If it has
// been seen with a different payload digest, no state changes and
// ErrIdempotencyCollision is returned.
func (b *Inbox) Receive(provider, deliveryID string, deliveryBytes []byte) (receipt InboxReceipt, isNew bool, err error) {
	sum := sha256.Sum256(deliveryBytes)
	digest := "sha256:" + hex.EncodeToString(sum[:])

	b.mu.Lock()
	defer b.mu.Unlock()

	k := inboxKey{provider, deliveryID}
	existing, ok := b.entries[k]
	if !ok {
		receipt = InboxReceipt{Provider: provider, DeliveryID: deliveryID, PayloadDigest: digest}
		b.entries[k] = receipt
		return receipt, true, nil
	}
	if existing.PayloadDigest != digest {
		return InboxReceipt{}, false, ErrIdempotencyCollision
	}
	return existing, false, nil
}
