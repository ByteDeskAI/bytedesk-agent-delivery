package canonical_test

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
	"github.com/gowebpki/jcs"
)

const fixtureRoot = "../../../contracts/fixtures/encoding"

func TestEquivalentJSONAndYAMLHaveOneIdentity(t *testing.T) {
	t.Parallel()

	jsonInput := readFixture(t, "positive/equivalent.json")
	yamlInput := readFixture(t, "positive/equivalent.yaml")
	wantCanonical := readJCSFixture(t, "positive/equivalent.jcs.hex")
	wantDigest := strings.TrimSpace(string(readFixture(t, "positive/equivalent.sha256")))

	jsonResult, err := canonical.CanonicalizeBytes(jsonInput, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("canonicalize JSON: %v", err)
	}
	yamlResult, err := canonical.CanonicalizeBytes(yamlInput, canonical.FormatYAML, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("canonicalize YAML: %v", err)
	}

	if !bytes.Equal(jsonResult.Bytes, wantCanonical) {
		t.Fatalf("JSON canonical bytes\n got: %q\nwant: %q", jsonResult.Bytes, wantCanonical)
	}
	if !bytes.Equal(yamlResult.Bytes, wantCanonical) {
		t.Fatalf("YAML canonical bytes\n got: %q\nwant: %q", yamlResult.Bytes, wantCanonical)
	}
	if jsonResult.Digest != wantDigest || yamlResult.Digest != wantDigest {
		t.Fatalf("digest mismatch: JSON=%q YAML=%q want=%q", jsonResult.Digest, yamlResult.Digest, wantDigest)
	}
	if jsonResult.Digest != yamlResult.Digest {
		t.Fatalf("equivalent inputs differ: JSON=%q YAML=%q", jsonResult.Digest, yamlResult.Digest)
	}
}

func TestRFC8785NumericFixture(t *testing.T) {
	t.Parallel()

	result, err := canonical.CanonicalizeBytes(
		readFixture(t, "numeric/rfc8785.json"),
		canonical.FormatJSON,
		canonical.DefaultLimits(),
	)
	if err != nil {
		t.Fatalf("canonicalize: %v", err)
	}
	assertBytesEqual(t, result.Bytes, readJCSFixture(t, "numeric/rfc8785.jcs.hex"))

	yamlResult, err := canonical.CanonicalizeBytes(
		readFixture(t, "numeric/rfc8785.yaml"),
		canonical.FormatYAML,
		canonical.DefaultLimits(),
	)
	if err != nil {
		t.Fatalf("canonicalize YAML: %v", err)
	}
	assertBytesEqual(t, yamlResult.Bytes, result.Bytes)
	if yamlResult.Digest != result.Digest {
		t.Fatalf("numeric JSON/YAML digest mismatch: JSON=%s YAML=%s", result.Digest, yamlResult.Digest)
	}
}

func TestRFC8785UnicodeOrderingAndEscaping(t *testing.T) {
	t.Parallel()

	result, err := canonical.CanonicalizeBytes(
		readFixture(t, "unicode/ordering-and-escaping.json"),
		canonical.FormatJSON,
		canonical.DefaultLimits(),
	)
	if err != nil {
		t.Fatalf("canonicalize: %v", err)
	}
	assertBytesEqual(t, result.Bytes, readJCSFixture(t, "unicode/ordering-and-escaping.jcs.hex"))
}

