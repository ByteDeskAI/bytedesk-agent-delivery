// Package canary verifies promotion canary plans and purpose-separated evidence.
//
// It deliberately consumes current policy, grant, workload-identity, signer,
// authentication, and time facts independently. Artifact claims cannot make
// themselves current or trusted.
package canary

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

const (
	CommonSchemaID                     = "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0"
	CanaryPlanSchemaID                 = "https://schemas.bytedesk.ai/agent-delivery/v1/canary-plan/1.0.0"
	CanaryEvidenceSchemaID             = "https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0"
	AuthorizationDecisionProofSchemaID = "https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0"
)

const maxValidityWindow = 30 * time.Minute

type ErrorCode string

const (
	CodeInvalidInputs            ErrorCode = "invalid_inputs"
	CodeInvalidContract          ErrorCode = "invalid_contract"
	CodeBindingMismatch          ErrorCode = "binding_mismatch"
	CodeSignerMismatch           ErrorCode = "signer_mismatch"
	CodeStaleEvidence            ErrorCode = "stale_evidence"
	CodeUnauthenticatedEvidence  ErrorCode = "unauthenticated_evidence"
	CodePermitProofMissing       ErrorCode = "permit_authorization_proof_missing"
	CodeDenialNotProven          ErrorCode = "capability_denial_not_proven"
	CodeUnauthenticatedProof     ErrorCode = "unauthenticated_authorization_proof"
	CodeTransportFailure         ErrorCode = "authorization_transport_failure"
	CodePermitDecisionMismatch   ErrorCode = "permit_authorization_decision_mismatch"
	CodeHostCheckFailed          ErrorCode = "host_canary_check_failed"
	CodeWorkloadLoginFailed      ErrorCode = "workload_login_failed"
	CodeNotApplicableCheckFailed ErrorCode = "not_applicable_check_failed"
	CodeUncertifiedNotApplicable ErrorCode = "uncertified_not_applicable"
)

var verificationErrorCodes = [...]ErrorCode{
	CodeInvalidInputs,
	CodeInvalidContract,
	CodeBindingMismatch,
	CodeSignerMismatch,
	CodeStaleEvidence,
	CodeUnauthenticatedEvidence,
	CodePermitProofMissing,
	CodeDenialNotProven,
	CodeUnauthenticatedProof,
	CodeTransportFailure,
	CodePermitDecisionMismatch,
	CodeHostCheckFailed,
	CodeWorkloadLoginFailed,
	CodeNotApplicableCheckFailed,
	CodeUncertifiedNotApplicable,
}

// StableProblemCode is the public problem-catalog code emitted at a port
// boundary. Internal verifier diagnostics remain more specific, while every
// diagnostic has exactly one stable public representation.
type StableProblemCode string

const (
	ProblemEvidenceInvalid           StableProblemCode = "evidence_invalid"
	ProblemCapabilityDenialNotProven StableProblemCode = "capability_denial_not_proven"
	ProblemCapabilityTransportFailed StableProblemCode = "capability_transport_failed"
	ProblemTrustVerificationFailed   StableProblemCode = "trust_verification_failed"
)

// StableProblemForErrorCode returns the sole public problem-catalog code for a
// closed internal verifier error code. Unknown codes are deliberately rejected
// so new diagnostics cannot escape without an explicit compatibility decision.
func StableProblemForErrorCode(code ErrorCode) (StableProblemCode, bool) {
	switch code {
	case CodeInvalidInputs, CodeInvalidContract, CodeBindingMismatch, CodeStaleEvidence,
		CodePermitProofMissing, CodePermitDecisionMismatch, CodeHostCheckFailed,
		CodeWorkloadLoginFailed, CodeNotApplicableCheckFailed, CodeUncertifiedNotApplicable:
		return ProblemEvidenceInvalid, true
	case CodeSignerMismatch, CodeUnauthenticatedEvidence, CodeUnauthenticatedProof:
		return ProblemTrustVerificationFailed, true
	case CodeDenialNotProven:
		return ProblemCapabilityDenialNotProven, true
	case CodeTransportFailure:
		return ProblemCapabilityTransportFailed, true
	default:
		return "", false
	}
}

type VerificationError struct {
	Code        ErrorCode
	ProblemCode StableProblemCode
	Detail      string
	Cause       error
}

func (e *VerificationError) Error() string {
	if e.Detail == "" {
		return string(e.Code)
	}
	return string(e.Code) + ": " + e.Detail
}
func (e *VerificationError) Unwrap() error { return e.Cause }

func fail(code ErrorCode, detail string, cause error) error {
	problemCode, ok := StableProblemForErrorCode(code)
	if !ok {
		panic(fmt.Sprintf("canary verifier error code %q has no stable public problem mapping", code))
	}
	return &VerificationError{Code: code, ProblemCode: problemCode, Detail: detail, Cause: cause}
}

