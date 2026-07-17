// Package canonical parses the accepted contract JSON or restricted YAML
// authoring syntax into one JSON data model and emits RFC 8785 JCS bytes.
//
// This package performs encoding validation and resource enforcement. Schema
// and policy validation remain separate mandatory gates before its output can
// become authority.
package canonical

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"math"
	"unicode/utf16"
)

const (
	defaultMaxBytes = int64(4 << 20)
	defaultMaxDepth = 64
	defaultMaxNodes = 100_000
)

// Format selects a parser explicitly. Content sniffing is intentionally not
// supported because the selected contract parser is security-relevant.
type Format string

const (
	FormatJSON Format = "json"
	FormatYAML Format = "yaml"
)

// Limits bounds untrusted structured input and its canonical result. Zero
// values select the accepted defaults; negative values are invalid.
type Limits struct {
	MaxInputBytes     int64
	MaxCanonicalBytes int64
	MaxDepth          int
	MaxNodes          int
}

// DefaultLimits returns the accepted v1 operational parser profile.
func DefaultLimits() Limits {
	return Limits{
		MaxInputBytes:     defaultMaxBytes,
		MaxCanonicalBytes: defaultMaxBytes,
		MaxDepth:          defaultMaxDepth,
		MaxNodes:          defaultMaxNodes,
	}
}

// Result binds the canonical JSON bytes to their semantic SHA-256 identity.
type Result struct {
	Bytes  []byte
	Digest string
}

// Canonicalize reads one bounded input document and canonicalizes it.
func Canonicalize(reader io.Reader, format Format, limits Limits) (Result, error) {
	limits, err := normalizeLimits(limits)
	if err != nil {
		return Result{}, err
	}
	if reader == nil {
		return Result{}, fail(CodeInputReadFailed)
	}

	input, err := io.ReadAll(io.LimitReader(reader, limits.MaxInputBytes+1))
	if err != nil {
		return Result{}, fail(CodeInputReadFailed)
	}
	if int64(len(input)) > limits.MaxInputBytes {
		return Result{}, fail(CodeInputTooLarge)
	}
	return canonicalize(input, format, limits)
}

// CanonicalizeBytes canonicalizes one already materialized, bounded document.
func CanonicalizeBytes(input []byte, format Format, limits Limits) (Result, error) {
	limits, err := normalizeLimits(limits)
	if err != nil {
		return Result{}, err
	}
	if int64(len(input)) > limits.MaxInputBytes {
		return Result{}, fail(CodeInputTooLarge)
	}
	return canonicalize(input, format, limits)
}

func canonicalize(input []byte, format Format, limits Limits) (Result, error) {
	var (
		root *value
		err  error
	)
	switch format {
	case FormatJSON:
		root, err = parseJSON(input, limits)
	case FormatYAML:
		root, err = parseYAML(input, limits)
	default:
		return Result{}, fail(CodeUnsupportedFormat)
	}
	if err != nil {
		return Result{}, err
	}

	encoded, err := encodeCanonical(root, limits.MaxCanonicalBytes)
	if err != nil {
		return Result{}, err
	}
	sum := sha256.Sum256(encoded)
	return Result{
		Bytes:  encoded,
		Digest: "sha256:" + hex.EncodeToString(sum[:]),
	}, nil
}

func normalizeLimits(limits Limits) (Limits, error) {
	if limits.MaxInputBytes < 0 || limits.MaxCanonicalBytes < 0 || limits.MaxDepth < 0 || limits.MaxNodes < 0 {
		return Limits{}, fail(CodeInvalidLimits)
	}
	if limits.MaxInputBytes == 0 {
		limits.MaxInputBytes = defaultMaxBytes
	}
	if limits.MaxCanonicalBytes == 0 {
		limits.MaxCanonicalBytes = defaultMaxBytes
	}
	if limits.MaxDepth == 0 {
		limits.MaxDepth = defaultMaxDepth
	}
	if limits.MaxNodes == 0 {
		limits.MaxNodes = defaultMaxNodes
	}
	if limits.MaxInputBytes == math.MaxInt64 ||
		limits.MaxInputBytes > defaultMaxBytes ||
		limits.MaxCanonicalBytes > defaultMaxBytes ||
		limits.MaxDepth > defaultMaxDepth ||
		limits.MaxNodes > defaultMaxNodes {
		return Limits{}, fail(CodeInvalidLimits)
	}
	return limits, nil
}

type valueKind uint8

const (
	kindNull valueKind = iota
	kindBool
	kindNumber
	kindString
	kindArray
	kindObject
)

type value struct {
	kind    valueKind
	boolean bool
	number  float64
	text    string
	array   []*value
	object  []member
}

type member struct {
	name    string
	sortKey []uint16
	value   *value
}

func newMember(name string, item *value) member {
	return member{name: name, sortKey: utf16.Encode([]rune(name)), value: item}
}

type budget struct {
	limits Limits
	nodes  int
}

func (b *budget) value(depth int) error {
	if depth > b.limits.MaxDepth {
		return fail(CodeDepthExceeded)
	}
	return b.node()
}

func (b *budget) node() error {
	if b.nodes >= b.limits.MaxNodes {
		return fail(CodeNodeLimitExceeded)
	}
	b.nodes++
	return nil
}
