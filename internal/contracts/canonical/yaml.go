package canonical

import (
	"bytes"
	"io"
	"strings"
	"unicode/utf8"

	"go.yaml.in/yaml/v3"
)

const (
	yamlMapTag    = "!!map"
	yamlSeqTag    = "!!seq"
	yamlStringTag = "!!str"
	yamlNullTag   = "!!null"
	yamlBoolTag   = "!!bool"
	yamlIntTag    = "!!int"
	yamlFloatTag  = "!!float"
)

func parseYAML(input []byte, limits Limits) (*value, error) {
	if len(input) == 0 {
		return nil, fail(CodeEmptyInput)
	}
	if !utf8.Valid(input) {
		return nil, fail(CodeInvalidUTF8)
	}

	decoder := yaml.NewDecoder(bytes.NewReader(input))
	var document yaml.Node
	if err := decoder.Decode(&document); err != nil {
		if err == io.EOF {
			return nil, fail(CodeEmptyInput)
		}
		return nil, fail(CodeInvalidYAML)
	}
	var extra yaml.Node
	if err := decoder.Decode(&extra); err == nil {
		return nil, fail(CodeMultipleDocuments)
	} else if err != io.EOF {
		return nil, fail(CodeInvalidYAML)
	}
	if document.Kind != yaml.DocumentNode || len(document.Content) != 1 {
		return nil, fail(CodeInvalidYAML)
	}

	b := &budget{limits: limits}
	return convertYAMLNode(document.Content[0], 1, b)
}

func convertYAMLNode(node *yaml.Node, depth int, b *budget) (*value, error) {
	if node == nil {
		return nil, fail(CodeInvalidYAML)
	}
	if node.Kind == yaml.AliasNode {
		return nil, fail(CodeAliasForbidden)
	}
	if err := b.value(depth); err != nil {
		return nil, err
	}

	switch node.Kind {
	case yaml.MappingNode:
		if node.Tag != yamlMapTag {
			return nil, fail(CodeUnsupportedTag)
		}
		if len(node.Content)%2 != 0 {
			return nil, fail(CodeInvalidYAML)
		}
		result := &value{kind: kindObject}
		seen := make(map[string]struct{}, len(node.Content)/2)
		for index := 0; index < len(node.Content); index += 2 {
			key := node.Content[index]
			if key.Kind == yaml.AliasNode {
				return nil, fail(CodeAliasForbidden)
			}
			if key.Kind != yaml.ScalarNode || key.Tag != yamlStringTag {
				if !isCoreTag(key.Tag) {
					return nil, fail(CodeUnsupportedTag)
				}
				return nil, fail(CodeNonStringKey)
			}
			if !utf8.ValidString(key.Value) {
				return nil, fail(CodeInvalidUTF8)
			}
			if err := b.node(); err != nil {
				return nil, err
			}
			if _, duplicate := seen[key.Value]; duplicate {
				return nil, fail(CodeDuplicateKey)
			}
			seen[key.Value] = struct{}{}
			child, err := convertYAMLNode(node.Content[index+1], depth+1, b)
			if err != nil {
				return nil, err
			}
			result.object = append(result.object, newMember(key.Value, child))
		}
		return result, nil

	case yaml.SequenceNode:
		if node.Tag != yamlSeqTag {
			return nil, fail(CodeUnsupportedTag)
		}
		result := &value{kind: kindArray}
		for _, item := range node.Content {
			child, err := convertYAMLNode(item, depth+1, b)
			if err != nil {
				return nil, err
			}
			result.array = append(result.array, child)
		}
		return result, nil

	case yaml.ScalarNode:
		return convertYAMLScalar(node)

	default:
		return nil, fail(CodeUnsupportedNode)
	}
}

func convertYAMLScalar(node *yaml.Node) (*value, error) {
	if !utf8.ValidString(node.Value) {
		return nil, fail(CodeInvalidUTF8)
	}
	switch node.Tag {
	case yamlStringTag:
		return &value{kind: kindString, text: node.Value}, nil
	case yamlNullTag:
		return &value{kind: kindNull}, nil
	case yamlBoolTag:
		switch strings.ToLower(node.Value) {
		case "true":
			return &value{kind: kindBool, boolean: true}, nil
		case "false":
			return &value{kind: kindBool, boolean: false}, nil
		default:
			return nil, fail(CodeUnsupportedNode)
		}
	case yamlIntTag, yamlFloatTag:
		number, err := parseFiniteNumber(node.Value)
		if err != nil {
			return nil, err
		}
		return &value{kind: kindNumber, number: number}, nil
	default:
		if !isCoreTag(node.Tag) {
			return nil, fail(CodeUnsupportedTag)
		}
		return nil, fail(CodeUnsupportedNode)
	}
}

func isCoreTag(tag string) bool {
	switch tag {
	case yamlMapTag, yamlSeqTag, yamlStringTag, yamlNullTag, yamlBoolTag, yamlIntTag, yamlFloatTag:
		return true
	default:
		return false
	}
}
