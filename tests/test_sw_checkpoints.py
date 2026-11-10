"""File-only checkpoints: no SolidWorks connection, writes only under tmp_path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sw_checkpoints import CheckpointStore  # noqa: E402
import sw_checkpoints as checkpoints  # noqa: E402


@pytest.fixture
def part(tmp_path):
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"saved part fixture\x00\x01")
    return source


def make(store, part):
    return store.create(part, label="before cut", context={"volume_mm3": 8000.0},
                        metadata={"features": ["Base"], "reviewed": False})


def test_readonly_missing_store_does_not_create_root(tmp_path):
    root = tmp_path / "missing" / "checkpoints"
    store = CheckpointStore(root)
    assert store.list() == []
    with pytest.raises(FileNotFoundError):
        store.get("a" * 32)
    assert not root.exists()


def test_copy_is_independent_and_restore_never_mutates_source(tmp_path, part):
    original = part.read_bytes()
    store = CheckpointStore(tmp_path / "store")
    context = {"dimensions": [120, 80, 12]}
    result = store.create(part, label="baseline", context=context)
    context["dimensions"][0] = 999
    part.write_bytes(b"later source changes")
    assert store.get(result["id"])["context"] == {"dimensions": [120, 80, 12]}
    assert Path(result["model_path"]).read_bytes() == original
    restored = store.restore(result["id"], tmp_path / "restored.sldprt")
    assert Path(restored["path"]).read_bytes() == original
    assert restored["sha256"] == hashlib.sha256(original).hexdigest()
    assert part.read_bytes() == b"later source changes"
    assert len(store.list()) == 1
    assert result["metadata"] == {}


@pytest.mark.parametrize("same_size", [True, False])
def test_tampered_model_cannot_be_read_or_restored(tmp_path, part, same_size):
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    model = Path(result["model_path"])
    model.write_bytes(b"X" * (result["size"] if same_size else 1))
    target = tmp_path / "restored.sldprt"
    with pytest.raises(ValueError, match="hash/size"):
        store.get(result["id"])
    with pytest.raises(ValueError, match="hash/size"):
        store.restore(result["id"], target)
    assert not target.exists()
    assert store.list() == []


@pytest.mark.parametrize("damage", [
    b"not JSON", b'{"id": "one", "id": "two"}', b'[]', b'{"x": NaN}',
])
def test_corrupt_manifest_is_rejected(tmp_path, part, damage):
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    Path(result["manifest_path"]).write_bytes(damage)
    with pytest.raises(ValueError):
        store.get(result["id"])
    assert store.list() == []


@pytest.mark.parametrize("field,value", [
    ("model_file", "../../source.SLDPRT"), ("id", "b" * 32),
    ("size", True), ("created_at", "yesterday"), ("sha256", "Z" * 64),
    ("metadata", {"invalid": float("inf")}), ("unexpected", "field"),
])
def test_manifest_contract_does_not_allow_external_paths_or_bad_types(tmp_path, part, field, value):
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    path = Path(result["manifest_path"])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        store.get(result["id"])


@pytest.mark.parametrize("bad_id", ["../source.SLDPRT", "..", "a/b", "a\\b", "a" * 31, "A" * 32, "C:\\other"])
def test_unsafe_ids_are_rejected(tmp_path, bad_id):
    store = CheckpointStore(tmp_path / "store")
    with pytest.raises(ValueError, match="ID"):
        store.get(bad_id)
    with pytest.raises(ValueError, match="ID"):
        store.restore(bad_id, tmp_path / "restore.sldprt")


def test_restore_refuses_existing_files_and_store_namespace(tmp_path, part):
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    for target in (part, tmp_path / "existing.sldprt"):
        if not target.exists():
            target.write_bytes(b"keep me")
        before = target.read_bytes()
        with pytest.raises(FileExistsError):
            store.restore(result["id"], target)
        assert target.read_bytes() == before
    with pytest.raises(ValueError, match="inside checkpoint"):
        store.restore(result["id"], store.root / "injected.sldprt")
    assert not (store.root / "injected.sldprt").exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {"x"}, {1: "key"}])
def test_invalid_metadata_is_rejected_before_any_storage_write(tmp_path, part, value):
    root = tmp_path / "store"
    store = CheckpointStore(root)
    with pytest.raises(ValueError):
        store.create(part, label="bad", context={}, metadata={"bad": value})
    assert not root.exists()


def test_empty_nonpart_and_directory_sources_are_rejected(tmp_path):
    store = CheckpointStore(tmp_path / "store")
    empty = tmp_path / "empty.sldprt"
    empty.touch()
    other = tmp_path / "other.step"
    other.write_bytes(b"STEP")
    folder = tmp_path / "folder.sldprt"
    folder.mkdir()
    for source in (empty, other, folder):
        with pytest.raises(ValueError):
            make(store, source)
    assert not store.root.exists()


def test_failed_create_never_publishes_a_checkpoint(tmp_path, part, monkeypatch):
    store = CheckpointStore(tmp_path / "store")
    def fail(source, destination):
        destination.write_bytes(b"partial")
        raise OSError("copy interrupted")
    monkeypatch.setattr(checkpoints, "_copy_exclusive", fail)
    with pytest.raises(OSError, match="interrupted"):
        make(store, part)
    assert store.list() == []
    assert list(store.root.iterdir()) == []


def test_same_label_creates_distinct_checkpoints(tmp_path, part):
    store = CheckpointStore(tmp_path / "store")
    first, second = make(store, part), make(store, part)
    assert first["id"] != second["id"]
    assert first["sha256"] == second["sha256"]
    assert len(store.list()) == 2


def test_symlink_source_root_and_checkpoint_files_are_rejected(tmp_path, part):
    linked = tmp_path / "linked.sldprt"
    try:
        linked.symlink_to(part)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not allow test symlinks")
    with pytest.raises(ValueError, match="Symlink/reparse"):
        make(CheckpointStore(tmp_path / "bad-store"), linked)
    real = tmp_path / "real"
    real.mkdir()
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink/reparse"):
        CheckpointStore(linked_root / "child")
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    model = Path(result["model_path"])
    model.unlink()
    model.symlink_to(part)
    with pytest.raises(ValueError, match="Symlink/reparse"):
        store.get(result["id"])


def test_manifest_reparse_flag_is_rejected_even_when_not_a_symlink(tmp_path, part, monkeypatch):
    store = CheckpointStore(tmp_path / "store")
    result = make(store, part)
    original_lstat = Path.lstat
    class ReparseInfo:
        st_mode = checkpoints.stat.S_IFREG
        st_file_attributes = 0x400
    def fake_lstat(path):
        if path == Path(result["manifest_path"]):
            return ReparseInfo()
        return original_lstat(path)
    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(ValueError, match="Symlink/reparse"):
        store.get(result["id"])
