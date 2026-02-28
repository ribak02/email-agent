#!/usr/bin/env python3
"""
One-time CLI script to authorize a user's Microsoft account via device code flow.
Run this once per user to connect their Outlook account.

Usage:
    python scripts/authorize_user.py --phone +1234567890
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def authorize(phone_number: str) -> None:
    from app.services.session_store import get_redis
    from app.auth.microsoft_oauth import initiate_device_flow, poll_for_token

    redis = await get_redis()
    try:
        print(f"\nStarting Microsoft OAuth for phone: {phone_number}")
        flow = await initiate_device_flow(phone_number, redis)

        user_code = flow.get("user_code", "")
        verification_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")
        expires_in = flow.get("expires_in", 900)

        print(f"\n{'='*50}")
        print(f"  Visit:  {verification_uri}")
        print(f"  Code:   {user_code}")
        print(f"{'='*50}")
        print(f"\nYou have {expires_in // 60} minutes to complete authorization.")
        print("Waiting for authorization", end="", flush=True)

        # Poll until authorized or timeout
        for _ in range(expires_in // 5):
            await asyncio.sleep(5)
            print(".", end="", flush=True)
            authorized = await poll_for_token(phone_number, redis)
            if authorized:
                print(f"\n\n✓ Authorization successful for {phone_number}!")
                print("You can now send WhatsApp messages to interact with your Outlook email.")
                return

        print("\n\n✗ Authorization timed out. Please try again.")
        sys.exit(1)

    finally:
        await redis.aclose()


def main():
    parser = argparse.ArgumentParser(
        description="Authorize Microsoft Outlook access for a WhatsApp user"
    )
    parser.add_argument(
        "--phone",
        required=True,
        help="WhatsApp phone number in E.164 format (e.g. +1234567890)",
    )
    args = parser.parse_args()

    # Validate phone number format
    if not args.phone.startswith("+"):
        print("Error: Phone number must be in E.164 format (e.g. +1234567890)")
        sys.exit(1)

    asyncio.run(authorize(args.phone))


if __name__ == "__main__":
    main()
