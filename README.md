# GitHub Leads Scraper

Single-page tool that streams repository owner emails from the explicit GitHub search queries you supply (one per line). No scoring, no filtering heuristics – every repository returned by GitHub for your queries is processed and any commit/public emails discovered are emitted.

> Email sending / campaign features live in a separate repository.
> Email sender repo: https://github.com/<your-org>/email-sender

## Features
- Explicit queries only (textarea, one GitHub search query per line)
- Streams all repositories returned for each query (up to your specified per‑query cap)
- Live streaming updates (queries_received, query_start, lead_added, progress, finished, no_email, query_empty, error)
- Writes `leads.csv` (also downloadable at /leads.csv)

## Quick Start
```bash
git clone <repository-url>
cd github-email-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "GITHUB_TOKEN=your_token_here" > .env  # optional but recommended
python web_ui/app.py
```
Open http://127.0.0.1:5001 and paste queries (one per line) then Start.

## Example Queries
```
electron stars:>20 in:description
desktop stars:>30
blender addon stars:>15
unity plugin stars:>25
"upgrade" stars:>40 language:typescript
```
Tips:
- Use stars thresholds (stars:>20) to surface active repos
- Add language: or in:description constraints to focus
- Everything returned by GitHub for your queries will stream; refine queries for relevance

## Minimal API
POST /scrape/customers
```json
{
  "token": "<optional PAT>",
  "max_repos_per_query": 30,
  "queries_raw": "electron stars:>20 in:description\ndesktop stars:>30"
}
```
Response is streamed NDJSON (one JSON object per line).

Download final CSV: GET /leads.csv

## Output Columns
email, github_username, name, repository, repo_description, repo_stars, repo_language, company, bio

## Behavior
- No scoring or filtering: every repo returned is inspected
- Commit author emails (excluding obvious generic/noreply) are collected (first valid email per repo owner)
- Falls back to the owner's public profile email if no commit email found
- Duplicate emails are skipped (first occurrence kept)

## Notes
- Provide focused queries; broad queries produce large volumes quickly
- Use a GitHub token to avoid low rate limits
- `leads.csv` is git-ignored (avoid committing emails)

## License
MIT
