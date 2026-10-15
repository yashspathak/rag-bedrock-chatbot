"""Recursive character splitter with overlap and source metadata."""

from __future__ import annotations

from dataclasses import dataclass

SEPARATORS = ("\n## ", "\n# ", "\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    text: str
    offset: int


def split_text(text: str, source: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    if chunk_overlap >= chunk_size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    pieces = _recursive_split(normalized, SEPARATORS, chunk_size)
    merged = _merge_pieces(pieces, chunk_size)
    return _window_with_overlap(merged, source, chunk_size, chunk_overlap)


def _recursive_split(text: str, separators: tuple[str, ...], chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []
    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    separator, *rest = separators
    parts = text.split(separator)
    chunks: list[str] = []
    for index, part in enumerate(parts):
        piece = part if index == 0 else f"{separator}{part}"
        if len(piece) <= chunk_size:
            if piece:
                chunks.append(piece)
            continue
        chunks.extend(_recursive_split(piece, tuple(rest), chunk_size))
    return chunks


def _merge_pieces(pieces: list[str], chunk_size: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}{piece}" if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            merged.append(current)
        current = piece
    if current:
        merged.append(current)
    return merged


def _window_with_overlap(
    segments: list[str], source: str, chunk_size: int, chunk_overlap: int
) -> list[Chunk]:
    joined = "".join(segments)
    if len(joined) <= chunk_size:
        return [Chunk(chunk_id=f"{source}#0", source=source, text=joined, offset=0)]

    chunks: list[Chunk] = []
    start = 0
    index = 0
    step = max(chunk_size - chunk_overlap, 1)
    while start < len(joined):
        end = min(start + chunk_size, len(joined))
        window = joined[start:end].strip()
        if window:
            chunks.append(
                Chunk(
                    chunk_id=f"{source}#{index}",
                    source=source,
                    text=window,
                    offset=start,
                )
            )
            index += 1
        if end >= len(joined):
            break
        start += step
    return chunks
