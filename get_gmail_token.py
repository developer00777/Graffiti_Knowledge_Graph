#!/usr/bin/env python3
"""
Gmail OAuth Token Generator - Manual Flow

This script generates the OAuth URL for you to visit manually,
then you paste the authorization code back to get your refresh token.
"""
import os
import urllib.parse

# Your OAuth credentials — set these in your environment or .env file
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
]

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # For manual copy/paste flow


def generate_auth_url():
    """Generate the OAuth authorization URL"""
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # Force consent to get refresh token
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return url


def exchange_code_for_tokens(auth_code):
    """Exchange authorization code for access and refresh tokens"""
    import requests

    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    response = requests.post(token_url, data=data)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def test_token(access_token):
    """Test the access token by getting user profile"""
    import requests

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        "https://www.googleapis.com/gmail/v1/users/me/profile",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    return None


def update_env_file(refresh_token, email):
    """Update .env file with the refresh token"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')

    with open(env_path, 'r') as f:
        content = f.read()

    # Update refresh token
    import re
    content = re.sub(
        r'^GOOGLE_REFRESH_TOKEN=.*$',
        f'GOOGLE_REFRESH_TOKEN={refresh_token}',
        content,
        flags=re.MULTILINE
    )

    # Update email if not set
    content = re.sub(
        r'^GOOGLE_USER_EMAIL=.*$',
        f'GOOGLE_USER_EMAIL={email}',
        content,
        flags=re.MULTILINE
    )

    with open(env_path, 'w') as f:
        f.write(content)

    print(f"\n[OK] Updated .env with refresh token and email")


def main():
    print("=" * 70)
    print("Gmail OAuth Token Generator")
    print("=" * 70)

    # Step 1: Generate auth URL
    auth_url = generate_auth_url()

    print("\nSTEP 1: Open this URL in your browser:")
    print("-" * 70)
    print(auth_url)
    print("-" * 70)

    print("\nSTEP 2: Sign in with your Google account and click 'Allow'")
    print("\nSTEP 3: Copy the authorization code shown on the page")

    # Step 2: Get the code from user
    print("\n" + "=" * 70)
    auth_code = input("Paste the authorization code here: ").strip()

    if not auth_code:
        print("No code provided. Exiting.")
        return

    # Step 3: Exchange code for tokens
    print("\nExchanging code for tokens...")
    tokens = exchange_code_for_tokens(auth_code)

    if not tokens:
        print("Failed to get tokens. Please try again.")
        return

    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')

    if not refresh_token:
        print("\n[WARNING] No refresh token received!")
        print("This might happen if you've already authorized this app.")
        print("Try revoking access at: https://myaccount.google.com/permissions")
        print("Then run this script again.")
        return

    # Step 4: Test the token
    print("\nTesting token...")
    profile = test_token(access_token)

    if profile:
        email = profile.get('emailAddress', 'unknown')
        print(f"\n[OK] Successfully authenticated as: {email}")

        # Step 5: Save to .env
        update_env_file(refresh_token, email)

        print("\n" + "=" * 70)
        print("SUCCESS! Your Gmail OAuth setup is complete.")
        print("=" * 70)
        print(f"\nRefresh Token: {refresh_token[:20]}...{refresh_token[-10:]}")
        print(f"Email: {email}")
        print("\nYou can now run the email sync!")
    else:
        print("\n[ERROR] Token test failed. Please try again.")


if __name__ == "__main__":
    # Check for requests library
    try:
        import requests
    except ImportError:
        print("Installing requests library...")
        import subprocess
        subprocess.run(["pip", "install", "requests"])
        import requests

    main()