func TestYAMLParserDifferentialsAreExplicit(t *testing.T) {
	t.Parallel()

	accepted := []struct {
		name string
		want string
	}{
		{name: "parser-differential/yaml-1.1-booleans-are-strings.yaml", want: `{"value":"yes"}`},
		{name: "parser-differential/quoted-number-is-string.yaml", want: `{"value":"01"}`},
		{name: "parser-differential/explicit-core-string.yaml", want: `{"value":"true"}`},
	}
	for _, tc := range accepted {
		tc := tc
		t.Run(filepath.Base(tc.name), func(t *testing.T) {
			t.Parallel()
			result, err := canonical.CanonicalizeBytes(readFixture(t, tc.name), canonical.FormatYAML, canonical.DefaultLimits())
			if err != nil {
				t.Fatalf("canonicalize: %v", err)
			}
			assertBytesEqual(t, result.Bytes, []byte(tc.want))
		})
	}

	rejected := []struct {
		name string
		code canonical.ErrorCode
	}{
		{name: "parser-differential/timestamp.yaml", code: canonical.CodeUnsupportedTag},
		{name: "parser-differential/nonnormal-number.yaml", code: canonical.CodeInvalidNumber},
		{name: "parser-differential/binary-tag.yaml", code: canonical.CodeUnsupportedTag},
		{name: "parser-differential/hex-number.yaml", code: canonical.CodeInvalidNumber},
		{name: "parser-differential/underscore-number.yaml", code: canonical.CodeInvalidNumber},
		{name: "parser-differential/leading-plus-number.yaml", code: canonical.CodeInvalidNumber},
	}
	for _, tc := range rejected {
		tc := tc
		t.Run(filepath.Base(tc.name), func(t *testing.T) {
			t.Parallel()
			_, err := canonical.CanonicalizeBytes(readFixture(t, tc.name), canonical.FormatYAML, canonical.DefaultLimits())
			assertErrorCode(t, err, tc.code)
		})
	}
}

func TestDenialFixturesFailClosed(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		format canonical.Format
		code   canonical.ErrorCode
	}{
		{name: "negative/duplicate-key.json", format: canonical.FormatJSON, code: canonical.CodeDuplicateKey},
		{name: "negative/duplicate-key.yaml", format: canonical.FormatYAML, code: canonical.CodeDuplicateKey},
		{name: "negative/alias.yaml", format: canonical.FormatYAML, code: canonical.CodeAliasForbidden},
		{name: "negative/custom-tag.yaml", format: canonical.FormatYAML, code: canonical.CodeUnsupportedTag},
		{name: "negative/non-string-key.yaml", format: canonical.FormatYAML, code: canonical.CodeNonStringKey},
		{name: "negative/nan.yaml", format: canonical.FormatYAML, code: canonical.CodeInvalidNumber},
		{name: "negative/infinity.yaml", format: canonical.FormatYAML, code: canonical.CodeInvalidNumber},
		{name: "negative/multiple-documents.yaml", format: canonical.FormatYAML, code: canonical.CodeMultipleDocuments},
		{name: "negative/lone-high-surrogate.json", format: canonical.FormatJSON, code: canonical.CodeInvalidUnicode},
		{name: "negative/lone-low-surrogate.json", format: canonical.FormatJSON, code: canonical.CodeInvalidUnicode},
		{name: "negative/wrong-surrogate-pair.json", format: canonical.FormatJSON, code: canonical.CodeInvalidUnicode},
		{name: "negative/lone-high-surrogate.yaml", format: canonical.FormatYAML, code: canonical.CodeInvalidYAML},
		{name: "negative/malformed-number.json", format: canonical.FormatJSON, code: canonical.CodeInvalidJSON},
		{name: "malicious/escaped-duplicate-key.json", format: canonical.FormatJSON, code: canonical.CodeDuplicateKey},
		{name: "malicious/escaped-duplicate-key.yaml", format: canonical.FormatYAML, code: canonical.CodeDuplicateKey},
		{name: "malicious/alias-expansion.yaml", format: canonical.FormatYAML, code: canonical.CodeAliasForbidden},
		{name: "malicious/huge-exponent.json", format: canonical.FormatJSON, code: canonical.CodeInvalidNumber},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(filepath.Base(tc.name), func(t *testing.T) {
			t.Parallel()
			_, err := canonical.CanonicalizeBytes(readFixture(t, tc.name), tc.format, canonical.DefaultLimits())
			assertErrorCode(t, err, tc.code)
		})
	}
}

