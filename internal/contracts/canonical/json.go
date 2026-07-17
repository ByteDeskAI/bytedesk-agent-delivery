package canonical

import (
	"bytes"
	"encoding/json"
	"io"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

var jsonNumberPattern = regexp.MustCompile(`^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$`)

const (
	minSafeInteger = int64(-9_007_199_254_740_991)
	maxSafeInteger = int64(9_007_199_254_740_991)
)

func parseJSON(input []byte, limits Limits) (*value, error) {
	if len(input) == 0 {
		return nil, fail(CodeEmptyInput)
	}
	if !utf8.Valid(input) {
		return nil, fail(CodeInvalidUTF8)
	}
	if err := validateJSONStrings(input); err != nil {
		return nil, err
	}

	decoder := json.NewDecoder(bytes.NewReader(input))
	decoder.UseNumber()
	token, err := decoder.Token()
	if err != nil {
		return nil, fail(CodeInvalidJSON)
	}
	b := &budget{limits: limits}
	root, err := parseJSONToken(decoder, token, 1, b)
	if err != nil {
		return nil, err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return nil, fail(CodeInvalidJSON)
	}
	return root, nil
}

func parseJSONToken(decoder *json.Decoder, token json.Token, depth int, b *budget) (*value, error) {
	if err := b.value(depth); err != nil {
		return nil, err
	}
	switch typed := token.(type) {
	case nil:
		return &value{kind: kindNull}, nil
	case bool:
		return &value{kind: kindBool, boolean: typed}, nil
	case string:
		return &value{kind: kindString, text: typed}, nil
	case json.Number:
		number, err := parseFiniteNumber(string(typed))
		if err != nil {
			return nil, err
		}
		return &value{kind: kindNumber, number: number}, nil
	case json.Delim:
		switch typed {
		case '{':
			return parseJSONObject(decoder, depth, b)
		case '[':
			return parseJSONArray(decoder, depth, b)
		default:
			return nil, fail(CodeInvalidJSON)
		}
	default:
		return nil, fail(CodeInvalidJSON)
	}
}

func parseJSONObject(decoder *json.Decoder, depth int, b *budget) (*value, error) {
	result := &value{kind: kindObject}
	seen := make(map[string]struct{})
	for decoder.More() {
		token, err := decoder.Token()
		if err != nil {
			return nil, fail(CodeInvalidJSON)
		}
		name, ok := token.(string)
		if !ok {
			return nil, fail(CodeInvalidJSON)
		}
		if err := b.node(); err != nil {
			return nil, err
		}
		if _, duplicate := seen[name]; duplicate {
			return nil, fail(CodeDuplicateKey)
		}
		seen[name] = struct{}{}

		token, err = decoder.Token()
		if err != nil {
			return nil, fail(CodeInvalidJSON)
		}
		child, err := parseJSONToken(decoder, token, depth+1, b)
		if err != nil {
			return nil, err
		}
		result.object = append(result.object, newMember(name, child))
	}
	closing, err := decoder.Token()
	if err != nil || closing != json.Delim('}') {
		return nil, fail(CodeInvalidJSON)
	}
	return result, nil
}

func parseJSONArray(decoder *json.Decoder, depth int, b *budget) (*value, error) {
	result := &value{kind: kindArray}
	for decoder.More() {
		token, err := decoder.Token()
		if err != nil {
			return nil, fail(CodeInvalidJSON)
		}
		child, err := parseJSONToken(decoder, token, depth+1, b)
		if err != nil {
			return nil, err
		}
		result.array = append(result.array, child)
	}
	closing, err := decoder.Token()
	if err != nil || closing != json.Delim(']') {
		return nil, fail(CodeInvalidJSON)
	}
	return result, nil
}

func parseFiniteNumber(raw string) (float64, error) {
	if !jsonNumberPattern.MatchString(raw) {
		return 0, fail(CodeInvalidNumber)
	}
	if !strings.ContainsAny(raw, ".eE") {
		integer, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || integer < minSafeInteger || integer > maxSafeInteger {
			return 0, fail(CodeInvalidNumber)
		}
	}
	number, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsInf(number, 0) || math.IsNaN(number) {
		return 0, fail(CodeInvalidNumber)
	}
	return number, nil
}

func validateJSONStrings(input []byte) error {
	inString := false
	for index := 0; index < len(input); index++ {
		current := input[index]
		if !inString {
			if current == '"' {
				inString = true
			}
			continue
		}
		if current == '"' {
			inString = false
			continue
		}
		if current < 0x20 {
			return fail(CodeInvalidJSON)
		}
		if current != '\\' {
			continue
		}
		if index+1 >= len(input) {
			return fail(CodeInvalidJSON)
		}
		escape := input[index+1]
		if escape != 'u' {
			if !bytes.ContainsRune([]byte(`"\\/bfnrt`), rune(escape)) {
				return fail(CodeInvalidJSON)
			}
			index++
			continue
		}

		first, ok := readHexQuad(input, index+2)
		if !ok {
			return fail(CodeInvalidJSON)
		}
		if first >= 0xdc00 && first <= 0xdfff {
			return fail(CodeInvalidUnicode)
		}
		if first >= 0xd800 && first <= 0xdbff {
			if index+11 >= len(input) || input[index+6] != '\\' || input[index+7] != 'u' {
				return fail(CodeInvalidUnicode)
			}
			second, ok := readHexQuad(input, index+8)
			if !ok || second < 0xdc00 || second > 0xdfff {
				return fail(CodeInvalidUnicode)
			}
			index += 11
			continue
		}
		index += 5
	}
	return nil
}

func readHexQuad(input []byte, start int) (uint16, bool) {
	if start+4 > len(input) {
		return 0, false
	}
	var result uint16
	for _, char := range input[start : start+4] {
		result <<= 4
		switch {
		case char >= '0' && char <= '9':
			result |= uint16(char - '0')
		case char >= 'a' && char <= 'f':
			result |= uint16(char-'a') + 10
		case char >= 'A' && char <= 'F':
			result |= uint16(char-'A') + 10
		default:
			return 0, false
		}
	}
	return result, true
}
