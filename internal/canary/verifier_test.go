package canary

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

const (
	digestA = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	digestB = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
	digestC = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
	digestD = "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
	digestE = "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
	digestF = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)

func TestVerifyPromotionAcceptsExactRequiredCapabilityEvidence(t *testing.T) {
	fixture := newPromotionFixture(t, "required")

	result, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	if err != nil {
		t.Fatalf("%v: %v", err, errors.Unwrap(err))
	}
	if result.PlanDigest != fixture.inputs.CurrentPlanDigest || len(result.EvidenceDigests) != 3 || len(result.AuthorizationProofDigests) != 2 {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func TestEveryCanaryErrorCodeHasOneStablePublicProblem(t *testing.T) {
	want := map[ErrorCode]StableProblemCode{
		CodeInvalidInputs:            ProblemEvidenceInvalid,
		CodeInvalidContract:          ProblemEvidenceInvalid,
		CodeBindingMismatch:          ProblemEvidenceInvalid,
		CodeSignerMismatch:           ProblemTrustVerificationFailed,
		CodeStaleEvidence:            ProblemEvidenceInvalid,
		CodeUnauthenticatedEvidence:  ProblemTrustVerificationFailed,
		CodePermitProofMissing:       ProblemEvidenceInvalid,
		CodeDenialNotProven:          ProblemCapabilityDenialNotProven,
		CodeUnauthenticatedProof:     ProblemTrustVerificationFailed,
		CodeTransportFailure:         ProblemCapabilityTransportFailed,
		CodePermitDecisionMismatch:   ProblemEvidenceInvalid,
		CodeHostCheckFailed:          ProblemEvidenceInvalid,
		CodeWorkloadLoginFailed:      ProblemEvidenceInvalid,
		CodeNotApplicableCheckFailed: ProblemEvidenceInvalid,
		CodeUncertifiedNotApplicable: ProblemEvidenceInvalid,
	}
	if len(verificationErrorCodes) != len(want) {
		t.Fatalf("verificationErrorCodes=%d, want %d", len(verificationErrorCodes), len(want))
	}
	seen := make(map[ErrorCode]struct{}, len(verificationErrorCodes))
	for _, code := range verificationErrorCodes {
		if _, duplicate := seen[code]; duplicate {
			t.Fatalf("duplicate verification error code %q", code)
		}
		seen[code] = struct{}{}
		got, ok := StableProblemForErrorCode(code)
		if !ok || got != want[code] {
			t.Fatalf("StableProblemForErrorCode(%q)=(%q,%t), want (%q,true)", code, got, ok, want[code])
		}
	}
	if got, ok := StableProblemForErrorCode(ErrorCode("unknown_internal_code")); ok || got != "" {
		t.Fatalf("unknown internal code mapped to (%q,%t)", got, ok)
	}
}

func TestStableProblemMappingMatchesFrozenCapabilityProfile(t *testing.T) {
	payload, err := os.ReadFile(filepath.Join(repositoryRoot(t), "contracts/ports/v1/protocol-profiles.json"))
	if err != nil {
		t.Fatal(err)
	}
	var catalog struct {
		Profiles []struct {
			ProfileID    string `json:"profileId"`
			Requirements struct {
				FailureMapping map[string]string `json:"failureMapping"`
			} `json:"requirements"`
		} `json:"profiles"`
	}
	if err := json.Unmarshal(payload, &catalog); err != nil {
		t.Fatal(err)
	}
	var frozen map[string]string
	for _, profile := range catalog.Profiles {
		if profile.ProfileID == "bytedesk.capability-verification/1" {
			frozen = profile.Requirements.FailureMapping
			break
		}
	}
	if len(frozen) != len(verificationErrorCodes) {
		t.Fatalf("frozen failure mapping has %d entries, want %d", len(frozen), len(verificationErrorCodes))
	}
	for _, code := range verificationErrorCodes {
		want, ok := StableProblemForErrorCode(code)
		if !ok {
			t.Fatalf("internal error code %q is not mapped", code)
		}
		if got := frozen[string(code)]; got != string(want) {
			t.Fatalf("frozen failure mapping[%q]=%q, want %q", code, got, want)
		}
	}
}

func TestVerificationErrorCarriesStablePublicProblem(t *testing.T) {
	err := fail(CodeTransportFailure, "consumer verifier unavailable", errors.New("timeout"))
	var typed *VerificationError
	if !errors.As(err, &typed) {
		t.Fatalf("error=%v, want *VerificationError", err)
	}
	if typed.ProblemCode != ProblemCapabilityTransportFailed {
		t.Fatalf("ProblemCode=%q, want %q", typed.ProblemCode, ProblemCapabilityTransportFailed)
	}
}

func TestVerifyPromotionRequiresDistinctHostEvidencePhases(t *testing.T) {
	tests := []struct {
		name        string
		targetIndex int
		sourceIndex int
	}{
		{name: "candidate ready substituted for active readback", targetIndex: 2, sourceIndex: 0},
		{name: "active readback substituted for candidate ready", targetIndex: 0, sourceIndex: 2},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			copyEvidenceResults(t, &fixture.request.Evidence[test.targetIndex], fixture.request.Evidence[test.sourceIndex])
			fixture.reauthenticateEvidence(t)

			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, CodeInvalidContract)
		})
	}
}

