"""
One-off check that ALPACA_API_KEY/ALPACA_SECRET_KEY in .env actually work -
hits Alpaca's real /v2/account endpoint and prints back what it finds.
Doesn't touch any service code, just for verifying credentials before
broker-gateway exists.

Usage: python verify_alpaca_key.py
"""

import os
import sys
from pathlib import Path

import httpx


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    load_env_file(Path(__file__).parent / ".env")

    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not secret_key:
        print("ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env - fill those in first.")
        return 1

    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}

    print(f"Checking {base_url}/v2/account ...")
    try:
        response = httpx.get(f"{base_url}/v2/account", headers=headers, timeout=10.0)
    except httpx.RequestError as exc:
        print(f"Couldn't reach Alpaca: {exc}")
        return 1

    if response.status_code == 401:
        print("401 Unauthorized - key or secret is wrong, or this is a live key hitting the paper endpoint.")
        return 1
    if response.status_code != 200:
        print(f"Unexpected response: {response.status_code} {response.text}")
        return 1

    account = response.json()
    print("\nConnected. Account summary:")
    print(f"  status:                {account.get('status')}")
    print(f"  account number:        {account.get('account_number')}")
    print(f"  currency:              {account.get('currency')}")
    print(f"  portfolio_value:       ${account.get('portfolio_value')}")
    print(f"  cash:                  ${account.get('cash')}")
    print(f"  buying_power:          ${account.get('buying_power')}")
    print(f"  options_trading_level: {account.get('options_trading_level')}")

    if float(account.get("portfolio_value", 0)) != 100000:
        print(
            "\nNote: portfolio_value isn't $100,000 - the hackathon requires a fresh account "
            "starting there. Reset it from the Alpaca dashboard if this isn't that account."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
