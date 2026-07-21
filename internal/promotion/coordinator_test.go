package promotion

import (
	"errors"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/desiredstate"
)

func TestCoordinatorPromotesAutoProgressClassification(t *testing.T) {
	coordinator := NewCoordinator(desiredstate.NewStore())
	classification := Classification{Disposition: DispositionAutoProgress, RebasedProposed: map[string]any{"v": 1}}

	record, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, false, []byte(`{"v":1}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if record.Revision != 1 {
		t.Fatalf("expected revision 1, got %d", record.Revision)
	}
}

func TestCoordinatorRefusesUnapprovedApprovalRequired(t *testing.T) {
	coordinator := NewCoordinator(desiredstate.NewStore())
	classification := Classification{Disposition: DispositionApprovalRequired, Reason: "skill digest set changed"}

	_, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, false, []byte(`{"v":1}`))
	if !errors.Is(err, ErrApprovalRequired) {
		t.Fatalf("expected ErrApprovalRequired, got %v", err)
	}

	if _, ok := coordinator.Read("c1", "t1"); ok {
		t.Fatal("refused promotion must not have written state")
	}
}

func TestCoordinatorPromotesApprovalRequiredWhenApproved(t *testing.T) {
	coordinator := NewCoordinator(desiredstate.NewStore())
	classification := Classification{Disposition: DispositionApprovalRequired, Reason: "skill digest set changed"}

	record, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, true, []byte(`{"v":1}`))
	if err != nil {
		t.Fatalf("unexpected error on approved promotion: %v", err)
	}
	if record.Revision != 1 {
		t.Fatalf("expected revision 1, got %d", record.Revision)
	}
}

func TestCoordinatorStillEnforcesStoreCAS(t *testing.T) {
	coordinator := NewCoordinator(desiredstate.NewStore())
	classification := Classification{Disposition: DispositionAutoProgress, RebasedProposed: map[string]any{"v": 1}}

	if _, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, false, []byte(`{"v":1}`)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Same absent precondition again must fail: the target now exists.
	_, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, false, []byte(`{"v":2}`))
	if !errors.Is(err, desiredstate.ErrPreconditionFailed) {
		t.Fatalf("expected ErrPreconditionFailed, got %v", err)
	}
}

func TestOnlyCoordinatorCanWriteExactlyOneConcurrentPromotion(t *testing.T) {
	coordinator := NewCoordinator(desiredstate.NewStore())
	classification := Classification{Disposition: DispositionAutoProgress, RebasedProposed: map[string]any{"v": 1}}

	const writers = 32
	var wg sync.WaitGroup
	var successCount int64
	for i := 0; i < writers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := coordinator.Promote("c1", "t1", desiredstate.Precondition{Kind: "absent"}, classification, false, []byte(`{"v":1}`))
			if err == nil {
				atomic.AddInt64(&successCount, 1)
			}
		}()
	}
	wg.Wait()

	if successCount != 1 {
		t.Fatalf("expected exactly one concurrent promotion to succeed, got %d", successCount)
	}
}
