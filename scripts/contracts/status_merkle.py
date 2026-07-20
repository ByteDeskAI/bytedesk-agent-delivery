#!/usr/bin/env python3
"""Bounded RFC 6962-style release-status Merkle proof primitives."""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

import rfc8785


EMPTY_ROOT = "sha256:" + hashlib.sha256(b"").hexdigest()


def _raw(digest: str) -> bytes:
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("invalid SHA-256 digest")
    return bytes.fromhex(digest.removeprefix("sha256:"))


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def status_leaf_digest(
    *,
    subject_kind: str,
    subject: dict[str, Any],
    sequence: int,
    epoch: int,
    head: dict[str, Any],
) -> str:
    preimage = {
        "profile": "bytedesk.release-status-merkle-leaf/1",
        "subjectKind": subject_kind,
        "subject": subject,
        "sequence": sequence,
        "epoch": epoch,
        "head": head,
    }
    return _digest(b"\x00" + rfc8785.dumps(preimage))


def node_digest(left: str, right: str) -> str:
    return _digest(b"\x01" + _raw(left) + _raw(right))


def _split(size: int) -> int:
    if size <= 1:
        raise ValueError("Merkle split requires at least two leaves")
    return 1 << ((size - 1).bit_length() - 1)


def merkle_root(leaves: Sequence[str]) -> str:
    size = len(leaves)
    if size == 0:
        return EMPTY_ROOT
    if size == 1:
        _raw(leaves[0])
        return leaves[0]
    split = _split(size)
    return node_digest(
        merkle_root(leaves[:split]),
        merkle_root(leaves[split:]),
    )


def inclusion_proof(leaves: Sequence[str], leaf_index: int) -> list[str]:
    if not 0 <= leaf_index < len(leaves):
        raise ValueError("leaf index is outside the Merkle tree")
    if len(leaves) == 1:
        return []
    split = _split(len(leaves))
    if leaf_index < split:
        return [
            *inclusion_proof(leaves[:split], leaf_index),
            merkle_root(leaves[split:]),
        ]
    return [
        *inclusion_proof(leaves[split:], leaf_index - split),
        merkle_root(leaves[:split]),
    ]


def verify_inclusion(
    *,
    leaf_digest: str,
    leaf_index: int,
    tree_size: int,
    audit_path: Sequence[str],
    expected_root: str,
) -> bool:
    if tree_size <= 0 or not 0 <= leaf_index < tree_size:
        return False

    def rebuild(index: int, size: int, path: Sequence[str]) -> str:
        if size == 1:
            if path:
                raise ValueError("inclusion path has trailing nodes")
            return leaf_digest
        if not path:
            raise ValueError("inclusion path is incomplete")
        split = _split(size)
        sibling = path[-1]
        if index < split:
            return node_digest(rebuild(index, split, path[:-1]), sibling)
        return node_digest(sibling, rebuild(index - split, size - split, path[:-1]))

    try:
        return rebuild(leaf_index, tree_size, audit_path) == expected_root
    except (ValueError, IndexError):
        return False


def consistency_proof(
    leaves: Sequence[str],
    old_size: int,
) -> list[str]:
    new_size = len(leaves)
    if not 0 < old_size <= new_size:
        raise ValueError("invalid consistency proof sizes")

    def subproof(prefix_size: int, nodes: Sequence[str], complete: bool) -> list[str]:
        if prefix_size == len(nodes):
            return [] if complete else [merkle_root(nodes)]
        split = _split(len(nodes))
        if prefix_size <= split:
            return [
                *subproof(prefix_size, nodes[:split], complete),
                merkle_root(nodes[split:]),
            ]
        return [
            *subproof(prefix_size - split, nodes[split:], False),
            merkle_root(nodes[:split]),
        ]

    return subproof(old_size, leaves, True)


def verify_consistency(
    *,
    old_size: int,
    new_size: int,
    old_root: str,
    new_root: str,
    audit_path: Sequence[str],
) -> bool:
    if not 0 < old_size <= new_size:
        return False
    if old_size == new_size:
        return not audit_path and old_root == new_root
    fn = old_size - 1
    sn = new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    path_index = 0
    if fn == 0:
        first_root = old_root
        second_root = old_root
    else:
        if not audit_path:
            return False
        first_root = audit_path[0]
        second_root = audit_path[0]
        path_index = 1
    while path_index < len(audit_path):
        node = audit_path[path_index]
        if (fn & 1) or fn == sn:
            first_root = node_digest(node, first_root)
            second_root = node_digest(node, second_root)
            while fn and not (fn & 1):
                fn >>= 1
                sn >>= 1
        else:
            second_root = node_digest(second_root, node)
        fn >>= 1
        sn >>= 1
        path_index += 1
    return fn == 0 and first_root == old_root and second_root == new_root
