# Project: Simcluster Daemons for mubz.24

## User
- Username: mubz.24 (@24Tryn)
- charShortId: kEx2X9oq
- Email: savageadedoja@gmail.com
- Subscription: Delta tier

## Architecture
- All Simcluster files live in `/home/runner/workspace/simcluster/` (project tree, persists)
- Bearer token in Replit Secret `SIMCLUSTER_BEARER` (do NOT commit, do NOT display)
- MCP endpoint: https://simcluster.ai/mcp
- Required headers: `X-Simcluster-Skill-Hash` (sha256 of skill.md) + `X-Simcluster-Skill-Ack: prevent.trap.length.horse` (rotated 2026-04-28; phrase is hidden inside skill.md prose under "How to read your local files")
- Daily post cap is 12/day rolling 24h (NOT 5 — strategy.md is stale on this point)
- Posting strategy decision (2026-04-29): user picked **Hybrid (option 2)** — bounty-first, then organic posts with rotated concepts. Strategy.md's fixed tante-ernieee + ThinTallTosin loop is intentionally NOT used (would trigger skill.md "Be your own agent" anti-farming rule).
- Workflow `Simcluster Daemons` runs `bash simcluster/loop.sh` continuously
- Cycle: cloutbomb every 90 min; bounty_hunt every 4th cycle (~6h); organic_post every cycle (with internal cap)

## Files
- `simcluster/strategy.md` — USER'S strategy file, NEVER ALTER
- `simcluster/skill.md`, `agent.md` — re-fetchable from https://simcluster.ai/skill.md and /agent.md
- `simcluster/cloutbomb.py` — patched: YOUR_CHAR=kEx2X9oq, agent.readFeed→posts.getForYouFeed
- `simcluster/bounty_hunt.py` — patched: create.textCompletion→create.text; create.post response unwrapped from `newPost.short_id`
- `simcluster/organic_post.py` — hybrid daemon: rotates billboard top-10 concepts; PER_CYCLE_MAX=1, DAILY_ORGANIC_MAX=8, RESERVE_FOR_OTHER=2 free slots, MIN_CLOUT=100¢
- `simcluster/organic_state.json` — rolling 48h record of organic posts (for rotation + cap)
- `simcluster/cloutbomb_log.md` — cooldown roster (5-day)
- `simcluster/loop.sh` — daemon loop runner
- `simcluster/daily_report.py` — self-gating end-of-UTC-day rollup; appends to `daily_report.md` (newest first); state in `daily_report_state.json`

## Known MCP response quirks
- `create.post` returns `{newPost: {short_id, ...}}` — must unwrap and read `short_id` (snake_case). Both organic_post.py and bounty_hunt.py handle this.

## User preferences
- **Always give a session overview + current stats at the end of every session** (clout balance, posts used, daily spend, leaderboard rank, followers, what was cloutbombed/posted this session)
- Manual daily tasks (no API): claim sign-in streak, billboard streak, balenciaga at simcluster.ai/bonuses around 18:52 UTC

## Two API fixes baked into scripts (strategy untouched)
1. `agent.readFeed` returns plaintext that crashed the parser → swapped for `posts.getForYouFeed`
2. `create.textCompletion` doesn't exist on live MCP → renamed to `create.text`
