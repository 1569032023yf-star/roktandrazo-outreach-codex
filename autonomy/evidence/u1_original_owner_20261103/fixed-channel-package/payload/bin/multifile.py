"""Multi-file, byte-exact patch parsing for the Rokt deploy channel.

Design constraints:
- No external tools (git/gnu patch). Pure Python, deterministic.
- Any ambiguity fails closed: a section that cannot be parsed raises PatchError
  instead of being "best effort".
- The parser is a strict state machine driven by the hunk counts, exactly like
  `executor.apply_unified`. This is what makes a removed source line that looks
  like `--- a/x` inside a hunk harmless: it is consumed as body content, never
  mistaken for a file header.

Patch format accepted: unified diff with `--- a/<path>` / `+++ b/<path>` headers
(git style). `diff --git`, `index`, `new file mode`, `rename` metadata lines are
skipped and counted. A count of 1 may be omitted (git habit) and a section
heading may follow the closing `@@`.
"""
from __future__ import annotations

import hashlib
import re

HEADER_OLD = re.compile(rb"^--- a/(.+)$")
HEADER_NEW = re.compile(rb"^\+\+\+ b/(.+)$")
HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _header_path(line: bytes, pattern) -> str | None:
    m = pattern.match(line.rstrip(b"\r\n"))
    return m.group(1).decode("utf-8") if m else None


def parse_sections(patch: bytes) -> list[dict]:
    """Split a unified patch into [{path, section, hunk_count, metadata_lines}]."""
    if not patch:
        raise PatchError("PATCH_EMPTY", "")
    lines = patch.splitlines(keepends=True)
    n = len(lines)
    sections: list[dict] = []
    i = 0
    while i < n:
        path = _header_path(lines[i], HEADER_OLD)
        if path is not None:
            nxt = _header_path(lines[i + 1], HEADER_NEW) if i + 1 < n else None
            if nxt != path:
                raise PatchError("PATCH_HEADER_MISMATCH", f"{path} vs {nxt}")
        if path is None:
            if lines[i].startswith(b"@@"):
                raise PatchError("PATCH_HUNK_OUTSIDE_SECTION", str(lines[i][:40]))
            i += 1
            continue

        header = [lines[i], lines[i + 1]]
        i += 2
        body: list[bytes] = []
        metadata = 0
        hunks = 0
        while i < n:
            line = lines[i]
            m = HUNK.match(line)
            if m:
                old_count = int(m.group(2)) if m.group(2) else 1
                new_count = int(m.group(4)) if m.group(4) else 1
                body.append(line)
                i += 1
                hunks += 1
                consumed = produced = 0
                while i < n and (consumed < old_count or produced < new_count):
                    b = lines[i]
                    kind = b[:1]
                    if kind not in (b" ", b"+", b"-") or not b.endswith(b"\n"):
                        raise PatchError("PATCH_LINE_INVALID", str(b[:40]))
                    if kind in (b" ", b"-"):
                        consumed += 1
                    if kind in (b" ", b"+"):
                        produced += 1
                    body.append(b)
                    i += 1
                if (consumed, produced) != (old_count, new_count):
                    raise PatchError("PATCH_COUNT_INVALID",
                                     f"{path} {consumed}/{old_count} {produced}/{new_count}")
                continue
            # not inside a hunk: either the next file header or metadata
            nxt_path = _header_path(line, HEADER_OLD)
            if nxt_path is not None and i + 1 < n and \
                    _header_path(lines[i + 1], HEADER_NEW) == nxt_path:
                break
            if line.startswith(b"@@"):
                raise PatchError("PATCH_HUNK_INVALID", str(line[:40]))
            metadata += 1
            i += 1
        if hunks == 0:
            raise PatchError("PATCH_SECTION_EMPTY", path)
        sections.append({"path": path,
                         "section": b"".join(header) + b"".join(body),
                         "hunk_count": hunks, "metadata_lines": metadata})

    if not sections:
        raise PatchError("PATCH_NO_SECTIONS", "")
    paths = [s["path"] for s in sections]
    if len(set(paths)) != len(paths):
        raise PatchError("PATCH_DUPLICATE_PATH", str(paths))
    return sections


def file_sha(data: bytes) -> str:
    return sha256_hex(data)
