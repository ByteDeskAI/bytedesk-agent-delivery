package scmintake

import (
	"errors"
	"strings"
	"testing"
)

func TestValidateCommitRefAcceptsFullLowercaseSHA(t *testing.T) {
	if err := ValidateCommitRef(strings.Repeat("a", 40)); err != nil {
		t.Fatalf("expected a full lowercase 40-hex SHA to be accepted, got %v", err)
	}
}

func TestValidateCommitRefRejectsMutableRefs(t *testing.T) {
	cases := []string{
		"main",
		"refs/heads/main",
		"v1.0.0",
		"HEAD",
		"latest",
		strings.Repeat("a", 7),  // abbreviated SHA
		strings.Repeat("A", 40), // uppercase is not the canonical form
		strings.Repeat("g", 40), // non-hex characters
		"",
	}
	for _, ref := range cases {
		if err := ValidateCommitRef(ref); !errors.Is(err, ErrMutableRef) {
			t.Errorf("ref %q: expected ErrMutableRef, got %v", ref, err)
		}
	}
}

func TestRepositoryIdentityRequiresNumericID(t *testing.T) {
	cases := []struct {
		name string
		id   RepositoryIdentity
		ok   bool
	}{
		{"valid", RepositoryIdentity{Provider: "github", NumericID: 12345, Name: "bytedesk/agent-delivery"}, true},
		{"missing numeric id", RepositoryIdentity{Provider: "github", NumericID: 0, Name: "bytedesk/agent-delivery"}, false},
		{"negative numeric id", RepositoryIdentity{Provider: "github", NumericID: -1, Name: "bytedesk/agent-delivery"}, false},
		{"name only, no provider", RepositoryIdentity{NumericID: 12345, Name: "bytedesk/agent-delivery"}, false},
		{"missing name", RepositoryIdentity{Provider: "github", NumericID: 12345}, false},
	}
	for _, tc := range cases {
		err := tc.id.Validate()
		if tc.ok && err != nil {
			t.Errorf("%s: expected valid, got %v", tc.name, err)
		}
		if !tc.ok && !errors.Is(err, ErrRepositoryIdentityInvalid) {
			t.Errorf("%s: expected ErrRepositoryIdentityInvalid, got %v", tc.name, err)
		}
	}
}
