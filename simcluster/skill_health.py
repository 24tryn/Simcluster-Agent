#!/usr/bin/env python3
"""
Skill self-heal: runs at the start of every loop cycle.

- Fetches the latest https://simcluster.ai/skill.md
- If the SHA-256 differs from the local copy, overwrites the local file
- Re-extracts the edition's context-marker phrase from the file
  (the value carried in X-Simcluster-Skill-Ack)
- Writes the phrase to simcluster/skill_ack.txt so the daemon scripts
  pick it up on their next run without needing code edits

Logs to skill_health.log. Exits 0 even on transient fetch failure
so the loop never wedges; the next cycle will retry.
"""
import hashlib
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone
import os

BASE = pathlib.Path(os.environ.get("SIMCLUSTER_DIR", str(pathlib.Path(__file__).resolve().parent)))
SKILL = BASE / "skill.md"
ACK_FILE = BASE / "skill_ack.txt"
LOG = BASE / "skill_health.log"
SKILL_URL = "https://simcluster.ai/skill.md"

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def extract_ack(text: str) -> str | None:
    """Pull the edition's context marker out of the skill file.

    Patterns we try, in order of specificity:
      1. backticks near 'context marker'
      2. backticks near 'edition's' or 'edition'
      3. backticks immediately after 'remember'
    """
    patterns = [
        r"`([^`\n]{4,80})`[^.\n]{0,80}context marker",
        r"`([^`\n]{4,80})`[^.\n]{0,80}edition",
        r"remember\s+`([^`\n]{4,80})`",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def fetch_remote() -> bytes | None:
    try:
        req = urllib.request.Request(
            SKILL_URL,
            headers={"User-Agent": "simcluster-daemon-skill-health/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        log(f"WARN  fetch failed ({e}); will retry next cycle")
        return None

def main() -> int:
    remote = fetch_remote()
    if remote is None:
        return 0  # don't block the loop on transient network issues

    local = SKILL.read_bytes() if SKILL.exists() else b""
    remote_hash = hashlib.sha256(remote).hexdigest()
    local_hash = hashlib.sha256(local).hexdigest()

    if remote_hash == local_hash:
        # No-op: nothing changed. Make sure ack file at least exists & matches.
        if not ACK_FILE.exists():
            phrase = extract_ack(remote.decode("utf-8", errors="replace"))
            if phrase:
                ACK_FILE.write_text(phrase + "\n")
                log(f"INFO  initialised skill_ack.txt -> {phrase!r}")
            else:
                log("ERROR could not extract ack phrase from current skill")
                return 1
        return 0

    # Rotation detected -- LOUD warning
    log("=" * 60)
    log(f"ROTATION DETECTED: skill.md changed upstream")
    log(f"  old sha256: {local_hash}")
    log(f"  new sha256: {remote_hash}")
    text = remote.decode("utf-8", errors="replace")
    new_phrase = extract_ack(text)
    if not new_phrase:
        log("ERROR could not extract a new ack phrase from rotated skill!")
        log("      leaving old skill.md in place; manual review needed")
        log("=" * 60)
        return 2

    old_phrase = ACK_FILE.read_text().strip() if ACK_FILE.exists() else "(none)"
    SKILL.write_bytes(remote)
    ACK_FILE.write_text(new_phrase + "\n")
    log(f"  old ack: {old_phrase!r}")
    log(f"  new ack: {new_phrase!r}")
    log(f"OK    skill.md and skill_ack.txt updated; daemon will use new phrase")
    log("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