func TestNewVerifierRequiresIndependentlyTrustedExactSchemaDigests(t *testing.T) {
	ctx := context.Background()
	base := filesystemSchemaResolver{root: repositoryRoot(t)}
	trusted := trustedSchemaDigests(t, base)
	proofs := &memoryProofResolver{documents: map[string][]byte{}}

	t.Run("exact baseline", func(t *testing.T) {
		if _, err := NewVerifier(ctx, base, proofs, cloneStrings(trusted)); err != nil {
			t.Fatal(err)
		}
	})
	t.Run("substituted relaxed schema", func(t *testing.T) {
		payload, err := base.ResolveSchema(ctx, CanaryPlanSchemaID)
		if err != nil {
			t.Fatal(err)
		}
		var root map[string]any
		if err := json.Unmarshal(payload, &root); err != nil {
			t.Fatal(err)
		}
		delete(root, "additionalProperties")
		delete(root, "unevaluatedProperties")
		resolver := substitutingSchemaResolver{base: base, id: CanaryPlanSchemaID, payload: marshalJSON(t, root)}
		_, err = NewVerifier(ctx, resolver, proofs, cloneStrings(trusted))
		assertErrorCode(t, err, CodeBindingMismatch)
	})
	t.Run("missing descriptor", func(t *testing.T) {
		digests := cloneStrings(trusted)
		delete(digests, CommonSchemaID)
		_, err := NewVerifier(ctx, base, proofs, digests)
		assertErrorCode(t, err, CodeInvalidInputs)
	})
	t.Run("unexpected descriptor", func(t *testing.T) {
		digests := cloneStrings(trusted)
		digests["https://schemas.bytedesk.ai/agent-delivery/v1/untrusted/1.0.0"] = digestA
		_, err := NewVerifier(ctx, base, proofs, digests)
		assertErrorCode(t, err, CodeInvalidInputs)
	})
}

func TestVerifyPromotionRejectsOverlongPlanWindow(t *testing.T) {
	fixture := newPromotionFixture(t, "required")
	mutateJSON(t, &fixture.request.Plan, "expiresAt", "2026-07-17T12:30:01Z")
	digest, err := CanonicalDigest(fixture.request.Plan)
	if err != nil {
		t.Fatal(err)
	}
	fixture.inputs.CurrentPlanDigest = digest

	_, err = fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	assertErrorCode(t, err, CodeStaleEvidence)
}

func TestActiveWindowCapsEveryCanaryObjectAtThirtyMinutes(t *testing.T) {
	now := time.Date(2026, 7, 17, 12, 15, 0, 0, time.UTC)
	if _, _, err := activeWindow("2026-07-17T12:00:00Z", "2026-07-17T12:30:00Z", now); err != nil {
		t.Fatal(err)
	}
	_, _, err := activeWindow("2026-07-17T12:00:00Z", "2026-07-17T12:30:00.000000001Z", now)
	assertErrorCode(t, err, CodeStaleEvidence)
}

func TestVerifyPromotionAcceptsIndependentlyCertifiedNotApplicable(t *testing.T) {
	fixture := newPromotionFixture(t, "certified_not_applicable")

	if _, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs); err != nil {
		t.Fatal(err)
	}
}

