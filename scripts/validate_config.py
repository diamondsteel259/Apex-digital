#!/usr/bin/env python3
"""
Configuration Validation Script for Apex Core Bot

This script validates the bot configuration before deployment to catch
common mistakes and security issues.

Usage:
    python3 scripts/validate_config.py
    python3 scripts/validate_config.py --config path/to/config.json
    python3 scripts/validate_config.py --env-only  # Only check environment variables
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ConfigValidator:
    """Validates Apex Core configuration files and environment variables."""

    def __init__(self, config_path: str = "config.json", env_path: str = ".env"):
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_all(self) -> bool:
        """Run all validation checks. Returns True if no errors found."""
        print("🔍 Apex Core Configuration Validator")
        print("=" * 60)
        
        # Check environment variables
        self.validate_environment()
        
        # Check config.json
        if self.config_path.exists():
            self.validate_config_json()
        else:
            self.errors.append(f"Config file not found: {self.config_path}")
        
        # Check payments config
        payments_path = Path("config/payments.json")
        if payments_path.exists():
            self.validate_payments_config(payments_path)
        else:
            self.warnings.append("config/payments.json not found - payment features may not work")
        
        # Check file permissions
        self.validate_file_permissions()
        
        # Print results
        self.print_results()
        
        return len(self.errors) == 0

    def validate_environment(self):
        """Validate environment variables."""
        print("\n📋 Checking Environment Variables...")
        
        # Check if .env exists
        if not self.env_path.exists():
            self.warnings.append(f".env file not found at {self.env_path}")
            self.info.append("Environment variables can also be set in the system environment")
        
        # Check critical environment variables
        discord_token = os.getenv("DISCORD_TOKEN")
        if discord_token:
            if self._validate_discord_token(discord_token):
                self.info.append("✅ DISCORD_TOKEN is set and valid format")
            else:
                self.errors.append("DISCORD_TOKEN has invalid format")
        else:
            self.info.append("DISCORD_TOKEN not in environment (will use config.json)")
        
        # Check optional but recommended variables
        optional_vars = {
            "GEMINI_API_KEY": "AI support (Free/Ultra tier)",
            "GROQ_API_KEY": "AI support (Premium tier)",
            "ATTO_MAIN_WALLET_ADDRESS": "Atto cryptocurrency payments",
            "ATTO_NODE_API": "Atto node connection",
        }
        
        for var, description in optional_vars.items():
            if os.getenv(var):
                self.info.append(f"✅ {var} is set ({description})")
            else:
                self.info.append(f"ℹ️  {var} not set ({description})")

    def validate_config_json(self):
        """Validate main config.json file."""
        print("\n📋 Checking config.json...")
        
        try:
            with self.config_path.open("r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in config.json: {e}")
            return
        except Exception as e:
            self.errors.append(f"Error reading config.json: {e}")
            return
        
        # Check for placeholder values
        self._check_placeholders(config, "config.json")
        
        # Validate required fields
        required_fields = ["token", "guild_ids", "role_ids", "logging_channels"]
        for field in required_fields:
            if field not in config:
                self.errors.append(f"Missing required field in config.json: {field}")
        
        # Validate token if present
        if "token" in config:
            token = config["token"]
            if "YOUR_" in token or "your_" in token.lower():
                self.warnings.append("Token in config.json appears to be a placeholder")
            elif not os.getenv("DISCORD_TOKEN"):  # Only validate if not using env var
                if not self._validate_discord_token(token):
                    self.errors.append("Discord token in config.json has invalid format")
                else:
                    self.info.append("✅ Token in config.json is valid format")
        
        # Validate guild IDs
        if "guild_ids" in config:
            if not isinstance(config["guild_ids"], list):
                self.errors.append("guild_ids must be a list")
            elif len(config["guild_ids"]) == 0:
                self.errors.append("guild_ids list is empty")
            else:
                self.info.append(f"✅ {len(config['guild_ids'])} guild(s) configured")
        
        # Validate role_ids
        if "role_ids" in config:
            if not isinstance(config["role_ids"], dict):
                self.errors.append("role_ids must be an object")
            elif "admin" not in config["role_ids"]:
                self.errors.append("role_ids.admin is required")
            else:
                self.info.append("✅ Admin role configured")
        
        # Check logging channels
        if "logging_channels" in config:
            channels = config["logging_channels"]
            required_log_channels = ["audit", "payments", "tickets", "errors"]
            for channel in required_log_channels:
                if channel not in channels:
                    self.errors.append(f"Missing required logging channel: {channel}")
            
            if all(ch in channels for ch in required_log_channels):
                self.info.append("✅ All required logging channels configured")
        
        # Validate roles configuration
        if "roles" in config and isinstance(config["roles"], list):
            self._validate_roles(config["roles"])
        
        # Check refund settings
        if "refund_settings" in config:
            refund = config["refund_settings"]
            if "max_days" in refund:
                max_days = refund["max_days"]
                if not isinstance(max_days, int) or max_days < 0 or max_days > 365:
                    self.errors.append(f"refund_settings.max_days must be between 0 and 365 (got {max_days})")

    def validate_payments_config(self, path: Path):
        """Validate payments configuration file."""
        print("\n📋 Checking config/payments.json...")
        
        try:
            with path.open("r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in payments.json: {e}")
            return
        except Exception as e:
            self.errors.append(f"Error reading payments.json: {e}")
            return
        
        # Check for placeholder values
        self._check_placeholders(config, "payments.json")
        
        # Validate required fields
        required_fields = ["payment_methods", "order_confirmation_template", "refund_policy"]
        for field in required_fields:
            if field not in config:
                self.errors.append(f"Missing required field in payments.json: {field}")
        
        # Validate order confirmation template
        if "order_confirmation_template" in config:
            template = config["order_confirmation_template"]
            required_placeholders = ["{order_id}", "{service_name}", "{variant_name}", "{price}", "{eta}"]
            missing = [p for p in required_placeholders if p not in template]
            if missing:
                self.errors.append(f"order_confirmation_template missing placeholders: {', '.join(missing)}")
            else:
                self.info.append("✅ Order confirmation template is valid")
        
        # Check payment methods
        if "payment_methods" in config:
            methods = config["payment_methods"]
            if not isinstance(methods, list):
                self.errors.append("payment_methods must be a list")
            elif len(methods) == 0:
                self.warnings.append("No payment methods configured")
            else:
                self.info.append(f"✅ {len(methods)} payment method(s) configured")

    def validate_file_permissions(self):
        """Check file permissions for security."""
        print("\n📋 Checking File Permissions...")
        
        sensitive_files = [
            self.config_path,
            self.env_path,
            Path("config/payments.json"),
        ]
        
        for file_path in sensitive_files:
            if not file_path.exists():
                continue
            
            # Check if file is readable by others (on Unix systems)
            if hasattr(os, 'stat'):
                stat_info = os.stat(file_path)
                mode = stat_info.st_mode
                
                # Check if others can read (octal 004)
                if mode & 0o004:
                    self.warnings.append(
                        f"{file_path} is readable by others. "
                        f"Recommended: chmod 600 {file_path}"
                    )
                else:
                    self.info.append(f"✅ {file_path} has secure permissions")

    def _validate_discord_token(self, token: str) -> bool:
        """Validate Discord token format."""
        if not token or not isinstance(token, str):
            return False
        
        parts = token.split('.')
        if len(parts) != 3:
            return False
        
        # Check that each part matches base64-like pattern
        token_part_pattern = r'^[A-Za-z0-9_-]+$'
        if not all(re.match(token_part_pattern, part) for part in parts):
            return False
        
        # Reasonable length checks
        if len(parts[0]) < 10 or len(parts[1]) < 3 or len(parts[2]) < 10:
            return False
        
        return True

    def _check_placeholders(self, data: dict, filename: str, path: str = ""):
        """Recursively check for placeholder values."""
        placeholder_patterns = [
            r'YOUR_\w+',
            r'your_\w+_here',
            r'REPLACE_ME',
            r'CHANGE_THIS',
            r'123456789012345678',  # Sequential placeholder IDs
        ]
        
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, str):
                for pattern in placeholder_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        self.warnings.append(
                            f"Possible placeholder in {filename} at {current_path}: {value[:50]}"
                        )
                        break
            elif isinstance(value, dict):
                self._check_placeholders(value, filename, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._check_placeholders(item, filename, f"{current_path}[{i}]")

    def _validate_roles(self, roles: list):
        """Validate roles configuration."""
        valid_modes = {"automatic_spend", "automatic_first_purchase", "automatic_all_ranks", "manual"}
        
        for i, role in enumerate(roles):
            if not isinstance(role, dict):
                continue
            
            name = role.get("name", f"Role {i}")
            
            # Check required fields
            if "assignment_mode" in role:
                mode = role["assignment_mode"]
                if mode not in valid_modes:
                    self.errors.append(
                        f"Role '{name}': invalid assignment_mode '{mode}'. "
                        f"Must be one of: {', '.join(valid_modes)}"
                    )
            
            # Check discount percent
            if "discount_percent" in role:
                discount = role["discount_percent"]
                if not isinstance(discount, (int, float)) or discount < 0 or discount > 100:
                    self.errors.append(
                        f"Role '{name}': discount_percent must be between 0 and 100 (got {discount})"
                    )

    def print_results(self):
        """Print validation results."""
        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS")
        print("=" * 60)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info_msg in self.info:
                print(f"   • {info_msg}")
        
        print("\n" + "=" * 60)
        if not self.errors:
            print("✅ Configuration validation passed!")
            print("=" * 60)
            return True
        else:
            print(f"❌ Configuration validation failed with {len(self.errors)} error(s)")
            print("=" * 60)
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Apex Core bot configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/validate_config.py
  python3 scripts/validate_config.py --config config.json
  python3 scripts/validate_config.py --env-only
        """
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json file (default: config.json)"
    )
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Only validate environment variables"
    )
    
    args = parser.parse_args()
    
    validator = ConfigValidator(config_path=args.config)
    
    if args.env_only:
        validator.validate_environment()
        validator.print_results()
    else:
        success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
