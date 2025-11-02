#!/usr/bin/env python3
"""
Helper script to encode Firebase credentials JSON file to base64 for use in Vercel.

This script reads firebase.json (or a specified file) and outputs the base64-encoded
string that can be set as the FIREBASE_CREDENTIALS_BASE64 environment variable in Vercel.

Usage:
    python tools/encode_firebase_creds.py [path/to/firebase.json]

    Or pipe the output:
    python tools/encode_firebase_creds.py > base64_creds.txt
"""

import argparse
import base64
import json
import sys
from pathlib import Path


def encode_firebase_credentials(file_path: str) -> str:
    """
    Encode Firebase credentials JSON file to base64.

    Args:
        file_path: Path to Firebase credentials JSON file

    Returns:
        Base64-encoded string
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Firebase credentials file not found: {file_path}")

    # Read and validate JSON
    try:
        with open(path) as f:
            json.load(f)  # Validate JSON format
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in credentials file: {e}") from e

    # Encode to base64
    with open(path, "rb") as f:
        file_bytes = f.read()
        base64_encoded = base64.b64encode(file_bytes).decode("utf-8")

    return base64_encoded


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Encode Firebase credentials JSON to base64 for Vercel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode firebase.json and output to console
  python tools/encode_firebase_creds.py

  # Encode specific file and save to text file
  python tools/encode_firebase_creds.py path/to/firebase.json > base64_creds.txt

  # Validate the encoding
  python tools/encode_firebase_creds.py --validate

Vercel Setup:
  1. Run this script to encode your firebase.json:
     python tools/encode_firebase_creds.py > base64_creds.txt

  2. Copy the base64 string from base64_creds.txt

  3. In Vercel dashboard, go to your project Settings > Environment Variables

  4. Add a new environment variable:
     Name:  FIREBASE_CREDENTIALS_BASE64
     Value: [paste the base64 string from step 2]
     Environment: Production, Preview, Development (as needed)

  5. Also set these required variables:
     - IMAGE_STORAGE_BACKEND=firebase
     - FIREBASE_STORAGE_BUCKET=your-bucket-name.appspot.com

  6. Redeploy your application

Note: The base64 string can be very long. Make sure to copy the entire string.
        """,
    )
    parser.add_argument(
        "credentials_file",
        type=str,
        nargs="?",
        default="firebase.json",
        help="Path to Firebase credentials JSON file (default: firebase.json)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the base64-encoded credentials by decoding them",
    )
    parser.add_argument(
        "--instructions",
        action="store_true",
        help="Print Vercel setup instructions only",
    )

    args = parser.parse_args()

    if args.instructions:
        print(
            """
Vercel Environment Variable Setup
==================================

1. Encode your firebase.json file:
   python tools/encode_firebase_creds.py > base64_creds.txt

2. Copy the entire base64 string from base64_creds.txt (it may be very long)

3. In Vercel dashboard:
   - Go to your project
   - Navigate to Settings > Environment Variables
   - Add a new variable:
     * Name: FIREBASE_CREDENTIALS_BASE64
     * Value: [paste the base64 string]
     * Environment: Select Production, Preview, Development as needed

4. Set these additional required environment variables:
   * IMAGE_STORAGE_BACKEND=firebase
   * FIREBASE_STORAGE_BUCKET=your-bucket-name.appspot.com

5. Redeploy your application

The application will automatically detect FIREBASE_CREDENTIALS_BASE64 and use it
instead of FIREBASE_CREDENTIALS_PATH when available.
        """,
            file=sys.stderr,
        )
        sys.exit(0)

    try:
        base64_encoded = encode_firebase_credentials(args.credentials_file)

        if args.validate:
            # Validate by decoding
            try:
                decoded = base64.b64decode(base64_encoded)
                decoded_json = json.loads(decoded.decode("utf-8"))
                print("✓ Base64 encoding validated successfully", file=sys.stderr)
                print(
                    f"✓ Credentials contain project_id: {decoded_json.get('project_id', 'N/A')}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"✗ Validation failed: {e}", file=sys.stderr)
                sys.exit(1)

        # Output the base64 string
        print(base64_encoded)

        # Print helpful instructions to stderr so they don't interfere with piping
        if not args.validate:
            print("\n" + "=" * 60, file=sys.stderr)
            print("✓ Firebase credentials encoded successfully!", file=sys.stderr)
            print("\nTo set this in Vercel:", file=sys.stderr)
            print("1. Copy the base64 string above (entire output)", file=sys.stderr)
            print("2. In Vercel: Settings > Environment Variables", file=sys.stderr)
            print(
                "3. Add variable: FIREBASE_CREDENTIALS_BASE64 = [paste base64 string]",
                file=sys.stderr,
            )
            print("4. Also set: IMAGE_STORAGE_BACKEND=firebase", file=sys.stderr)
            print(
                "5. Also set: FIREBASE_STORAGE_BUCKET=your-bucket-name", file=sys.stderr
            )
            print("6. Redeploy your application", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
