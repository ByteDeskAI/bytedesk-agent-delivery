package operations

import (
	"bytes"
	"encoding"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

var (
	digestPattern     = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
	identifierPattern = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9._:-]{0,255})$`)
	mediaTypePattern  = regexp.MustCompile(`^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+(?:;[ -~]+)?$`)
	windowsDrive      = regexp.MustCompile(`^[A-Za-z]:`)
	registryHost      = regexp.MustCompile(`^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`)
	repositorySegment = regexp.MustCompile(`^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*$`)
	jsonMarshalerType = reflect.TypeOf((*json.Marshaler)(nil)).Elem()
	textMarshalerType = reflect.TypeOf((*encoding.TextMarshaler)(nil)).Elem()
)

const maxSafeInteger int64 = 9_007_199_254_740_991

type JSONPatch struct {
	Profile    string           `json:"profile"`
	Operations []PatchOperation `json:"operations"`
}

// FunctionalTarget names the only complete documents that the v1 JSON Patch
// profile may mutate. Authority and security inputs are separate objects and
// therefore cannot be selected as patch targets.
type FunctionalTarget string

const (
	TargetAgentSpec                FunctionalTarget = "agent-spec"
	TargetRendererFunctionalConfig FunctionalTarget = "renderer-functional-config"
)

type PatchOperation struct {
	Op    string          `json:"op"`
	Path  string          `json:"path"`
	Value json.RawMessage `json:"value,omitempty"`
}

type TrustPolicyRef struct {
	ID     string `json:"id"`
	Digest string `json:"digest"`
}

type ArtifactDescriptor struct {
	Repository  string         `json:"repository"`
	Digest      string         `json:"digest"`
	MediaType   string         `json:"mediaType"`
	Size        int64          `json:"size"`
	TrustPolicy TrustPolicyRef `json:"trustPolicy"`
}

type Precondition struct {
	Kind   string `json:"kind"`
	Digest string `json:"digest,omitempty"`
}

type FileRecord struct {
	Content ArtifactDescriptor `json:"content"`
	Mode    string             `json:"mode"`
}

type SkillRecord struct {
	Descriptor ArtifactDescriptor `json:"descriptor"`
}

type FileOperationSet struct {
	Contract   string          `json:"contract"`
	Operations []FileOperation `json:"operations"`
}

type FileOperation struct {
	Op           string              `json:"op"`
	Path         string              `json:"path"`
	Precondition Precondition        `json:"precondition"`
	Content      *ArtifactDescriptor `json:"content,omitempty"`
	Mode         string              `json:"mode,omitempty"`
}

type SkillOperationSet struct {
	Contract   string           `json:"contract"`
	Operations []SkillOperation `json:"operations"`
}

type SkillOperation struct {
	Op           string              `json:"op"`
	PackageID    string              `json:"packageId"`
	Precondition Precondition        `json:"precondition"`
	Descriptor   *ArtifactDescriptor `json:"descriptor,omitempty"`
}

func ApplyJSONPatch(document any, patch JSONPatch, target FunctionalTarget) (any, error) {
	if patch.Profile != "bytedesk.json-patch/1" {
		return nil, fmt.Errorf("unsupported patch profile %q", patch.Profile)
	}
	if target != TargetAgentSpec && target != TargetRendererFunctionalConfig {
		return nil, fmt.Errorf("unsupported functional patch target %q", target)
	}
	if len(patch.Operations) > 10_000 {
		return nil, errors.New("patch exceeds 10000 operations")
	}
	working, err := cloneJSON(document)
	if err != nil {
		return nil, fmt.Errorf("clone patch input: %w", err)
	}
	if _, ok := working.(map[string]any); !ok {
		return nil, errors.New("functional patch target must be a complete object document")
	}
	for index, operation := range patch.Operations {
		tokens, err := parsePointer(operation.Path)
		if err != nil {
			return nil, fmt.Errorf("operation %d: %w", index, err)
		}
		value, err := patchOperationValue(operation, index)
		if err != nil {
			return nil, err
		}
		working, err = applyJSONOperation(working, tokens, operation.Op, value)
		if err != nil {
			return nil, fmt.Errorf("operation %d: %w", index, err)
		}
		working, err = cloneJSON(working)
		if err != nil {
			return nil, fmt.Errorf("operation %d result exceeds canonical resource limits: %w", index, err)
		}
	}
	return working, nil
}

func parsePointer(pointer string) ([]string, error) {
	if pointer == "" {
		return nil, errors.New("empty root pointer is forbidden")
	}
	if len([]byte(pointer)) > 4096 {
		return nil, errors.New("JSON pointer exceeds 4096 UTF-8 bytes")
	}
	if strings.HasPrefix(pointer, "#") || !strings.HasPrefix(pointer, "/") {
		return nil, fmt.Errorf("invalid JSON pointer %q", pointer)
	}
	rawTokens := strings.Split(pointer[1:], "/")
	tokens := make([]string, len(rawTokens))
	for i, raw := range rawTokens {
		var decoded strings.Builder
		for j := 0; j < len(raw); j++ {
			if raw[j] != '~' {
				decoded.WriteByte(raw[j])
				continue
			}
			if j+1 >= len(raw) {
				return nil, fmt.Errorf("invalid JSON pointer escape in %q", pointer)
			}
			switch raw[j+1] {
			case '0':
				decoded.WriteByte('~')
			case '1':
				decoded.WriteByte('/')
			default:
				return nil, fmt.Errorf("invalid JSON pointer escape in %q", pointer)
			}
			j++
		}
		token := decoded.String()
		if !utf8.ValidString(token) || token != norm.NFC.String(token) {
			return nil, fmt.Errorf("pointer token is not valid NFC Unicode in %q", pointer)
		}
		tokens[i] = token
	}
	return tokens, nil
}

func applyJSONOperation(node any, tokens []string, operation string, value any) (any, error) {
	if len(tokens) == 0 {
		return nil, errors.New("empty root pointer is forbidden")
	}
	if len(tokens) == 1 {
		return applyJSONLeaf(node, tokens[0], operation, value)
	}
	token := tokens[0]
	switch typed := node.(type) {
	case map[string]any:
		child, exists := typed[token]
		if !exists {
			return nil, fmt.Errorf("parent path component %q does not exist", token)
		}
		updated, err := applyJSONOperation(child, tokens[1:], operation, value)
		if err != nil {
			return nil, err
		}
		typed[token] = updated
		return typed, nil
	case []any:
		index, err := existingArrayIndex(token, len(typed))
		if err != nil {
			return nil, err
		}
		updated, err := applyJSONOperation(typed[index], tokens[1:], operation, value)
		if err != nil {
			return nil, err
		}
		typed[index] = updated
		return typed, nil
	default:
		return nil, fmt.Errorf("parent path component %q is not a container", token)
	}
}

func applyJSONLeaf(node any, token, operation string, value any) (any, error) {
	switch typed := node.(type) {
	case map[string]any:
		_, exists := typed[token]
		switch operation {
		case "add":
			if exists {
				return nil, fmt.Errorf("add target %q already exists", token)
			}
			typed[token] = value
		case "replace":
			if !exists {
				return nil, fmt.Errorf("replace target %q does not exist", token)
			}
			typed[token] = value
		case "remove":
			if !exists {
				return nil, fmt.Errorf("remove target %q does not exist", token)
			}
			delete(typed, token)
		}
		return typed, nil
	case []any:
		if operation == "add" {
			if token == "-" {
				return append(typed, value), nil
			}
			return nil, fmt.Errorf("add array target %q is invalid; use '-' to append", token)
		}
		index, err := existingArrayIndex(token, len(typed))
		if err != nil {
			return nil, err
		}
		if operation == "replace" {
			typed[index] = value
			return typed, nil
		}
		return append(typed[:index], typed[index+1:]...), nil
	default:
		return nil, fmt.Errorf("target parent is not a container")
	}
}

func existingArrayIndex(token string, length int) (int, error) {
	return arrayIndex(token, length, false)
}

func arrayIndex(token string, length int, allowEnd bool) (int, error) {
	if token == "-" {
		return 0, errors.New("'-' is valid only as the final add token")
	}
	if token == "" || (len(token) > 1 && token[0] == '0') {
		return 0, fmt.Errorf("non-canonical array index %q", token)
	}
	for _, char := range token {
		if char < '0' || char > '9' {
			return 0, fmt.Errorf("invalid array index %q", token)
		}
	}
	index, err := strconv.Atoi(token)
	if err != nil {
		return 0, fmt.Errorf("invalid array index %q", token)
	}
	limit := length - 1
	if allowEnd {
		limit = length
	}
	if index < 0 || index > limit {
		return 0, fmt.Errorf("array index %q is out of bounds", token)
	}
	return index, nil
}

// ApplyFileOperations evaluates one nested binding delta atomically. The caller
// must first win the enclosing binding's revision-plus-canonical-digest CAS;
// item digests protect delta intent but are not a second aggregate authority.
func ApplyFileOperations(initial map[string]FileRecord, set FileOperationSet) (map[string]FileRecord, error) {
	if set.Contract != "bytedesk.file-operations/1" {
		return nil, fmt.Errorf("unsupported file operation contract %q", set.Contract)
	}
	if len(set.Operations) > 10_000 {
		return nil, errors.New("file operation set exceeds 10000 operations")
	}
	working := cloneFileState(initial)
	index, err := filePathIndex(working)
	if err != nil {
		return nil, err
	}
	seenTargets := map[string]struct{}{}
	for operationIndex, operation := range set.Operations {
		folded, err := validatePortablePath(operation.Path)
		if err != nil {
			return nil, fmt.Errorf("file operation %d: %w", operationIndex, err)
		}
		if _, duplicate := seenTargets[folded]; duplicate {
			return nil, fmt.Errorf("file operation %d: duplicate normalized target %q", operationIndex, operation.Path)
		}
		seenTargets[folded] = struct{}{}
		existingPath, collision := index[folded]
		existing, exists := working[operation.Path]
		if collision && existingPath != operation.Path {
			return nil, fmt.Errorf("file operation %d: path %q collides with %q", operationIndex, operation.Path, existingPath)
		}
		switch operation.Op {
		case "add":
			if operation.Precondition.Kind != "absent" || operation.Precondition.Digest != "" {
				return nil, fmt.Errorf("file operation %d: add requires absent precondition", operationIndex)
			}
			if exists || collision {
				return nil, fmt.Errorf("file operation %d: add target exists", operationIndex)
			}
			if err := validateDescriptor(operation.Content); err != nil {
				return nil, fmt.Errorf("file operation %d: %w", operationIndex, err)
			}
			if !validFileMode(operation.Mode) {
				return nil, fmt.Errorf("file operation %d: unsafe file mode %q", operationIndex, operation.Mode)
			}
			if conflict, prior := fileTreeConflict(index, folded, ""); conflict {
				return nil, fmt.Errorf("file operation %d: path conflicts with existing regular file %q", operationIndex, prior)
			}
			working[operation.Path] = FileRecord{Mode: operation.Mode, Content: *cloneDescriptor(operation.Content)}
			index[folded] = operation.Path
		case "replace":
			if !exists || operation.Precondition.Kind != "match" ||
				operation.Precondition.Digest != existing.Content.Digest {
				return nil, fmt.Errorf("file operation %d: replace precondition failed", operationIndex)
			}
			if err := validateDescriptor(operation.Content); err != nil {
				return nil, fmt.Errorf("file operation %d: %w", operationIndex, err)
			}
			if !validFileMode(operation.Mode) {
				return nil, fmt.Errorf("file operation %d: unsafe file mode %q", operationIndex, operation.Mode)
			}
			working[operation.Path] = FileRecord{Mode: operation.Mode, Content: *cloneDescriptor(operation.Content)}
		case "remove":
			if operation.Content != nil || operation.Mode != "" {
				return nil, fmt.Errorf("file operation %d: remove forbids content and mode", operationIndex)
			}
			if !exists || operation.Precondition.Kind != "match" ||
				operation.Precondition.Digest != existing.Content.Digest {
				return nil, fmt.Errorf("file operation %d: remove precondition failed", operationIndex)
			}
			delete(working, operation.Path)
			delete(index, folded)
		default:
			return nil, fmt.Errorf("file operation %d: unsupported operation %q", operationIndex, operation.Op)
		}
	}
	return working, nil
}

// ApplySkillOperations has the same outer aggregate-CAS requirement as file
// operations and retains each effective package's complete exact descriptor.
func ApplySkillOperations(initial map[string]SkillRecord, set SkillOperationSet) (map[string]SkillRecord, error) {
	if set.Contract != "bytedesk.skill-operations/1" {
		return nil, fmt.Errorf("unsupported skill operation contract %q", set.Contract)
	}
	if len(set.Operations) > 10_000 {
		return nil, errors.New("skill operation set exceeds 10000 operations")
	}
	if err := validateSkillState(initial); err != nil {
		return nil, err
	}
	working := cloneSkillState(initial)
	seen := map[string]struct{}{}
	for index, operation := range set.Operations {
		if !identifierPattern.MatchString(operation.PackageID) {
			return nil, fmt.Errorf("skill operation %d: invalid package identifier %q", index, operation.PackageID)
		}
		if _, duplicate := seen[operation.PackageID]; duplicate {
			return nil, fmt.Errorf("skill operation %d: duplicate package target %q", index, operation.PackageID)
		}
		seen[operation.PackageID] = struct{}{}
		existing, exists := working[operation.PackageID]
		switch operation.Op {
		case "add":
			if operation.Precondition.Kind != "absent" || operation.Precondition.Digest != "" || exists {
				return nil, fmt.Errorf("skill operation %d: add precondition failed", index)
			}
			if err := validateDescriptor(operation.Descriptor); err != nil {
				return nil, fmt.Errorf("skill operation %d: %w", index, err)
			}
			working[operation.PackageID] = SkillRecord{Descriptor: *cloneDescriptor(operation.Descriptor)}
		case "replace":
			if !exists || operation.Precondition.Kind != "match" ||
				operation.Precondition.Digest != existing.Descriptor.Digest {
				return nil, fmt.Errorf("skill operation %d: replace precondition failed", index)
			}
			if err := validateDescriptor(operation.Descriptor); err != nil {
				return nil, fmt.Errorf("skill operation %d: %w", index, err)
			}
			working[operation.PackageID] = SkillRecord{Descriptor: *cloneDescriptor(operation.Descriptor)}
		case "remove":
			if operation.Descriptor != nil {
				return nil, fmt.Errorf("skill operation %d: remove forbids descriptor", index)
			}
			if !exists || operation.Precondition.Kind != "match" ||
				operation.Precondition.Digest != existing.Descriptor.Digest {
				return nil, fmt.Errorf("skill operation %d: remove precondition failed", index)
			}
			delete(working, operation.PackageID)
		default:
			return nil, fmt.Errorf("skill operation %d: unsupported operation %q", index, operation.Op)
		}
	}
	return working, nil
}

func validateSkillState(state map[string]SkillRecord) error {
	for packageID, record := range state {
		if !identifierPattern.MatchString(packageID) {
			return errors.New("invalid existing skill package identifier")
		}
		if err := validateDescriptor(&record.Descriptor); err != nil {
			return errors.New("invalid existing skill package descriptor")
		}
	}
	return nil
}

func validatePortablePath(path string) (string, error) {
	if !utf8.ValidString(path) || path != norm.NFC.String(path) {
		return "", fmt.Errorf("path %q is not valid NFC Unicode", path)
	}
	if path == "" || len([]byte(path)) > 1024 || strings.HasPrefix(path, "/") || strings.Contains(path, "\\") || windowsDrive.MatchString(path) {
		return "", fmt.Errorf("path %q is not a portable relative path", path)
	}
	segments := strings.Split(path, "/")
	if len(segments) > 32 {
		return "", fmt.Errorf("path %q exceeds 32 segments", path)
	}
	for _, segment := range segments {
		if segment == "" || segment == "." || segment == ".." {
			return "", fmt.Errorf("path %q contains an invalid segment", path)
		}
		if len([]byte(segment)) > 255 {
			return "", fmt.Errorf("path %q contains a segment exceeding 255 UTF-8 bytes", path)
		}
		if strings.HasSuffix(segment, ".") || strings.HasSuffix(segment, " ") ||
			strings.ContainsAny(segment, `:<>"|?*`) {
			return "", fmt.Errorf("path %q contains Windows-ambiguous syntax", path)
		}
		for _, char := range segment {
			if char == 0 || unicode.IsControl(char) {
				return "", fmt.Errorf("path %q contains a control character", path)
			}
		}
		base := strings.SplitN(cases.Fold().String(segment), ".", 2)[0]
		if isWindowsDeviceName(base) {
			return "", fmt.Errorf("path %q contains a Windows device name", path)
		}
	}
	return norm.NFC.String(cases.Fold().String(path)), nil
}