type SchemaResolver interface {
	ResolveSchema(context.Context, string) ([]byte, error)
}

type AuthorizationDecisionProofResolver interface {
	ResolveAuthorizationDecisionProof(context.Context, string) ([]byte, error)
}

type TrustPolicyRef struct {
	ID     string `json:"id"`
	Digest string `json:"digest"`
}

type SignerExpectation struct {
	Identity string
	Policy   TrustPolicyRef
}

type AuthenticatedVerificationRecord struct {
	SignerIdentity             string
	SignerPolicy               TrustPolicyRef
	VerificationEvidenceDigest string
	ChannelResult              string
}

const (
	ChannelSignatureVerified          = "signature_verified"
	ChannelAuthenticatedNonRepudiable = "authenticated_nonrepudiable_channel_verified"
)

type CurrentInputs struct {
	CurrentPlanDigest             string
	CurrentAuthorityDigest        string
	CurrentPolicyDigest           string
	CurrentGrantSetDigest         string
	CurrentWorkloadIdentityDigest string
	CurrentCapabilityDispatch     CapabilityDispatchBinding
	Now                           time.Time
	EvidenceSigners               map[string]SignerExpectation
	AuthorizationSigner           SignerExpectation
	AuthenticatedEvidenceDigests  map[string]AuthenticatedVerificationRecord
	AuthenticatedProofDigests     map[string]AuthenticatedVerificationRecord
	AuthenticatedCertifications   map[string]TrustPolicyRef
}

type PromotionRequest struct {
	Plan     []byte
	Evidence [][]byte
}

type VerificationResult struct {
	PlanDigest                string
	EvidenceDigests           []string
	AuthorizationProofDigests []string
}

type compiledContract struct {
	digest string
	schema *jsonschema.Schema
}

type Verifier struct {
	contracts map[string]compiledContract
	proofs    AuthorizationDecisionProofResolver
}

func NewVerifier(ctx context.Context, resolver SchemaResolver, proofs AuthorizationDecisionProofResolver, trustedSchemaDigests map[string]string) (*Verifier, error) {
	if resolver == nil || proofs == nil {
		return nil, fail(CodeInvalidInputs, "schema and proof resolvers are required", nil)
	}
	ids := []string{CommonSchemaID, CanaryPlanSchemaID, CanaryEvidenceSchemaID, AuthorizationDecisionProofSchemaID}
	if len(trustedSchemaDigests) != len(ids) {
		return nil, fail(CodeInvalidInputs, "trusted schema digest set must contain exactly common, plan, evidence, and authorization-proof schemas", nil)
	}
	for _, id := range ids {
		if trustedSchemaDigests[id] == "" {
			return nil, fail(CodeInvalidInputs, "missing independently trusted schema digest for "+id, nil)
		}
	}
	for id := range trustedSchemaDigests {
		known := false
		for _, expectedID := range ids {
			if id == expectedID {
				known = true
				break
			}
		}
		if !known {
			return nil, fail(CodeInvalidInputs, "unexpected trusted schema descriptor "+id, nil)
		}
	}
	documents := make(map[string]any, len(ids))
	digests := make(map[string]string, len(ids))
	compiler := jsonschema.NewCompiler()
	compiler.DefaultDraft(jsonschema.Draft2020)
	compiler.AssertFormat()
	compiler.AssertVocabs()
	compiler.UseLoader(rejectNetworkLoader{})
	for _, id := range ids {
		payload, err := resolver.ResolveSchema(ctx, id)
		if err != nil {
			return nil, fail(CodeInvalidInputs, "resolve schema "+id, err)
		}
		canonicalResult, err := canonical.CanonicalizeBytes(payload, canonical.FormatJSON, canonical.Limits{})
		if err != nil {
			return nil, fail(CodeInvalidContract, "schema is not strict canonicalizable JSON: "+id, err)
		}
		if canonicalResult.Digest != trustedSchemaDigests[id] {
			return nil, fail(CodeBindingMismatch, "resolved schema bytes do not match independently trusted digest for "+id, nil)
		}
		var document any
		if err := json.Unmarshal(canonicalResult.Bytes, &document); err != nil {
			return nil, fail(CodeInvalidContract, "decode schema "+id, err)
		}
		root, ok := document.(map[string]any)
		if !ok || root["$id"] != id || root["$schema"] != "https://json-schema.org/draft/2020-12/schema" {
			return nil, fail(CodeInvalidContract, "schema identity or Draft 2020-12 declaration does not match "+id, nil)
		}
		if err := compiler.AddResource(id, document); err != nil {
			return nil, fail(CodeInvalidContract, "register schema "+id, err)
		}
		documents[id] = document
		digests[id] = canonicalResult.Digest
	}
	contracts := make(map[string]compiledContract, len(ids)-1)
	for _, id := range ids[1:] {
		compiled, err := compiler.Compile(id)
		if err != nil {
			return nil, fail(CodeInvalidContract, "compile schema "+id, err)
		}
		contracts[id] = compiledContract{digest: digests[id], schema: compiled}
	}
	return &Verifier{contracts: contracts, proofs: proofs}, nil
}

