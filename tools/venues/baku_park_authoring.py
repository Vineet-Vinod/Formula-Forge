"""Compile the reviewed authored source-space mesh into the atomic Ground patch."""

from __future__ import annotations

import gzip
import hashlib
import struct
from pathlib import Path

from pydantic import TypeAdapter

from venues.baku_ground_dataclasses import GroundPatchSource, PackedPatchRow
from venues.baku_park_authoring_dataclasses import ParkAuthoredGround


def compile_ground(source: ParkAuthoredGround) -> bytes:
    vertices = []
    for vertex in source.vertices:
        p, n, uv = vertex.position_m, vertex.source_normal, vertex.uv
        vertices.append(
            struct.pack(
                "<8f", -p[1] * 100, -p[0] * 100, p[2] * 100, -n[1], -n[0], n[2], *uv
            )
        )
    additions = []
    for face in source.faces:
        if max(face.vertices) >= len(vertices):
            raise ValueError("A Baku authored face references a missing control vertex")
        payload = b"".join(vertices[i] for i in face.vertices)
        additions.append(PackedPatchRow(face.tile, face.material, payload, face.copies))
    patch = GroundPatchSource(
        1,
        source.protected_source_sha256,
        list(source.removals),
        additions,
        source.source_note,
    )
    encoded = gzip.compress(TypeAdapter(GroundPatchSource).dump_json(patch), mtime=0)
    if hashlib.sha256(encoded).hexdigest() != source.expected_output_sha256:
        raise ValueError(
            "Baku authored controls differ from the reviewed patch; requalification is required"
        )
    return encoded


def rebuild(path: Path, output: Path, *, check: bool = False) -> None:
    source = TypeAdapter(ParkAuthoredGround).validate_json(
        gzip.decompress(path.read_bytes())
    )
    encoded = compile_ground(source)
    if check:
        if output.read_bytes() != encoded:
            raise ValueError("The versioned Baku Ground delta is stale")
    else:
        output.write_bytes(encoded)