func isWindowsDeviceName(base string) bool {
	switch base {
	case "con", "prn", "aux", "nul", "clock$", "conin$", "conout$":
		return true
	}
	for _, prefix := range []string{"com", "lpt"} {
		if strings.HasPrefix(base, prefix) {
			suffix := []rune(strings.TrimPrefix(base, prefix))
			if len(suffix) == 1 && ((suffix[0] >= '1' && suffix[0] <= '9') ||
				suffix[0] == '¹' || suffix[0] == '²' || suffix[0] == '³') {
				return true
			}
		}
	}
	return false
}

func filePathIndex(state map[string]FileRecord) (map[string]string, error) {
	index := make(map[string]string, len(state))
	for path, record := range state {
		folded, err := validatePortablePath(path)
		if err != nil {
			return nil, fmt.Errorf("invalid existing file path: %w", err)
		}
		if prior, exists := index[folded]; exists {
			return nil, fmt.Errorf("existing file paths %q and %q collide", prior, path)
		}
		if !validFileMode(record.Mode) {
			return nil, fmt.Errorf("existing file %q has invalid mode", path)
		}
		if err := validateDescriptor(&record.Content); err != nil {
			return nil, fmt.Errorf("existing file %q has invalid content descriptor", path)
		}
		index[folded] = path
	}
	for folded, path := range index {
		if conflict, prior := fileTreeConflict(index, folded, path); conflict {
			return nil, fmt.Errorf("existing regular files %q and %q have an ancestor conflict", path, prior)
		}
	}
	return index, nil
}