func (v *Verifier) SchemaDigest(id string) string { return v.contracts[id].digest }

func CanonicalDigest(payload []byte) (string, error) {
	result, err := canonical.CanonicalizeBytes(payload, canonical.FormatJSON, canonical.Limits{})
	if err != nil {
		return "", err
	}
	return result.Digest, nil
}

type rejectNetworkLoader struct{}

func (rejectNetworkLoader) Load(location string) (any, error) {
	return nil, fmt.Errorf("offline schema resolution denied: %s", location)
}

type SchemaDescriptor struct {
	ID     string `json:"id"`
	Digest string `json:"digest"`
}
type CapabilityDescriptor struct {
	ID     string `json:"id"`
	Digest string `json:"digest"`
}

type CanaryPlan struct {
	Contract               string                 `json:"contract"`
	Schema                 SchemaDescriptor       `json:"schema"`
	PlanID                 string                 `json:"planId"`
	RolloutID              string                 `json:"rolloutId"`
	Nonce                  string                 `json:"nonce"`
	CandidateDigest        string                 `json:"candidateDigest"`
	DesiredRevisionDigest  string                 `json:"desiredRevisionDigest"`
	ReleaseDigest          string                 `json:"releaseDigest"`
	DeploymentDigest       string                 `json:"deploymentDigest"`
	ConsumerID             string                 `json:"consumerId"`
	SubjectID              string                 `json:"subjectId"`
	TargetID               string                 `json:"targetId"`
	SlotID                 string                 `json:"slotId"`
	Generation             int64                  `json:"generation"`
	ActivationMode         string                 `json:"activationMode"`
	AuthorityDigest        string                 `json:"authorityDigest"`
	PolicyDigest           string                 `json:"policyDigest"`
	GrantSetDigest         string                 `json:"grantSetDigest"`
	WorkloadIdentityDigest string                 `json:"workloadIdentityDigest"`
	ExpectedChecks         ExpectedChecks         `json:"expectedChecks"`
	EvidenceSignerPolicies EvidenceSignerPolicies `json:"evidenceSignerPolicies"`
	IssuedAt               string                 `json:"issuedAt"`
	ExpiresAt              string                 `json:"expiresAt"`
}

type ExpectedChecks struct {
	Host       HostExpectedChecks       `json:"host_reconciler"`
	Capability CapabilityExpectedChecks `json:"consumer_capability_verifier"`
}
type HostExpectedChecks struct {
	CandidateReady CandidateReadyExpectedChecks `json:"candidate_ready"`
	ActiveReadback ActiveReadbackExpectedChecks `json:"active_readback"`
}
type CandidateReadyExpectedChecks struct {
	ArtifactReadback   string `json:"artifact_readback"`
	FileInventory      string `json:"file_inventory"`
	SlotGeneration     string `json:"slot_generation"`
	ServiceProcess     string `json:"service_process"`
	ResourceThresholds string `json:"resource_thresholds"`
	HarnessReadiness   string `json:"harness_readiness"`
}
type ActiveReadbackExpectedChecks struct {
	SwitchMarker   string `json:"switch_marker"`
	ActivePointer  string `json:"active_pointer"`
	FileInventory  string `json:"file_inventory"`
	ServiceProcess string `json:"service_process"`
}
type CapabilityExpectedChecks struct {
	Mode                string               `json:"mode"`
	Checks              map[string]string    `json:"checks"`
	PermittedCapability CapabilityDescriptor `json:"permittedCapability"`
	DeniedSentinel      struct {
		ID                   string `json:"id"`
		Digest               string `json:"digest"`
		ExpectedDecisionCode string `json:"expectedDecisionCode"`
	} `json:"deniedSentinel"`
	CertificationDigest string         `json:"certificationDigest"`
	CertificationPolicy TrustPolicyRef `json:"certificationPolicy"`
}
type EvidenceSignerPolicies struct {
	Host          TrustPolicyRef `json:"host_reconciler"`
	Capability    TrustPolicyRef `json:"consumer_capability_verifier"`
	Authorization TrustPolicyRef `json:"authorization_decision"`
}

