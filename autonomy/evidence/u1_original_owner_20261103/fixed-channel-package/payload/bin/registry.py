"""Scoped, sealed release registration for the Rokt deploy channel.

Codex (or any authorised engineering client holding the bearer token) drops a
release bundle into `inbox/<release_id>/`:

    manifest.json   declarative file list + before/after fingerprints
    change.patch    unified diff (git style, one section per file)
    tests.json      machine-readable test result
    tests.log       the test artifact whose sha256 is declared in tests.json
    review.json     independent review record

`register_release()` validates the bundle against live production state and
appends a pinned entry to releases/channel_config.json. It never touches
production code; deployment remains the separate `apply` operation.

The registry itself is protected by a seal (`state/registry_seal.json`):
channel_config.json + allowed_scope.json + every release entry are hashed at
the last controlled write. Any out-of-band edit (a human or an agent editing
the JSON directly) is detected on the next load and stops the channel.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import multifile as mf

MAX_TESTS_AGE_HOURS = 168
MIN_TESTS_TOTAL = 5


class RegisterError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha_bytes(data: bytes) -> str:
    return mf.sha256_hex(data)


def _json_sha(obj) -> str:
    return _sha_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def scope_path(cfg: dict) -> Path:
    return Path(cfg["_paths"]["releases"]) / "allowed_scope.json"


def scope(cfg: dict) -> dict:
    p = scope_path(cfg)
    if not p.is_file():
        raise RegisterError("SCOPE_FILE_MISSING", str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def inbox_root(cfg: dict) -> Path:
    return Path(cfg["_paths"]["inbox"])


def seal_path(cfg: dict) -> Path:
    return Path(cfg["_paths"]["state"]) / "registry_seal.json"


def _release_entry_hash(rel: dict) -> str:
    return _json_sha(rel)


def compute_seal(cfg: dict) -> dict:
    cfg_file = Path(cfg["_paths"]["releases"]) / "channel_config.json"
    return {
        "channel_config_sha256": _sha_bytes(cfg_file.read_bytes()),
        "scope_sha256": _sha_bytes(scope_path(cfg).read_bytes()),
        "release_entries": {rid: _release_entry_hash(rel) for rid, rel in cfg["releases"].items()},
        "sealed_at": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def verify_seal(cfg: dict) -> dict:
    """Fail closed if the registry was edited outside the controlled writer."""
    p = seal_path(cfg)
    if not p.is_file():
        return {"sealed": False, "note": "no seal yet (first controlled write will create one)",
                "tampered": False}
    seal = json.loads(p.read_text(encoding="utf-8"))
    cur = compute_seal(cfg)
    diffs = []
    if seal.get("channel_config_sha256") != cur["channel_config_sha256"]:
        diffs.append("channel_config_sha256")
    if seal.get("scope_sha256") != cur["scope_sha256"]:
        diffs.append("scope_sha256")
    old_entries = seal.get("release_entries") or {}
    for rid, h in cur["release_entries"].items():
        if rid in old_entries and old_entries[rid] != h:
            diffs.append(f"entry_modified:{rid}")
        if rid not in old_entries:
            diffs.append(f"entry_unsealed:{rid}")
    for rid in old_entries:
        if rid not in cur["release_entries"]:
            diffs.append(f"entry_removed:{rid}")
    return {"sealed": True, "tampered": bool(diffs), "diffs": diffs,
            "sealed_at": seal.get("sealed_at")}


def write_seal(cfg: dict) -> dict:
    seal = compute_seal(cfg)
    p = seal_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(seal, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    return seal


# ---------------------------------------------------------------- validation
def _load_bundle(cfg: dict, release_id: str) -> dict:
    root = inbox_root(cfg) / release_id
    if not root.is_dir():
        raise RegisterError("BUNDLE_MISSING", str(root))
    files = {}
    for name in ("manifest.json", "change.patch", "tests.json", "review.json"):
        p = root / name
        if not p.is_file():
            raise RegisterError("BUNDLE_INCOMPLETE", f"{release_id}/{name}")
        files[name] = p
    manifest = json.loads(files["manifest.json"].read_text(encoding="utf-8"))
    tests = json.loads(files["tests.json"].read_text(encoding="utf-8"))
    review = json.loads(files["review.json"].read_text(encoding="utf-8"))
    patch = files["change.patch"].read_bytes()
    return {"root": root, "manifest": manifest, "tests": tests, "review": review,
            "patch": patch, "paths": files}


def _check_schema(manifest: dict, release_id: str, sc: dict) -> dict:
    problems = []
    if manifest.get("schema_version") != 2:
        problems.append("schema_version!=2")
    if manifest.get("release_id") != release_id:
        problems.append("release_id_mismatch")
    targets = manifest.get("target_files")
    if not isinstance(targets, list) or not targets:
        problems.append("target_files_empty")
        targets = []
    if len(targets) > sc["rules"]["max_files_per_release"]:
        problems.append(f"too_many_files:{len(targets)}")
    for t in targets:
        for k in ("path", "before_sha256", "after_sha256", "before_bytes", "after_bytes"):
            if k not in t:
                problems.append(f"missing:{k}")
        h = t.get("before_sha256") or ""
        if h != "ABSENT" and (len(h) != 64 or any(c not in "0123456789abcdef" for c in h)):
            problems.append(f"bad_sha256:{t.get('path')}")
        if not str(t.get("path", "")).endswith(".py"):
            problems.append(f"not_python:{t.get('path')}")
    if problems:
        raise RegisterError("MANIFEST_SCHEMA_INVALID", ";".join(sorted(set(problems))))
    return {"targets": targets}


def _check_scope(targets: list[dict], sc: dict) -> list[str]:
    allowed = set(sc["paths"])
    bad = []
    for t in targets:
        p = t["path"].replace("\\", "/")
        if p in allowed:
            continue
        bad.append(p)
    if bad:
        raise RegisterError("SCOPE_NOT_ALLOWED", ",".join(bad))
    return [t["path"].replace("\\", "/") for t in targets]


def _check_patch(patch: bytes, paths: list[str], sc: dict) -> list[dict]:
    if len(patch) > sc["rules"]["max_patch_bytes"]:
        raise RegisterError("PATCH_TOO_LARGE", str(len(patch)))
    try:
        sections = mf.parse_sections(patch)
    except mf.PatchError as e:
        raise RegisterError("PATCH_PARSE_FAILED", e.code)
    sec_paths = [s["path"].replace("\\", "/") for s in sections]
    if sorted(sec_paths) != sorted(paths):
        raise RegisterError("PATCH_SCOPE_MISMATCH", f"patch={sec_paths} manifest={paths}")
    return sections


def _check_tests(tests: dict, bundle_root: Path) -> dict:
    problems = []
    if int(tests.get("failed", -1)) != 0:
        problems.append("failed>0")
    if int(tests.get("total", 0)) < MIN_TESTS_TOTAL:
        problems.append(f"total<{MIN_TESTS_TOTAL}")
    if int(tests.get("exit_code", -1)) != 0:
        problems.append("exit_code!=0")
    ran_at = tests.get("ran_at")
    try:
        dt = datetime.fromisoformat(str(ran_at))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        age_h = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600.0
        if age_h > MAX_TESTS_AGE_HOURS:
            problems.append(f"tests_stale:{age_h:.1f}h")
    except Exception:
        problems.append("ran_at_unparseable")
    art = tests.get("artifact")
    art_sha = tests.get("artifact_sha256")
    if not art or not art_sha:
        problems.append("artifact_missing")
    else:
        ap = (bundle_root / art).resolve()
        if bundle_root.resolve() not in ap.parents or not ap.is_file():
            problems.append("artifact_not_in_bundle")
        elif _sha_bytes(ap.read_bytes()) != art_sha:
            problems.append("artifact_sha_mismatch")
    if problems:
        raise RegisterError("TESTS_NOT_ACCEPTABLE", ";".join(problems))
    return {"total": int(tests["total"]), "failed": int(tests["failed"]),
            "suite": tests.get("suite"), "ran_at": ran_at,
            "artifact": art, "artifact_sha256": art_sha}


def _check_review(review: dict, patch_sha: str, manifest: dict) -> dict:
    problems = []
    if str(review.get("verdict", "")).upper() != "APPROVED":
        problems.append("verdict_not_approved")
    reviewer = str(review.get("reviewer_identity") or "").strip().lower()
    author = str(manifest.get("author_identity") or "").strip().lower()
    if not reviewer:
        problems.append("reviewer_missing")
    if reviewer and reviewer == author:
        problems.append("reviewer_equals_author")
    if review.get("patch_sha256") != patch_sha:
        problems.append("review_patch_sha_mismatch")
    if problems:
        raise RegisterError("REVIEW_NOT_ACCEPTABLE", ";".join(problems))
    return {"reviewer_identity": reviewer, "verdict": "APPROVED",
            "reviewed_at": review.get("reviewed_at"), "findings": review.get("findings", [])}


def _attest(prod_root: Path, targets: list[dict]) -> dict:
    out = {}
    for t in targets:
        p = (prod_root / t["path"].replace("/", os.sep)).resolve()
        if not p.is_file():
            out[t["path"]] = {"exists": False, "actual_sha256": None,
                              "matches_before": t["before_sha256"] == "ABSENT"}
            continue
        data = p.read_bytes()
        actual = _sha_bytes(data)
        out[t["path"]] = {"exists": True, "actual_sha256": actual, "actual_bytes": len(data),
                          "matches_before": actual == t["before_sha256"]}
    return out


def _apply_checks(executor, prod_root: Path, targets: list[dict], sections: list[dict]) -> dict:
    """Forward/reverse byte verification, only possible when production matches."""
    results = {}
    by_path = {s["path"].replace("\\", "/"): s for s in sections}
    for t in targets:
        path = t["path"].replace("/", os.sep)
        p = (prod_root / path).resolve()
        sec = by_path[t["path"].replace("\\", "/")]
        if not p.is_file():
            results[t["path"]] = {"feasible": False, "reason": "target_absent"}
            continue
        src = p.read_bytes()
        if _sha_bytes(src) != t["before_sha256"]:
            results[t["path"]] = {"feasible": False, "reason": "before_sha_mismatch",
                                  "actual": _sha_bytes(src), "declared": t["before_sha256"]}
            continue
        try:
            cand = executor.apply_unified(src, sec["section"], t["path"].replace("\\", "/"),
                                          expected_hunks=sec["hunk_count"])
        except Exception as e:
            results[t["path"]] = {"feasible": False, "reason": f"forward_failed:{e}"}
            continue
        after_sha = _sha_bytes(cand)
        if after_sha != t["after_sha256"] or len(cand) != int(t["after_bytes"]):
            results[t["path"]] = {"feasible": False, "reason": "after_sha_mismatch",
                                  "computed": after_sha, "declared": t["after_sha256"]}
            continue
        try:
            back = executor.apply_unified(cand, sec["section"], t["path"].replace("\\", "/"),
                                          reverse=True, expected_hunks=sec["hunk_count"])
            reversible = _sha_bytes(back) == t["before_sha256"] and back == src
        except Exception as e:
            reversible = False
            results[t["path"]] = {"feasible": False, "reason": f"reverse_failed:{e}"}
            if t["path"] in results:
                continue
        if t["path"] not in results:
            results[t["path"]] = {"feasible": True, "after_sha256": after_sha,
                                  "reversible": reversible}
    return results


def register_release(cfg: dict, release_id: str, caller: str, executor) -> dict:
    from datetime import timezone as _tz
    import re
    if not isinstance(release_id, str) or not re.match(r"^[a-z0-9][a-z0-9._-]{0,63}$", release_id):
        raise RegisterError("INVALID_RELEASE_ID", "release_id failed strict pattern")

    bundle = _load_bundle(cfg, release_id)
    patch_sha = _sha_bytes(bundle["patch"])
    manifest_sha = _sha_bytes(bundle["paths"]["manifest.json"].read_bytes())

    # ---- idempotency first (cheap, and avoids re-validating a known release)
    existing = cfg["releases"].get(release_id)
    if existing:
        same = (existing.get("patch_sha256") == patch_sha
                and existing.get("manifest_sha256") == manifest_sha)
        executor.audit(cfg, {"op": "register", "release_id": release_id, "caller": caller,
                             "result": "IDEMPOTENT" if same else "CONFLICT"})
        if same:
            return {"operation": "register", "release_id": release_id, "state": "already_registered",
                    "verdict": "REGISTER_IDEMPOTENT", "deployable": bool(existing.get("deployable")),
                    "registered_at": existing.get("registered_at"), "ts": executor.iso_now()}
        raise RegisterError("RELEASE_ID_CONFLICT",
                            "release_id already registered with different content")

    sc = scope(cfg)
    schema = _check_schema(bundle["manifest"], release_id, sc)
    targets = schema["targets"]
    paths = _check_scope(targets, sc)
    sections = _check_patch(bundle["patch"], paths, sc)
    tests = _check_tests(bundle["tests"], bundle["root"])
    review = _check_review(bundle["review"], patch_sha, bundle["manifest"])

    prod_root = Path(cfg["production"]["root"]).resolve()
    attest = _attest(prod_root, targets)
    attestation_ok = all(a["matches_before"] for a in attest.values())
    apply_checks = _apply_checks(executor, prod_root, targets, sections)
    byte_ok = all(v.get("feasible") and v.get("reversible") for v in apply_checks.values())

    # ---- materialise artifacts inside releases/ (immutable copies)
    rel_dir = Path(cfg["_paths"]["releases"]) / "registered" / release_id
    if rel_dir.exists():
        shutil.rmtree(rel_dir)
    rel_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(bundle["paths"]["change.patch"], rel_dir / "change.patch")
    shutil.copy2(bundle["paths"]["manifest.json"], rel_dir / "manifest.json")
    shutil.copy2(bundle["paths"]["tests.json"], rel_dir / "tests.json")
    shutil.copy2(bundle["paths"]["review.json"], rel_dir / "review.json")
    if tests["artifact"]:
        shutil.copy2(bundle["root"] / tests["artifact"], rel_dir / Path(tests["artifact"]).name)

    entry = {
        "manifest_path": f"releases/registered/{release_id}/manifest.json",
        "manifest_sha256": manifest_sha,
        "patch_path": f"releases/registered/{release_id}/change.patch",
        "patch_sha256": patch_sha,
        "patch_bytes": len(bundle["patch"]),
        "source_commit": bundle["manifest"].get("source_commit"),
        "target_files": [
            {"path": t["path"].replace("\\", "/"),
             "before_sha256": t["before_sha256"], "after_sha256": t["after_sha256"],
             "before_bytes": t["before_bytes"], "after_bytes": t["after_bytes"],
             "hunk_count": next(s["hunk_count"] for s in sections
                                if s["path"].replace("\\", "/") == t["path"].replace("\\", "/"))}
            for t in targets],
        "file_count": len(targets),
        "hunk_count": sum(next(s["hunk_count"] for s in sections
                               if s["path"].replace("\\", "/") == t["path"].replace("\\", "/"))
                          for t in targets),
        "inventory_id": cfg.get("inventory_automation_id"),
        "registered_at": executor.iso_now(),
        "registered_by": caller,
        "author_identity": bundle["manifest"].get("author_identity"),
        "tests": tests,
        "review": review,
        "production_attestation": attest,
        "byte_verification": apply_checks,
        "deployable": bool(attestation_ok and byte_ok),
    }
    # legacy single-file aliases so the original single-file code path still works
    if len(targets) == 1:
        t = entry["target_files"][0]
        if t["path"] == "bd_orchestrator.py":
            entry.update({"target_relative_path": "bd_orchestrator.py",
                          "before_sha256": t["before_sha256"], "after_sha256": t["after_sha256"],
                          "before_bytes": t["before_bytes"], "after_bytes": t["after_bytes"]})

    cfg_path = Path(cfg["_paths"]["releases"]) / "channel_config.json"
    backup = cfg_path.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(cfg_path, backup)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    raw["releases"][release_id] = entry
    raw.setdefault("registration_log", []).append(
        {"release_id": release_id, "at": entry["registered_at"], "by": caller,
         "deployable": entry["deployable"], "patch_sha256": patch_sha})
    tmp = cfg_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, cfg_path)
    cfg["releases"][release_id] = entry
    seal = write_seal(cfg)

    verdict = ("REGISTERED_DEPLOYABLE" if entry["deployable"]
               else "REGISTERED_PENDING_SOURCE_ATTESTATION")
    result = {
        "operation": "register", "release_id": release_id, "state": "registered",
        "verdict": verdict, "ts": entry["registered_at"], "channel_id": cfg["channel_id"],
        "test_mode": cfg.get("_test_mode", False), "caller": caller,
        "file_count": entry["file_count"], "patch_sha256": patch_sha,
        "deployable": entry["deployable"],
        "attestation": attest, "byte_verification": apply_checks,
        "tests": {"total": tests["total"], "failed": tests["failed"], "artifact": tests["artifact"]},
        "review": {"reviewer_identity": review["reviewer_identity"], "verdict": review["verdict"]},
        "registry_backup": str(backup), "seal_written": bool(seal),
        "next_step": ("preflight then apply" if entry["deployable"]
                      else "production source no longer matches the declared before-SHA; "
                           "rebase the patch onto the live production snapshot"),
        "note_zh": "已登记为固定发布条目；未触碰生产代码。部署仍需独立的 preflight/apply。",
        "note_en": "Pinned into the registry; production code untouched. Deployment still "
                   "requires the separate preflight/apply operations.",
    }
    executor.audit(cfg, {"op": "register", "release_id": release_id, "caller": caller,
                         "result": verdict, "patch_sha256": patch_sha,
                         "deployable": entry["deployable"],
                         "attestation_failures": [k for k, v in attest.items()
                                                  if not v["matches_before"]]})
    return result


def list_releases(cfg: dict) -> dict:
    out = []
    for rid, rel in cfg["releases"].items():
        out.append({"release_id": rid, "file_count": rel.get("file_count", 1),
                    "targets": [t["path"] for t in rel.get("target_files", [])]
                    or [rel.get("target_relative_path")],
                    "deployable": rel.get("deployable", True),
                    "registered_at": rel.get("registered_at"),
                    "registered_by": rel.get("registered_by"),
                    "patch_sha256": rel.get("patch_sha256")})
    return {"operation": "releases", "count": len(out), "releases": out,
            "seal": verify_seal(cfg), "ts": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")}