func TestAcceptedJSONMatchesTheRFC8785ReferenceTransform(t *testing.T) {
	t.Parallel()

	fixtures := []string{
		"positive/equivalent.json",
		"numeric/rfc8785.json",
		"unicode/ordering-and-escaping.json",
	}
	for _, name := range fixtures {
		name := name
		t.Run(filepath.Base(name), func(t *testing.T) {
			t.Parallel()
			input := readFixture(t, name)
			result, err := canonical.CanonicalizeBytes(input, canonical.FormatJSON, canonical.DefaultLimits())
			if err != nil {
				t.Fatalf("canonicalize: %v", err)
			}
			reference, err := jcs.Transform(input)
			if err != nil {
				t.Fatalf("reference transform: %v", err)
			}
			assertBytesEqual(t, result.Bytes, reference)
		})
	}
}

func TestCanonicalOutputIsIdempotent(t *testing.T) {
	t.Parallel()

	first, err := canonical.CanonicalizeBytes(readFixture(t, "positive/equivalent.yaml"), canonical.FormatYAML, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("first canonicalization: %v", err)
	}
	second, err := canonical.CanonicalizeBytes(first.Bytes, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("second canonicalization: %v", err)
	}
	assertBytesEqual(t, second.Bytes, first.Bytes)
	if second.Digest != first.Digest {
		t.Fatalf("idempotent digest changed: first=%s second=%s", first.Digest, second.Digest)
	}
}

func TestInvalidUTF8FixtureFailsBeforeParsing(t *testing.T) {
	t.Parallel()

	hexInput := strings.TrimSpace(string(readFixture(t, "negative/invalid-utf8.hex")))
	input, err := hex.DecodeString(hexInput)
	if err != nil {
		t.Fatalf("decode fixture: %v", err)
	}
	_, err = canonical.CanonicalizeBytes(input, canonical.FormatJSON, canonical.DefaultLimits())
	assertErrorCode(t, err, canonical.CodeInvalidUTF8)
}

func TestValidSurrogatePairBecomesUTF8(t *testing.T) {
	t.Parallel()

	result, err := canonical.CanonicalizeBytes([]byte(`{"emoji":"\uD83D\uDE00"}`), canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("canonicalize: %v", err)
	}
	assertBytesEqual(t, result.Bytes, []byte(`{"emoji":"😀"}`))
}

func TestArrayOrderChangesIdentity(t *testing.T) {
	t.Parallel()

	first, err := canonical.CanonicalizeBytes([]byte(`{"items":[1,2]}`), canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("first: %v", err)
	}
	second, err := canonical.CanonicalizeBytes([]byte(`{"items":[2,1]}`), canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("second: %v", err)
	}
	if first.Digest == second.Digest {
		t.Fatal("array reorder must change semantic identity")
	}
}

