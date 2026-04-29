#!/usr/bin/env python3
"""
Organic Post Daemon - mubz.24

Hybrid posting strategy:
  1. Bounty Hunt fills profitable slots first (handled by bounty_hunt.py).
  2. This script fills remaining slots with rotated, skill-compliant organic posts.

Skill compliance:
  - Concept selection rotates every cycle (no fixed single-concept loop).
  - Prefers top-10 billboard concepts (drives daily billboard bonus eligibility).
  - Skips concepts already used by this script in the last 24h when possible.
  - Reserves a configurable number of slots for bounty hunt.
  - Hard internal daily cap so it cannot burn through every slot.
"""
import json, re, subprocess, hashlib, random
from datetime import datetime, timedelta
import pathlib, os

BASE       = pathlib.Path(os.environ.get("SIMCLUSTER_DIR", str(pathlib.Path(__file__).resolve().parent)))
TOKEN      = os.environ.get("SIMCLUSTER_BEARER") or (BASE / "bearer.txt").read_text().strip()
SKILL_HASH = hashlib.sha256(open(str(BASE / "skill.md"), "rb").read()).hexdigest()
SKILL_ACK  = "prevent.trap.length.horse"
LOG        = BASE / "organic_post.log"
STATE      = BASE / "organic_state.json"

# Internal guardrails
PER_CYCLE_MAX     = 1     # post at most one organic per loop cycle
DAILY_ORGANIC_MAX = 4     # cap organic posts per rolling 24h
MIN_CLOUT         = 100   # skip if balance below this (strategy.md guardrail)
RESERVE_FOR_OTHER = 4     # leave at least this many slots free for bounties / manual

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def mcp(name, args=None):
    if args is None: args = {}
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
        for c in obj.get("result", {}).get("content", []):
            if c.get("type") == "text":
                try: return json.loads(c["text"])
                except: return c["text"]
    except Exception as e:
        log(f"  MCP ERR [{name}]: {e}")
    return None

def load_state():
    if not STATE.exists(): return {"posts": []}
    try: return json.loads(STATE.read_text())
    except: return {"posts": []}

def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))

def organic_in_last_24h(state):
    cutoff = datetime.now() - timedelta(hours=24)
    out = []
    for p in state.get("posts", []):
        try:
            if datetime.fromisoformat(p["ts"]) > cutoff:
                out.append(p)
        except: pass
    return out

def pick_concepts(billboard, recent_posts):
    """Pick 1-2 concepts. Rotates by avoiding ones we used in last 24h.
    Always prefers a top-10 billboard concept primary (for billboard bonus eligibility)."""
    if not billboard: return []
    by_clout = sorted(billboard, key=lambda c: c.get("bounty_clout", 0), reverse=True)
    top10 = by_clout[:10]
    if not top10: return []

    used_recent = set()
    for p in recent_posts:
        used_recent.update(p.get("conceptIds", []))

    fresh_top = [c for c in top10 if c.get("shortId") not in used_recent]
    primary_pool = fresh_top if fresh_top else top10
    primary = random.choice(primary_pool)
    primary_id = primary.get("shortId")
    if not primary_id: return []

    # Optional secondary: a cheap concept different from primary, varied each cycle
    cheap_extras = [c for c in billboard
                    if c.get("shortId") and c.get("shortId") != primary_id
                    and c.get("price", 999) <= 2
                    and c.get("shortId") not in used_recent]
    if not cheap_extras:
        cheap_extras = [c for c in billboard
                        if c.get("shortId") and c.get("shortId") != primary_id
                        and c.get("price", 999) <= 2]
    chosen = [primary_id]
    if cheap_extras:
        secondary = random.choice(cheap_extras[:20])
        sid = secondary.get("shortId")
        if sid and sid != primary_id:
            chosen.append(sid)
    return chosen

def main():
    log("=" * 50)
    log("Organic Post START")

    status = mcp("agent.sessionStatus")
    if not status:
        log("  No sessionStatus -- aborting")
        log("Organic Post DONE")
        log("=" * 50 + "\n")
        return

    player = status.get("player", {}) if isinstance(status, dict) else {}
    clout = player.get("clout", {}).get("totalAvailable", 0)
    dp = player.get("dailyPosts", {})
    posted = dp.get("postedLast24h", 0)
    limit = dp.get("limit", 12)
    remaining = max(0, limit - posted)

    log(f"  Clout: {clout}c | Posts last 24h: {posted}/{limit} ({remaining} free)")

    if clout < MIN_CLOUT:
        log(f"  Clout below {MIN_CLOUT}c floor -- skipping")
        log("Organic Post DONE"); log("=" * 50 + "\n"); return
    if remaining <= RESERVE_FOR_OTHER:
        log(f"  Only {remaining} slots free; keeping >= {RESERVE_FOR_OTHER} for bounties -- skipping")
        log("Organic Post DONE"); log("=" * 50 + "\n"); return

    state = load_state()
    recent = organic_in_last_24h(state)
    if len(recent) >= DAILY_ORGANIC_MAX:
        log(f"  Already posted {len(recent)} organic in last 24h (cap {DAILY_ORGANIC_MAX}) -- skipping")
        log("Organic Post DONE"); log("=" * 50 + "\n"); return

    billboard_raw = mcp("bounties.listBillboardConcepts")
    if isinstance(billboard_raw, dict):
        billboard = billboard_raw.get("concepts") or billboard_raw.get("billboard") or []
    else:
        billboard = billboard_raw or []
    if not billboard:
        log("  No billboard concepts available -- skipping")
        log("Organic Post DONE"); log("=" * 50 + "\n"); return

    posted_this_run = 0
    for _ in range(PER_CYCLE_MAX):
        concept_ids = pick_concepts(billboard, recent)
        if not concept_ids:
            log("  No concepts could be selected -- aborting")
            break
        log(f"  Concepts: {concept_ids}")

        completion = mcp("create.text", {"conceptShortIds": concept_ids, "mediaShortIds": []})
        if not completion:
            log("  create.text failed -- aborting")
            break
        cid = completion.get("shortId") or completion.get("textCompletionShortId") if isinstance(completion, dict) else None
        if not cid:
            log(f"  No completion shortId in response: {completion}")
            break

        post = mcp("create.post", {
            "textCompletionShortId": cid,
            "mediaShortIds": []
        })
        if not post or not isinstance(post, dict):
            log(f"  create.post failed: {post}")
            break
        # Response wraps the post under "newPost" with snake_case short_id
        inner = post.get("newPost") if isinstance(post.get("newPost"), dict) else post
        post_id = inner.get("shortId") or inner.get("short_id")
        if not post_id:
            log(f"  No post shortId in response: {post}")
            break

        # Self-like = early engagement signal (per strategy.md)
        mcp("posts.likePost", {"shortId": post_id, "active": True})
        log(f"  Published {post_id} (concepts: {concept_ids}, self-liked)")

        state.setdefault("posts", []).append({
            "ts": datetime.now().isoformat(),
            "postId": post_id,
            "conceptIds": concept_ids,
        })
        # Trim entries older than 2 days
        state["posts"] = [p for p in state["posts"]
                          if (lambda t:
                              True if not t else datetime.fromisoformat(t) > datetime.now() - timedelta(days=2)
                          )(p.get("ts"))]
        save_state(state)
        recent = organic_in_last_24h(state)
        posted_this_run += 1
        if len(recent) >= DAILY_ORGANIC_MAX:
            log("  Hit internal daily cap")
            break

    log(f"  Posted: {posted_this_run} organic this cycle")
    log("Organic Post DONE")
    log("=" * 50 + "\n")

if __name__ == "__main__":
    main()