func TestVerifyPromotionFailsClosedOnAdversarialEvidence(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*promotionFixture)
		code   ErrorCode
	}{
		{
			name:   "mismatched current plan digest",
			mutate: func(f *promotionFixture) { f.inputs.CurrentPlanDigest = digestF },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched plan nonce",
			mutate: func(f *promotionFixture) { mutateJSON(t, &f.request.Evidence[1], "nonce", "different-nonce-0001") },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched target",
			mutate: func(f *promotionFixture) { mutateJSON(t, &f.request.Evidence[1], "targetId", "target-other") },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched current authority",
			mutate: func(f *promotionFixture) { f.inputs.CurrentAuthorityDigest = digestF },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched current policy",
			mutate: func(f *promotionFixture) { f.inputs.CurrentPolicyDigest = digestF },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched current grant set",
			mutate: func(f *promotionFixture) { f.inputs.CurrentGrantSetDigest = digestF },
			code:   CodeBindingMismatch,
		},
		{
			name:   "mismatched current workload identity",
			mutate: func(f *promotionFixture) { f.inputs.CurrentWorkloadIdentityDigest = digestF },
			code:   CodeBindingMismatch,
		},
		{
			name: "mismatched capability dispatch receipt",
			mutate: func(f *promotionFixture) {
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"capabilityDispatch", "receiptDigest"}, digestF)
			},
			code: CodeBindingMismatch,
		},
		{
			name: "wrong evidence actor identity",
			mutate: func(f *promotionFixture) {
				mutateJSON(t, &f.request.Evidence[1], "actorIdentity", "spiffe://consumer/wrong")
			},
			code: CodeSignerMismatch,
		},
		{
			name: "wrong evidence signer policy",
			mutate: func(f *promotionFixture) {
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"signerPolicy", "digest"}, digestF)
			},
			code: CodeSignerMismatch,
		},
		{
			name: "evidence is not independently authenticated",
			mutate: func(f *promotionFixture) {
				f.inputs.AuthenticatedEvidenceDigests = map[string]AuthenticatedVerificationRecord{}
			},
			code: CodeUnauthenticatedEvidence,
		},
		{
			name:   "permitted proof is missing",
			mutate: func(f *promotionFixture) { f.proofs.documents = map[string][]byte{} },
			code:   CodePermitProofMissing,
		},
		{
			name: "proof is not independently authenticated",
			mutate: func(f *promotionFixture) {
				f.inputs.AuthenticatedProofDigests = map[string]AuthenticatedVerificationRecord{}
			},
			code: CodeUnauthenticatedProof,
		},
		{
			name:   "proof nonce mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "nonce", "different-nonce-0001") },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof plan mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "planDigest", digestF) },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof target mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "targetId", "target-other") },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof candidate mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "candidateDigest", digestF) },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof policy mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "policyDigest", digestF) },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof grant mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "grantSetDigest", digestF) },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof workload identity mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "workloadIdentityDigest", digestF) },
			code:   CodeBindingMismatch,
		},
		{
			name:   "proof signer identity mismatch",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "signerIdentity", "spiffe://consumer/wrong") },
			code:   CodeSignerMismatch,
		},
		{
			name:   "stale proof",
			mutate: func(f *promotionFixture) { f.replaceProofField(t, "expiresAt", "2026-07-17T12:00:29Z") },
			code:   CodeStaleEvidence,
		},
		{
			name: "failed transport is not authorization denial",
			mutate: func(f *promotionFixture) {
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "outcome"}, "failed")
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "failureClass"}, "transport_error")
				deleteNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "decisionClass"})
				deleteNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "decisionCode"})
				deleteNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "authorizationDecisionProofDigest"})
			},
			code: CodeTransportFailure,
		},
		{
			name: "relabelled failed transport proof is invalid",
			mutate: func(f *promotionFixture) {
				f.replaceProofField(t, "transport", map[string]any{
					"authenticated": true, "completed": false, "parsed": true,
				})
			},
			code: CodeInvalidContract,
		},
		{
			name: "http 404 cannot be policy denial proof",
			mutate: func(f *promotionFixture) {
				f.replaceProofField(t, "transport", map[string]any{
					"outcome": "successful_authorization_response", "protocol": "https", "statusCode": 404,
					"authenticated": true, "completed": true, "parsed": true,
					"responseMediaType": "application/json", "responseDigest": digestA,
				})
			},
			code: CodeInvalidContract,
		},
		{
			name: "parser failure cannot be policy denial proof",
			mutate: func(f *promotionFixture) {
				f.replaceProofField(t, "transport", map[string]any{
					"outcome": "successful_authorization_response", "protocol": "https", "statusCode": 200,
					"authenticated": true, "completed": true, "parsed": false,
					"responseMediaType": "application/json", "responseDigest": digestA,
				})
			},
			code: CodeInvalidContract,
		},
		{
			name: "unavailable response cannot be policy denial proof",
			mutate: func(f *promotionFixture) {
				f.replaceProofField(t, "transport", map[string]any{
					"outcome": "unavailable", "protocol": "https", "statusCode": 200,
					"authenticated": true, "completed": true, "parsed": true,
					"responseMediaType": "application/json", "responseDigest": digestA,
				})
			},
			code: CodeInvalidContract,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			test.mutate(fixture)
			if test.code != CodeUnauthenticatedEvidence {
				fixture.reauthenticateEvidence(t)
			}
			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, test.code)
		})
	}
}

func TestVerifyPromotionRejectsWrongCheckPartitionAndDuplicateKeys(t *testing.T) {
	t.Run("host cannot report a capability check", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		mutateNestedJSON(t, &fixture.request.Evidence[0], []string{"results", "permitted_capability"}, map[string]any{"actual": "passed", "trace": trace()})
		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeInvalidContract)
	})

	t.Run("omitted host check", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		deleteNestedJSON(t, &fixture.request.Evidence[0], []string{"results", "file_inventory"})
		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeInvalidContract)
	})

	t.Run("duplicate object key", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		fixture.request.Evidence[0] = append(fixture.request.Evidence[0][:len(fixture.request.Evidence[0])-1], []byte(`,"actor":"consumer_capability_verifier"}`)...)
		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeInvalidContract)
	})
}

func TestVerifyPromotionRejectsUncertifiedNotApplicable(t *testing.T) {
	fixture := newPromotionFixture(t, "certified_not_applicable")
	fixture.inputs.AuthenticatedCertifications = map[string]TrustPolicyRef{}

	_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	assertErrorCode(t, err, CodeUncertifiedNotApplicable)
}

func TestVerifyPromotionRejectsNotApplicableCertificationPolicySubstitution(t *testing.T) {
	fixture := newPromotionFixture(t, "certified_not_applicable")
	fixture.inputs.AuthenticatedCertifications[digestC] = TrustPolicyRef{ID: "attacker-policy", Digest: digestF}

	_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	assertErrorCode(t, err, CodeUncertifiedNotApplicable)
}

func TestVerifyPromotionRequiresCurrentAuthorityDigest(t *testing.T) {
	fixture := newPromotionFixture(t, "required")
	fixture.inputs.CurrentAuthorityDigest = ""

	_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	assertErrorCode(t, err, CodeInvalidInputs)
}

func TestVerifyPromotionRequiresIndependentlyTrustedCapabilityDispatch(t *testing.T) {
	fixture := newPromotionFixture(t, "required")
	fixture.inputs.CurrentCapabilityDispatch = CapabilityDispatchBinding{}

	_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
	assertErrorCode(t, err, CodeInvalidInputs)
}

