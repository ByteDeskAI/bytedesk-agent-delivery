package canonical

import "errors"

// ErrorCode is a stable, content-free parser or canonicalization failure.
type ErrorCode string

const (
	CodeInputReadFailed   ErrorCode = "input_read_failed"
	CodeInputTooLarge     ErrorCode = "input_too_large"
	CodeCanonicalTooLarge ErrorCode = "canonical_too_large"
	CodeInvalidLimits     ErrorCode = "invalid_limits"
	CodeUnsupportedFormat ErrorCode = "unsupported_format"
	CodeEmptyInput        ErrorCode = "empty_input"
	CodeInvalidUTF8       ErrorCode = "invalid_utf8"
	CodeInvalidUnicode    ErrorCode = "invalid_unicode"
	CodeInvalidJSON       ErrorCode = "invalid_json"
	CodeInvalidYAML       ErrorCode = "invalid_yaml"
	CodeMultipleDocuments ErrorCode = "multiple_documents"
	CodeDuplicateKey      ErrorCode = "duplicate_key"
	CodeAliasForbidden    ErrorCode = "alias_forbidden"
	CodeUnsupportedTag    ErrorCode = "unsupported_tag"
	CodeUnsupportedNode   ErrorCode = "unsupported_node"
	CodeNonStringKey      ErrorCode = "non_string_key"
	CodeInvalidNumber     ErrorCode = "invalid_number"
	CodeDepthExceeded     ErrorCode = "depth_exceeded"
	CodeNodeLimitExceeded ErrorCode = "node_limit_exceeded"
)

// Error deliberately excludes parser text and input values from Error().
// Callers may safely expose the stable code without echoing untrusted content.
type Error struct {
	code ErrorCode
}

func (e *Error) Error() string { return string(e.code) }

// Code reports the stable failure code.
func (e *Error) Code() ErrorCode { return e.code }

func fail(code ErrorCode) error { return &Error{code: code} }

// CodeOf extracts a stable canonicalization code or returns the empty string
// for an error not created by this package.
func CodeOf(err error) ErrorCode {
	var target *Error
	if errors.As(err, &target) {
		return target.code
	}
	return ""
}
