from __future__ import annotations

import json

import pytest

from apex_core.config_writer import ConfigWriter, _normalize_role_name, update_config_atomically


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Apex Staff", "apex_staff"),
        ("VIP-Plus", "vip_plus"),
        ("  Weird   Name!!! ", "weird_name"),
    ],
)
def test_normalize_role_name(raw: str, expected: str) -> None:
    assert _normalize_role_name(raw) == expected


@pytest.mark.asyncio
async def test_config_writer_updates_and_creates_backup(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"role_ids": {"apex_staff": 1}}), encoding="utf-8")

    writer = ConfigWriter(cfg_path)
    await writer.update_config_section("role_ids", {"new_role": 2}, create_backup=True)

    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["role_ids"]["new_role"] == 2

    backups_dir = tmp_path / "config_backups"
    backups = list(backups_dir.glob("config_backup_*.json"))
    assert backups, "Expected a timestamped backup to be created"


@pytest.mark.asyncio
async def test_config_writer_set_role_ids_normalizes_names(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"role_ids": {}}), encoding="utf-8")

    writer = ConfigWriter(cfg_path)
    await writer.set_role_ids({"Apex Staff": 123}, bot=None)

    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["role_ids"]["apex_staff"] == 123


@pytest.mark.asyncio
async def test_config_writer_raises_on_missing_file(tmp_path):
    cfg_path = tmp_path / "missing.json"
    writer = ConfigWriter(cfg_path)

    with pytest.raises(FileNotFoundError):
        await writer.update_config_section("role_ids", {"x": 1}, create_backup=False)


@pytest.mark.asyncio
async def test_config_writer_raises_on_non_dict_section(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"role_ids": []}), encoding="utf-8")

    writer = ConfigWriter(cfg_path)
    with pytest.raises(ValueError, match="not a dictionary"):
        await writer.update_config_section("role_ids", {"x": 1}, create_backup=False)


@pytest.mark.asyncio
async def test_update_config_atomically_convenience(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"channel_ids": {}}), encoding="utf-8")

    await update_config_atomically("channel_ids", {"log": 999}, config_path=cfg_path)

    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["channel_ids"]["log"] == 999