func TestVerifyPromotionRejectsFailedActualTechnicalCheck(t *testing.T) {
	tests := []struct {
		name          string
		evidenceIndex int
		check         string
	}{
		{name: "candidate ready", evidenceIndex: 0, check: "service_process"},
		{name: "active readback", evidenceIndex: 2, check: "active_pointer"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			mutateNestedJSON(t, &fixture.request.Evidence[test.evidenceIndex], []string{"results", test.check, "actual"}, "failed")
			fixture.reauthenticateEvidence(t)

			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, CodeHostCheckFailed)
		})
	}
}

func TestVerifyPromotionUsesSpecificCapabilityCheckFailures(t *testing.T) {
	t.Run("workload login", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		mutateNestedJSON(t, &fixture.request.Evidence[1], []string{"results", "workload_login", "actual"}, "failed")
		fixture.reauthenticateEvidence(t)

		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeWorkloadLoginFailed)
	})

	t.Run("certified not applicable", func(t *testing.T) {
		fixture := newPromotionFixture(t, "certified_not_applicable")
		mutateNestedJSON(t, &fixture.request.Evidence[1], []string{"results", "certified_not_applicable", "actual"}, "failed")
		fixture.reauthenticateEvidence(t)

		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeNotApplicableCheckFailed)
	})
}

func TestVerifyPromotionDistinguishesPermitAndDenialFailures(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(*promotionFixture)
		code    ErrorCode
		problem StableProblemCode
	}{
		{
			name: "missing permitted proof is invalid evidence",
			mutate: func(f *promotionFixture) {
				delete(f.proofs.documents, f.permittedProofDigest)
			},
			code:    CodePermitProofMissing,
			problem: ProblemEvidenceInvalid,
		},
		{
			name: "missing denied-sentinel proof is not a proven denial",
			mutate: func(f *promotionFixture) {
				delete(f.proofs.documents, f.deniedProofDigest)
			},
			code:    CodeDenialNotProven,
			problem: ProblemCapabilityDenialNotProven,
		},
		{
			name: "mismatched permitted result is invalid evidence",
			mutate: func(f *promotionFixture) {
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "permitted_capability", "decisionClass"}, "policy_denied")
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "permitted_capability", "decisionCode"}, "sentinel_denied")
			},
			code:    CodePermitDecisionMismatch,
			problem: ProblemEvidenceInvalid,
		},
		{
			name: "mismatched denied-sentinel result is not a proven denial",
			mutate: func(f *promotionFixture) {
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "decisionClass"}, "permitted")
				mutateNestedJSON(t, &f.request.Evidence[1], []string{"results", "denied_sentinel", "decisionCode"}, "allow_policy_match")
			},
			code:    CodeDenialNotProven,
			problem: ProblemCapabilityDenialNotProven,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			test.mutate(fixture)
			fixture.reauthenticateEvidence(t)

			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, test.code)
			assertStableProblemCode(t, err, test.problem)
		})
	}
}

func TestVerifyPromotionRejectsWrongAuthenticatedEvidenceSigner(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*AuthenticatedVerificationRecord)
	}{
		{name: "wrong identity", mutate: func(record *AuthenticatedVerificationRecord) { record.SignerIdentity = "spiffe://consumer/wrong" }},
		{name: "wrong policy", mutate: func(record *AuthenticatedVerificationRecord) {
			record.SignerPolicy = TrustPolicyRef{ID: "wrong-policy", Digest: digestF}
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			digest := fixture.evidenceDigest(t, "consumer_capability_verifier")
			record := fixture.inputs.AuthenticatedEvidenceDigests[digest]
			test.mutate(&record)
			fixture.inputs.AuthenticatedEvidenceDigests[digest] = record
			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, CodeSignerMismatch)
		})
	}
}

func TestVerifyPromotionRejectsWrongAuthenticatedProofSigner(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*AuthenticatedVerificationRecord)
	}{
		{name: "wrong identity", mutate: func(record *AuthenticatedVerificationRecord) { record.SignerIdentity = "spiffe://consumer/wrong" }},
		{name: "wrong policy", mutate: func(record *AuthenticatedVerificationRecord) {
			record.SignerPolicy = TrustPolicyRef{ID: "wrong-policy", Digest: digestF}
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newPromotionFixture(t, "required")
			record := fixture.inputs.AuthenticatedProofDigests[fixture.deniedProofDigest]
			test.mutate(&record)
			fixture.inputs.AuthenticatedProofDigests[fixture.deniedProofDigest] = record
			_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
			assertErrorCode(t, err, CodeSignerMismatch)
		})
	}
}

func TestVerifyPromotionRejectsIncompleteAuthenticationRecords(t *testing.T) {
	t.Run("evidence verification digest missing", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		digest := fixture.evidenceDigest(t, "host_reconciler")
		record := fixture.inputs.AuthenticatedEvidenceDigests[digest]
		record.VerificationEvidenceDigest = ""
		fixture.inputs.AuthenticatedEvidenceDigests[digest] = record
		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeUnauthenticatedEvidence)
	})
	t.Run("proof channel result missing", func(t *testing.T) {
		fixture := newPromotionFixture(t, "required")
		record := fixture.inputs.AuthenticatedProofDigests[fixture.permittedProofDigest]
		record.ChannelResult = ""
		fixture.inputs.AuthenticatedProofDigests[fixture.permittedProofDigest] = record
		_, err := fixture.verifier.VerifyPromotion(context.Background(), fixture.request, fixture.inputs)
		assertErrorCode(t, err, CodeUnauthenticatedProof)
	})
}