func TestConfiguredLimitsHaveExactBoundaries(t *testing.T) {
	t.Parallel()

	t.Run("input bytes", func(t *testing.T) {
		limits := canonical.DefaultLimits()
		limits.MaxInputBytes = 4
		if _, err := canonical.Canonicalize(strings.NewReader("null"), canonical.FormatJSON, limits); err != nil {
			t.Fatalf("exact boundary rejected: %v", err)
		}
		limits.MaxInputBytes = 3
		_, err := canonical.Canonicalize(strings.NewReader("null"), canonical.FormatJSON, limits)
		assertErrorCode(t, err, canonical.CodeInputTooLarge)
	})

	t.Run("depth", func(t *testing.T) {
		input := readFixture(t, "boundary/depth.json")
		limits := canonical.DefaultLimits()
		limits.MaxDepth = 3
		if _, err := canonical.CanonicalizeBytes(input, canonical.FormatJSON, limits); err != nil {
			t.Fatalf("exact boundary rejected: %v", err)
		}
		limits.MaxDepth = 2
		_, err := canonical.CanonicalizeBytes(input, canonical.FormatJSON, limits)
		assertErrorCode(t, err, canonical.CodeDepthExceeded)
	})

	t.Run("nodes", func(t *testing.T) {
		input := readFixture(t, "boundary/depth.json")
		limits := canonical.DefaultLimits()
		limits.MaxNodes = 4 // object, member name, array, null
		if _, err := canonical.CanonicalizeBytes(input, canonical.FormatJSON, limits); err != nil {
			t.Fatalf("exact boundary rejected: %v", err)
		}
		limits.MaxNodes = 3
		_, err := canonical.CanonicalizeBytes(input, canonical.FormatJSON, limits)
		assertErrorCode(t, err, canonical.CodeNodeLimitExceeded)
	})

	t.Run("canonical bytes", func(t *testing.T) {
		input := []byte("value: \\u0000\n")
		want := []byte(`{"value":"\\u0000"}`)
		limits := canonical.DefaultLimits()
		limits.MaxCanonicalBytes = int64(len(want))
		result, err := canonical.CanonicalizeBytes(input, canonical.FormatYAML, limits)
		if err != nil {
			t.Fatalf("exact boundary rejected: %v", err)
		}
		assertBytesEqual(t, result.Bytes, want)
		limits.MaxCanonicalBytes--
		_, err = canonical.CanonicalizeBytes(input, canonical.FormatYAML, limits)
		assertErrorCode(t, err, canonical.CodeCanonicalTooLarge)
	})
}

func TestInteroperableIntegerLiteralBoundary(t *testing.T) {
	t.Parallel()

	for _, format := range []canonical.Format{canonical.FormatJSON, canonical.FormatYAML} {
		if _, err := canonical.CanonicalizeBytes(
			readFixture(t, "boundary/safe-integer-literals.json"),
			format,
			canonical.DefaultLimits(),
		); err != nil {
			t.Fatalf("exact safe-integer boundaries rejected as %s: %v", format, err)
		}
	}

	for _, name := range []string{
		"negative/unsafe-positive-integer.json",
		"negative/unsafe-negative-integer.json",
	} {
		for _, format := range []canonical.Format{canonical.FormatJSON, canonical.FormatYAML} {
			_, err := canonical.CanonicalizeBytes(readFixture(t, name), format, canonical.DefaultLimits())
			assertErrorCode(t, err, canonical.CodeInvalidNumber)
		}
	}
}

func TestDefaultLimitsMatchTheAcceptedOperationalProfile(t *testing.T) {
	t.Parallel()

	limits := canonical.DefaultLimits()
	if limits.MaxInputBytes != 4<<20 || limits.MaxCanonicalBytes != 4<<20 {
		t.Fatalf("authoritative byte limits = input:%d output:%d, want 4 MiB", limits.MaxInputBytes, limits.MaxCanonicalBytes)
	}
	if limits.MaxDepth != 64 || limits.MaxNodes != 100_000 {
		t.Fatalf("authoritative structural limits = depth:%d nodes:%d, want depth 64 and 100000 nodes", limits.MaxDepth, limits.MaxNodes)
	}
}

