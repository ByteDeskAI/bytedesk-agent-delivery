"""Shared fail-closed helpers for Agent Delivery contract tooling."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
from typing import Any, BinaryIO, Callable

import rfc8785


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_ROOT = REPOSITORY_ROOT / "contracts"
SCHEMAS_ROOT = CONTRACTS_ROOT / "schemas" / "v1"
MAX_STRUCTURED_JSON_BYTES = 4 * 1024 * 1024
MAX_JSON_MODEL_DEPTH = 64
MAX_JSON_MODEL_NODES = 100_000
MIN_SAFE_INTEGER = -9_007_199_254_740_991
MAX_SAFE_INTEGER = 9_007_199_254_740_991


class ContractToolError(RuntimeError):
    """A deterministic, safe-to-display contract-tool failure."""


def _reject_duplicate(pairs: list[tuple[str, Any]], description: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractToolError(f"duplicate JSON member in {description}")
        result[key] = value
    return result


def _reject_constant(_value: str, description: str) -> None:
    raise ContractToolError(f"non-finite JSON number in {description}")


def _parse_integer(raw: str, description: str) -> int:
    digits = raw[1:] if raw.startswith("-") else raw
    if len(digits) > 16:
        raise ContractToolError(f"JSON integer exceeds the interoperable range in {description}")
    value = int(raw)
    if value < MIN_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
        raise ContractToolError(f"JSON integer exceeds the interoperable range in {description}")
    return value


def _parse_float(raw: str, description: str) -> float:
    try:
        value = float(raw)
    except (OverflowError, ValueError) as error:
        raise ContractToolError(f"invalid JSON number in {description}") from error
    if not math.isfinite(value):
        raise ContractToolError(f"non-finite JSON number in {description}")
    return value


def _register_preflight_node(nodes: int, description: str) -> int:
    nodes += 1
    if nodes > MAX_JSON_MODEL_NODES:
        raise ContractToolError(f"JSON model exceeds the node limit in {description}")
    return nodes


def _preflight_json_bytes(payload: bytes, description: str) -> tuple[int, int]:
    """Count JSON lexical value/key nodes and depth before decoder allocation."""

    if len(payload) > MAX_STRUCTURED_JSON_BYTES:
        raise ContractToolError(f"structured JSON exceeds the input byte limit in {description}")
    nodes = 0
    depth = 0
    maximum_depth = 0
    index = 0
    whitespace = b" \t\r\n"
    length = len(payload)
    while index < length:
        current = payload[index]
        if current in whitespace or current in b",:":
            index += 1
            continue
        if current in b"{[":
            value_depth = depth + 1
            if value_depth > MAX_JSON_MODEL_DEPTH:
                raise ContractToolError(f"JSON model exceeds the depth limit in {description}")
            maximum_depth = max(maximum_depth, value_depth)
            nodes = _register_preflight_node(nodes, description)
            depth += 1
            index += 1
            continue
        if current in b"}]":
            depth = max(0, depth - 1)
            index += 1
            continue
        if current == ord('"'):
            index += 1
            while index < length:
                current = payload[index]
                if current == ord('"'):
                    index += 1
                    break
                if current == ord("\\"):
                    index += 2
                else:
                    index += 1
            nodes = _register_preflight_node(nodes, description)
            lookahead = index
            while lookahead < length and payload[lookahead] in whitespace:
                lookahead += 1
            if lookahead >= length or payload[lookahead] != ord(":"):
                value_depth = depth + 1
                if value_depth > MAX_JSON_MODEL_DEPTH:
                    raise ContractToolError(f"JSON model exceeds the depth limit in {description}")
                maximum_depth = max(maximum_depth, value_depth)
            continue
        if current == ord("-") or ord("0") <= current <= ord("9"):
            nodes = _register_preflight_node(nodes, description)
            value_depth = depth + 1
            if value_depth > MAX_JSON_MODEL_DEPTH:
                raise ContractToolError(f"JSON model exceeds the depth limit in {description}")
            maximum_depth = max(maximum_depth, value_depth)
            index += 1
            while index < length and payload[index] not in whitespace + b",]}":
                index += 1
            continue
        literal_length = 0
        if payload.startswith(b"true", index) or payload.startswith(b"null", index):
            literal_length = 4
        elif payload.startswith(b"false", index):
            literal_length = 5
        if literal_length:
            nodes = _register_preflight_node(nodes, description)
            value_depth = depth + 1
            if value_depth > MAX_JSON_MODEL_DEPTH:
                raise ContractToolError(f"JSON model exceeds the depth limit in {description}")
            maximum_depth = max(maximum_depth, value_depth)
            index += literal_length
            continue
        # The standard decoder supplies the precise syntax failure. Advancing
        # here keeps preflight linear and prevents malformed input from looping.
        index += 1
    return nodes, maximum_depth


def _contains_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _validate_json_model(value: Any, description: str) -> tuple[int, int]:
    nodes = 0
    maximum_depth = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_JSON_MODEL_DEPTH:
            raise ContractToolError(f"JSON model exceeds the depth limit in {description}")
        maximum_depth = max(maximum_depth, depth)
        nodes = _register_preflight_node(nodes, description)
        if current is None or isinstance(current, bool):
            continue
        if isinstance(current, int):
            if current < MIN_SAFE_INTEGER or current > MAX_SAFE_INTEGER:
                raise ContractToolError(
                    f"JSON integer exceeds the interoperable range in {description}"
                )
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                raise ContractToolError(f"non-finite JSON number in {description}")
            continue
        if isinstance(current, str):
            if _contains_surrogate(current):
                raise ContractToolError(f"invalid Unicode scalar value in {description}")
            continue
        if isinstance(current, list):
            stack.extend((child, depth + 1) for child in reversed(current))
            continue
        if isinstance(current, dict):
            for key, child in reversed(list(current.items())):
                if not isinstance(key, str):
                    raise ContractToolError(f"non-string JSON member name in {description}")
                if _contains_surrogate(key):
                    raise ContractToolError(f"invalid Unicode scalar value in {description}")
                nodes = _register_preflight_node(nodes, description)
                stack.append((child, depth + 1))
            continue
        raise ContractToolError(f"value is outside the JSON data model in {description}")
    return nodes, maximum_depth


def strict_json_bytes(payload: bytes, description: str) -> Any:
    """Parse one bounded JSON data-model value without ambiguous inputs."""

    preflight_nodes, preflight_depth = _preflight_json_bytes(payload, description)
    try:
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _reject_duplicate(pairs, description),
            parse_constant=lambda constant: _reject_constant(constant, description),
            parse_int=lambda raw: _parse_integer(raw, description),
            parse_float=lambda raw: _parse_float(raw, description),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ContractToolError(f"cannot parse strict JSON in {description}") from error
    observed_nodes, observed_depth = _validate_json_model(value, description)
    if (preflight_nodes, preflight_depth) != (observed_nodes, observed_depth):
        raise ContractToolError(f"JSON preflight/model accounting differs in {description}")
    return value


def load_json_bytes(path: Path) -> tuple[Any, bytes]:
    """Read and parse one JSON file without reading beyond the accepted limit."""

    try:
        payload = stable_read_bytes(
            path,
            description=f"strict JSON {path}",
            maximum_bytes=MAX_STRUCTURED_JSON_BYTES,
        )
    except ContractToolError as error:
        if "exceeds the 4194304-byte limit" in str(error):
            raise ContractToolError(
                f"structured JSON exceeds the input byte limit in {path}"
            ) from error
        raise
    return strict_json_bytes(payload, str(path)), payload


def load_json(path: Path) -> Any:
    """Load one JSON file under the accepted structured-object limits."""

    return load_json_bytes(path)[0]


def canonical_json(value: Any) -> bytes:
    """Return RFC 8785 JSON Canonicalization Scheme bytes."""

    _validate_json_model(value, "canonical JSON value")
    try:
        payload = rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, ValueError, TypeError) as error:
        raise ContractToolError(f"value is not RFC 8785 canonicalizable: {error}") from error
    if len(payload) > MAX_STRUCTURED_JSON_BYTES:
        raise ContractToolError("canonical JSON exceeds the output byte limit")
    return payload


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def file_digest(path: Path) -> str:
    digest, _ = stable_file_digest(path, description=str(path))
    return digest


def stable_file_digest(
    path: Path,
    *,
    description: str,
    maximum_bytes: int | None = None,
) -> tuple[str, int]:
    """Hash one regular non-link file through one stable descriptor."""

    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ContractToolError(f"cannot open {description} safely: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ContractToolError(f"{description} must be a regular file")
        if maximum_bytes is not None and before.st_size > maximum_bytes:
            raise ContractToolError(f"{description} exceeds the {maximum_bytes}-byte limit")
        digest = hashlib.sha256()
        observed = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            observed += len(block)
            if maximum_bytes is not None and observed > maximum_bytes:
                raise ContractToolError(f"{description} exceeds the {maximum_bytes}-byte limit")
            digest.update(block)
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or observed != before.st_size:
            raise ContractToolError(f"{description} changed while it was being hashed")
        return f"sha256:{digest.hexdigest()}", observed
    except OSError as error:
        raise ContractToolError(f"cannot hash {description} safely: {error}") from error
    finally:
        os.close(descriptor)


def stable_read_bytes(path: Path, *, description: str, maximum_bytes: int) -> bytes:
    """Bounded-read one regular non-link file through one stable descriptor."""

    if maximum_bytes < 0:
        raise ContractToolError(f"invalid byte limit for {description}")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ContractToolError(f"cannot open {description} safely: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ContractToolError(f"{description} must be a regular file")
        if before.st_size > maximum_bytes:
            raise ContractToolError(f"{description} exceeds the {maximum_bytes}-byte limit")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or len(payload) != before.st_size:
            raise ContractToolError(f"{description} changed while it was being read")
        if len(payload) > maximum_bytes:
            raise ContractToolError(f"{description} exceeds the {maximum_bytes}-byte limit")
        return payload
    except OSError as error:
        raise ContractToolError(f"cannot read {description} safely: {error}") from error
    finally:
        os.close(descriptor)


def repository_path(path: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except (OSError, ValueError) as error:
        raise ContractToolError(f"path escapes repository or is unavailable: {path}") from error


def atomic_write(
    path: Path,
    writer: Callable[[BinaryIO], None],
    *,
    require_absent: bool = False,
) -> None:
    """Atomically publish writer output from an exclusive randomized file."""

    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise ContractToolError(f"cannot resolve output directory for {path}: {error}") from error
    if parent != path.parent:
        raise ContractToolError(f"output directory contains a symbolic-link component: {path.parent}")
    if path.is_symlink():
        raise ContractToolError(f"output path must not be a symbolic link: {path}")
    directory_flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    try:
        directory_descriptor = os.open(parent, directory_flags)
    except OSError as error:
        raise ContractToolError(f"cannot open output directory safely: {parent}") from error
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    temporary_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        temporary_flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(
            temporary_name,
            temporary_flags,
            0o600,
            dir_fd=directory_descriptor,
        )
    except OSError as error:
        os.close(directory_descriptor)
        raise ContractToolError(f"cannot create exclusive output temporary for {path}") from error
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", buffering=0, closefd=False) as target:
            writer(target)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if require_absent:
            try:
                os.link(
                    temporary_name,
                    path.name,
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise ContractToolError(f"output path must be absent: {path}") from error
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        else:
            os.rename(
                temporary_name,
                path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
            )
        os.fsync(directory_descriptor)
    except OSError as error:
        raise ContractToolError(f"cannot atomically write {path}: {error}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        os.close(directory_descriptor)


def write_bytes(path: Path, value: bytes, *, require_absent: bool = False) -> None:
    """Atomically write bytes without following a predictable temporary link."""

    def writer(target: BinaryIO) -> None:
        written = 0
        while written < len(value):
            count = target.write(value[written:])
            if count is None or count <= 0:
                raise ContractToolError(f"short write while creating {path}")
            written += count

    atomic_write(path, writer, require_absent=require_absent)


def write_json(path: Path, value: Any, *, canonical: bool = False) -> None:
    if canonical:
        payload = canonical_json(value) + b"\n"
    else:
        payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    write_bytes(path, payload)


def validation_error_key(error: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return a total ordering even when JSON paths mix array indexes and keys."""

    return (
        tuple(str(part) for part in error.absolute_path),
        tuple(str(part) for part in error.absolute_schema_path),
    )