type promotionFixture struct {
	verifier             *Verifier
	proofs               *memoryProofResolver
	request              PromotionRequest
	inputs               CurrentInputs
	permittedProofDigest string
	deniedProofDigest    string
}

func newPromotionFixture(t *testing.T, capabilityMode string) *promotionFixture {
	t.Helper()
	ctx := context.Background()
	proofs := &memoryProofResolver{documents: map[string][]byte{}}
	resolver := filesystemSchemaResolver{root: repositoryRoot(t)}
	verifier, err := NewVerifier(ctx, resolver, proofs, trustedSchemaDigests(t, resolver))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 7, 17, 12, 0, 30, 0, time.UTC)
	plan := requiredPlan(verifier, capabilityMode)
	planBytes := marshalJSON(t, plan)
	planDigest, err := CanonicalDigest(planBytes)
	if err != nil {
		t.Fatal(err)
	}

	plan["schema"].(map[string]any)["digest"] = verifier.SchemaDigest(CanaryPlanSchemaID)
	planBytes = marshalJSON(t, plan)
	planDigest, err = CanonicalDigest(planBytes)
	if err != nil {
		t.Fatal(err)
	}

	candidateReadyEvidence := evidenceBase(verifier, "host_reconciler", planDigest)
	candidateReadyEvidence["evidenceId"] = "evidence-host-candidate-ready"
	candidateReadyEvidence["results"] = candidateReadyResults()
	candidateReadyBytes := marshalJSON(t, candidateReadyEvidence)

	activeReadbackEvidence := evidenceBase(verifier, "host_reconciler", planDigest)
	activeReadbackEvidence["evidenceId"] = "evidence-host-active-readback"
	activeReadbackEvidence["results"] = activeReadbackResults()
	activeReadbackBytes := marshalJSON(t, activeReadbackEvidence)

	capabilityEvidence := evidenceBase(verifier, "consumer_capability_verifier", planDigest)
	capabilityDispatch := CapabilityDispatchBinding{
		RequestDigest:               digestA,
		ReceiptDigest:               digestB,
		CheckProfileDigest:          digestC,
		AuthorizationDecisionDigest: digestF,
	}
	capabilityEvidence["capabilityDispatch"] = map[string]any{
		"requestDigest": capabilityDispatch.RequestDigest, "receiptDigest": capabilityDispatch.ReceiptDigest,
		"checkProfileDigest": capabilityDispatch.CheckProfileDigest, "authorizationDecisionDigest": capabilityDispatch.AuthorizationDecisionDigest,
	}
	var permittedDigest, deniedDigest string
	if capabilityMode == "required" {
		permittedProof := authorizationProof(verifier, planDigest, "capability.read", digestA, "permitted", "allow_policy_match")
		deniedProof := authorizationProof(verifier, planDigest, "capability.forbidden", digestB, "policy_denied", "sentinel_denied")
		permittedBytes := marshalJSON(t, permittedProof)
		deniedBytes := marshalJSON(t, deniedProof)
		permittedDigest, _ = CanonicalDigest(permittedBytes)
		deniedDigest, _ = CanonicalDigest(deniedBytes)
		proofs.documents[permittedDigest] = permittedBytes
		proofs.documents[deniedDigest] = deniedBytes
		capabilityEvidence["results"] = map[string]any{
			"mode":           "required",
			"workload_login": map[string]any{"actual": "passed", "trace": trace()},
			"permitted_capability": map[string]any{
				"outcome": "decision", "decisionClass": "permitted", "decisionCode": "allow_policy_match", "authorizationDecisionProofDigest": permittedDigest,
			},
			"denied_sentinel": map[string]any{
				"outcome": "decision", "decisionClass": "policy_denied", "decisionCode": "sentinel_denied", "authorizationDecisionProofDigest": deniedDigest,
			},
		}
	} else {
		capabilityEvidence["results"] = map[string]any{
			"mode": "certified_not_applicable",
			"certified_not_applicable": map[string]any{
				"actual": "not_applicable", "certificationDigest": digestC,
				"certificationPolicy": policyRef("capability-na-cert-v1", digestD), "trace": trace(),
			},
		}
	}
	capabilityBytes := marshalJSON(t, capabilityEvidence)
	candidateReadyDigest, _ := CanonicalDigest(candidateReadyBytes)
	activeReadbackDigest, _ := CanonicalDigest(activeReadbackBytes)
	capabilityDigest, _ := CanonicalDigest(capabilityBytes)
	inputs := CurrentInputs{
		CurrentPlanDigest:             planDigest,
		CurrentAuthorityDigest:        digestB,
		CurrentPolicyDigest:           digestC,
		CurrentGrantSetDigest:         digestD,
		CurrentWorkloadIdentityDigest: digestE,
		CurrentCapabilityDispatch:     capabilityDispatch,
		Now:                           now,
		EvidenceSigners: map[string]SignerExpectation{
			"host_reconciler":              {Identity: "spiffe://consumer/host", Policy: TrustPolicyRef{ID: "host-evidence-v1", Digest: digestA}},
			"consumer_capability_verifier": {Identity: "spiffe://consumer/capability-verifier", Policy: TrustPolicyRef{ID: "capability-evidence-v1", Digest: digestB}},
		},
		AuthorizationSigner: SignerExpectation{Identity: "spiffe://consumer/authorization", Policy: TrustPolicyRef{ID: "authorization-decision-v1", Digest: digestF}},
		AuthenticatedEvidenceDigests: map[string]AuthenticatedVerificationRecord{
			candidateReadyDigest: authenticatedRecord(SignerExpectation{Identity: "spiffe://consumer/host", Policy: TrustPolicyRef{ID: "host-evidence-v1", Digest: digestA}}, digestA),
			activeReadbackDigest: authenticatedRecord(SignerExpectation{Identity: "spiffe://consumer/host", Policy: TrustPolicyRef{ID: "host-evidence-v1", Digest: digestA}}, digestA),
			capabilityDigest:     authenticatedRecord(SignerExpectation{Identity: "spiffe://consumer/capability-verifier", Policy: TrustPolicyRef{ID: "capability-evidence-v1", Digest: digestB}}, digestB),
		},
		AuthenticatedProofDigests:   map[string]AuthenticatedVerificationRecord{},
		AuthenticatedCertifications: map[string]TrustPolicyRef{digestC: {ID: "capability-na-cert-v1", Digest: digestD}},
	}
	for digest := range proofs.documents {
		inputs.AuthenticatedProofDigests[digest] = authenticatedRecord(inputs.AuthorizationSigner, digestC)
	}
	return &promotionFixture{verifier: verifier, proofs: proofs, request: PromotionRequest{Plan: planBytes, Evidence: [][]byte{candidateReadyBytes, capabilityBytes, activeReadbackBytes}}, inputs: inputs, permittedProofDigest: permittedDigest, deniedProofDigest: deniedDigest}
}

