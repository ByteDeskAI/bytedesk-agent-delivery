package privatecompile

import (
	"errors"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

func TestScanValueForRawSecretDetectsKnownShapes(t *testing.T) {
	cases := []string{
		"-----BEGIN RSA PRIVATE KEY-----\nMIIB...",
		"AKIAABCDEFGHIJKLMNOP",
		"ghp_abcdefghijklmnopqrstuvwxyz0123456789",
		"sk-abcdefghijklmnopqrstuvwxyz012345",
		"xoxb-1234567890-abcdefghij",
		"Bearer abcdefghijklmnopqrstuvwx",
	}
	for _, s := range cases {
		if err := ScanValueForRawSecret(s); !errors.Is(err, ErrRawSecretDetected) {
			t.Errorf("value %q: expected ErrRawSecretDetected, got %v", s, err)
		}
	}
}

func TestScanValueForRawSecretAllowsOrdinaryValues(t *testing.T) {
	cases := []string{
		"gpt-5",
		"customer-support-assistant",
		"secretRef:vault://consumer-1/api-key",
		"",
	}
	for _, s := range cases {
		if err := ScanValueForRawSecret(s); err != nil {
			t.Errorf("value %q: expected no error, got %v", s, err)
		}
	}
}

func TestScanPatchForRawSecretsRejectsNestedSecret(t *testing.T) {
	patch := operations.JSONPatch{
		Profile: "bytedesk.json-patch/1",
		Operations: []operations.PatchOperation{
			{Op: "add", Path: "/tools/0/config", Value: []byte(`{"apiKey":"AKIAABCDEFGHIJKLMNOP"}`)},
		},
	}
	if err := ScanPatchForRawSecrets(patch); !errors.Is(err, ErrRawSecretDetected) {
		t.Fatalf("expected ErrRawSecretDetected, got %v", err)
	}
}

func TestScanPatchForRawSecretsAllowsSecretReference(t *testing.T) {
	patch := operations.JSONPatch{
		Profile: "bytedesk.json-patch/1",
		Operations: []operations.PatchOperation{
			{Op: "add", Path: "/tools/0/config", Value: []byte(`{"apiKeyRef":"vault://consumer-1/api-key"}`)},
		},
	}
	if err := ScanPatchForRawSecrets(patch); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
