import json
from pathlib import Path

import pytest

import apex_core.config as config_module
from apex_core.config import load_config


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_base_config() -> dict:
    return {
        "token": "TEST",
        "guild_ids": [1],
        "role_ids": {"admin": 99},
        "ticket_categories": {"support": 1, "billing": 2, "sales": 3},
        "operating_hours": {"start_hour_utc": 9, "end_hour_utc": 21},
        "payment_methods": [
            {"name": "Wallet", "instructions": "Use wallet"},
        ],
        "logging_channels": {"audit": 10, "payments": 11, "tickets": 12, "errors": 13},
        "roles": [
            {
                "name": "Client",
                "role_id": 1,
                "assignment_mode": "automatic_spend",
                "unlock_condition": 0,
                "discount_percent": 0,
            }
        ],
        "refund_settings": {"enabled": True, "max_days": 3, "handling_fee_percent": 10},
        "rate_limits": {"balance": {"cooldown": 60, "max_uses": 2, "per": "user"}},
    }


@pytest.fixture
def payments_payload() -> dict:
    return {
        "payment_methods": [
            {
                "name": "Wallet",
                "instructions": "Use wallet",
                "emoji": "💰",
                "metadata": {"is_enabled": True},
            }
        ],
        "order_confirmation_template": "Order #{order_id} {service_name} {variant_name} {price} {eta}",
        "refund_policy": "3 days",
    }


def test_load_config_success(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"

    _write_json(config_path, _build_base_config())
    _write_json(payments_path, payments_payload)

    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    cfg = load_config(config_path)
    assert cfg.token == "TEST"
    assert cfg.refund_settings is not None and cfg.refund_settings.max_days == 3
    assert cfg.payment_settings is not None
    assert cfg.payment_settings.order_confirmation_template.startswith("Order #")
    assert "balance" in cfg.rate_limits


def test_load_config_missing_file(tmp_path, monkeypatch):
    config_path = tmp_path / "missing.json"
    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", tmp_path / "payments.json")

    with pytest.raises(FileNotFoundError):
        load_config(config_path)


def test_rate_limit_validation_errors(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"

    invalid_config = _build_base_config()
    invalid_config["rate_limits"] = {"balance": "invalid"}

    _write_json(config_path, invalid_config)
    _write_json(payments_path, payments_payload)

    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    with pytest.raises(ValueError, match="rate_limits entry"):
        load_config(config_path)


def test_refund_settings_validation(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"
    _write_json(payments_path, payments_payload)
    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    # 1. Test valid boundary values
    valid_config = _build_base_config()
    valid_config["refund_settings"] = {
        "enabled": True,
        "max_days": 365,
        "handling_fee_percent": 100.0
    }
    _write_json(config_path, valid_config)
    cfg = load_config(config_path)
    assert cfg.refund_settings.max_days == 365
    assert cfg.refund_settings.handling_fee_percent == 100.0

    valid_config["refund_settings"] = {
        "enabled": True,
        "max_days": 0,
        "handling_fee_percent": 0.0
    }
    _write_json(config_path, valid_config)
    cfg = load_config(config_path)
    assert cfg.refund_settings.max_days == 0
    assert cfg.refund_settings.handling_fee_percent == 0.0

    # 2. Test non-numeric max_days
    invalid_config = _build_base_config()
    invalid_config["refund_settings"]["max_days"] = "three"
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.max_days must be an integer"):
        load_config(config_path)

    # 3. Test out-of-range max_days
    invalid_config["refund_settings"]["max_days"] = 366
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.max_days must be between 0 and 365"):
        load_config(config_path)

    invalid_config["refund_settings"]["max_days"] = -1
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.max_days must be between 0 and 365"):
        load_config(config_path)

    # 4. Test non-numeric handling_fee_percent
    invalid_config = _build_base_config()  # reset to clean base
    invalid_config["refund_settings"]["handling_fee_percent"] = "ten"
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.handling_fee_percent must be a number"):
        load_config(config_path)

    # 5. Test out-of-range handling_fee_percent
    invalid_config["refund_settings"]["handling_fee_percent"] = 100.1
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.handling_fee_percent must be between 0 and 100"):
        load_config(config_path)

    invalid_config["refund_settings"]["handling_fee_percent"] = -0.1
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="refund_settings.handling_fee_percent must be between 0 and 100"):
        load_config(config_path)


def test_role_validation(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"
    _write_json(payments_path, payments_payload)
    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    # 1. Happy path
    valid_config = _build_base_config()
    valid_config["roles"] = [
        {
            "name": "Valid Role",
            "role_id": 123456,
            "assignment_mode": "automatic_spend",
            "unlock_condition": 100,
            "discount_percent": 10.5,
            "tier_priority": 1,
            "benefits": ["Benefit 1"]
        }
    ]
    _write_json(config_path, valid_config)
    cfg = load_config(config_path)
    assert len(cfg.roles) == 1
    assert cfg.roles[0].name == "Valid Role"
    assert cfg.roles[0].discount_percent == 10.5

    # 2. Invalid assignment_mode
    invalid_config = _build_base_config()
    invalid_config["roles"] = [
        {
            "name": "Bad Mode",
            "role_id": 123,
            "assignment_mode": "invalid_mode",
            "unlock_condition": 0,
            "discount_percent": 0
        }
    ]
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="assignment_mode must be one of"):
        load_config(config_path)

    # 3. Invalid discount_percent (non-numeric)
    invalid_config["roles"][0]["assignment_mode"] = "manual"  # fix mode
    invalid_config["roles"][0]["discount_percent"] = "ten"
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="discount_percent must be a number"):
        load_config(config_path)

    # 4. Invalid discount_percent (out of range)
    invalid_config["roles"][0]["discount_percent"] = 101.0
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="discount_percent must be between 0 and 100"):
        load_config(config_path)

    # 5. Invalid tier_priority (negative)
    invalid_config["roles"][0]["discount_percent"] = 0  # fix discount
    invalid_config["roles"][0]["tier_priority"] = -1
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="tier_priority must be non-negative"):
        load_config(config_path)

    # 6. Invalid role_id (non-numeric)
    invalid_config["roles"][0]["tier_priority"] = 0  # fix priority
    invalid_config["roles"][0]["role_id"] = "abc"
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="role_id must be an integer"):
        load_config(config_path)

    # 7. Invalid role_id (negative)
    invalid_config["roles"][0]["role_id"] = -5
    _write_json(config_path, invalid_config)
    with pytest.raises(ValueError, match="role_id must be a positive integer"):
        load_config(config_path)