type CanaryEvidence struct {
	Contract               string                     `json:"contract"`
	Schema                 SchemaDescriptor           `json:"schema"`
	EvidenceID             string                     `json:"evidenceId"`
	Actor                  string                     `json:"actor"`
	RolloutID              string                     `json:"rolloutId"`
	PlanDigest             string                     `json:"planDigest"`
	Nonce                  string                     `json:"nonce"`
	CandidateDigest        string                     `json:"candidateDigest"`
	DesiredRevisionDigest  string                     `json:"desiredRevisionDigest"`
	ReleaseDigest          string                     `json:"releaseDigest"`
	DeploymentDigest       string                     `json:"deploymentDigest"`
	ConsumerID             string                     `json:"consumerId"`
	SubjectID              string                     `json:"subjectId"`
	TargetID               string                     `json:"targetId"`
	SlotID                 string                     `json:"slotId"`
	Generation             int64                      `json:"generation"`
	AuthorityDigest        string                     `json:"authorityDigest"`
	PolicyDigest           string                     `json:"policyDigest"`
	GrantSetDigest         string                     `json:"grantSetDigest"`
	WorkloadIdentityDigest string                     `json:"workloadIdentityDigest"`
	ActorIdentity          string                     `json:"actorIdentity"`
	ActorVersion           string                     `json:"actorVersion"`
	SignerPolicy           TrustPolicyRef             `json:"signerPolicy"`
	CapabilityDispatch     *CapabilityDispatchBinding `json:"capabilityDispatch,omitempty"`
	Results                json.RawMessage            `json:"results"`
	IssuedAt               string                     `json:"issuedAt"`
	ExpiresAt              string                     `json:"expiresAt"`
}

type CapabilityDispatchBinding struct {
	RequestDigest               string `json:"requestDigest"`
	ReceiptDigest               string `json:"receiptDigest"`
	CheckProfileDigest          string `json:"checkProfileDigest"`
	AuthorizationDecisionDigest string `json:"authorizationDecisionDigest"`
}
type TechnicalResult struct {
	Actual string `json:"actual"`
}
type HostCandidateReadyResults struct {
	Phase              string          `json:"phase"`
	ArtifactReadback   TechnicalResult `json:"artifact_readback"`
	FileInventory      TechnicalResult `json:"file_inventory"`
	SlotGeneration     TechnicalResult `json:"slot_generation"`
	ServiceProcess     TechnicalResult `json:"service_process"`
	ResourceThresholds TechnicalResult `json:"resource_thresholds"`
	HarnessReadiness   TechnicalResult `json:"harness_readiness"`
}
type HostActiveReadbackResults struct {
	Phase          string          `json:"phase"`
	SwitchMarker   TechnicalResult `json:"switch_marker"`
	ActivePointer  TechnicalResult `json:"active_pointer"`
	FileInventory  TechnicalResult `json:"file_inventory"`
	ServiceProcess TechnicalResult `json:"service_process"`
}
type AuthorizationDecisionResult struct {
	Outcome       string `json:"outcome"`
	DecisionClass string `json:"decisionClass"`
	DecisionCode  string `json:"decisionCode"`
	ProofDigest   string `json:"authorizationDecisionProofDigest"`
	FailureClass  string `json:"failureClass"`
}
type CapabilityRequiredResults struct {
	Mode          string                      `json:"mode"`
	WorkloadLogin TechnicalResult             `json:"workload_login"`
	Permitted     AuthorizationDecisionResult `json:"permitted_capability"`
	Denied        AuthorizationDecisionResult `json:"denied_sentinel"`
}
type CapabilityNotApplicableResults struct {
	Mode   string `json:"mode"`
	Result struct {
		Actual              string         `json:"actual"`
		CertificationDigest string         `json:"certificationDigest"`
		CertificationPolicy TrustPolicyRef `json:"certificationPolicy"`
	} `json:"certified_not_applicable"`
}

type AuthorizationDecisionProof struct {
	Contract               string               `json:"contract"`
	Schema                 SchemaDescriptor     `json:"schema"`
	PlanDigest             string               `json:"planDigest"`
	Nonce                  string               `json:"nonce"`
	ConsumerID             string               `json:"consumerId"`
	SubjectID              string               `json:"subjectId"`
	TargetID               string               `json:"targetId"`
	CandidateDigest        string               `json:"candidateDigest"`
	ReleaseDigest          string               `json:"releaseDigest"`
	DeploymentDigest       string               `json:"deploymentDigest"`
	Capability             CapabilityDescriptor `json:"capability"`
	PolicyDigest           string               `json:"policyDigest"`
	GrantSetDigest         string               `json:"grantSetDigest"`
	WorkloadIdentityDigest string               `json:"workloadIdentityDigest"`
	Decision               struct {
		Class string `json:"class"`
		Code  string `json:"code"`
	} `json:"decision"`
	SignerIdentity string         `json:"signerIdentity"`
	SignerPolicy   TrustPolicyRef `json:"signerPolicy"`
	IssuedAt       string         `json:"issuedAt"`
	ExpiresAt      string         `json:"expiresAt"`
}

