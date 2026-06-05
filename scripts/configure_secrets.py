#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract supported KEY=value tokens from an install command and write .env."""

import os
import shlex
import stat
import sys


ALLOWED_KEYS = {
    "ARK_API_KEY",
}


def parse_tokens(argv):
    tokens = []
    for arg in argv:
        try:
            tokens.extend(shlex.split(arg))
        except ValueError:
            tokens.append(arg)

    found = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in ALLOWED_KEYS and value:
            found[key] = value
    return found


def read_existing(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in ALLOWED_KEYS:
                values[key] = value.strip()
    return values


def quote_env(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main():
    secrets = parse_tokens(sys.argv[1:])
    if not secrets:
        print("No supported KEY=value secrets found.")
        return 1

    skill_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(skill_dir, ".env")
    values = read_existing(env_path)
    values.update(secrets)

    lines = [
        "# Local secrets for financial-report-parser. Do not commit this file.",
        *[f"{key}={quote_env(values[key])}" for key in sorted(values)],
        "",
    ]
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)

    print(f"Configured {len(secrets)} secret(s) in {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
