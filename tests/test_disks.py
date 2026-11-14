import pytest

from rushes import disks
from rushes.config import Config
from rushes.disks import DiskError, DiskInfo, NeedsDestination, check_destination, resolve_destination
from rushes.job import destination, set_destination


def test_needs_destination_when_nothing_configured():
    with pytest.raises(NeedsDestination):
        resolve_destination()


def test_chosen_folder(tmp_path):
    disk, base = resolve_destination(dest_folder=str(tmp_path))
    assert base == tmp_path and disk.free_bytes > 0


def test_check_rejects_missing_folder(tmp_path):
    with pytest.raises(DiskError, match="no existe"):
        check_destination(tmp_path / "nope")


def test_check_rejects_fat32(tmp_path, monkeypatch):
    monkeypatch.setattr(disks, "volume_of", lambda p: DiskInfo("E:\\", "USB", "FAT32", 1, 1, 7))
    with pytest.raises(DiskError, match="FAT32"):
        check_destination(tmp_path)


def test_disconnected_disk_message(tmp_path):
    with pytest.raises(DiskError, match="Conectalo"):
        resolve_destination(dest_folder=str(tmp_path / "desconectado" / "Rushes"), serial=0, label="Seagate")


def test_same_disk_with_new_letter(tmp_path, monkeypatch):
    # La carpeta guardada ya no existe (otra "letra"), pero un volumen con el mismo serial sí.
    new_root = tmp_path / "F"
    new_root.mkdir()
    monkeypatch.setattr(disks, "list_volumes", lambda: [DiskInfo(str(new_root), "Seagate", "NTFS", 9, 9, 1234)])
    old = tmp_path / "E" / "Material" / "Rushes"
    disk, base = resolve_destination(dest_folder=str(old), serial=1234)
    assert base == new_root / old.relative_to(old.anchor) and base.is_dir()


def test_set_destination_and_migration_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = Config.load()
    target = tmp_path / "Rushes"
    target.mkdir()
    set_destination(cfg, str(target))
    assert Config.load().dest_folder == str(target)
    _, base = destination(cfg)
    assert base == target
