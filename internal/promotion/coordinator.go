package promotion

import (
	"encoding/json"
	"errors"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/desiredstate"
)

// ErrApprovalRequired is returned when a caller attempts to commit a
// classification that requires human approval without supplying it. No
// state is written.
var ErrApprovalRequired = errors.New("promotion: approval required, refusing to write TargetDeliveryState")

// Coordinator is the sole writer of TargetDeliveryState. It wraps AD-09's
// desiredstate.Store and only accepts a Classification produced by
// ClassifyUpdate (or an explicit human Approve), never a raw payload write -
// matching AD-12's acceptance criterion that observations, Git, bots,
// compilers, hosts, capability verifiers, leases, and operators cannot
// bypass exact CAS. Read passes straight through to the store; it never
// requires a precondition or classification.
type Coordinator struct {
	store *desiredstate.Store
}

func NewCoordinator(store *desiredstate.Store) *Coordinator {
	return &Coordinator{store: store}
}

func (c *Coordinator) Read(consumerID, targetID string) (desiredstate.Record, bool) {
	return c.store.Read(consumerID, targetID)
}

// Promote CAS-writes payload for (consumerID, targetID). A
// DispositionApprovalRequired classification is always refused unless
// approved is true, so callers cannot silently auto-merge a change AD-12
// requires to stop for human approval or rejection. Callers normally derive
// payload from classification.RebasedProposed for an auto-progress
// disposition; an approved-required disposition instead carries whatever
// content a human explicitly approved, which need not equal the original
// proposal.
func (c *Coordinator) Promote(consumerID, targetID string, precondition desiredstate.Precondition, classification Classification, approved bool, payload json.RawMessage) (desiredstate.Record, error) {
	if classification.Disposition == DispositionApprovalRequired && !approved {
		return desiredstate.Record{}, ErrApprovalRequired
	}
	return c.store.CompareAndSwap(consumerID, targetID, precondition, payload)
}
