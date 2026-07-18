"""Closed resource and portable-path profile for contract bundle v1."""

from __future__ import annotations

import unicodedata
import io
import hashlib
import tarfile
from collections.abc import Iterable
from typing import BinaryIO, Mapping


# Contract bundles contain schemas and conformance material. The only payload
# blobs are closed, digest-named raw CAS fixtures required to verify the exact
# renderer and private-compilation graphs; they are not deployable releases.
# These deliberately lower limits keep the Python reference verifier's raw
# snapshot plus extracted-member working set below a predictable ceiling.
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_MEMBERS = 20_000
MAX_BUNDLE_MEMBER_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_CONTENT_BYTES = 48 * 1024 * 1024
MAX_PORTABLE_PATH_BYTES = 1_024
MAX_PORTABLE_PATH_SEGMENTS = 32
MAX_PORTABLE_SEGMENT_BYTES = 255
CANONICAL_ARCHIVE_MEMORY_SPOOL_BYTES = 8 * 1024 * 1024

RAW_JSON_PREFIXES = (
    "contracts/fixtures/encoding/",
    "contracts/vendor/",
)
RAW_CAS_PREFIXES = (
    "contracts/fixtures/operations/private-compilation-cas/blobs/sha256/",
    "contracts/fixtures/operations/renderer-cas/blobs/sha256/",
)
STRUCTURED_CONTROL_PREFIXES = (
    "contracts/asyncapi/v1/",
    "contracts/bundle/v1/",
    "contracts/compatibility/",
    "contracts/events/v1/",
    "contracts/fixtures/lifecycle/",
    "contracts/fixtures/operations/",
    "contracts/fixtures/schema/",
    "contracts/lifecycle/",
    "contracts/openapi/v1/",
    "contracts/ports/v1/",
    "contracts/schemas/v1/",
)

WINDOWS_FORBIDDEN_CHARACTERS = frozenset(':<>"|?*')
WINDOWS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul", "clock$", "conin$", "conout$"}
    | {f"com{suffix}" for suffix in "123456789¹²³"}
    | {f"lpt{suffix}" for suffix in "123456789¹²³"}
)


class BundleProfileError(ValueError):
    """An input is outside the closed contract-bundle profile."""


def structured_control_member(path: str) -> bool:
    """Return the fixed semantic role for one contract-bundle member path.

    JSON filename suffixes do not determine authority. The v1 source layout is
    the closed role declaration: contract/control namespaces are JCS objects,
    while parser probes and pinned vendor material are exact raw payloads.
    Any future JSON namespace must be classified here before publication.
    """

    portable_path_collision_key(path)
    if not path.endswith(".json"):
        return False
    if path.startswith(RAW_JSON_PREFIXES):
        return False
    if path.startswith(STRUCTURED_CONTROL_PREFIXES):
        return True
    raise BundleProfileError(f"JSON bundle member has no declared v1 role: {path}")


def normalized_member_payload(path: str, payload: bytes) -> bytes:
    """Return the exact v1 authority bytes for a classified member."""

    if any(path.startswith(prefix) for prefix in RAW_CAS_PREFIXES):
        digest_hex = path.rsplit("/", 1)[-1]
        if (
            len(digest_hex) != 64
            or any(character not in "0123456789abcdef" for character in digest_hex)
        ):
            raise BundleProfileError(f"raw CAS member has an invalid digest path: {path}")
        if hashlib.sha256(payload).hexdigest() != digest_hex:
            raise BundleProfileError(f"raw CAS member bytes do not match its digest path: {path}")
        return payload
    if not structured_control_member(path):
        return payload
    # Local import keeps the archive/path profile reusable by contractlib while
    # still routing all structured controls through the one strict JCS lane.
    from contractlib import canonical_json, strict_json_bytes

    return canonical_json(strict_json_bytes(payload, path))


def portable_path_collision_key(value: str) -> str:
    """Validate one portable path and return its NFC case-fold collision key."""

    if not isinstance(value, str) or not value:
        raise BundleProfileError("portable path must be a non-empty string")
    if unicodedata.normalize("NFC", value) != value:
        raise BundleProfileError(f"portable path is not Unicode NFC: {value!r}")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise BundleProfileError(f"portable path is not valid UTF-8: {value!r}") from error
    if len(encoded) > MAX_PORTABLE_PATH_BYTES:
        raise BundleProfileError(
            f"portable path exceeds {MAX_PORTABLE_PATH_BYTES} UTF-8 bytes: {value!r}"
        )
    if value.startswith("/") or "\\" in value:
        raise BundleProfileError(f"portable path is not relative POSIX syntax: {value!r}")

    segments = value.split("/")
    if len(segments) > MAX_PORTABLE_PATH_SEGMENTS:
        raise BundleProfileError(
            f"portable path exceeds {MAX_PORTABLE_PATH_SEGMENTS} segments: {value!r}"
        )
    for segment in segments:
        if segment in {"", ".", ".."}:
            raise BundleProfileError(f"portable path has an invalid segment: {value!r}")
        if len(segment.encode("utf-8")) > MAX_PORTABLE_SEGMENT_BYTES:
            raise BundleProfileError(
                f"portable path segment exceeds {MAX_PORTABLE_SEGMENT_BYTES} UTF-8 bytes: {value!r}"
            )
        if segment.endswith((".", " ")) or any(
            character in WINDOWS_FORBIDDEN_CHARACTERS for character in segment
        ):
            raise BundleProfileError(f"portable path has Windows-ambiguous syntax: {value!r}")
        if any(unicodedata.category(character).startswith("C") for character in segment):
            raise BundleProfileError(
                f"portable path has a control, format, surrogate, private-use, or unassigned character: {value!r}"
            )
        base = segment.casefold().split(".", 1)[0]
        if base in WINDOWS_DEVICE_NAMES:
            raise BundleProfileError(f"portable path has a Windows device name: {value!r}")

    return unicodedata.normalize("NFC", value.casefold())


def validate_portable_path_set(paths: Iterable[str], description: str) -> None:
    """Reject exact, Unicode-normalized, or case-folded path collisions."""

    exact: set[str] = set()
    collision_keys: dict[str, str] = {}
    for value in paths:
        if value in exact:
            raise BundleProfileError(f"duplicate {description} path: {value}")
        exact.add(value)
        key = portable_path_collision_key(value)
        previous = collision_keys.get(key)
        if previous is not None and previous != value:
            raise BundleProfileError(
                f"{description} paths collide after NFC case folding: {previous!r}, {value!r}"
            )
        collision_keys[key] = value


def write_deterministic_tar(target: BinaryIO, members: Mapping[str, bytes]) -> None:
    """Write the one accepted uncompressed PAX representation of bundle members."""

    if len(members) > MAX_BUNDLE_MEMBERS:
        raise BundleProfileError("bundle exceeds the member-count limit")
    validate_portable_path_set(members, "archive member")
    start_offset = target.tell()
    cumulative_size = 0
    with tarfile.open(fileobj=target, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for member_path in sorted(members):
            payload = members[member_path]
            if len(payload) > MAX_BUNDLE_MEMBER_BYTES:
                raise BundleProfileError(f"bundle member exceeds the size limit: {member_path}")
            cumulative_size += len(payload)
            if cumulative_size > MAX_BUNDLE_CONTENT_BYTES:
                raise BundleProfileError("bundle exceeds the cumulative content limit")
            info = tarfile.TarInfo(member_path)
            info.size = len(payload)
            info.mode = 0o444
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    if target.tell() - start_offset > MAX_BUNDLE_BYTES:
        raise BundleProfileError("bundle exceeds the exact archive byte limit")
