package scmintake

import (
	"errors"
	"sync"
	"testing"
)

func TestNewDeliveryCommits(t *testing.T) {
	inbox := NewInbox()
	receipt, isNew, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !isNew {
		t.Fatal("expected first delivery to be new")
	}
	if receipt.PayloadDigest == "" {
		t.Fatal("expected a payload digest on the receipt")
	}
}

func TestDuplicateDeliverySameBytesIsSideEffectFree(t *testing.T) {
	inbox := NewInbox()
	first, _, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	second, isNew, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`))
	if err != nil {
		t.Fatalf("unexpected error on replay: %v", err)
	}
	if isNew {
		t.Fatal("expected replay of identical delivery to not be new")
	}
	if second != first {
		t.Fatalf("expected replay to return the original receipt unchanged, got %+v vs %+v", second, first)
	}
}

func TestReplayWithDifferentBytesIsIdempotencyCollision(t *testing.T) {
	inbox := NewInbox()
	if _, _, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	_, isNew, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"b"}`))
	if !errors.Is(err, ErrIdempotencyCollision) {
		t.Fatalf("expected ErrIdempotencyCollision, got %v", err)
	}
	if isNew {
		t.Fatal("a collision must never report isNew")
	}
}

func TestDifferentProvidersOrDeliveryIDsAreIsolated(t *testing.T) {
	inbox := NewInbox()
	if _, isNew, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`)); err != nil || !isNew {
		t.Fatalf("expected new: isNew=%v err=%v", isNew, err)
	}
	if _, isNew, err := inbox.Receive("gitlab", "delivery-1", []byte(`{"ref":"a"}`)); err != nil || !isNew {
		t.Fatalf("expected a different provider with the same deliveryId to be treated as new: isNew=%v err=%v", isNew, err)
	}
	if _, isNew, err := inbox.Receive("github", "delivery-2", []byte(`{"ref":"a"}`)); err != nil || !isNew {
		t.Fatalf("expected a different deliveryId to be treated as new: isNew=%v err=%v", isNew, err)
	}
}

func TestConcurrentIdenticalDeliveryExactlyOneCommit(t *testing.T) {
	inbox := NewInbox()
	const writers = 32
	var wg sync.WaitGroup
	newCount := make([]bool, writers)
	for i := 0; i < writers; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			_, isNew, err := inbox.Receive("github", "delivery-1", []byte(`{"ref":"a"}`))
			if err != nil {
				t.Errorf("unexpected error: %v", err)
			}
			newCount[idx] = isNew
		}(i)
	}
	wg.Wait()

	commits := 0
	for _, isNew := range newCount {
		if isNew {
			commits++
		}
	}
	if commits != 1 {
		t.Fatalf("expected exactly one concurrent delivery to commit as new, got %d", commits)
	}
}
