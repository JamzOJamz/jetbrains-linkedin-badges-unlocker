#!/usr/bin/env python3
import argparse
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import sys
import threading
import webbrowser
from urllib.parse import quote

import requests
from flask import Flask, request
from requests_oauthlib import OAuth2Session
from werkzeug.serving import make_server

logging.getLogger("werkzeug").setLevel(logging.WARNING)

CLIENT_ID = "78ue55jmgrtzuj"
PORT = 19191
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPE = ["openid", "profile", "rw_credibilitySignals"]
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
AUTH_API_URL = "https://vmnr9qtn83.execute-api.eu-west-2.amazonaws.com/auth"
PLUGIN_SECRET = os.environ.get("JETBRAINS_PLUGIN_SECRET")
DEBUG_API = False
EXTERNAL_ID_NAMESPACE = "jetbrains-linkedin-badges-unlocker:v1:"
SIGNAL_URL = "https://api.linkedin.com/rest/credibilitySignalV2"
URN_PATTERN = re.compile(
    r"urn:li:profileCredibilitySignal:\(0,APP::urn:li:standardizedProduct:(\d+)::"
)
# Default top-to-bottom badge order; override with --priority
SIGNALS = (
    ("jetbrains-intellij-idea", "intellij-idea_level-5-coding-and-ai"),
    ("jetbrains-clion", "clion_level-5-coding-and-ai"),
    ("jetbrains-pycharm", "pycharm_level-5-coding-and-ai"),
    ("jetbrains-goland", "goland_level-5-coding-and-ai"),
    ("jetbrains-phpstorm", "phpstorm_level-5-coding-and-ai"),
    ("jetbrains-rider", "rider_level-5-coding-and-ai"),
    ("jetbrains-rustrover-a-ide", "rustrover_level-5-coding-and-ai"),
    ("jetbrains-webstorm", "webstorm_level-5-coding-and-ai"),
    ("jetbrains-rubymine", "rubymine_level-5-coding-and-ai"),
)
LEVELS = (
    "1",
    "2",
    "3-coding",
    "3-ai",
    "3-coding-and-ai",
    "4-coding",
    "4-ai",
    "5-coding-and-ai",
)
DEFAULT_LEVEL = "1"
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "badges.json")
SIGNALS_BY_NAME = dict(
    zip((signal[0].removeprefix("jetbrains-") for signal in SIGNALS), SIGNALS)
)

app = Flask(__name__)
oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
# State is generated randomly by oauthlib
auth_url, state = oauth.authorization_url(AUTH_URL, enable_extended_login="true")
server = make_server("localhost", PORT, app)
result = {}


def debug_api_response(response):
    if not DEBUG_API:
        return

    redacted_headers = {
        key: "******"
        if key.lower() in {"authorization", "x-plugin-secret", "set-cookie"}
        else value
        for key, value in response.headers.items()
    }
    try:
        body = response.json()
        if isinstance(body, dict):
            body = {
                key: "******"
                if key.lower() in {
                    "access_token",
                    "refresh_token",
                    "id_token",
                    "token",
                }
                else value
                for key, value in body.items()
            }
    except ValueError:
        body = response.text

    request = response.request
    method = request.method if request else "UNKNOWN"
    url = request.url if request else response.url
    print(f"[api] {method} {url} -> {response.status_code}")
    print(f"[api] response headers: {redacted_headers}")
    print(f"[api] response body: {body}")


@app.get("/callback")
def callback():
    if request.args.get("state") != state:
        result["error"] = "state mismatch"
    elif "error" in request.args:
        result["error"] = request.args.get("error_description", request.args["error"])
    else:
        result["code"] = request.args.get("code")

    threading.Thread(target=server.shutdown, daemon=True).start()
    return (
        "Done. You can close this tab and return to the script."
        if "code" in result
        else f"Failed: {result['error']}"
    )


def external_id_from_id_token(id_token):
    if not isinstance(id_token, str):
        raise ValueError("the authorization response contained an invalid ID token")

    try:
        _, payload, _ = id_token.split(".")
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("the authorization response contained an invalid ID token") from error

    if not isinstance(claims, dict):
        raise ValueError("the ID token payload was not an object")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("the ID token did not contain a usable subject")

    return hashlib.sha256(
        f"{EXTERNAL_ID_NAMESPACE}{subject}".encode("utf-8")
    ).hexdigest()[:25]


