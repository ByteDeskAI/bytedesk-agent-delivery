package desiredstate

import (
	"encoding/json"
	"errors"
	"sync"
	"testing"
)

func mustPayload(t *testing.T, v any) json.RawMessage {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestInitialCreationRequiresAbsent(t *testing.T) {
	store := NewStore()
	payload := mustPayload(t, map[string]any{"activeRelease": "v1"})

	if _, err := store.CompareAndSwap("consumer-1", "target-1", Precondition{Kind: "match", Revision: 1, Digest: "sha256:" + "a"}, payload); !errors.Is(err, ErrPreconditionFailed) {
		t.Fatalf("expected precondition failure creating with match, got %v", err)
	}

	record, err := store.CompareAndSwap("consumer-1", "target-1", Precondition{Kind: "absent"}, payload)
	if err != nil {
		t.Fatalf("expected absent creation to succeed: %v", err)
	}
	if record.Revision != 1 {
		t.Fatalf("expected first revision to be 1, got %d", record.Revision)
	}

	if _, err := store.CompareAndSwap("consumer-1", "target-1", Precondition{Kind: "absent"}, payload); !errors.Is(err, ErrPreconditionFailed) {
		t.Fatalf("expected second absent creation to fail, got %v", err)
	}
}

func TestUpdateRequiresExactPriorRevisionAndDigest(t *testing.T) {
	store := NewStore()
	first, err := store.CompareAndSwap("c", "t", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 1}))
	if err != nil {
		t.Fatal(err)
	}

	// Wrong revision.
	_, err = store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: 99, Digest: first.Digest}, mustPayload(t, map[string]any{"v": 2}))
	if !errors.Is(err, ErrPreconditionFailed) {
		t.Fatalf("expected failure for wrong revision, got %v", err)
	}

	// Wrong digest.
	_, err = store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: first.Revision, Digest: "sha256:" + "0000000000000000000000000000000000000000000000000000000000000000"[:64]}, mustPayload(t, map[string]any{"v": 2}))
	if !errors.Is(err, ErrPreconditionFailed) {
		t.Fatalf("expected failure for wrong digest, got %v", err)
	}

	// Exact match succeeds.
	second, err := store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: first.Revision, Digest: first.Digest}, mustPayload(t, map[string]any{"v": 2}))
	if err != nil {
		t.Fatalf("expected exact-match update to succeed: %v", err)
	}
	if second.Revision != first.Revision+1 {
		t.Fatalf("expected revision to advance by exactly one, got %d -> %d", first.Revision, second.Revision)
	}
}

func TestABAIsRejected(t *testing.T) {
	store := NewStore()
	v1, err := store.CompareAndSwap("c", "t", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 1}))
	if err != nil {
		t.Fatal(err)
	}
	v2, err := store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: v1.Revision, Digest: v1.Digest}, mustPayload(t, map[string]any{"v": 2}))
	if err != nil {
		t.Fatal(err)
	}
	// Revert content back to the v1 payload under a legitimate match on v2.
	v3, err := store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: v2.Revision, Digest: v2.Digest}, mustPayload(t, map[string]any{"v": 1}))
	if err != nil {
		t.Fatal(err)
	}
	// A caller still holding the original v1 (revision 1) precondition must
	// be rejected even though the payload now matches v1's content again -
	// revision is authoritative, not payload equality (classic ABA).
	if _, err := store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: v1.Revision, Digest: v1.Digest}, mustPayload(t, map[string]any{"v": 4})); !errors.Is(err, ErrPreconditionFailed) {
		t.Fatalf("expected stale v1 precondition to fail after v3, got %v", err)
	}
	if v3.Revision != 3 {
		t.Fatalf("expected revision 3, got %d", v3.Revision)
	}
}

func TestWildcardAndDigestOnlyPreconditionsAreRejectedWithoutSideEffects(t *testing.T) {
	store := NewStore()
	cases := []Precondition{
		{Kind: "match", Digest: "sha256:abc"}, // digest-only, no revision
		{Kind: "match", Revision: 1},          // revision-only, no digest
		{Kind: "lease"},                       // unknown kind
		{Kind: ""},                            // wildcard/empty
		{Kind: "absent", Revision: 1},         // absent must not carry extra fields
	}
	for _, precondition := range cases {
		if _, err := store.CompareAndSwap("c", "t", precondition, mustPayload(t, map[string]any{"v": 1})); !errors.Is(err, ErrPreconditionInvalid) {
			t.Fatalf("precondition %+v: expected ErrPreconditionInvalid, got %v", precondition, err)
		}
	}
	if _, ok := store.Read("c", "t"); ok {
		t.Fatal("expected no state to have been created by invalid preconditions")
	}
}

func TestConcurrentWritersOnlyOneSucceedsPerRevision(t *testing.T) {
	store := NewStore()
	base, err := store.CompareAndSwap("c", "t", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 0}))
	if err != nil {
		t.Fatal(err)
	}

	const writers = 32
	var wg sync.WaitGroup
	successes := make([]bool, writers)
	for i := 0; i < writers; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			_, err := store.CompareAndSwap("c", "t", Precondition{Kind: "match", Revision: base.Revision, Digest: base.Digest}, mustPayload(t, map[string]any{"v": i}))
			successes[i] = err == nil
		}(i)
	}
	wg.Wait()

	successCount := 0
	for _, ok := range successes {
		if ok {
			successCount++
		}
	}
	if successCount != 1 {
		t.Fatalf("expected exactly one concurrent writer to succeed against the same revision, got %d", successCount)
	}

	final, ok := store.Read("c", "t")
	if !ok {
		t.Fatal("expected a record to exist")
	}
	if final.Revision != base.Revision+1 {
		t.Fatalf("expected exactly one revision advance, got %d -> %d", base.Revision, final.Revision)
	}
}

func TestUnrelatedTargetsDoNotInterfere(t *testing.T) {
	store := NewStore()
	if _, err := store.CompareAndSwap("c1", "t1", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 1})); err != nil {
		t.Fatal(err)
	}
	if _, err := store.CompareAndSwap("c2", "t1", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 1})); err != nil {
		t.Fatal(err)
	}
	if _, err := store.CompareAndSwap("c1", "t2", Precondition{Kind: "absent"}, mustPayload(t, map[string]any{"v": 1})); err != nil {
		t.Fatal(err)
	}
}

func TestKeyOrderInPayloadDoesNotChangeTheDigest(t *testing.T) {
	store := NewStore()
	first, err := store.CompareAndSwap("c", "t", Precondition{Kind: "absent"}, json.RawMessage(`{"a":1,"b":2}`))
	if err != nil {
		t.Fatal(err)
	}

	store2 := NewStore()
	second, err := store2.CompareAndSwap("c", "t", Precondition{Kind: "absent"}, json.RawMessage(`{"b":2,"a":1}`))
	if err != nil {
		t.Fatal(err)
	}
	if first.Digest != second.Digest {
		t.Fatalf("expected key-order-independent digest, got %s vs %s", first.Digest, second.Digest)
	}
}