func (v *Verifier) VerifyPromotion(ctx context.Context, request PromotionRequest, inputs CurrentInputs) (VerificationResult, error) {
	if inputs.Now.IsZero() || inputs.CurrentPlanDigest == "" || inputs.CurrentAuthorityDigest == "" || inputs.CurrentPolicyDigest == "" || inputs.CurrentGrantSetDigest == "" || inputs.CurrentWorkloadIdentityDigest == "" || !validCapabilityDispatchBinding(inputs.CurrentCapabilityDispatch) {
		return VerificationResult{}, fail(CodeInvalidInputs, "current plan, authority, policy, grant set, workload identity, capability dispatch, and time are required", nil)
	}
	if len(request.Evidence) != 3 {
		return VerificationResult{}, fail(CodeInvalidContract, "exactly two host-phase evidence objects and one capability evidence object are required", nil)
	}
	var plan CanaryPlan
	planDigest, err := v.validate(CanaryPlanSchemaID, request.Plan, &plan)
	if err != nil {
		return VerificationResult{}, err
	}
	if planDigest != inputs.CurrentPlanDigest {
		return VerificationResult{}, fail(CodeBindingMismatch, "plan bytes do not match the independently current plan digest", nil)
	}
	if err := v.requireSchemaHeader(plan.Schema, CanaryPlanSchemaID); err != nil {
		return VerificationResult{}, err
	}
	if plan.AuthorityDigest != inputs.CurrentAuthorityDigest || plan.PolicyDigest != inputs.CurrentPolicyDigest || plan.GrantSetDigest != inputs.CurrentGrantSetDigest || plan.WorkloadIdentityDigest != inputs.CurrentWorkloadIdentityDigest {
		return VerificationResult{}, fail(CodeBindingMismatch, "plan authority, policy, grant-set, or workload-identity digest is not current", nil)
	}
	planIssued, planExpires, err := activeWindow(plan.IssuedAt, plan.ExpiresAt, inputs.Now)
	if err != nil {
		return VerificationResult{}, err
	}
	if err := validatePlanSignerPolicies(plan, inputs); err != nil {
		return VerificationResult{}, err
	}

	result := VerificationResult{PlanDigest: planDigest}
	seen := make(map[string]struct{}, 3)
	for _, document := range request.Evidence {
		var evidence CanaryEvidence
		digest, err := v.validate(CanaryEvidenceSchemaID, document, &evidence)
		if err != nil {
			return VerificationResult{}, err
		}
		if err := v.requireSchemaHeader(evidence.Schema, CanaryEvidenceSchemaID); err != nil {
			return VerificationResult{}, err
		}
		if err := bindEvidence(plan, planDigest, evidence); err != nil {
			return VerificationResult{}, err
		}
		if err := verifyEvidenceSigner(plan, evidence, inputs); err != nil {
			return VerificationResult{}, err
		}
		issued, expires, err := activeWindow(evidence.IssuedAt, evidence.ExpiresAt, inputs.Now)
		if err != nil {
			return VerificationResult{}, err
		}
		if issued.Before(planIssued) || expires.After(planExpires) {
			return VerificationResult{}, fail(CodeStaleEvidence, "evidence freshness window escapes the plan window", nil)
		}
		authenticated, ok := inputs.AuthenticatedEvidenceDigests[digest]
		if err := verifyAuthenticatedRecord(authenticated, ok, inputs.EvidenceSigners[evidence.Actor], SignerExpectation{Identity: evidence.ActorIdentity, Policy: evidence.SignerPolicy}, CodeUnauthenticatedEvidence, "evidence"); err != nil {
			return VerificationResult{}, err
		}
		result.EvidenceDigests = append(result.EvidenceDigests, digest)
		switch evidence.Actor {
		case "host_reconciler":
			phase, err := verifyHostResults(evidence.Results)
			if err != nil {
				return VerificationResult{}, err
			}
			key := evidence.Actor + ":" + phase
			if _, duplicate := seen[key]; duplicate {
				return VerificationResult{}, fail(CodeInvalidContract, "duplicate host evidence phase "+phase, nil)
			}
			seen[key] = struct{}{}
		case "consumer_capability_verifier":
			if _, duplicate := seen[evidence.Actor]; duplicate {
				return VerificationResult{}, fail(CodeInvalidContract, "duplicate capability evidence", nil)
			}
			seen[evidence.Actor] = struct{}{}
			if evidence.CapabilityDispatch == nil || *evidence.CapabilityDispatch != inputs.CurrentCapabilityDispatch {
				return VerificationResult{}, fail(CodeBindingMismatch, "capability evidence does not match the independently trusted dispatch binding", nil)
			}
			proofDigests, err := v.verifyCapabilityResults(ctx, plan, planDigest, evidence, expires, inputs)
			if err != nil {
				return VerificationResult{}, err
			}
			result.AuthorizationProofDigests = append(result.AuthorizationProofDigests, proofDigests...)
		default:
			return VerificationResult{}, fail(CodeInvalidContract, "unknown evidence actor", nil)
		}
	}
	for _, phase := range []string{"candidate_ready", "active_readback"} {
		if _, ok := seen["host_reconciler:"+phase]; !ok {
			return VerificationResult{}, fail(CodeInvalidContract, "host evidence phase "+phase+" is required", nil)
		}
	}
	if _, ok := seen["consumer_capability_verifier"]; !ok {
		return VerificationResult{}, fail(CodeInvalidContract, "capability evidence is required", nil)
	}
	return result, nil
}

