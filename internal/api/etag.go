package api

import (
	"fmt"
	"regexp"
	"strconv"
)

var strongETagPattern = regexp.MustCompile(`^"([1-9][0-9]*)-(sha256:[0-9a-f]{64})"$`)

// strongETag encodes a TargetDeliveryState revision+digest as a strong ETag.
// The digest is embedded (not just the revision) so a client cannot forge a
// valid-looking ETag for a revision it never actually observed.
func strongETag(revision int64, digest string) string {
	return fmt.Sprintf("%q", fmt.Sprintf("%d-%s", revision, digest))
}

// parseStrongETag reverses strongETag. Weak ETags (W/"...") and any
// non-exact format are rejected - only a strong, exact revision-digest pair
// is an acceptable If-Match precondition.
func parseStrongETag(value string) (revision int64, digest string, ok bool) {
	match := strongETagPattern.FindStringSubmatch(value)
	if match == nil {
		return 0, "", false
	}
	revision, err := strconv.ParseInt(match[1], 10, 64)
	if err != nil {
		return 0, "", false
	}
	return revision, match[2], true
}
