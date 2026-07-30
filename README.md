# Consciousness feed fix

## Upload these files
- `index.html` to the repo root
- `generate-feed.py` to the repo root
- `feed.json` to the repo root
- `.github/workflows/update-feed.yml`

## What happens
`index.html` reads `feed.json`.

`generate-feed.py` runs on GitHub Actions every hour, fetches arXiv Atom feeds, and rewrites `feed.json`.

## Why this is more reliable
The browser no longer depends on an external feed proxy. GitHub Actions does the fetching server-side, then GitHub Pages serves the finished static file.

## After upload
1. Commit the files.
2. Open the **Actions** tab and confirm the workflow runs.
3. Open `https://tasselrex.github.io/AIResearchFeed/feed.json`.
4. If it updates, your widget page will show live items on the next refresh.