func validCapabilityDispatchBinding(binding CapabilityDispatchBinding) bool {
	return validSHA256(binding.RequestDigest) && validSHA256(binding.ReceiptDigest) &&
		validSHA256(binding.CheckProfileDigest) && validSHA256(binding.AuthorizationDecisionDigest)
}

func (v *Verifier) validate(id string, payload []byte, out any) (string, error) {
	contract, ok := v.contracts[id]
	if !ok {
		return "", fail(CodeInvalidInputs, "schema is not loaded: "+id, nil)
	}
	canonicalResult, err := canonical.CanonicalizeBytes(payload, canonical.FormatJSON, canonical.Limits{})
	if err != nil {
		return "", fail(CodeInvalidContract, "contract is not strict canonicalizable JSON", err)
	}
	var instance any
	if err := json.Unmarshal(canonicalResult.Bytes, &instance); err != nil {
		return "", fail(CodeInvalidContract, "decode contract", err)
	}
	if err := contract.schema.Validate(instance); err != nil {
		return "", fail(CodeInvalidContract, "schema validation failed", err)
	}
	if err := json.Unmarshal(canonicalResult.Bytes, out); err != nil {
		return "", fail(CodeInvalidContract, "decode typed contract", err)
	}
	return canonicalResult.Digest, nil
}

func (v *Verifier) requireSchemaHeader(header SchemaDescriptor, id string) error {
	if header.ID != id || header.Digest != v.contracts[id].digest {
		return fail(CodeBindingMismatch, "schema descriptor does not match the exact loaded schema", nil)
	}
	return nil
}

func validatePlanSignerPolicies(plan CanaryPlan, inputs CurrentInputs) error {
	host, hostOK := inputs.EvidenceSigners["host_reconciler"]
	capability, capabilityOK := inputs.EvidenceSigners["consumer_capability_verifier"]
	if !hostOK || !capabilityOK || host.Identity == "" || capability.Identity == "" || inputs.AuthorizationSigner.Identity == "" {
		return fail(CodeInvalidInputs, "all independent signer expectations are required", nil)
	}
	if host.Policy != plan.EvidenceSignerPolicies.Host || capability.Policy != plan.EvidenceSignerPolicies.Capability || inputs.AuthorizationSigner.Policy != plan.EvidenceSignerPolicies.Authorization {
		return fail(CodeSignerMismatch, "plan signer policies do not match independent expectations", nil)
	}
	return nil
}

func bindEvidence(plan CanaryPlan, planDigest string, evidence CanaryEvidence) error {
	if evidence.RolloutID != plan.RolloutID || evidence.PlanDigest != planDigest || evidence.Nonce != plan.Nonce ||
		evidence.CandidateDigest != plan.CandidateDigest || evidence.DesiredRevisionDigest != plan.DesiredRevisionDigest ||
		evidence.ReleaseDigest != plan.ReleaseDigest || evidence.DeploymentDigest != plan.DeploymentDigest ||
		evidence.ConsumerID != plan.ConsumerID || evidence.SubjectID != plan.SubjectID || evidence.TargetID != plan.TargetID ||
		evidence.SlotID != plan.SlotID || evidence.Generation != plan.Generation || evidence.AuthorityDigest != plan.AuthorityDigest ||
		evidence.PolicyDigest != plan.PolicyDigest || evidence.GrantSetDigest != plan.GrantSetDigest || evidence.WorkloadIdentityDigest != plan.WorkloadIdentityDigest {
		return fail(CodeBindingMismatch, "evidence does not match every plan binding", nil)
	}
	return nil
}

func verifyEvidenceSigner(plan CanaryPlan, evidence CanaryEvidence, inputs CurrentInputs) error {
	expected, ok := inputs.EvidenceSigners[evidence.Actor]
	if !ok || evidence.ActorIdentity != expected.Identity || evidence.SignerPolicy != expected.Policy {
		return fail(CodeSignerMismatch, "evidence signer identity or policy mismatch", nil)
	}
	if evidence.Actor == "host_reconciler" && evidence.SignerPolicy != plan.EvidenceSignerPolicies.Host {
		return fail(CodeSignerMismatch, "host signer policy does not match plan", nil)
	}
	if evidence.Actor == "consumer_capability_verifier" && evidence.SignerPolicy != plan.EvidenceSignerPolicies.Capability {
		return fail(CodeSignerMismatch, "capability signer policy does not match plan", nil)
	}
	return nil
}