func requiredPlan(verifier *Verifier, capabilityMode string) map[string]any {
	capability := map[string]any{
		"mode":                "required",
		"checks":              map[string]any{"workload_login": "passed", "permitted_capability": "permitted", "denied_sentinel": "policy_denied"},
		"permittedCapability": map[string]any{"id": "capability.read", "digest": digestA},
		"deniedSentinel":      map[string]any{"id": "capability.forbidden", "digest": digestB, "expectedDecisionCode": "sentinel_denied"},
	}
	if capabilityMode == "certified_not_applicable" {
		capability = map[string]any{
			"mode":                "certified_not_applicable",
			"checks":              map[string]any{"certified_not_applicable": "not_applicable"},
			"certificationDigest": digestC,
			"certificationPolicy": policyRef("capability-na-cert-v1", digestD),
		}
	}
	return map[string]any{
		"contract": "bytedesk.canary-plan/1", "schema": schemaHeader(CanaryPlanSchemaID, verifier.SchemaDigest(CanaryPlanSchemaID)),
		"planId": "canary-plan-01", "rolloutId": "rollout-01", "nonce": "canary-nonce-0001",
		"candidateDigest": digestA, "desiredRevisionDigest": digestB, "releaseDigest": digestC, "deploymentDigest": digestD,
		"consumerId": "consumer-01", "subjectId": "agent-01", "targetId": "target-01", "slotId": "slot-01", "generation": 7,
		"activationMode": "isolated_candidate", "authorityDigest": digestB, "policyDigest": digestC,
		"grantSetDigest": digestD, "workloadIdentityDigest": digestE,
		"expectedChecks": map[string]any{"host_reconciler": expectedHostChecks(), "consumer_capability_verifier": capability},
		"evidenceSignerPolicies": map[string]any{
			"host_reconciler":              policyRef("host-evidence-v1", digestA),
			"consumer_capability_verifier": policyRef("capability-evidence-v1", digestB),
			"authorization_decision":       policyRef("authorization-decision-v1", digestF),
		},
		"issuedAt": "2026-07-17T12:00:00Z", "expiresAt": "2026-07-17T12:05:00Z",
	}
}

func evidenceBase(verifier *Verifier, actor, planDigest string) map[string]any {
	identity := "spiffe://consumer/host"
	policy := policyRef("host-evidence-v1", digestA)
	if actor == "consumer_capability_verifier" {
		identity = "spiffe://consumer/capability-verifier"
		policy = policyRef("capability-evidence-v1", digestB)
	}
	return map[string]any{
		"contract": "bytedesk.canary-evidence/1", "schema": schemaHeader(CanaryEvidenceSchemaID, verifier.SchemaDigest(CanaryEvidenceSchemaID)),
		"evidenceId": "evidence-" + actor, "actor": actor, "rolloutId": "rollout-01", "planDigest": planDigest, "nonce": "canary-nonce-0001",
		"candidateDigest": digestA, "desiredRevisionDigest": digestB, "releaseDigest": digestC, "deploymentDigest": digestD,
		"consumerId": "consumer-01", "subjectId": "agent-01", "targetId": "target-01", "slotId": "slot-01", "generation": 7,
		"authorityDigest": digestB, "policyDigest": digestC, "grantSetDigest": digestD, "workloadIdentityDigest": digestE,
		"actorIdentity": identity, "actorVersion": "1.0.0", "signerPolicy": policy,
		"issuedAt": "2026-07-17T12:00:20Z", "expiresAt": "2026-07-17T12:04:00Z", "trace": trace(),
	}
}

