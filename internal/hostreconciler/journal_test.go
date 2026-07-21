package hostreconciler

import (
	"errors"
	"sync"
	"sync/atomic"
	"testing"
)

func identityA() SwitchIdentity {
	return SwitchIdentity{
		ReleaseDigest:                             "sha256:release-a",
		DeployableGraphDigest:                     "sha256:graph-a",
		ActivationAuthorizationDigest:             "sha256:authz-a",
		HostEligibilityVerificationEvidenceDigest: "sha256:eligibility-a",
	}
}

func identityB() SwitchIdentity {
	return SwitchIdentity{
		ReleaseDigest:                             "sha256:release-b",
		DeployableGraphDigest:                     "sha256:graph-b",
		ActivationAuthorizationDigest:             "sha256:authz-b",
		HostEligibilityVerificationEvidenceDigest: "sha256:eligibility-b",
	}
}

func TestFreshActivateCommits(t *testing.T) {
	journal := NewJournal()
	entry, isNew, err := journal.Activate("t1", identityA())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !isNew {
		t.Fatal("expected the first activation to be new")
	}
	if entry.State != SwitchStateActive {
		t.Fatalf("expected active state, got %s", entry.State)
	}
}

func TestDuplicateActivateIsIdempotent(t *testing.T) {
	journal := NewJournal()
	first, _, err := journal.Activate("t1", identityA())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	second, isNew, err := journal.Activate("t1", identityA())
	if err != nil {
		t.Fatalf("unexpected error on replay: %v", err)
	}
	if isNew {
		t.Fatal("expected replay to not be new")
	}
	if second != first {
		t.Fatalf("expected identical entry on replay, got %+v vs %+v", second, first)
	}
}

func TestPostSwitchFailureIsFencedToCurrentIdentity(t *testing.T) {
	journal := NewJournal()
	if _, _, err := journal.Activate("t1", identityA()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// A stale failure report naming an identity that isn't current is refused.
	if _, err := journal.MarkPostSwitchFailure("t1", identityB()); !errors.Is(err, ErrFencedFailure) {
		t.Fatalf("expected ErrFencedFailure, got %v", err)
	}

	entry, err := journal.MarkPostSwitchFailure("t1", identityA())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if entry.State != SwitchStateRecoveryRequired {
		t.Fatalf("expected recovery_required, got %s", entry.State)
	}
}

func TestActivateRefusedWhileInRecovery(t *testing.T) {
	journal := NewJournal()
	journal.Activate("t1", identityA())
	journal.MarkPostSwitchFailure("t1", identityA())

	if _, _, err := journal.Activate("t1", identityA()); !errors.Is(err, ErrRecoveryRequired) {
		t.Fatalf("expected ErrRecoveryRequired, got %v", err)
	}
}

func TestRecoveryCannotReactivateFailedRelease(t *testing.T) {
	journal := NewJournal()
	journal.Activate("t1", identityA())
	journal.MarkPostSwitchFailure("t1", identityA())

	sameRelease := identityA()
	sameRelease.DeployableGraphDigest = "sha256:graph-a-recompiled" // everything but the release changed
	if _, err := journal.RecoverTo("t1", sameRelease); !errors.Is(err, ErrReactivatesFailedRelease) {
		t.Fatalf("expected ErrReactivatesFailedRelease, got %v", err)
	}
}

func TestRecoveryToNewReleaseSucceeds(t *testing.T) {
	journal := NewJournal()
	journal.Activate("t1", identityA())
	journal.MarkPostSwitchFailure("t1", identityA())

	entry, err := journal.RecoverTo("t1", identityB())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if entry.State != SwitchStateActive {
		t.Fatalf("expected active state after recovery, got %s", entry.State)
	}
	if entry.Identity != identityB() {
		t.Fatalf("expected the recovery identity to be active, got %+v", entry.Identity)
	}
}

func TestRecoverToRefusedWhenNotInRecovery(t *testing.T) {
	journal := NewJournal()
	journal.Activate("t1", identityA())

	if _, err := journal.RecoverTo("t1", identityB()); !errors.Is(err, ErrNotInRecovery) {
		t.Fatalf("expected ErrNotInRecovery, got %v", err)
	}
}

func TestDifferentTargetsAreIsolated(t *testing.T) {
	journal := NewJournal()
	journal.Activate("t1", identityA())
	journal.MarkPostSwitchFailure("t1", identityA())

	entry, isNew, err := journal.Activate("t2", identityA())
	if err != nil || !isNew {
		t.Fatalf("expected an unrelated target to activate normally: isNew=%v err=%v", isNew, err)
	}
	if entry.State != SwitchStateActive {
		t.Fatalf("expected t2 active, got %s", entry.State)
	}
}

func TestConcurrentActivateExactlyOneCommitsAsNew(t *testing.T) {
	journal := NewJournal()
	const writers = 32
	var wg sync.WaitGroup
	var newCount int64
	for i := 0; i < writers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, isNew, err := journal.Activate("t1", identityA())
			if err != nil {
				t.Errorf("unexpected error: %v", err)
			}
			if isNew {
				atomic.AddInt64(&newCount, 1)
			}
		}()
	}
	wg.Wait()

	if newCount != 1 {
		t.Fatalf("expected exactly one concurrent activation to commit as new, got %d", newCount)
	}
}
