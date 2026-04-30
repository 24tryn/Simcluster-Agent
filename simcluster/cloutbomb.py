#!/usr/bin/env python3
"""
Cloutbomb Daemon - mubz.24
Run every 90 minutes via Windows Task Scheduler
Likes up to 25 posts per target user to trigger reciprocal engagement
"""
import json, re, subprocess, hashlib
from datetime import datetime, timedelta
import pathlib
from pathlib import Path

import os
BASE       = pathlib.Path(os.environ.get("SIMCLUSTER_DIR", str(pathlib.Path(__file__).resolve().parent)))
TOKEN      = os.environ.get("SIMCLUSTER_BEARER") or (BASE / "bearer.txt").read_text().strip()
SKILL_HASH = hashlib.sha256(open(str(BASE / "skill.md"), "rb").read()).hexdigest()
SKILL_ACK  = "curious awake iron turn cabbage"
LOG        = BASE / "cloutbomb_daemon.log"
BOMB_LOG   = BASE / "cloutbomb_log.md"
YOUR_CHAR  = "kEx2X9oq"  # Replace with your charShortId from sessionStatus

BOMB_LOG.touch(exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def mcp(name, args={}):
    payload = {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":args}}
    r = subprocess.run([
        "curl","-s","-X","POST","https://simcluster.ai/mcp",
        "-H",f"Authorization: Bearer {TOKEN}",
        "-H","Content-Type: application/json",
        "-H","Accept: application/json, text/event-stream",
        "-H",f"X-Simcluster-Skill-Hash: {SKILL_HASH}",
        "-H",f"X-Simcluster-Skill-Ack: {SKILL_ACK}",
        "-d",json.dumps(payload)
    ], capture_output=True, text=True, timeout=30)
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', r.stdout)
    try:
        obj = json.loads(raw)
        for c in obj.get("result",{}).get("content",[]):
            if c.get("type") == "text":
                try: return json.loads(c["text"])
                except: return c["text"]
    except Exception as e:
        log(f"  MCP ERR [{name}]: {e}")
    return None

def like(sid):
    mcp("posts.likePost", {"shortId": sid, "active": True})

def load_bomb_log():
    bombed = {}
    today = datetime.now().date()
    for line in BOMB_LOG.read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[0] and not parts[0].startswith("#"):
            try:
                bomb_date     = datetime.strptime(parts[2], "%Y-%m-%d").date()
                next_eligible = datetime.strptime(parts[3], "%Y-%m-%d")
                if bomb_date == today:
                    next_eligible = datetime.combine(today + timedelta(days=1), datetime.min.time())
                if parts[0] not in bombed or bombed[parts[0]] < next_eligible:
                    bombed[parts[0]] = next_eligible
            except: pass
    return bombed

def log_bomb(username, char_id):
    today    = datetime.now()
    eligible = today + timedelta(days=5)
    with open(BOMB_LOG, "a") as f:
        f.write(f"{username} | {char_id} | {today.strftime('%Y-%m-%d')} | {eligible.strftime('%Y-%m-%d')}\n")

def cloutbomb(username, char_id, bombed):
    if not username or not char_id: return False
    if username in bombed and datetime.now() < bombed[username]:
        log(f"  Skip @{username} -- cooldown until {bombed[username].strftime('%Y-%m-%d')}")
        return False
    result = mcp("posts.getCharacterTimelineFeed", {"charShortIds": [char_id], "limit": 25})
    posts = []
    if isinstance(result, dict): posts = result.get("posts", [])
    elif isinstance(result, list): posts = result
    count = 0
    for p in posts[:25]:
        sid = p.get("shortId") or p.get("short_id")
        if sid:
            like(sid)
            count += 1
    if count:
        log(f"  Cloutbombed @{username}: {count} likes")
        log_bomb(username, char_id)
        bombed[username] = datetime.now() + timedelta(days=5)
        return True
    else:
        log(f"  @{username} -- no posts found")
        return False

def main():
    log("=" * 50)
    log("Cloutbomb START")
    bombed = load_bomb_log()

    log("-- Feed --")
    feed_raw = mcp("posts.getForYouFeed", {"limit": 15})
    feed_posts = feed_raw if isinstance(feed_raw, list) else (feed_raw or {}).get("posts", [])

    liked = 0
    for post in feed_posts[:15]:
        sid = post.get("shortId") or post.get("short_id")
        if sid:
            like(sid)
            liked += 1
    log(f"  Liked {liked} feed posts")

    # Agents first, then humans
    for post in sorted(feed_posts[:15], key=lambda p: p.get("is_agent", False), reverse=True):
        author = post.get("author", {})
        uname = author.get("username") if isinstance(author, dict) else post.get("author_username")
        cid   = author.get("shortId") or author.get("charShortId") if isinstance(author, dict) else post.get("charShortId")
        if uname and cid:
            cloutbomb(uname, cid, bombed)

    log("Cloutbomb DONE")
    log("=" * 50 + "\n")

if __name__ == "__main__":
    main()
