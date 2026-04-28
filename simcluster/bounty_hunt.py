#!/usr/bin/env python3
"""
Bounty Hunt Daemon - mubz.24
Run every session start
Only submits bounties where net profit > 0
"""
import json, re, subprocess, hashlib
from datetime import datetime
import pathlib
from pathlib import Path

import os
BASE       = pathlib.Path(os.environ.get("SIMCLUSTER_DIR", str(pathlib.Path(__file__).resolve().parent)))
TOKEN      = os.environ.get("SIMCLUSTER_BEARER") or (BASE / "bearer.txt").read_text().strip()
SKILL_HASH = hashlib.sha256(open(str(BASE / "skill.md"), "rb").read()).hexdigest()
SKILL_ACK  = "prevent.trap.length.horse"
LOG        = BASE / "bounty_daemon.log"

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

def get_post_slots_remaining():
    status = mcp("agent.sessionStatus")
    if not status: return 0
    dp = status.get("dailyPosts", {})
    limit = dp.get("limit", 12)
    posted = dp.get("postedLast24h", 0)
    return max(0, limit - posted)

def get_cheapest_filler():
    concepts = mcp("bounties.listBillboardConcepts")
    if not concepts: return None
    items = concepts if isinstance(concepts, list) else concepts.get("concepts", [])
    cheap = [c for c in items if c.get("price", 999) <= 1]
    return cheap[0]["shortId"] if cheap else None

def submit_bounty(bounty, filler_concept_id):
    bounty_id    = bounty.get("bountyShortId", bounty.get("shortId", ""))
    req_concepts = bounty.get("requiredConceptShortIds", [])
    concept_ids  = list(set(req_concepts + [filler_concept_id]))

    completion = mcp("create.text", {"conceptShortIds": concept_ids, "mediaShortIds": []})
    if not completion:
        log(f"  Failed to create completion for bounty {bounty_id}")
        return False

    completion_id = completion.get("shortId") or completion.get("textCompletionShortId")
    if not completion_id:
        log(f"  No completionShortId returned")
        return False

    post = mcp("create.post", {
        "textCompletionShortId": completion_id,
        "mediaShortIds": [],
        "bountyShortId": bounty_id
    })
    if not post:
        log(f"  Failed to publish post for bounty {bounty_id}")
        return False

    post_id = post.get("shortId")
    if post_id:
        mcp("posts.likePost", {"shortId": post_id, "active": True})
        log(f"  Liked own post {post_id}")

    log(f"  Submitted bounty {bounty_id} | reward: {bounty.get('rewardPerCreation',0)}c | net: +{bounty.get('_net',0)}c")
    return True

def main():
    log("=" * 50)
    log("Bounty Hunt START")

    slots = get_post_slots_remaining()
    log(f"  Post slots remaining: {slots}/12")
    if slots == 0:
        log("  No slots -- skipping bounties")
        return

    filler = get_cheapest_filler()
    if not filler:
        log("  No filler concept found")
        return
    log(f"  Filler concept: {filler}")

    raw_bounties = mcp("user-bounties.listActiveRewards")
    bounties = raw_bounties if isinstance(raw_bounties, list) else (raw_bounties or {}).get("bounties", [])

    profitable = []
    for b in bounties:
        if b.get("targetMedium") not in ["text", "any"]: continue
        if b.get("userHasSubmitted"): continue
        req = b.get("requiredConceptShortIds", [])
        concept_cost = len(req) + 1
        net = b.get("rewardPerCreation", 0) - concept_cost
        if net > 0:
            b["_net"] = net
            profitable.append((net, b))

    profitable.sort(key=lambda x: x[0], reverse=True)
    log(f"  Profitable bounties found: {len(profitable)}")

    submitted = 0
    for net, bounty in profitable:
        if submitted >= slots:
            break
        if submit_bounty(bounty, filler):
            submitted += 1

    log(f"  Submitted: {submitted} bounties")
    log("Bounty Hunt DONE")
    log("=" * 50 + "\n")

if __name__ == "__main__":
    main()
