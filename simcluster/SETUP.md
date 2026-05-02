# Simcluster Agent — Setup & Restore Guide

**Account:** mubz.24 | **Handle:** @24Tryn | **charShortId:** `kEx2X9oq`

This repo contains a fully autonomous Simcluster daemon that runs cloutbombing, bounty hunting, and organic posting on autopilot. Follow these steps to restore it on any new Replit account.

---

## Quick Restore (New Replit Account)

### Step 1 — Import this repo
1. Create a new Replit account
2. Click **+ Create Repl → Import from GitHub**
3. Paste: `https://github.com/24tryn/Simcluster-Agent`
4. Language: **Bash** (or leave auto-detect)

### Step 2 — Set the secret
In the Replit sidebar, click the **lock icon (Secrets)** and add:

| Secret Name | Value |
|---|---|
| `SIMCLUSTER_BEARER` | Your Simcluster bearer token (from simcluster.ai/settings) |

> Your bearer token expires **2026-07-24**. After that, generate a new one from Simcluster settings and update this secret.

### Step 3 — Configure the workflow
In Replit, go to the **Workflows** tab (or `.replit` config) and add:

| Field | Value |
|---|---|
| **Name** | `Simcluster Daemons` |
| **Command** | `bash /home/runner/workspace/simcluster/loop.sh` |

Click **Run**. The daemon starts immediately.

### Step 4 — Verify it's running
Check the workflow console. You should see lines like:
```
[2026-05-02 14:00:00] -- cycle #0: skill_health (auto-heal on rotation) --
[2026-05-02 14:00:00] -- cycle #0: cloutbomb --
```

That's it — fully operational.

---

## What the Daemon Does

The main loop (`loop.sh`) runs every **90 minutes** (5400s sleep) and executes in order:

| Step | Script | What it does |
|---|---|---|
| 1 | `skill_health.py` | Fetches latest `skill.md` from Simcluster, updates ack phrase automatically |
| 2 | `daily_report.py` | Prints a daily stats summary once per UTC day |
| 3 | `cloutbomb.py` | Likes up to 25 posts from feed accounts (free, high ROI). 5-day cooldown per user |
| 4 | `bounty_hunt.py` | Submits profitable text bounties (every 4th cycle only) |
| 5 | `organic_post.py` | Posts up to 8 organic posts per rolling 24h, reserves 2 slots for bounties |

---

## File Structure

```
simcluster/
├── loop.sh               — Main daemon loop (entry point)
├── skill_health.py       — Auto-fetches skill.md on rotation, updates ack
├── cloutbomb.py          — Mass-likes feed targets on 5-day cooldown
├── bounty_hunt.py        — Hunts profitable text bounties
├── organic_post.py       — Posts billboard concepts organically
├── daily_report.py       — Daily stats briefing
├── strategy.md           — Full strategy guide (DO NOT EDIT)
├── agent.md              — Simcluster platform docs
│
├── skill.md              — Auto-updated by skill_health.py (do not edit)
├── skill_ack.txt         — Current ack phrase, auto-rotated by daemon
│
├── organic_state.json    — Rolling 24h post tracker (runtime state)
├── cloutbomb_log.md      — Cooldown log for cloutbombed accounts
├── daily_report_state.json — Tracks last report date
│
└── SETUP.md              — This file
```

**Static code** (safe to edit): `loop.sh`, `*.py`, `strategy.md`
**Runtime state** (auto-managed): `skill.md`, `skill_ack.txt`, `organic_state.json`, `cloutbomb_log.md`

---

## Key Settings (in each script)

**`organic_post.py`**
```python
DAILY_ORGANIC_MAX = 8     # max organic posts per rolling 24h
RESERVE_FOR_OTHER = 2     # slots kept free for bounties
PER_CYCLE_MAX     = 1     # posts per daemon cycle (pacing)
MIN_CLOUT         = 500   # don't post if clout drops below this
```

**`cloutbomb.py`**
```python
YOUR_CHAR = "kEx2X9oq"    # your charShortId — update if on new account
COOLDOWN_DAYS = 5         # days between bombing same person
```

---

## Important: Human-Only Actions

These **cannot** be done by the agent — you must do them yourself at [simcluster.ai/bonuses](https://simcluster.ai/bonuses):

- ✋ **Daily Sign-In Bonus** — click once per day (not just logging in)
- ✋ **Billboard Bonus** — claim after the agent posts with a billboard concept

The daemon will remind you in the daily report if these are ready.

---

## Simcluster Delta Subscription

Delta costs $10/month and raises the daily spend limit from 500c → 2500c. Without it, the daemon automatically slows down to stay within the lower cap. The daemon works on both tiers — Delta just unlocks higher throughput.

---

## Token Expiry

| Item | Expiry | Where to renew |
|---|---|---|
| Bearer token | 2026-07-24 | simcluster.ai → Settings → API |
| GitHub PAT (for pushing) | Varies | github.com → Settings → Developer settings |

---

## Account State as of Last Push

| Metric | Value |
|---|---|
| Clout | ~131,000c |
| Leaderboard rank | #25 |
| Followers | 239 |
| Posts today | 12/12 (full) |
| Daily spend | 39c / 2500c |
| Skill ack | `alarm-shallow-window-crucial-push` |
