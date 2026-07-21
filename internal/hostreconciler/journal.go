// Package hostreconciler implements the real, testable core of AD-14's
// atomic target-wide switch journal (required-work items 8 and 9): one
// switch marker per target, bound to the full runtime-release identity
// rather than any single subject's deploymentDigest, that never reactivates
// a release that already failed post-switch.
//
// This is a slice of AD-14, not the full task. It does not implement digest-
// pinned artifact pull, per-subject staging/preflight, the harness runtime
// Adapter, technical or capability canary evidence collection (the separate
// internal/canary package already verifies canary evidence once collected),
// or Coordinator-dispatched capability verification - those need a real
// running host, private registry, and consumer capability verifier this
// environment does not have, per docs/planning/infra-defaults.md.
package hostreconciler

import (
	"errors"
	"sync"
)

// SwitchState is the closed state of one target's switch journal entry.
type SwitchState string

const (
	SwitchStateActive           SwitchState = "active"
	SwitchStateRecoveryRequired SwitchState = "recovery_required"
)

// SwitchIdentity is the exact four-digest binding AD-14 requires for switch
// journal identity: "Bind one atomic target-wide switch journal and marker
// to releaseDigest, deployableGraphDigest, activationAuthorizationDigest,
// and hostEligibilityVerificationEvidenceDigest; never use one subject's
// deploymentDigest as journal identity." A journal entry is only ever
// identified by all four digests together, never by any single subject's
// descriptor.
type SwitchIdentity struct {
	ReleaseDigest                             string
	DeployableGraphDigest                     string
	ActivationAuthorizationDigest             string
	HostEligibilityVerificationEvidenceDigest string
}

// Entry is the durable (for process lifetime) record for one target.
type Entry struct {
	TargetID string
	State    SwitchState
	Identity SwitchIdentity
	// FailedIdentity is the identity that produced recovery_required, kept
	// so a recovery attempt can be checked against it even after the
	// journal moves back to active.
	FailedIdentity *SwitchIdentity
}

var (
	// ErrRecoveryRequired is returned when Activate is called on a target
	// currently in recovery_required - only RecoverTo may leave that state,
	// so a plain retry of the original switch can never silently reactivate
	// the failed release.
	ErrRecoveryRequired = errors.New("hostreconciler: target requires recovery, use RecoverTo")
	// ErrFencedFailure is returned when MarkPostSwitchFailure names an
	// identity that does not match the target's current active identity -
	// a stale or superseded switch attempt cannot fail an attempt it no
	// longer owns.
	ErrFencedFailure = errors.New("hostreconciler: failure identity does not match the current active switch")
	// ErrReactivatesFailedRelease is returned when RecoverTo names the same
	// releaseDigest as the identity that just failed - "never reactivate an
	// old release" is enforced structurally, not left to caller discipline.
	ErrReactivatesFailedRelease = errors.New("hostreconciler: recovery cannot reactivate the release that just failed")
	// ErrNotInRecovery is returned when RecoverTo is called on a target that
	// is not currently in recovery_required.
	ErrNotInRecovery = errors.New("hostreconciler: target is not in recovery_required")
)

// Journal is the sole owner of every target's switch state. Safe for
// concurrent use; every transition is serialized so two concurrent switch
// attempts for the same target cannot both commit.
type Journal struct {
	mu      sync.Mutex
	entries map[string]Entry
}

func NewJournal() *Journal {
	return &Journal{entries: make(map[string]Entry)}
}

func (j *Journal) Read(targetID string) (Entry, bool) {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[targetID]
	return entry, ok
}

// Activate commits one atomic switch to identity for targetID. A repeated
// call with the exact same identity while already active is a side-effect-
// free idempotent replay (isNew=false, same entry) - "duplicate and
// restarted operations converge without duplicate activation." A target
// currently in recovery_required refuses Activate entirely: only RecoverTo
// may resolve that state.
func (j *Journal) Activate(targetID string, identity SwitchIdentity) (entry Entry, isNew bool, err error) {
	j.mu.Lock()
	defer j.mu.Unlock()

	current, exists := j.entries[targetID]
	if exists && current.State == SwitchStateRecoveryRequired {
		return Entry{}, false, ErrRecoveryRequired
	}
	if exists && current.State == SwitchStateActive && current.Identity == identity {
		return current, false, nil
	}

	entry = Entry{TargetID: targetID, State: SwitchStateActive, Identity: identity}
	j.entries[targetID] = entry
	return entry, true, nil
}

// MarkPostSwitchFailure transitions targetID to recovery_required. It is
// fenced: failedIdentity must match the target's current active identity,
// so a stale or already-superseded attempt cannot force a live switch into
// recovery out from under it.
func (j *Journal) MarkPostSwitchFailure(targetID string, failedIdentity SwitchIdentity) (Entry, error) {
	j.mu.Lock()
	defer j.mu.Unlock()

	current, exists := j.entries[targetID]
	if !exists || current.State != SwitchStateActive || current.Identity != failedIdentity {
		return Entry{}, ErrFencedFailure
	}

	failed := failedIdentity
	entry := Entry{TargetID: targetID, State: SwitchStateRecoveryRequired, Identity: current.Identity, FailedIdentity: &failed}
	j.entries[targetID] = entry
	return entry, nil
}

// RecoverTo transitions a target out of recovery_required into active with
// a newly compiled recovery identity. It refuses to reactivate the exact
// release that just failed - the recovery identity's ReleaseDigest must
// differ from the failed identity's ReleaseDigest, matching "Never
// reactivate an old release, render, receipt, signature, authority
// snapshot, or revoked renderer."
func (j *Journal) RecoverTo(targetID string, newIdentity SwitchIdentity) (Entry, error) {
	j.mu.Lock()
	defer j.mu.Unlock()

	current, exists := j.entries[targetID]
	if !exists || current.State != SwitchStateRecoveryRequired {
		return Entry{}, ErrNotInRecovery
	}
	if current.FailedIdentity != nil && current.FailedIdentity.ReleaseDigest == newIdentity.ReleaseDigest {
		return Entry{}, ErrReactivatesFailedRelease
	}

	entry := Entry{TargetID: targetID, State: SwitchStateActive, Identity: newIdentity}
	j.entries[targetID] = entry
	return entry, nil
}