def exchange_authorization_code(code):
    if not PLUGIN_SECRET:
        raise RuntimeError("Set JETBRAINS_PLUGIN_SECRET before running the script")

    headers = {
        "Accept": "application/json; charset=utf-8",
        "X-Plugin-Secret": PLUGIN_SECRET,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        response = requests.post(
            AUTH_API_URL,
            headers=headers,
            json={"grant_type": "authorization_code", "code": code},
            timeout=30,
        )
        debug_api_response(response)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Failed to exchange authorization code: {error}", file=sys.stderr)
        sys.exit(1)

    try:
        token_response = response.json()
    except ValueError:
        print("Failed to obtain access token: invalid response", file=sys.stderr)
        sys.exit(1)

    access_token = token_response.get("access_token")
    if not access_token:
        print(
            "Failed to obtain access token: response did not include one",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        external_id = external_id_from_id_token(token_response["id_token"])
    except (KeyError, ValueError) as error:
        print(f"Failed to derive a stable external ID: {error}", file=sys.stderr)
        sys.exit(1)

    return access_token, external_id


def build_signal_data(
    external_id, product_vanity_name, capability_template_id, top_percentile
):
    metadata = {
        "externalId": external_id,
        "productVanityName": product_vanity_name,
        "capabilityTemplateId": capability_template_id,
        "isTopUser": top_percentile is not None,
    }
    if top_percentile is not None:
        metadata["topUserPercentile"] = top_percentile
    return {
        "entityType": "APP",
        "issuer": "JETBRAINS",
        "metadata": json.dumps(metadata),
    }


def submit_signal(
    access_token,
    external_id,
    product_vanity_name,
    capability_template_id,
    top_percentile,
):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202604",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = build_signal_data(
        external_id, product_vanity_name, capability_template_id, top_percentile
    )
    response = None

    try:
        response = requests.post(SIGNAL_URL, headers=headers, json=data, timeout=30)
        debug_api_response(response)
        if response.status_code == 409:
            match = URN_PATTERN.search(response.text)
            if match is None:
                raise requests.HTTPError(
                    "409 response did not contain a credibility signal URN"
                )

            product_id = match.group(1)
            urn = (
                "urn:li:profileCredibilitySignal:"
                f"(0,APP::urn:li:standardizedProduct:{product_id}::{external_id})"
            )
            response = requests.put(
                f"{SIGNAL_URL}/{quote(urn, safe='')}",
                headers=headers,
                json=data,
                timeout=30,
            )
            debug_api_response(response)
        response.raise_for_status()
    except requests.RequestException as error:
        if response is not None:
            print(f"LinkedIn response status: {response.status_code}", file=sys.stderr)
            print(f"LinkedIn response body: {response.text}", file=sys.stderr)
            request_id = response.headers.get("x-restli-id") or response.headers.get(
                "x-li-request-id"
            )
            if request_id:
                print(f"LinkedIn request ID: {request_id}", file=sys.stderr)
        print(f"Failed to submit credibility signal: {error}", file=sys.stderr)
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        add_help=False,
        description=(
            "Add JetBrains badges to your LinkedIn profile with freely customizable "
            "badge levels and top-user rankings, without installing or using the IDEs."
        ),
        epilog=(
            "By default, unlock all IDE badges at level 1 without top-user status. "
            "A badges.json file can change the order, level, and top-user percentile "
            "for all badges or individual badges. Settings left out use the defaults. "
            "Badge levels: " + ", ".join(LEVELS)
        ),
    )
    parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit."
    )
    parser.add_argument(
        "--priority",
        nargs="+",
        metavar="IDE",
        choices=tuple(SIGNALS_BY_NAME),
        help=(
            "Show these IDEs first, in this order. Any others follow in the usual "
            "order (example: --priority rider webstorm clion)."
        ),
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="IDE",
        choices=tuple(SIGNALS_BY_NAME),
        help="Only unlock badges for these IDEs (example: --only rider clion).",
    )
    parser.add_argument(
        "--top-percentile",
        type=int,
        default=None,
        metavar="N",
        help="Show yourself as a top user at this percentile, 1-100 (default: off).",
    )
    parser.add_argument(
        "--level",
        choices=LEVELS,
        default=DEFAULT_LEVEL,
        help=f"Badge level to use for every IDE (default: {DEFAULT_LEVEL}).",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help=(
            "Load badges from a JSON file in the order listed. You can set a level "
            "or top-user percentile for each badge. Example files are in examples/. "
            "By default, uses badges.json next to this script if it exists. Can't "
            "be used with --only or --priority."
        ),
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Don't use badges.json next to this script; use the options above instead.",
    )
    parser.add_argument(
        "--debug-api",
        action="store_true",
        help="Print API responses for troubleshooting (tokens and secrets are hidden).",
    )
    args = parser.parse_args()
    if args.config and args.no_config:
        parser.error("--config cannot be combined with --no-config")
    if args.config and (args.only or args.priority):
        parser.error("--config cannot be combined with --only or --priority")
    if args.top_percentile is not None and not 1 <= args.top_percentile <= 100:
        parser.error("--top-percentile must be between 1 and 100")
    if args.only and len(args.only) != len(set(args.only)):
        parser.error("--only cannot contain duplicate IDE names")
    if args.priority and len(args.priority) != len(set(args.priority)):
        parser.error("--priority cannot contain duplicate IDE names")
    return args


