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

Vercel Setup (using Vercel CLI):
  1. Encode credentials and save to file:
     python tools/encode_firebase_creds.py > base64_creds.txt

  2. Add environment variables using Vercel CLI:
     # Read base64 string and add to Vercel
     vercel env add FIREBASE_CREDENTIALS_BASE64 production < base64_creds.txt

     # Set storage backend (type 'firebase' when prompted)
     echo firebase | vercel env add IMAGE_STORAGE_BACKEND production

     # Set bucket name (replace with your bucket)
     echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET production

  3. Repeat for preview/development if needed:
     vercel env add FIREBASE_CREDENTIALS_BASE64 preview < base64_creds.txt
     echo firebase | vercel env add IMAGE_STORAGE_BACKEND preview
     echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET preview

Alternative (using Vercel Dashboard):
  - Copy base64 string from base64_creds.txt
  - Go to: https://vercel.com/[project]/settings/environment-variables
  - Add variables manually

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

Using Vercel CLI:

1. Encode your firebase.json file:
   python tools/encode_firebase_creds.py > base64_creds.txt

2. Add environment variables using CLI commands:
   vercel env add FIREBASE_CREDENTIALS_BASE64 production < base64_creds.txt
   echo firebase | vercel env add IMAGE_STORAGE_BACKEND production
   echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET production

3. For preview/development environments:
   vercel env add FIREBASE_CREDENTIALS_BASE64 preview < base64_creds.txt
   echo firebase | vercel env add IMAGE_STORAGE_BACKEND preview
   echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET preview

Using Vercel Dashboard (alternative):
  - Copy base64 string from base64_creds.txt
  - Go to: https://vercel.com/[project]/settings/environment-variables
  - Add variables manually

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

        # Print helpful CLI commands to stderr so they don't interfere with piping
        if not args.validate:
            print("\n" + "=" * 60, file=sys.stderr)
            print("✓ Firebase credentials encoded successfully!", file=sys.stderr)
            print("\nTo set this in Vercel, run these CLI commands:", file=sys.stderr)
            print("\n# Save base64 output to file first:", file=sys.stderr)
            print(
                "python tools/encode_firebase_creds.py > base64_creds.txt",
                file=sys.stderr,
            )
            print("\n# Add base64 credentials to production:", file=sys.stderr)
            print(
                "vercel env add FIREBASE_CREDENTIALS_BASE64 production < base64_creds.txt",
                file=sys.stderr,
            )
            print("\n# Set storage backend:", file=sys.stderr)
            print(
                "echo firebase | vercel env add IMAGE_STORAGE_BACKEND production",
                file=sys.stderr,
            )
            print(
                "\n# Set Firebase bucket (replace with your bucket name):",
                file=sys.stderr,
            )
            print(
                "echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET production",
                file=sys.stderr,
            )
            print("\n# For preview/development environments:", file=sys.stderr)
            print(
                "vercel env add FIREBASE_CREDENTIALS_BASE64 preview < base64_creds.txt",
                file=sys.stderr,
            )
            print(
                "echo firebase | vercel env add IMAGE_STORAGE_BACKEND preview",
                file=sys.stderr,
            )
            print(
                "echo your-bucket.appspot.com | vercel env add FIREBASE_STORAGE_BUCKET preview",
                file=sys.stderr,
            )
            print("=" * 60, file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
