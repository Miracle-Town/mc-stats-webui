"""Encode lossless WebP atlases and verify their RGBA pixels without Python packages."""
from __future__ import annotations

import argparse
import re
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

ATLAS_NAME = re.compile(r"minecraft_texture_atlas(?:-([1-9][0-9]*))?\.png")


def read_png_rgba(path: Path) -> tuple[int, int, bytes]:
    """Read the non-interlaced, 8-bit RGB/RGBA PNGs produced by ImageIO and dwebp.

    Other PNG encodings fail explicitly. This is a pipeline verifier, not a general
    image loader; it preserves RGB values even when alpha is zero.
    """
    header = None
    compressed = bytearray()
    with path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Invalid PNG signature: {path}")
        while True:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise ValueError(f"Truncated PNG: {path}")
            length, kind = struct.unpack(">I4s", chunk_header)
            data, checksum = stream.read(length), stream.read(4)
            if len(data) != length or len(checksum) != 4:
                raise ValueError(f"Truncated PNG chunk: {path}")
            if zlib.crc32(kind + data) != struct.unpack(">I", checksum)[0]:
                raise ValueError(f"Invalid PNG checksum: {path}")
            if kind == b"IHDR":
                if header is not None or length != 13:
                    raise ValueError(f"Invalid PNG header: {path}")
                header = struct.unpack(">IIBBBBB", data)
            elif kind == b"tRNS":
                raise ValueError(f"PNG colour-key transparency is unsupported: {path}")
            elif kind == b"IDAT":
                compressed.extend(data)
            elif kind == b"IEND":
                break
            elif kind[:1].isupper():
                raise ValueError(f"Unsupported PNG chunk {kind!r}: {path}")
    if header is None:
        raise ValueError(f"Missing PNG header: {path}")
    width, height, depth, colour, compression, filtering, interlace = header
    if not width or not height or depth != 8 or colour not in (2, 6) or (compression, filtering, interlace) != (0, 0, 0):
        raise ValueError(f"Expected non-interlaced 8-bit RGB/RGBA PNG: {path}")
    channels = 4 if colour == 6 else 3
    stride = width * channels
    raw = zlib.decompress(compressed)
    if len(raw) != height * (stride + 1):
        raise ValueError(f"Invalid PNG pixel data size: {path}")
    rgba = bytearray()
    previous = bytearray(stride)
    for row_index in range(height):
        offset = row_index * (stride + 1)
        filter_type = raw[offset]
        if filter_type > 4:
            raise ValueError(f"Invalid PNG filter: {path}")
        row = bytearray(raw[offset + 1:offset + stride + 1])
        for i in range(stride) if filter_type else ():
            left = row[i - channels] if i >= channels else 0
            above = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            predictor = 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
            row[i] = (row[i] + predictor) & 255
        if channels == 4:
            rgba.extend(row)
        else:
            for i in range(0, stride, 3):
                rgba.extend(row[i:i + 3])
                rgba.append(255)
        previous = row
    return width, height, bytes(rgba)


def verify_pixels(source: Path, decoded: Path) -> None:
    width, height, pixels = read_png_rgba(source)
    actual_width, actual_height, actual_pixels = read_png_rgba(decoded)
    if (width, height) != (actual_width, actual_height):
        raise ValueError(f"WebP dimensions changed: {source}")
    if pixels != actual_pixels:
        raise ValueError(f"WebP RGBA pixels changed: {source}")


def convert_atlases(source: Path, output: Path, quality: int, method: int) -> None:
    if not 0 <= quality <= 100 or not 0 <= method <= 6:
        raise ValueError("WebP quality must be 0–100 and method must be 0–6")
    pages = {int(match[1] or 0): path for path in source.iterdir()
             if path.is_file() and (match := ATLAS_NAME.fullmatch(path.name))}
    if not pages or sorted(pages) != list(range(len(pages))):
        raise ValueError("Atlas PNG pages are missing or non-contiguous")
    output.mkdir(parents=True, exist_ok=True)
    for page, path in sorted(pages.items()):
        target = output / f"items-{page}.webp"
        verified = False
        try:
            with tempfile.TemporaryDirectory(prefix="webp-check-", dir=output) as temporary:
                decoded = Path(temporary) / "decoded.png"
                subprocess.run(["cwebp", "-quiet", "-lossless", "-exact", "-q", str(quality), "-m", str(method),
                                str(path), "-o", str(target)], check=True)
                subprocess.run(["dwebp", "-quiet", str(target), "-o", str(decoded)], check=True)
                verify_pixels(path, decoded)
                verified = True
            print(f"Verified lossless WebP: {target.name} ({path.stat().st_size} -> {target.stat().st_size} bytes)")
        finally:
            if not verified:
                target.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("quality", type=int)
    parser.add_argument("method", type=int)
    args = parser.parse_args()
    convert_atlases(args.source, args.output, args.quality, args.method)
