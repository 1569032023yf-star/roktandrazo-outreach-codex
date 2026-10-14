"""Exact-byte offline rehearsal only / 仅精确字节离线演练，不部署生产。

Uses the WorkBuddy-approved fingerprint and the already tested 4A.8R result.
使用 WorkBuddy 认可的指纹和已测试的 4A.8R 修复结果。
No business module is imported and no database or network is opened.
不导入业务模块，不打开数据库或网络。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

BEFORE_SHA256 = "7afc4d7f6ac18e22bba7cc6a9ea2250dc6d6bafe92128c00c08252731bb2e969"
AFTER_SHA256 = "e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903"
PATCH_SHA256 = "3c7ba8d9baf9c6c4e35ecd5cfa5ef91e87b949ef10abad560fe191f768714bda"
BEFORE_BYTES = 30645
AFTER_BYTES = 31552
HUNK = re.compile(rb"@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n")


class VerificationError(ValueError):
    """Verification refused / 核验拒绝。"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(data: bytes) -> dict:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    style = "MIXED" if sum(bool(n) for n in (crlf, lf, cr)) > 1 else (
        "CRLF" if crlf else "LF" if lf else "CR" if cr else "NONE")
    return {"sha256": sha256(data), "bytes": len(data), "line_endings": style,
            "lf": lf, "crlf": crlf, "bare_cr": cr, "utf8_bom": data.startswith(b"\xef\xbb\xbf")}


def _apply_unified(source: bytes, patch: bytes, *, reverse: bool = False) -> bytes:
    """Match every context byte; never normalize newline bytes.
    逐字节匹配上下文，绝不归一化换行。
    """
    lines = patch.splitlines(keepends=True)
    if lines[:2] != [b"--- a/bd_orchestrator.py\n", b"+++ b/bd_orchestrator.py\n"]:
        raise VerificationError("PATCH_SCOPE_INVALID / 补丁文件范围错误")
    original = source.splitlines(keepends=True)
    output = []
    cursor = 0
    index = 2
    hunks = 0
    while index < len(lines):
        match = HUNK.fullmatch(lines[index])
        if not match:
            raise VerificationError("PATCH_HUNK_INVALID / 补丁块格式错误")
        old_start, old_count, new_start, new_count = map(int, match.groups())
        if reverse:
            old_start, new_start = new_start, old_start
            old_count, new_count = new_count, old_count
        start = old_start - 1
        if start < cursor or start > len(original):
            raise VerificationError("PATCH_OFFSET_INVALID / 补丁位置错误")
        output.extend(original[cursor:start])
        cursor = start
        if len(output) != new_start - 1:
            raise VerificationError("PATCH_NEW_OFFSET_INVALID / 目标位置错误")
        index += 1
        consumed = produced = 0
        while index < len(lines) and not lines[index].startswith(b"@@ "):
            line = lines[index]
            kind, body = line[:1], line[1:]
            if reverse:
                kind = {b"+": b"-", b"-": b"+"}.get(kind, kind)
            if kind not in (b" ", b"+", b"-") or not body.endswith(b"\n"):
                raise VerificationError("PATCH_LINE_INVALID / 补丁行格式错误")
            if kind in (b" ", b"-"):
                if cursor >= len(original) or original[cursor] != body:
                    raise VerificationError("PATCH_CONTEXT_MISMATCH / 补丁上下文字节不匹配")
                cursor += 1
                consumed += 1
            if kind in (b" ", b"+"):
                output.append(body)
                produced += 1
            index += 1
        if (consumed, produced) != (old_count, new_count):
            raise VerificationError("PATCH_COUNT_INVALID / 补丁行数错误")
        hunks += 1
    if hunks != 3:
        raise VerificationError("PATCH_HUNK_COUNT_INVALID / 必须恰为三块")
    output.extend(original[cursor:])
    return b"".join(output)


def apply_checked(source: bytes, patch: bytes, *, reverse: bool = False) -> bytes:
    expected_input = AFTER_SHA256 if reverse else BEFORE_SHA256
    expected_output = BEFORE_SHA256 if reverse else AFTER_SHA256
    expected_size = BEFORE_BYTES if reverse else AFTER_BYTES
    if sha256(source) != expected_input:
        raise VerificationError("SOURCE_SHA_MISMATCH / 源文件 SHA256 不匹配；禁止应用")
    if sha256(patch) != PATCH_SHA256:
        raise VerificationError("PATCH_SHA_MISMATCH / 补丁 SHA256 不匹配；禁止应用")
    result = _apply_unified(source, patch, reverse=reverse)
    if sha256(result) != expected_output or len(result) != expected_size:
        raise VerificationError("RESULT_SHA_MISMATCH / 结果字节不匹配")
    ast.parse(result.decode("utf-8"))
    return result