func fileTreeConflict(index map[string]string, folded, self string) (bool, string) {
	for existing, original := range index {
		if original == self || existing == folded {
			continue
		}
		if strings.HasPrefix(folded, existing+"/") || strings.HasPrefix(existing, folded+"/") {
			return true, original
		}
	}
	return false, ""
}

func validFileMode(mode string) bool {
	switch mode {
	case "0444", "0555", "0644", "0755":
		return true
	default:
		return false
	}
}

func validateDescriptor(descriptor *ArtifactDescriptor) error {
	if descriptor == nil {
		return errors.New("missing exact artifact descriptor")
	}
	if !validOCIRepository(descriptor.Repository) {
		return errors.New("invalid descriptor repository")
	}
	if !digestPattern.MatchString(descriptor.Digest) || descriptor.Size < 0 || descriptor.Size > maxSafeInteger {
		return errors.New("invalid descriptor digest or size")
	}
	if len(descriptor.MediaType) > 255 || !mediaTypePattern.MatchString(descriptor.MediaType) {
		return errors.New("invalid descriptor media type")
	}
	if !identifierPattern.MatchString(descriptor.TrustPolicy.ID) || !digestPattern.MatchString(descriptor.TrustPolicy.Digest) {
		return errors.New("invalid descriptor trust policy")
	}
	return nil
}

