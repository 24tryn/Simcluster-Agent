#!/usr/bin/env python3
"""
Daily Report - mubz.24

Runs at the top of every cycle. Self-gates: only generates a report when the
UTC date has rolled over since the last report. Aggregates yesterday's activity
from the daemon logs and appends a section to `daily_report.md`.
"""
import json, re, subprocess, hashlib
from datetime import datetime, timedelta, timezone
import pathlib, os
from collections import defaultdict

BASE       = pathlib.Path(os.environ.get("SIMCLUSTER_DIR", str(pathlib.Path(__file__).resolve().parent)))
TOKEN      = os.environ.get("SIMCLUSTER_BEARER") or (BASE / "bearer.txt").read_text().strip()
SKILL_HASH = hashlib.sha256(open(str(BASE / "skill.md"), "rb").read()).hexdigest()
SKILL_ACK  = "prevent.trap.length.horse"

REPORT     = BASE / "daily_report.md"
STATE      = BASE / "daily_report_state.json"
LOG        = BASE / "daily_report.log"

CLOUTBOMB_LOG = BASE / "cloutbomb_daemon.log"
ORGANIC_LOG   = BASE / "organic_post.log"
BOUNTY_LOG    = BASE / "bounty_daemon.log"

LINE_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\]")

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
    if not STATE.exists(): return {}
    try: return json.loads(STATE.read_text())
    except: return {}

def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))

def lines_for_date(path, target_date_str):
    """Return log lines whose timestamp matches the target date (YYYY-MM-DD)."""
    if not path.exists(): return []
    out = []
    for line in path.read_text(errors="ignore").splitlines():
        m = LINE_TS_RE.match(line)
        if m and m.group(1) == target_date_str:
            out.append(line)
    return out

def summarize_cloutbomb(lines):
    """Count feed likes, users bombed, and total likes given via cloutbomb."""
    feed_likes = 0
    users = []
    total_likes = 0
    re_feed = re.compile(r"Liked (\d+) feed posts")
    re_bomb = re.compile(r"Cloutbombed @(\S+):\s*(\d+) likes")
    for ln in lines:
        m = re_feed.search(ln)
        if m: feed_likes += int(m.group(1))
        m = re_bomb.search(ln)
        if m:
            users.append(m.group(1))
            total_likes += int(m.group(2))
    return {
        "feed_likes": feed_likes,
        "users_bombed": users,
        "bomb_likes": total_likes,
    }

def summarize_organic(lines):
    re_pub = re.compile(r"Published (\S+) \(concepts: (\[[^\]]*\])")
    posts = []
    for ln in lines:
        m = re_pub.search(ln)
        if m:
            try:
                concept_ids = json.loads(m.group(2).replace("'", '"'))
            except Exception:
                concept_ids = []
            posts.append({"id": m.group(1), "concepts": concept_ids})
    return posts

def summarize_bounty(lines):
    re_sub = re.compile(r"Submitted bounty (\S+).*reward:\s*(\d+)c.*net:\s*\+?(-?\d+)c")
    re_found = re.compile(r"Profitable bounties found:\s*(\d+)")
    runs = 0
    submissions = []
    profitable_total = 0
    for ln in lines:
        if "Bounty Hunt START" in ln:
            runs += 1
        m = re_sub.search(ln)
        if m:
            submissions.append({
                "id": m.group(1),
                "reward": int(m.group(2)),
                "net": int(m.group(3)),
            })
        m = re_found.search(ln)
        if m:
            profitable_total += int(m.group(1))
    return {
        "runs": runs,
        "submissions": submissions,
        "profitable_seen": profitable_total,
    }

def render_report(yesterday_str, cb, org, bt, live):
    lines = []
    lines.append(f"\n## {yesterday_str} (UTC)\n")
    lines.append(f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_\n")

    # Live snapshot
    if live:
        player = live.get("player", {}) if isinstance(live, dict) else {}
        clout = player.get("clout", {}).get("totalAvailable", "?")
        spend = player.get("dailySpend", {})
        posts = player.get("dailyPosts", {})
        social = player.get("social", {})
        lb = player.get("leaderboard", {})
        lines.append("### Snapshot at report time")
        lines.append(f"- Clout: **{clout}c**")
        lines.append(f"- Daily spend: {spend.get('spentToday','?')} / {spend.get('limit','?')}c")
        lines.append(f"- Posts last 24h: {posts.get('postedLast24h','?')} / {posts.get('limit','?')}")
        lines.append(f"- Followers: {social.get('followers','?')} | Following: {social.get('following','?')}")
        lines.append(f"- Leaderboard rank: #{lb.get('rank','?')}")
        lines.append("")

    # Cloutbomb
    lines.append("### Cloutbomb")
    lines.append(f"- Feed likes given: **{cb['feed_likes']}**")
    lines.append(f"- Users cloutbombed: **{len(cb['users_bombed'])}** ({cb['bomb_likes']} likes)")
    if cb["users_bombed"]:
        joined = ", ".join(f"@{u}" for u in cb["users_bombed"])
        lines.append(f"  - {joined}")
    lines.append("")

    # Organic
    lines.append("### Organic posts")
    lines.append(f"- Published: **{len(org)}**")
    for p in org:
        lines.append(f"  - `{p['id']}` concepts: {p['concepts']}")
    lines.append("")

    # Bounty
    lines.append("### Bounty hunt")
    lines.append(f"- Runs: {bt['runs']}")
    lines.append(f"- Profitable bounties seen (sum across runs): {bt['profitable_seen']}")
    lines.append(f"- Submissions: **{len(bt['submissions'])}**")
    for s in bt["submissions"]:
        lines.append(f"  - `{s['id']}` reward {s['reward']}c, net +{s['net']}c")
    lines.append("")

    # Manual reminder
    lines.append("### Manual claims (you must do these)")
    lines.append("- Sign-in streak, Billboard streak, Balenciaga at https://simcluster.ai/bonuses")
    lines.append("")
    return "\n".join(lines)

def main():
    today_utc = datetime.now(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)
    yesterday_str = yesterday_utc.isoformat()

    state = load_state()
    last = state.get("last_report_date")
    if last == yesterday_str:
        # Already reported for yesterday -- nothing to do
        return

    log(f"Generating daily report for {yesterday_str}")

    cb = summarize_cloutbomb(lines_for_date(CLOUTBOMB_LOG, yesterday_str))
    org = summarize_organic(lines_for_date(ORGANIC_LOG, yesterday_str))
    bt = summarize_bounty(lines_for_date(BOUNTY_LOG, yesterday_str))

    # Skip writing an empty report on the very first run (no logs from yesterday)
    if not (cb["feed_likes"] or cb["users_bombed"] or org or bt["runs"]):
        log("  No activity recorded for yesterday -- skipping report (first run)")
        state["last_report_date"] = yesterday_str
        save_state(state)
        return

    live = mcp("agent.sessionStatus")
    body = render_report(yesterday_str, cb, org, bt, live)

    # Prepend latest report to the top of the file (newest first), keep history below.
    header = "# Simcluster Daily Reports\n\n_Newest first._\n"
    existing = ""
    if REPORT.exists():
        text = REPORT.read_text()
        # Strip existing header if present so we don't duplicate it
        if text.startswith(header):
            existing = text[len(header):]
        else:
            existing = text
    REPORT.write_text(header + body + existing)

    state["last_report_date"] = yesterday_str
    save_state(state)
    log(f"  Report appended for {yesterday_str}")

if __name__ == "__main__":
    main()