func activeWindow(issuedText, expiresText string, now time.Time) (time.Time, time.Time, error) {
	issued, err := time.Parse(time.RFC3339Nano, issuedText)
	if err != nil {
		return time.Time{}, time.Time{}, fail(CodeInvalidContract, "invalid issuedAt", err)
	}
	expires, err := time.Parse(time.RFC3339Nano, expiresText)
	if err != nil {
		return time.Time{}, time.Time{}, fail(CodeInvalidContract, "invalid expiresAt", err)
	}
	if !expires.After(issued) || expires.Sub(issued) > maxValidityWindow || now.Before(issued) || !now.Before(expires) {
		return time.Time{}, time.Time{}, fail(CodeStaleEvidence, "freshness window is inactive", nil)
	}
	return issued, expires, nil
}

func verifyHostResults(raw json.RawMessage) (string, error) {
	var discriminator struct {
		Phase string `json:"phase"`
	}
	if err := json.Unmarshal(raw, &discriminator); err != nil {
		return "", fail(CodeInvalidContract, "decode host result phase", err)
	}
	var checks []TechnicalResult
	switch discriminator.Phase {
	case "candidate_ready":
		var results HostCandidateReadyResults
		if err := json.Unmarshal(raw, &results); err != nil {
			return "", fail(CodeInvalidContract, "decode candidate-ready host results", err)
		}
		checks = []TechnicalResult{results.ArtifactReadback, results.FileInventory, results.SlotGeneration, results.ServiceProcess, results.ResourceThresholds, results.HarnessReadiness}
	case "active_readback":
		var results HostActiveReadbackResults
		if err := json.Unmarshal(raw, &results); err != nil {
			return "", fail(CodeInvalidContract, "decode active-readback host results", err)
		}
		checks = []TechnicalResult{results.SwitchMarker, results.ActivePointer, results.FileInventory, results.ServiceProcess}
	default:
		return "", fail(CodeInvalidContract, "unknown host result phase", nil)
	}
	for _, check := range checks {
		if check.Actual != "passed" {
			return "", fail(CodeHostCheckFailed, "technical check did not pass", nil)
		}
	}
	return discriminator.Phase, nil
}

func (v *Verifier) verifyCapabilityResults(ctx context.Context, plan CanaryPlan, planDigest string, evidence CanaryEvidence, evidenceExpires time.Time, inputs CurrentInputs) ([]string, error) {
	var discriminator struct {
		Mode string `json:"mode"`
	}
	if err := json.Unmarshal(evidence.Results, &discriminator); err != nil {
		return nil, fail(CodeInvalidContract, "decode capability result mode", err)
	}
	if discriminator.Mode != plan.ExpectedChecks.Capability.Mode {
		return nil, fail(CodeBindingMismatch, "capability evidence mode does not match plan", nil)
	}
	switch discriminator.Mode {
	case "required":
		var results CapabilityRequiredResults
		if err := json.Unmarshal(evidence.Results, &results); err != nil {
			return nil, fail(CodeInvalidContract, "decode required capability results", err)
		}
		if results.WorkloadLogin.Actual != "passed" {
			return nil, fail(CodeWorkloadLoginFailed, "workload login did not pass", nil)
		}
		permitted, err := v.verifyDecision(ctx, plan, planDigest, evidence, evidenceExpires, plan.ExpectedChecks.Capability.PermittedCapability, "permitted", "", results.Permitted, inputs)
		if err != nil {
			return nil, err
		}
		deniedExpected := CapabilityDescriptor{ID: plan.ExpectedChecks.Capability.DeniedSentinel.ID, Digest: plan.ExpectedChecks.Capability.DeniedSentinel.Digest}
		denied, err := v.verifyDecision(ctx, plan, planDigest, evidence, evidenceExpires, deniedExpected, "policy_denied", plan.ExpectedChecks.Capability.DeniedSentinel.ExpectedDecisionCode, results.Denied, inputs)
		if err != nil {
			return nil, err
		}
		return []string{permitted, denied}, nil
	case "certified_not_applicable":
		var results CapabilityNotApplicableResults
		if err := json.Unmarshal(evidence.Results, &results); err != nil {
			return nil, fail(CodeInvalidContract, "decode not-applicable result", err)
		}
		if results.Result.Actual != "not_applicable" {
			return nil, fail(CodeNotApplicableCheckFailed, "not-applicable certification check failed", nil)
		}
		expected := plan.ExpectedChecks.Capability
		if results.Result.CertificationDigest != expected.CertificationDigest || results.Result.CertificationPolicy != expected.CertificationPolicy {
			return nil, fail(CodeBindingMismatch, "not-applicable certification does not match plan", nil)
		}
		authenticatedPolicy, ok := inputs.AuthenticatedCertifications[results.Result.CertificationDigest]
		if !ok || authenticatedPolicy != expected.CertificationPolicy {
			return nil, fail(CodeUncertifiedNotApplicable, "certification digest was not independently authenticated", nil)
		}
		return nil, nil
	default:
		return nil, fail(CodeInvalidContract, "unknown capability mode", nil)
	}
}

