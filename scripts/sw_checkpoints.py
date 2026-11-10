"""Immutable file checkpoints for saved SolidWorks parts; never attaches to CAD.

A checkpoint is a byte copy, not proof that SolidWorks saved or rebuilt a part.
Readers verify its manifest and bytes on every access. Restoring always creates
a new file and never overwrites or activates an existing document.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
from typing import Any, Iterator
import uuid


_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_MANIFEST_KEYS = {
    "schema_version", "id", "label", "created_at", "model_file", "sha256",
    "size", "context", "metadata",
}


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _safe_path(path: Path) -> None:
    """Reject links/junctions in every existing component, before resolving it."""
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
            raise ValueError(f"Symlink/reparse paths are not allowed: {component}")


def _json_value(value: Any, active: set[int] | None = None) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Checkpoint data must contain only finite JSON values")
        return
    if type(value) not in (dict, list):
        raise ValueError("Checkpoint data must contain only JSON types")
    active = set() if active is None else active
    if id(value) in active:
        raise ValueError("Checkpoint data cannot contain cycles")
    active.add(id(value))
    try:
        if isinstance(value, dict):
            if any(type(key) is not str for key in value):
                raise ValueError("Checkpoint JSON keys must be strings")
            children = value.values()
        else:
            children = value
        for child in children:
            _json_value(child, active)
    finally:
        active.remove(id(value))


def _json_object(value: Any, name: str) -> dict:
    if type(value) is not dict:
        raise ValueError(f"{name} must be a JSON object")
    _json_value(value)
    # Copy caller-owned containers and validate UTF-8 before filesystem writes.
    data = json.dumps(value, ensure_ascii=False, allow_nan=False)
    data.encode("utf-8")
    return json.loads(data)


def _identity(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


@contextmanager
def _read_file(path: Path) -> Iterator[Any]:
    _safe_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"Expected a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        current = os.fstat(stream.fileno())
        if not stat.S_ISREG(current.st_mode) or getattr(current, "st_file_attributes", 0) & _REPARSE_POINT:
            raise ValueError(f"Expected a regular non-reparse file: {path}")
        if _identity(before) != _identity(current):
            raise ValueError(f"File changed while opening: {path}")
        yield stream
        _safe_path(path)
        if _identity(current) != _identity(os.fstat(stream.fileno())) or _identity(current) != _identity(path.lstat()):
            raise ValueError(f"File changed while reading: {path}")


def _copy_exclusive(source: Path, destination: Path) -> tuple[str, int]:
    _safe_path(destination)
    digest = hashlib.sha256()
    size = 0
    with _read_file(source) as source_stream:
        with destination.open("xb") as target:
            while chunk := source_stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    return digest.hexdigest(), size


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with _read_file(path) as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {value}")


class CheckpointStore:
    """Store immutable .sldprt byte snapshots under caller-selected storage.

    Construction/get/list do not create a missing root. ``list`` returns only
    fully valid checkpoints, omitting incomplete or damaged entries. Checkpoint
    IDs and internal filenames are fixed contracts, never arbitrary paths.
    """

    def __init__(self, root: Path | str):
        self.root = _absolute(root)
        _safe_path(self.root)
        if self.root.exists() and not self.root.is_dir():
            raise ValueError("Checkpoint root must be a directory")

    def _directory(self, checkpoint_id: str) -> Path:
        if type(checkpoint_id) is not str or not _ID.fullmatch(checkpoint_id):
            raise ValueError("Unsafe checkpoint ID")
        _safe_path(self.root)
        directory = self.root / checkpoint_id
        _safe_path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        return directory

    def create(self, source: Path, *, label: str, context: dict, metadata: dict | None = None) -> dict:
        source = _absolute(source)
        if source.suffix.lower() != ".sldprt":
            raise ValueError("Checkpoint source must be a .sldprt file")
        if type(label) is not str or not label.strip():
            raise ValueError("Checkpoint label must be a nonempty string")
        label.encode("utf-8")
        context = _json_object(context, "context")
        metadata = _json_object({} if metadata is None else metadata, "metadata")
        # Validate the source before creating storage, including empty files.
        with _read_file(source) as stream:
            if os.fstat(stream.fileno()).st_size <= 0:
                raise ValueError("Cannot checkpoint an empty file")
        _safe_path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        _safe_path(self.root)
        checkpoint_id = uuid.uuid4().hex
        staging = self.root / (".pending-" + checkpoint_id)
        final = self.root / checkpoint_id
        staging.mkdir(exist_ok=False)
        published = False
        try:
            digest, size = _copy_exclusive(source, staging / "model.sldprt")
            if size <= 0:
                raise ValueError("Cannot checkpoint an empty file")
            manifest = {
                "schema_version": 1, "id": checkpoint_id, "label": label,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_file": "model.sldprt", "sha256": digest, "size": size,
                "context": context, "metadata": metadata,
            }
            with (staging / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(manifest, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            _safe_path(self.root)
            if final.exists():
                raise FileExistsError(f"Checkpoint already exists: {checkpoint_id}")
            # Same-filesystem directory rename publishes complete files together.
            os.rename(staging, final)
            published = True
            return self.get(checkpoint_id)
        finally:
            # Pending names are never accepted by get/list, even after a crash.
            if not published and staging.exists():
                _safe_path(staging)
                shutil.rmtree(staging)

    def get(self, checkpoint_id: str) -> dict:
        directory = self._directory(checkpoint_id)
        manifest_path = directory / "manifest.json"
        with _read_file(manifest_path) as stream:
            try:
                manifest = json.loads(stream.read().decode("utf-8"), object_pairs_hook=_unique_object,
                                      parse_constant=_invalid_constant)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid checkpoint manifest") from exc
        if type(manifest) is not dict or set(manifest) != _MANIFEST_KEYS:
            raise ValueError("Unexpected checkpoint manifest fields")
        if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
            raise ValueError("Unsupported checkpoint manifest version")
        if manifest["id"] != checkpoint_id or manifest["model_file"] != "model.sldprt":
            raise ValueError("Checkpoint identity/path mismatch")
        if type(manifest["label"]) is not str or not manifest["label"].strip():
            raise ValueError("Invalid checkpoint label")
        if type(manifest["created_at"]) is not str:
            raise ValueError("Invalid checkpoint timestamp")
        try:
            timestamp = datetime.fromisoformat(manifest["created_at"])
        except ValueError as exc:
            raise ValueError("Invalid checkpoint timestamp") from exc
        if timestamp.tzinfo is None:
            raise ValueError("Checkpoint timestamp must include timezone")
        if type(manifest["size"]) is not int or manifest["size"] <= 0:
            raise ValueError("Invalid checkpoint size")
        if type(manifest["sha256"]) is not str or not _SHA256.fullmatch(manifest["sha256"]):
            raise ValueError("Invalid checkpoint SHA-256")
        _json_object(manifest["context"], "context")
        _json_object(manifest["metadata"], "metadata")
        model_path = directory / "model.sldprt"
        digest, size = _hash_file(model_path)
        if digest != manifest["sha256"] or size != manifest["size"]:
            raise ValueError("Checkpoint model hash/size mismatch")
        return {**manifest, "model_path": str(model_path), "manifest_path": str(manifest_path)}

    def list(self) -> list[dict]:
        _safe_path(self.root)
        if not self.root.exists():
            return []
        if not self.root.is_dir():
            raise ValueError("Checkpoint root must be a directory")
        checkpoints = []
        for child in sorted(self.root.iterdir(), key=lambda item: item.name):
            if _ID.fullmatch(child.name):
                try:
                    checkpoints.append(self.get(child.name))
                except (OSError, ValueError):
                    continue
        return checkpoints

    def restore(self, checkpoint_id: str, destination: Path) -> dict:
        checkpoint = self.get(checkpoint_id)
        destination = _absolute(destination)
        if destination.suffix.lower() != ".sldprt":
            raise ValueError("Restore destination must be a .sldprt file")
        _safe_path(destination)
        # Avoid even partial files inside this store's immutable namespace.
        if destination == self.root or self.root in destination.parents:
            raise ValueError("Restore destination cannot be inside checkpoint storage")
        created = False
        try:
            # Check existence first only for error clarity; xb is authoritative.
            if destination.exists():
                raise FileExistsError(f"Restore target already exists: {destination}")
            with destination.open("xb") as target:
                created = True
                digest = hashlib.sha256()
                size = 0
                with _read_file(Path(checkpoint["model_path"])) as source:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        size += len(chunk)
                        target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if digest.hexdigest() != checkpoint["sha256"] or size != checkpoint["size"]:
                raise ValueError("Checkpoint changed during restoration")
            return {"path": str(destination), "sha256": digest.hexdigest(), "size": size,
                    "checkpoint_id": checkpoint_id}
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
