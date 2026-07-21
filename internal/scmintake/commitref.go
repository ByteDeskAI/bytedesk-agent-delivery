package scmintake

import (
	"errors"
	"regexp"
)

// ErrMutableRef is returned when a caller-supplied Git reference is not an
// exact, full commit SHA - the AD-11 acceptance criterion "mutable tags are
// rejected as desired-state identity; exact digests are required" applies
// equally to any symbolic ref (branch name, tag, "HEAD", short SHA).
var ErrMutableRef = errors.New("scmintake: mutable ref rejected, exact commit SHA required")

var fullCommitSHA = regexp.MustCompile(`^[0-9a-f]{40}$`)

// ValidateCommitRef accepts only an exact, full, lowercase 40-hex-character
// Git commit SHA. Anything else - branch names, tags, "latest", "HEAD",
// abbreviated SHAs - is rejected as mutable/ambiguous identity.
func ValidateCommitRef(ref string) error {
	if !fullCommitSHA.MatchString(ref) {
		return ErrMutableRef
	}
	return nil
}

// ErrRepositoryIdentityInvalid is returned when a repository is identified
// only by name, without the numeric provider-assigned repository ID AD-11
// requires ("repository name alone is not authority").
var ErrRepositoryIdentityInvalid = errors.New("scmintake: numeric repository identity required")

// RepositoryIdentity is the exact repository authority AD-11 requires:
// a provider-assigned numeric ID (immutable even across a rename) plus the
// human-readable name for display only.
type RepositoryIdentity struct {
	Provider  string
	NumericID int64
	Name      string
}

// Validate rejects any RepositoryIdentity missing its numeric ID, provider,
// or name - a repository name alone is never sufficient authority.
func (r RepositoryIdentity) Validate() error {
	if r.Provider == "" || r.Name == "" || r.NumericID <= 0 {
		return ErrRepositoryIdentityInvalid
	}
	return nil
}
