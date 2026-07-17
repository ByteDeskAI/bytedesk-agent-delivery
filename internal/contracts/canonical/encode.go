package canonical

import (
	"bytes"
	"sort"
	"unicode/utf8"

	"github.com/gowebpki/jcs"
)

func encodeCanonical(root *value, maxBytes int64) ([]byte, error) {
	output := &limitedBuffer{maximum: maxBytes}
	if err := encodeValue(output, root); err != nil {
		return nil, err
	}
	return output.Bytes(), nil
}

func encodeValue(output *limitedBuffer, current *value) error {
	switch current.kind {
	case kindNull:
		return output.writeString("null")
	case kindBool:
		if current.boolean {
			return output.writeString("true")
		}
		return output.writeString("false")
	case kindNumber:
		number, err := jcs.NumberToJSON(current.number)
		if err != nil {
			return fail(CodeInvalidNumber)
		}
		return output.writeString(number)
	case kindString:
		return encodeString(output, current.text)
	case kindArray:
		if err := output.writeByte('['); err != nil {
			return err
		}
		for index, item := range current.array {
			if index > 0 {
				if err := output.writeByte(','); err != nil {
					return err
				}
			}
			if err := encodeValue(output, item); err != nil {
				return err
			}
		}
		return output.writeByte(']')
	case kindObject:
		members := append([]member(nil), current.object...)
		sort.Slice(members, func(first, second int) bool {
			return utf16Less(members[first].sortKey, members[second].sortKey)
		})
		if err := output.writeByte('{'); err != nil {
			return err
		}
		for index, entry := range members {
			if index > 0 {
				if err := output.writeByte(','); err != nil {
					return err
				}
			}
			if err := encodeString(output, entry.name); err != nil {
				return err
			}
			if err := output.writeByte(':'); err != nil {
				return err
			}
			if err := encodeValue(output, entry.value); err != nil {
				return err
			}
		}
		return output.writeByte('}')
	default:
		return fail(CodeUnsupportedNode)
	}
}

func utf16Less(first, second []uint16) bool {
	limit := len(first)
	if len(second) < limit {
		limit = len(second)
	}
	for index := 0; index < limit; index++ {
		if first[index] != second[index] {
			return first[index] < second[index]
		}
	}
	return len(first) < len(second)
}

func encodeString(output *limitedBuffer, input string) error {
	if err := output.writeByte('"'); err != nil {
		return err
	}
	for _, current := range input {
		switch current {
		case '"':
			if err := output.writeString(`\"`); err != nil {
				return err
			}
		case '\\':
			if err := output.writeString(`\\`); err != nil {
				return err
			}
		case '\b':
			if err := output.writeString(`\b`); err != nil {
				return err
			}
		case '\t':
			if err := output.writeString(`\t`); err != nil {
				return err
			}
		case '\n':
			if err := output.writeString(`\n`); err != nil {
				return err
			}
		case '\f':
			if err := output.writeString(`\f`); err != nil {
				return err
			}
		case '\r':
			if err := output.writeString(`\r`); err != nil {
				return err
			}
		default:
			if current < 0x20 {
				const hexadecimal = "0123456789abcdef"
				escaped := []byte{'\\', 'u', '0', '0', hexadecimal[byte(current)>>4], hexadecimal[byte(current)&0x0f]}
				if err := output.write(escaped); err != nil {
					return err
				}
				continue
			}
			var encoded [utf8.UTFMax]byte
			length := utf8.EncodeRune(encoded[:], current)
			if err := output.write(encoded[:length]); err != nil {
				return err
			}
		}
	}
	return output.writeByte('"')
}

type limitedBuffer struct {
	buffer  bytes.Buffer
	maximum int64
}

func (b *limitedBuffer) writeByte(value byte) error {
	return b.write([]byte{value})
}

func (b *limitedBuffer) writeString(value string) error {
	if int64(len(value)) > b.maximum-int64(b.buffer.Len()) {
		return fail(CodeCanonicalTooLarge)
	}
	b.buffer.WriteString(value)
	return nil
}

func (b *limitedBuffer) write(value []byte) error {
	if int64(len(value)) > b.maximum-int64(b.buffer.Len()) {
		return fail(CodeCanonicalTooLarge)
	}
	b.buffer.Write(value)
	return nil
}

func (b *limitedBuffer) Bytes() []byte { return b.buffer.Bytes() }