func validOCIRepository(repository string) bool {
	if repository == "" || repository != strings.ToLower(repository) || len([]byte(repository)) > 1024 ||
		strings.ContainsAny(repository, "@?#\\ \t\r\n") {
		return false
	}
	parts := strings.Split(repository, "/")
	if len(parts) < 2 {
		return false
	}
	authority := parts[0]
	host := authority
	if strings.HasPrefix(authority, "[") {
		closing := strings.IndexByte(authority, ']')
		if closing < 0 {
			return false
		}
		if closing == len(authority)-1 {
			host = authority[1:closing]
		} else {
			var port string
			var err error
			host, port, err = net.SplitHostPort(authority)
			if err != nil || !validPort(port) {
				return false
			}
		}
		if !strings.Contains(host, ":") || strings.Contains(host, ".") || net.ParseIP(host) == nil {
			return false
		}
	} else if strings.Contains(authority, ":") {
		var port string
		var err error
		host, port, err = net.SplitHostPort(authority)
		if err != nil || !validPort(port) {
			return false
		}
		if !validRegistryHost(host) {
			return false
		}
	} else if !validRegistryHost(host) {
		return false
	}
	for _, segment := range parts[1:] {
		if !repositorySegment.MatchString(segment) {
			return false
		}
	}
	return true
}

