"""Authentication providers for VersionOne API."""

import os
import subprocess


class AuthError(Exception):
    """Raised when authentication fails."""


def get_v1_url() -> str:
    """Get the VersionOne instance URL from environment.

    Returns:
        The V1 URL (e.g., 'https://www7.v1host.com/MyInstance')

    Raises:
        AuthError: If V1_URL is not set
    """
    url = os.environ.get("V1_URL")
    if not url:
        raise AuthError(
            "V1_URL environment variable not set.\n"
            "Set it to your VersionOne instance URL, e.g.:\n"
            "  export V1_URL='https://www7.v1host.com/MyInstance'"
        )
    return url.rstrip("/")


def get_auth_token() -> str:
    """Get the VersionOne API token from environment.

    Returns:
        The API token

    Raises:
        AuthError: If V1_TOKEN is not set
    """
    token = os.environ.get("V1_TOKEN")
    if not token:
        raise AuthError(
            "V1_TOKEN environment variable not set.\n"
            "Generate an access token in VersionOne:\n"
            "  1. Go to your V1 instance\n"
            "  2. Navigate to your profile settings\n"
            "  3. Create a new access token\n"
            "  4. Set: export V1_TOKEN='your-token-here'"
        )
    return token


def get_verify_ssl() -> bool:
    """Get SSL verification setting from environment.

    Set V1_VERIFY_SSL=false to disable SSL certificate verification.
    This is useful for corporate environments with custom CAs or self-signed certs.

    Returns:
        True if SSL should be verified (default), False otherwise
    """
    value = os.environ.get("V1_VERIFY_SSL", "true").lower()
    return value not in ("false", "0", "no", "off")


def get_auth_token_1password(item_name: str = "VersionOne") -> str:
    """Get the VersionOne API token from 1Password CLI.

    Args:
        item_name: The name of the 1Password item containing the token

    Returns:
        The API token

    Raises:
        AuthError: If 1Password CLI fails or item not found
    """
    try:
        result = subprocess.run(
            ["op", "item", "get", item_name, "--fields", "credential"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise AuthError(
            "1Password CLI (op) not found.\n"
            "Install it from: https://1password.com/downloads/command-line/"
        )
    except subprocess.CalledProcessError as e:
        raise AuthError(f"Failed to get token from 1Password: {e.stderr}")