def verify_backup(backup: bytes) -> None:
    if sha256(backup) != BEFORE_SHA256 or len(backup) != BEFORE_BYTES:
        raise VerificationError("BACKUP_SHA_MISMATCH / 备份字节不匹配；禁止回滚")


def _within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise VerificationError("REVIEW_PATH_OUTSIDE_ROOT / 路径不在受控审查目录")
    return resolved


def rehearse(source_path: Path, patch_path: Path, review_root: Path, output_dir: Path) -> dict:
    """Write only new review copies, never the input file.
    仅写入新的审查副本，绝不修改输入文件。
    """
    root = review_root.resolve()
    if not (root / ".development-copy").is_file():
        raise VerificationError("REVIEW_MARKER_MISSING / 缺少开发审查目录标记")
    if any(part.casefold() == "workbuddy" for part in root.parts):
        raise VerificationError("PRODUCTION_ROOT_BLOCKED / 禁止使用 WorkBuddy 生产目录")
    source_path = _within(source_path, root)
    patch_path = _within(patch_path, root)
    output_dir = _within(output_dir, root)
    if output_dir == root or source_path.is_relative_to(output_dir) or patch_path.is_relative_to(output_dir):
        raise VerificationError("REVIEW_PATH_COLLISION / 输入与演练目录冲突")
    if output_dir.exists():
        raise VerificationError("REVIEW_OUTPUT_EXISTS / 演练目录已存在；禁止覆盖")
    before = source_path.read_bytes()
    patch = patch_path.read_bytes()
    # Complete checks before creating output, including the reverse transform.
    # 创建输出之前完成全部核验，包括逆向转换。
    after = apply_checked(before, patch)
    if apply_checked(after, patch, reverse=True) != before:
        raise VerificationError("ROLLBACK_MISMATCH / 逆向回滚不一致")
    output_dir.mkdir(parents=True, exist_ok=False)
    backup = output_dir / "bd_orchestrator.py.before.bak"
    candidate = output_dir / "bd_orchestrator.py"
    restored = output_dir / "bd_orchestrator.py.rollback"
    backup.write_bytes(before)
    verify_backup(backup.read_bytes())
    candidate.write_bytes(after)
    if candidate.read_bytes() != after:
        raise VerificationError("CANDIDATE_WRITE_MISMATCH / 候选文件写入不一致")
    # The authoritative rollback is the hash-verified original backup.
    # 权威回滚来源为经过 SHA 校验的原始备份。
    restored.write_bytes(backup.read_bytes())
    verify_backup(restored.read_bytes())
    if source_path.read_bytes() != before:
        raise VerificationError("INPUT_CHANGED_DURING_REVIEW / 审查过程中输入发生变化")
    report = {
        "description_zh": "精确生产文件的离线副本应用及字节级回滚演练；未部署",
        "description_en": "Offline exact-source copy application and byte-exact rollback rehearsal; no deployment",
        "source_copy": str(source_path), "patch": str(patch_path),
        "before": fingerprint(before), "after": fingerprint(after),
        "patch_sha256": sha256(patch), "patch_file_count": 1, "patch_hunk_count": 3,
        "PATCH_APPLY_CHECK": True, "PATCH_ROLLBACK_CHECK": True,
        "BACKUP_SHA_MATCH": True, "ORIGINAL_INPUT_UNCHANGED": True,
        "production_deployment": False, "production_db_writes": 0,
        "backup": str(backup), "candidate": str(candidate), "rollback": str(restored),
    }
    (output_dir / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline review only / 仅离线审查，不部署")
    parser.add_argument("--source", required=True, type=Path, help="Approved source COPY / 获准的源文件副本")
    parser.add_argument("--review-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", required=True, type=Path, help="New review directory / 新的演练目录")
    parser.add_argument("--patch", type=Path, default=Path(__file__).with_name("continuous_discovery.patch"))
    args = parser.parse_args(argv)
    try:
        report = rehearse(args.source, args.patch, args.review_root, args.output_dir)
    except (OSError, ValueError, SyntaxError) as exc:
        print(json.dumps({"verified": False, "error": str(exc), "production_deployment": False,
                          "description_zh": "核验失败；未应用生产",
                          "description_en": "Verification failed; production was not patched"}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
