#!/usr/bin/env python3
"""
Account Type Helper Script

Reads the accounts configuration file and returns the account type for a given account name.
Can be imported as a module or used as a command-line script.
"""

import json
import sys
from pathlib import Path
from typing import Literal, Optional

AccountType = Literal["Personal", "Business"]
DEFAULT_ACCOUNT_TYPE: AccountType = "Personal"

def load_accounts_config(project_root: Optional[Path] = None) -> dict:
    """Load the accounts configuration file."""
    if project_root is None:
        project_root = Path(__file__).parent
    
    config_file = project_root / 'storage' / 'accounts.json'
    
    if not config_file.exists():
        return {"accounts": {}}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read accounts config: {e}", file=sys.stderr)
        return {"accounts": {}}

def get_account_type(account_name: str, project_root: Optional[Path] = None) -> AccountType:
    """
    Get the account type for a given account name.
    
    Args:
        account_name: The name of the account (folder name)
        project_root: Optional project root path (defaults to script directory)
    
    Returns:
        "Personal" or "Business", defaults to "Personal" if not found
    """
    config = load_accounts_config(project_root)
    accounts = config.get("accounts", {})
    
    account_config = accounts.get(account_name)
    if account_config and isinstance(account_config, dict):
        account_type = account_config.get("type")
        if account_type in ("Personal", "Business"):
            return account_type
    
    return DEFAULT_ACCOUNT_TYPE

def is_business_account(account_name: str, project_root: Optional[Path] = None) -> bool:
    """Check if an account is a business account."""
    return get_account_type(account_name, project_root) == "Business"

def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <account_name>")
        print(f"Returns: Personal or Business (default: {DEFAULT_ACCOUNT_TYPE})")
        sys.exit(1)
    
    account_name = sys.argv[1]
    account_type = get_account_type(account_name)
    print(account_type)

if __name__ == '__main__':
    main()