func TestInvalidConfigurationAndFormatFailClosed(t *testing.T) {
	t.Parallel()

	_, err := canonical.CanonicalizeBytes([]byte(`{}`), canonical.Format("toml"), canonical.DefaultLimits())
	assertErrorCode(t, err, canonical.CodeUnsupportedFormat)

	limits := canonical.DefaultLimits()
	limits.MaxDepth = -1
	_, err = canonical.CanonicalizeBytes([]byte(`{}`), canonical.FormatJSON, limits)
	assertErrorCode(t, err, canonical.CodeInvalidLimits)

	accepted := canonical.DefaultLimits()
	for name, mutate := range map[string]func(*canonical.Limits){
		"input bytes":     func(value *canonical.Limits) { value.MaxInputBytes++ },
		"canonical bytes": func(value *canonical.Limits) { value.MaxCanonicalBytes++ },
		"depth":           func(value *canonical.Limits) { value.MaxDepth++ },
		"nodes":           func(value *canonical.Limits) { value.MaxNodes++ },
	} {
		t.Run("raised "+name, func(t *testing.T) {
			limits := accepted
			mutate(&limits)
			_, err := canonical.CanonicalizeBytes([]byte(`{}`), canonical.FormatJSON, limits)
			assertErrorCode(t, err, canonical.CodeInvalidLimits)
		})
	}
}

func TestReaderFailureIsNotTreatedAsValidInput(t *testing.T) {
	t.Parallel()

	_, err := canonical.Canonicalize(failingReader{}, canonical.FormatJSON, canonical.DefaultLimits())
	assertErrorCode(t, err, canonical.CodeInputReadFailed)
}

func TestDigestCoversCanonicalBytes(t *testing.T) {
	t.Parallel()

	result, err := canonical.CanonicalizeBytes([]byte(` { "b": 2, "a": 1 } `), canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatalf("canonicalize: %v", err)
	}
	sum := sha256.Sum256(result.Bytes)
	want := "sha256:" + hex.EncodeToString(sum[:])
	if result.Digest != want {
		t.Fatalf("digest=%q want=%q", result.Digest, want)
	}
}

func TestErrorDoesNotEchoUntrustedContent(t *testing.T) {
	t.Parallel()

	secretLikeKey := "do-not-print-this-value"
	_, err := canonical.CanonicalizeBytes([]byte(fmt.Sprintf(`{"%s":1,"%s":2}`, secretLikeKey, secretLikeKey)), canonical.FormatJSON, canonical.DefaultLimits())
	if err == nil {
		t.Fatal("expected duplicate-key error")
	}
	if strings.Contains(err.Error(), secretLikeKey) {
		t.Fatalf("error echoed untrusted content: %q", err)
	}
}

func FuzzCanonicalizeDoesNotPanic(f *testing.F) {
	for _, seed := range [][]byte{
		[]byte(`null`),
		[]byte(`{"a":[1,true,null,"x"]}`),
		[]byte("a: &a [*a]\n"),
		{0xff, 0xfe, 0xfd},
	} {
		f.Add(seed)
	}
	limits := canonical.Limits{MaxInputBytes: 4096, MaxCanonicalBytes: 4096, MaxDepth: 16, MaxNodes: 256}
	f.Fuzz(func(t *testing.T, input []byte) {
		_, _ = canonical.CanonicalizeBytes(input, canonical.FormatJSON, limits)
		_, _ = canonical.CanonicalizeBytes(input, canonical.FormatYAML, limits)
	})
}

type failingReader struct{}

func (failingReader) Read([]byte) (int, error) { return 0, errors.New("injected read failure") }

func readFixture(t *testing.T, name string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(fixtureRoot, name))
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return data
}

func readJCSFixture(t *testing.T, name string) []byte {
	t.Helper()
	encoded := strings.TrimSpace(string(readFixture(t, name)))
	decoded, err := hex.DecodeString(encoded)
	if err != nil {
		t.Fatalf("decode JCS fixture %s: %v", name, err)
	}
	return decoded
}

func assertBytesEqual(t *testing.T, got, want []byte) {
	t.Helper()
	if !bytes.Equal(got, want) {
		t.Fatalf("bytes differ\n got: %q\nwant: %q", got, want)
	}
}

func assertErrorCode(t *testing.T, err error, want canonical.ErrorCode) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected %s, got nil", want)
	}
	if got := canonical.CodeOf(err); got != want {
		t.Fatalf("error code=%q want=%q (error=%v)", got, want, err)
	}
}

var _ io.Reader = failingReader{}