func validRegistryHost(host string) bool {
	if !registryHost.MatchString(host) {
		return false
	}
	for _, label := range strings.Split(host, ".") {
		if len(label) == 0 || len(label) > 63 {
			return false
		}
	}
	return true
}

func validPort(value string) bool {
	port, err := strconv.Atoi(value)
	return err == nil && port >= 1 && port <= 65535 && strconv.Itoa(port) == value
}

func cloneJSON(value any) (any, error) {
	if err := validateJSONDataModel(reflect.ValueOf(value), 0); err != nil {
		return nil, err
	}
	data, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	return decodeJSON(data)
}

// validateJSONDataModel runs before encoding/json so invalid UTF-8 cannot be
// silently coerced to U+FFFD and make distinct authoritative values compare
// equal. The operation boundary accepts JSON data-model values, not Go
// structs, pointers, byte slices, or custom serialization behavior.
func validateJSONDataModel(value reflect.Value, depth int) error {
	if depth > 64 {
		return errors.New("JSON value exceeds 64 container levels")
	}
	if !value.IsValid() {
		return nil
	}
	if value.Kind() == reflect.Interface {
		if value.IsNil() {
			return nil
		}
		return validateJSONDataModel(value.Elem(), depth)
	}
	if hasCustomSerialization(value.Type()) {
		return fmt.Errorf("JSON data model forbids custom serialization type %s", value.Type())
	}

	switch value.Kind() {
	case reflect.String:
		if !utf8.ValidString(value.String()) {
			return errors.New("JSON string is not valid UTF-8")
		}
		return nil
	case reflect.Bool,
		reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64,
		reflect.Float32, reflect.Float64:
		return nil
	case reflect.Map:
		if value.IsNil() {
			return nil
		}
		if value.Type().Key().Kind() != reflect.String {
			return errors.New("JSON object key type is not string")
		}
		if hasCustomSerialization(value.Type().Key()) {
			return fmt.Errorf("JSON data model forbids custom object-key serialization type %s", value.Type().Key())
		}
		iterator := value.MapRange()
		for iterator.Next() {
			key := iterator.Key().String()
			if !utf8.ValidString(key) {
				return errors.New("JSON object key is not valid UTF-8")
			}
			if err := validateJSONDataModel(iterator.Value(), depth+1); err != nil {
				return err
			}
		}
		return nil
	case reflect.Slice:
		if value.IsNil() {
			return nil
		}
		if value.Type().Elem().Kind() == reflect.Uint8 {
			return errors.New("JSON data model forbids byte-slice coercion")
		}
		for index := 0; index < value.Len(); index++ {
			if err := validateJSONDataModel(value.Index(index), depth+1); err != nil {
				return err
			}
		}
		return nil
	case reflect.Array:
		for index := 0; index < value.Len(); index++ {
			if err := validateJSONDataModel(value.Index(index), depth+1); err != nil {
				return err
			}
		}
		return nil
	default:
		return fmt.Errorf("unsupported non-JSON Go value kind %s", value.Kind())
	}
}