def ordered_signals(priority):
    prioritized = [SIGNALS_BY_NAME[name] for name in priority or ()]
    prioritized_names = set(priority or ())
    remaining = [
        signal
        for signal in SIGNALS
        if signal[0].removeprefix("jetbrains-") not in prioritized_names
    ]
    return prioritized + remaining


def selected_signals(priority, only):
    signals = ordered_signals(priority)
    if not only:
        return signals
    return [s for s in signals if s[0].removeprefix("jetbrains-") in set(only)]


def percentile_from(value, where):
    if value is None or value is False:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError(f"{where}: topPercentile must be 1-100 or null")
    return value


def load_config(path, default_percentile, default_level):
    """Return [(signal, percentile_or_None, level)] in display order."""
    try:
        with open(path, encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read config {path}: {error}")

    if isinstance(config, list):
        config = {"badges": config}
    if not isinstance(config, dict) or not isinstance(config.get("badges"), list):
        raise ValueError('config must contain a "badges" list')

    default = default_percentile
    if "topPercentile" in config:
        default = percentile_from(config["topPercentile"], "top level")

    if "level" in config:
        default_level = config["level"]
        if default_level not in LEVELS:
            raise ValueError(f"top level: unknown level {default_level!r} (choose from {', '.join(LEVELS)})")

    entries, seen = [], set()
    for index, item in enumerate(config["badges"]):
        where = f"badges[{index}]"
        if isinstance(item, str):
            item = {"ide": item}
        if not isinstance(item, dict) or "ide" not in item:
            raise ValueError(f'{where}: expected an IDE name or an object with "ide"')
        name = item["ide"]
        if name not in SIGNALS_BY_NAME:
            raise ValueError(
                f"{where}: unknown IDE {name!r} (choose from {', '.join(SIGNALS_BY_NAME)})"
            )
        if name in seen:
            raise ValueError(f"{where}: duplicate IDE {name!r}")
        seen.add(name)
        percentile = (
            percentile_from(item["topPercentile"], where)
            if "topPercentile" in item
            else default
        )
        level = item.get("level", default_level)
        if level not in LEVELS:
            raise ValueError(f"{where}: unknown level {level!r} (choose from {', '.join(LEVELS)})")
        entries.append((SIGNALS_BY_NAME[name], percentile, level))
    if not entries:
        raise ValueError("config lists no badges")
    return entries


def main():
    global DEBUG_API

    args = parse_args()
    DEBUG_API = args.debug_api
    top_percentile = args.top_percentile
    config_path = args.config
    if (
        not config_path
        and not (args.no_config or args.only or args.priority)
        and os.path.isfile(DEFAULT_CONFIG)
    ):
        config_path = DEFAULT_CONFIG
    if config_path:
        print(f"Using config: {config_path}")
        try:
            entries = load_config(config_path, top_percentile, args.level)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    else:
        entries = [
            (signal, top_percentile, args.level)
            for signal in selected_signals(args.priority, args.only)
        ]

    print("Opening browser:")
    print(auth_url)
    webbrowser.open(auth_url)
    server.serve_forever()
    if "code" not in result:
        print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    print("Authorization completed successfully.")

    access_token, external_id = exchange_authorization_code(result["code"])
    print("Access token obtained successfully.")

    for (product_vanity_name, default_template_id), percentile, level in reversed(
        entries
    ):
        template_prefix = default_template_id.split("_level-")[0]
        capability_template_id = f"{template_prefix}_level-{level}"
        print(f"Submitting {product_vanity_name} ({level}) signal...")
        submit_signal(
            access_token,
            external_id,
            product_vanity_name,
            capability_template_id,
            percentile,
        )

    print("Credibility signal(s) submitted successfully.")


if __name__ == "__main__":
    main()