func authorizationProof(verifier *Verifier, planDigest, capabilityID, capabilityDigest, decisionClass, decisionCode string) map[string]any {
	return map[string]any{
		"contract": "bytedesk.authorization-decision-proof/1", "schema": schemaHeader(AuthorizationDecisionProofSchemaID, verifier.SchemaDigest(AuthorizationDecisionProofSchemaID)),
		"proofId": "proof-" + capabilityID, "actor": "consumer_authorization_system", "planDigest": planDigest, "nonce": "canary-nonce-0001",
		"consumerId": "consumer-01", "subjectId": "agent-01", "targetId": "target-01", "candidateDigest": digestA, "releaseDigest": digestC, "deploymentDigest": digestD,
		"capability":   map[string]any{"id": capabilityID, "digest": capabilityDigest},
		"policyDigest": digestC, "grantSetDigest": digestD, "workloadIdentityDigest": digestE,
		"decision":       map[string]any{"class": decisionClass, "code": decisionCode},
		"signerIdentity": "spiffe://consumer/authorization", "signerPolicy": policyRef("authorization-decision-v1", digestF),
		"transport": map[string]any{"outcome": "successful_authorization_response", "protocol": "https", "statusCode": 200, "authenticated": true, "completed": true, "parsed": true, "responseMediaType": "application/json", "responseDigest": digestA},
		"issuedAt":  "2026-07-17T12:00:25Z", "expiresAt": "2026-07-17T12:03:00Z", "trace": trace(),
	}
}

func expectedHostChecks() map[string]any {
	return map[string]any{
		"candidate_ready": map[string]any{
			"artifact_readback": "passed", "file_inventory": "passed", "slot_generation": "passed",
			"service_process": "passed", "resource_thresholds": "passed", "harness_readiness": "passed",
		},
		"active_readback": map[string]any{
			"switch_marker": "passed", "active_pointer": "passed", "file_inventory": "passed", "service_process": "passed",
		},
	}
}
func candidateReadyResults() map[string]any {
	return map[string]any{
		"phase":               "candidate_ready",
		"artifact_readback":   technicalResult("passed"),
		"file_inventory":      technicalResult("passed"),
		"slot_generation":     technicalResult("passed"),
		"service_process":     technicalResult("passed"),
		"resource_thresholds": technicalResult("passed"),
		"harness_readiness":   technicalResult("passed"),
	}
}
func activeReadbackResults() map[string]any {
	return map[string]any{
		"phase":           "active_readback",
		"switch_marker":   technicalResult("passed"),
		"active_pointer":  technicalResult("passed"),
		"file_inventory":  technicalResult("passed"),
		"service_process": technicalResult("passed"),
	}
}
func technicalResult(actual string) map[string]any {
	return map[string]any{"actual": actual, "trace": trace()}
}
func trace() map[string]any {
	return map[string]any{"digest": digestA, "classification": "consumer-private"}
}
func policyRef(id, digest string) map[string]any { return map[string]any{"id": id, "digest": digest} }
func schemaHeader(id, digest string) map[string]any {
	return map[string]any{"id": id, "digest": digest}
}

func (f *promotionFixture) replaceProofField(t *testing.T, field string, value any) {
	t.Helper()
	oldDigest := f.deniedProofDigest
	document, ok := f.proofs.documents[oldDigest]
	if !ok {
		t.Fatalf("denied proof %s is missing", oldDigest)
	}
	mutateJSON(t, &document, field, value)
	newDigest, err := CanonicalDigest(document)
	if err != nil {
		t.Fatal(err)
	}
	delete(f.proofs.documents, oldDigest)
	f.proofs.documents[newDigest] = document
	delete(f.inputs.AuthenticatedProofDigests, oldDigest)
	f.inputs.AuthenticatedProofDigests[newDigest] = authenticatedRecord(f.inputs.AuthorizationSigner, digestC)
	f.deniedProofDigest = newDigest
	for index := range f.request.Evidence {
		var root map[string]any
		_ = json.Unmarshal(f.request.Evidence[index], &root)
		results, _ := root["results"].(map[string]any)
		item, _ := results["denied_sentinel"].(map[string]any)
		if item["authorizationDecisionProofDigest"] == oldDigest {
			item["authorizationDecisionProofDigest"] = newDigest
		}
		f.request.Evidence[index] = marshalJSON(t, root)
	}
	f.reauthenticateEvidence(t)
}

func (f *promotionFixture) reauthenticateEvidence(t *testing.T) {
	t.Helper()
	f.inputs.AuthenticatedEvidenceDigests = make(map[string]AuthenticatedVerificationRecord, len(f.request.Evidence))
	for _, document := range f.request.Evidence {
		digest, err := CanonicalDigest(document)
		if err != nil {
			t.Fatal(err)
		}
		var root map[string]any
		if err := json.Unmarshal(document, &root); err != nil {
			t.Fatal(err)
		}
		actor, _ := root["actor"].(string)
		f.inputs.AuthenticatedEvidenceDigests[digest] = authenticatedRecord(f.inputs.EvidenceSigners[actor], digestA)
	}
}

