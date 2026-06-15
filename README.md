# The Big Fat Kitty 🐱 — World Cup 2026

A tiny mobile web app that tracks our World Cup betting pool: the pot, who owes what,
each player's live chance of winning, and the next matches.

## How it stays current
A GitHub Action runs a few times a day, pulls the latest results from
[football-data.org](https://www.football-data.org) (free), and rewrites `data.json`.
The page reads `data.json` and recomputes everything:

- **Pot + who owes what** — exact, straight from the betting rules.
- **Win %** — a model from each team's `strength` rating, which rises as a team advances
  and drops to 0 when it's knocked out.
- **Next-match odds** — a model from the two teams' `strength` ratings.

## Files
| File | What it is |
|------|------------|
| `index.html` | the app (open this) |
| `data.json` | all teams, players, results, fixtures — the Action updates this |
| `og.png` | the WhatsApp/link preview card — re-rendered daily |
| `scripts/update.mjs` | the daily fetch-and-recompute script (Node, no dependencies) |
| `scripts/og.py` | renders `og.png` and refreshes the link-preview tags (Python + Pillow) |
| `.github/workflows/update.yml` | the schedule that runs both scripts |

## Sharing to WhatsApp
- **Share button:** the green button at the bottom of the app writes a tidy live
  summary (pot, standings, lightest payer, next match) and opens WhatsApp with it
  pre-filled — one tap to pick the group and send.
- **Link preview:** paste the site link in any chat and WhatsApp shows a card with
  the current pot, leader and standings (that's `og.png`). The share button adds a
  `?d=date` tag to the link each day so the preview refreshes instead of caching.
  The preview image goes fully live after the Action runs once.

## To change things by hand
Edit `data.json`: tweak a team's `strength`, add a player `avatar` (image URL),
or fix a result. The page recomputes on next load.

## Setup
1. Get a free API token at football-data.org.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**,
   name it `FOOTBALL_DATA_TOKEN`, paste the token.
3. **Settings → Pages → Deploy from branch → main → /(root)**.
4. **Actions** tab → run **Update Kitty** once to pull live data.
