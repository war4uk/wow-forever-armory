import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def request_json(url, headers, data=None):
    # Do not print responses or request headers: OAuth responses contain tokens.
    try:
        with urlopen(Request(url, headers=headers, data=data), timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Network request failed") from None


def main():
    client_id = os.environ.get("CLIENT_ID", "")
    secret = os.environ.get("CLIENT_SECRET", "")
    if not client_id or not secret:
        raise RuntimeError("Add CLIENT_ID and CLIENT_SECRET to Actions repository secrets")
    auth = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    token = request_json(
        "https://oauth.battle.net/token",
        {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        b"grant_type=client_credentials",
    )["access_token"]
    slug = "локт-арогар"
    base = "https://eu.api.blizzard.com/profile/wow/character/" + quote(slug, safe="-")
    query = urlencode({"namespace": "profile-forever-eu", "locale": "ru_RU"})
    headers = {"Authorization": f"Bearer {token}"}
    sections = {}
    errors = {}
    for section, suffix in [("profile", ""), ("equipment", "/equipment"),
                            ("specializations", "/specializations"), ("professions", "/professions")]:
        try:
            sections[section] = request_json(base + suffix + "?" + query, headers)
        except RuntimeError as error:
            if section == "profile":
                raise RuntimeError(f"Profile lookup failed: {error}") from None
            errors[section] = str(error)
    if not isinstance(sections["profile"], dict) or not sections["profile"].get("id"):
        raise RuntimeError("Invalid profile response; previous snapshot preserved")
    payload = {
        "schema_version": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "region": "eu", "character_slug": slug,
        "namespace": "profile-forever-eu",
        "status": "partial" if errors else "ok",
        "source": "Blizzard Battle.net API",
        "data": sections, "errors": errors,
    }
    target = Path("data/character.json")
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print("Public snapshot generated: " + payload["status"])


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError):
        # Fixed error text prevents accidental disclosure of credentials or tokens.
        raise SystemExit("Sync failed. Check Secrets, API availability and character visibility. Previous snapshot preserved.")