func (f *promotionFixture) evidenceDigest(t *testing.T, actor string) string {
	t.Helper()
	for _, document := range f.request.Evidence {
		var root map[string]any
		if err := json.Unmarshal(document, &root); err != nil {
			t.Fatal(err)
		}
		if root["actor"] == actor {
			digest, err := CanonicalDigest(document)
			if err != nil {
				t.Fatal(err)
			}
			return digest
		}
	}
	t.Fatalf("evidence actor %s not found", actor)
	return ""
}

func authenticatedRecord(signer SignerExpectation, verificationDigest string) AuthenticatedVerificationRecord {
	return AuthenticatedVerificationRecord{SignerIdentity: signer.Identity, SignerPolicy: signer.Policy, VerificationEvidenceDigest: verificationDigest, ChannelResult: ChannelSignatureVerified}
}

func assertErrorCode(t *testing.T, err error, expected ErrorCode) {
	t.Helper()
	var typed *VerificationError
	if !errors.As(err, &typed) || typed.Code != expected {
		t.Fatalf("error=%v, want code %s", err, expected)
	}
	wantProblem, ok := StableProblemForErrorCode(expected)
	if !ok {
		t.Fatalf("test expected unmapped internal error code %q", expected)
	}
	if typed.ProblemCode != wantProblem {
		t.Fatalf("error=%v has stable problem code %q, want %q", err, typed.ProblemCode, wantProblem)
	}
}

func assertStableProblemCode(t *testing.T, err error, expected StableProblemCode) {
	t.Helper()
	var typed *VerificationError
	if !errors.As(err, &typed) || typed.ProblemCode != expected {
		t.Fatalf("error=%v, want stable problem code %s", err, expected)
	}
}

func marshalJSON(t *testing.T, value any) []byte {
	t.Helper()
	payload, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return payload
}
func mutateJSON(t *testing.T, payload *[]byte, key string, value any) {
	t.Helper()
	var root map[string]any
	if err := json.Unmarshal(*payload, &root); err != nil {
		t.Fatal(err)
	}
	root[key] = value
	*payload = marshalJSON(t, root)
}
func mutateNestedJSON(t *testing.T, payload *[]byte, path []string, value any) {
	t.Helper()
	var root map[string]any
	if err := json.Unmarshal(*payload, &root); err != nil {
		t.Fatal(err)
	}
	current := root
	for _, key := range path[:len(path)-1] {
		current = current[key].(map[string]any)
	}
	current[path[len(path)-1]] = value
	*payload = marshalJSON(t, root)
}
func deleteNestedJSON(t *testing.T, payload *[]byte, path []string) {
	t.Helper()
	var root map[string]any
	if err := json.Unmarshal(*payload, &root); err != nil {
		t.Fatal(err)
	}
	current := root
	for _, key := range path[:len(path)-1] {
		current = current[key].(map[string]any)
	}
	delete(current, path[len(path)-1])
	*payload = marshalJSON(t, root)
}

func copyEvidenceResults(t *testing.T, target *[]byte, source []byte) {
	t.Helper()
	var targetRoot map[string]any
	if err := json.Unmarshal(*target, &targetRoot); err != nil {
		t.Fatal(err)
	}
	var sourceRoot map[string]any
	if err := json.Unmarshal(source, &sourceRoot); err != nil {
		t.Fatal(err)
	}
	targetRoot["results"] = sourceRoot["results"]
	*target = marshalJSON(t, targetRoot)
}

type filesystemSchemaResolver struct{ root string }

func (r filesystemSchemaResolver) ResolveSchema(_ context.Context, id string) ([]byte, error) {
	name := map[string]string{CommonSchemaID: "common.schema.json", CanaryPlanSchemaID: "canary-plan.schema.json", CanaryEvidenceSchemaID: "canary-evidence.schema.json", AuthorizationDecisionProofSchemaID: "authorization-decision-proof.schema.json"}[id]
	if name == "" {
		return nil, os.ErrNotExist
	}
	return os.ReadFile(filepath.Join(r.root, "contracts/schemas/v1", name))
}

type memoryProofResolver struct{ documents map[string][]byte }

func (r *memoryProofResolver) ResolveAuthorizationDecisionProof(_ context.Context, digest string) ([]byte, error) {
	payload, ok := r.documents[digest]
	if !ok {
		return nil, os.ErrNotExist
	}
	return append([]byte(nil), payload...), nil
}

type substitutingSchemaResolver struct {
	base    SchemaResolver
	id      string
	payload []byte
}

func (r substitutingSchemaResolver) ResolveSchema(ctx context.Context, id string) ([]byte, error) {
	if id == r.id {
		return append([]byte(nil), r.payload...), nil
	}
	return r.base.ResolveSchema(ctx, id)
}

func repositoryRoot(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	return root
}

func cloneStrings(input map[string]string) map[string]string {
	result := make(map[string]string, len(input))
	for key, value := range input {
		result[key] = value
	}
	return result
}

func trustedSchemaDigests(t *testing.T, resolver SchemaResolver) map[string]string {
	t.Helper()
	result := make(map[string]string, 4)
	for _, id := range []string{CommonSchemaID, CanaryPlanSchemaID, CanaryEvidenceSchemaID, AuthorizationDecisionProofSchemaID} {
		payload, err := resolver.ResolveSchema(context.Background(), id)
		if err != nil {
			t.Fatal(err)
		}
		digest, err := CanonicalDigest(payload)
		if err != nil {
			t.Fatal(err)
		}
		result[id] = digest
	}
	return result
}
