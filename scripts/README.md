# Apex Core Utility Scripts

This directory contains utility scripts for managing and maintaining your Apex Core bot deployment.

## Available Scripts

### validate_config.py

Validates bot configuration files before deployment to catch common mistakes and security issues.

**Features:**
- ✅ Validates Discord token format
- ✅ Checks for placeholder values
- ✅ Verifies required configuration fields
- ✅ Validates role configurations
- ✅ Checks payment configuration
- ✅ Verifies file permissions
- ✅ Validates environment variables

**Usage:**

```bash
# Validate all configuration
python3 scripts/validate_config.py

# Validate specific config file
python3 scripts/validate_config.py --config path/to/config.json

# Only check environment variables
python3 scripts/validate_config.py --env-only
```

**When to use:**
- Before first deployment
- After modifying configuration files
- When troubleshooting bot startup issues
- As part of deployment checklist

**Exit codes:**
- `0` - Validation passed (no errors)
- `1` - Validation failed (errors found)

## Future Scripts

Potential scripts that could be added:

- `backup_database.py` - Manual database backup utility
- `migrate_config.py` - Migrate configuration between versions
- `check_dependencies.py` - Check for outdated or vulnerable dependencies
- `setup_systemd.py` - Generate systemd service file
- `health_check.py` - Check bot health and connectivity

## Contributing

When adding new scripts:
1. Make them executable: `chmod +x scripts/your_script.py`
2. Include a shebang: `#!/usr/bin/env python3`
3. Add help text and examples
4. Document in this README
5. Follow existing code style

## Security Notes

- Scripts may read sensitive configuration files
- Keep scripts directory secure with appropriate permissions
- Never log or output sensitive credentials
- Validate all input from configuration files
