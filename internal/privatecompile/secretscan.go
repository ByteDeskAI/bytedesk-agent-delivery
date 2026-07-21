package privatecompile

import (
	"encoding/json"
	"errors"
	"regexp"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

// ErrRawSecretDetected is returned when a proposed private customization
// patch embeds a value shaped like a reusable secret rather than a secret
// reference - the AD-13 acceptance criterion "No private key, bearer/
// refresh token, provider credential, certificate, or reusable secret is
// present" applies to every functional customization value, not only to a
// dedicated authority field (agent-spec and renderer-functional-config
// documents structurally never contain an authority plane at all, per
// contracts/schemas/v1/functional-customization-profile.schema.json's
// authorityPlanePresent: false).
var ErrRawSecretDetected = errors.New("privatecompile: raw secret value rejected, use a secret reference")

var rawSecretPatterns = []*regexp.Regexp{
	regexp.MustCompile(`-----BEGIN [A-Z ]*PRIVATE KEY-----`),
	regexp.MustCompile(`AKIA[0-9A-Z]{16}`),                                            // AWS access key id
	regexp.MustCompile(`gh[pousr]_[A-Za-z0-9]{20,}`),                                  // GitHub tokens
	regexp.MustCompile(`sk-[A-Za-z0-9]{20,}`),                                         // OpenAI-shaped secret key
	regexp.MustCompile(`xox[baprs]-[A-Za-z0-9-]{10,}`),                                // Slack tokens
	regexp.MustCompile(`^[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{10,}$`), // JWT-shaped
	regexp.MustCompile(`(?i)bearer\s+[A-Za-z0-9._-]{16,}`),
}

// ScanValueForRawSecret reports ErrRawSecretDetected if s matches any known
// reusable-secret shape.
func ScanValueForRawSecret(s string) error {
	for _, pattern := range rawSecretPatterns {
		if pattern.MatchString(s) {
			return ErrRawSecretDetected
		}
	}
	return nil
}

// ScanPatchForRawSecrets rejects a functional customization JSON Patch if
// any operation's value contains a string shaped like a reusable secret,
// at any nesting depth.
func ScanPatchForRawSecrets(patch operations.JSONPatch) error {
	for _, op := range patch.Operations {
		if len(op.Value) == 0 {
			continue
		}
		var decoded any
		if err := json.Unmarshal(op.Value, &decoded); err != nil {
			// Not decodable JSON is rejected by the patch applier itself;
			// scanning is best-effort here and does not need to duplicate
			// that error.
			continue
		}
		if err := scanDecodedValue(decoded); err != nil {
			return err
		}
	}
	return nil
}

func scanDecodedValue(value any) error {
	switch v := value.(type) {
	case string:
		return ScanValueForRawSecret(v)
	case []any:
		for _, item := range v {
			if err := scanDecodedValue(item); err != nil {
				return err
			}
		}
	case map[string]any:
		for _, item := range v {
			if err := scanDecodedValue(item); err != nil {
				return err
			}
		}
	}
	return nil
}