func (v *Verifier) verifyDecision(ctx context.Context, plan CanaryPlan, planDigest string, evidence CanaryEvidence, evidenceExpires time.Time, expectedCapability CapabilityDescriptor, expectedClass, expectedCode string, result AuthorizationDecisionResult, inputs CurrentInputs) (string, error) {
	mismatchCode := CodePermitDecisionMismatch
	missingProofCode := CodePermitProofMissing
	if expectedClass == "policy_denied" {
		mismatchCode = CodeDenialNotProven
		missingProofCode = CodeDenialNotProven
	}
	if result.Outcome == "failed" {
		return "", fail(CodeTransportFailure, "authorization probe failed before an authenticated decision: "+result.FailureClass, nil)
	}
	if result.Outcome != "decision" || result.DecisionClass != expectedClass || (expectedCode != "" && result.DecisionCode != expectedCode) {
		return "", fail(mismatchCode, "capability result does not match the exact expected decision", nil)
	}
	payload, err := v.proofs.ResolveAuthorizationDecisionProof(ctx, result.ProofDigest)
	if err != nil {
		return "", fail(missingProofCode, "authorization proof cannot be resolved", err)
	}
	var proof AuthorizationDecisionProof
	digest, err := v.validate(AuthorizationDecisionProofSchemaID, payload, &proof)
	if err != nil {
		return "", err
	}
	if digest != result.ProofDigest {
		return "", fail(CodeBindingMismatch, "resolved authorization proof digest mismatch", nil)
	}
	authenticated, ok := inputs.AuthenticatedProofDigests[digest]
	if err := verifyAuthenticatedRecord(authenticated, ok, inputs.AuthorizationSigner, SignerExpectation{Identity: proof.SignerIdentity, Policy: proof.SignerPolicy}, CodeUnauthenticatedProof, "authorization proof"); err != nil {
		return "", err
	}
	if err := v.requireSchemaHeader(proof.Schema, AuthorizationDecisionProofSchemaID); err != nil {
		return "", err
	}
	if proof.PlanDigest != planDigest || proof.Nonce != plan.Nonce || proof.ConsumerID != plan.ConsumerID || proof.SubjectID != plan.SubjectID ||
		proof.TargetID != plan.TargetID || proof.CandidateDigest != plan.CandidateDigest || proof.ReleaseDigest != plan.ReleaseDigest || proof.DeploymentDigest != plan.DeploymentDigest ||
		proof.Capability != expectedCapability || proof.PolicyDigest != plan.PolicyDigest || proof.GrantSetDigest != plan.GrantSetDigest ||
		proof.WorkloadIdentityDigest != plan.WorkloadIdentityDigest {
		return "", fail(CodeBindingMismatch, "authorization proof does not match every plan/capability binding", nil)
	}
	if proof.SignerIdentity != inputs.AuthorizationSigner.Identity || proof.SignerPolicy != inputs.AuthorizationSigner.Policy || proof.SignerPolicy != plan.EvidenceSignerPolicies.Authorization {
		return "", fail(CodeSignerMismatch, "authorization proof signer identity or policy mismatch", nil)
	}
	issued, expires, err := activeWindow(proof.IssuedAt, proof.ExpiresAt, inputs.Now)
	if err != nil {
		return "", err
	}
	planIssued, _, _ := activeWindow(plan.IssuedAt, plan.ExpiresAt, inputs.Now)
	if issued.Before(planIssued) || expires.After(evidenceExpires) {
		return "", fail(CodeStaleEvidence, "authorization proof freshness window escapes plan/evidence", nil)
	}
	if proof.Decision.Class != result.DecisionClass || proof.Decision.Code != result.DecisionCode {
		return "", fail(mismatchCode, "authorization proof decision does not match evidence", nil)
	}
	return digest, nil
}

func verifyAuthenticatedRecord(record AuthenticatedVerificationRecord, found bool, expected, claimed SignerExpectation, unauthenticatedCode ErrorCode, subject string) error {
	if !found || !validSHA256(record.VerificationEvidenceDigest) ||
		(record.ChannelResult != ChannelSignatureVerified && record.ChannelResult != ChannelAuthenticatedNonRepudiable) {
		return fail(unauthenticatedCode, subject+" digest lacks a complete authenticated verification record", nil)
	}
	actual := SignerExpectation{Identity: record.SignerIdentity, Policy: record.SignerPolicy}
	if actual != expected || actual != claimed {
		return fail(CodeSignerMismatch, subject+" authenticated signer identity or policy does not match the independent expectation and document claim", nil)
	}
	return nil
}

func validSHA256(value string) bool {
	if len(value) != 71 || value[:7] != "sha256:" {
		return false
	}
	for _, character := range value[7:] {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}