func hasCustomSerialization(valueType reflect.Type) bool {
	if valueType.Implements(jsonMarshalerType) || valueType.Implements(textMarshalerType) {
		return true
	}
	if valueType.Kind() == reflect.Pointer {
		return false
	}
	pointerType := reflect.PointerTo(valueType)
	return pointerType.Implements(jsonMarshalerType) || pointerType.Implements(textMarshalerType)
}

func decodeJSON(data []byte) (any, error) {
	result, err := canonical.CanonicalizeBytes(data, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(result.Bytes))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	return value, nil
}

func cloneDescriptor(descriptor *ArtifactDescriptor) *ArtifactDescriptor {
	if descriptor == nil {
		return nil
	}
	clone := *descriptor
	return &clone
}

func cloneFileState(state map[string]FileRecord) map[string]FileRecord {
	clone := make(map[string]FileRecord, len(state))
	for path, record := range state {
		clone[path] = FileRecord{Content: *cloneDescriptor(&record.Content), Mode: record.Mode}
	}
	return clone
}

func cloneSkillState(state map[string]SkillRecord) map[string]SkillRecord {
	clone := make(map[string]SkillRecord, len(state))
	for packageID, record := range state {
		clone[packageID] = SkillRecord{Descriptor: *cloneDescriptor(&record.Descriptor)}
	}
	return clone
}
