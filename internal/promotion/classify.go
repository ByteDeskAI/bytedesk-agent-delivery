// Package promotion implements the real, testable core of AD-12: update
// compatibility classification and the sole-writer Coordinator boundary
// around AD-09's TargetDeliveryState CAS store.
//
// This is a slice of AD-12, not the full task. It does not implement canary
// challenges, capability-verifier dispatch, activation authorization,
// region fencing, or forward-recovery planning - those need real running
// services (a capability verifier, region infrastructure, a signing
// authority issuing activation authorizations) this environment does not
// have. What is real here is proven: only a policy-compatible stable
// successor whose customization rebases deterministically, whose skill
// digests are unchanged, and whose consumer policy verdict is valid may
// auto-progress; everything else is classified approval-required and the
// Coordinator refuses to write it without explicit approval, matching
// AD-12's required-work items 1, 3, and 5 and its "only the Coordinator
// advances TargetDeliveryState" acceptance criterion.
package promotion

import (
	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

// Disposition is the closed outcome of classifying a proposed update against
// its previous accepted source.
type Disposition string

const (
	// DispositionAutoProgress means the proposal may advance to
	// ready-to-compile without human approval.
	DispositionAutoProgress Disposition = "auto-progress"
	// DispositionApprovalRequired means the proposal stops for human
	// approval or rejection and must never auto-merge.
	DispositionApprovalRequired Disposition = "approval-required"
)

// Classification is the machine-verifiable result of evaluating one proposed
// update: the disposition plus the exact reason a human can audit.
type Classification struct {
	Disposition Disposition
	Reason      string
	// RebasedProposed is the proposed source with the accepted functional
	// patch reapplied, present only when Disposition is
	// DispositionAutoProgress.
	RebasedProposed any
}

// UpdateProposal is the exact input the Coordinator classifies: the
// previously accepted source, the newly proposed source, the functional
// patch describing the accepted change, and the non-rebase facts that alone
// can force approval regardless of a clean rebase.
type UpdateProposal struct {
	Previous                 map[string]any
	Proposed                 map[string]any
	Patch                    operations.JSONPatch
	Target                   operations.FunctionalTarget
	SkillDigestsUnchanged    bool
	TrustPolicyUnchanged     bool
	ConsumerPolicyVerdictOK  bool
	SecurityAuthorityChanged bool
	RawSecretPresent         bool
}

// ClassifyUpdate implements AD-12 required-work items 1 and 5: it performs
// the dual-working-tree rebase of the accepted functional patch over the
// proposed source (reusing operations.RebaseJSONPatch, built for AD-04's
// same JSON Patch profile) and classifies the result. Any of a failed
// rebase, a changed skill-digest set, a changed trust policy, a security-
// authority mutation, a raw secret, or an invalid consumer policy verdict
// forces DispositionApprovalRequired - matching the acceptance criterion
// that only a policy-compatible stable successor whose customization
// reapplies deterministically, whose skill digests are unchanged, and whose
// consumer policy verdict is valid may auto-progress.
func ClassifyUpdate(proposal UpdateProposal) Classification {
	if proposal.RawSecretPresent {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "raw secret present in proposed source"}
	}
	if proposal.SecurityAuthorityChanged {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "proposal mutates security-authority state"}
	}
	if !proposal.SkillDigestsUnchanged {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "skill digest set changed"}
	}
	if !proposal.TrustPolicyUnchanged {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "trust policy changed"}
	}
	if !proposal.ConsumerPolicyVerdictOK {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "consumer policy verdict is not valid"}
	}

	rebased, err := operations.RebaseJSONPatch(proposal.Previous, proposal.Proposed, proposal.Patch, proposal.Target)
	if err != nil {
		return Classification{Disposition: DispositionApprovalRequired, Reason: "functional customization does not rebase deterministically: " + err.Error()}
	}

	return Classification{Disposition: DispositionAutoProgress, Reason: "policy-compatible stable successor", RebasedProposed: rebased}
}
