name: SELF Portrait
on:
  push:
    branches: [main]
    paths:
      - "SELF/portrait-request.txt"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  respond:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests

      - name: Generate portrait
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python SELF/scripts/self_portrait.py

      - name: Commit response
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name "museum-bot"
          git config user.email "museum-bot@users.noreply.github.com"
          git add SELF/portrait-response.txt
          git add SELF/portrait-history.json
          git add museum-state.json
          git add journey/
          git diff --staged --quiet || git commit -m "SELF: portrait generated"
          git pull --rebase -X theirs https://x-access-token:${GITHUB_TOKEN}@github.com/${{ github.repository }}.git
          git push https://x-access-token:${GITHUB_TOKEN}@github.com/${{ github.repository }}.git
