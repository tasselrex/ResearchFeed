# Consciousness feed package

## Files
- `generate-feed.mjs` — fetches arXiv Atom feeds and writes `feed.json`
- `.github/workflows/update-feed.yml` — runs every hour on GitHub Actions
- `feed.json` — starter data so the widget displays immediately

## Upload steps
1. Put `generate-feed.mjs` in the repository root.
2. Put `feed.json` in the repository root.
3. Put `update-feed.yml` in `.github/workflows/`.
4. Commit and push.
5. Enable GitHub Actions if prompted.

## Notes
- The workflow uses UTC cron scheduling.
- The page will keep showing the last generated `feed.json` until the workflow runs again.
