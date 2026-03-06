# How to add sources (so you get real, varied updates)

You get the **same** findings every run because the pipeline keeps crawling the **same** URLs. Add your own sources in one of two ways.

---

## Option 1: Add sources in the UI (easiest)

1. Open the app and go to **Sources** in the nav.
2. Click **+ Add source**.
3. Fill in:
   - **URL** – e.g. `https://openai.com/blog` or `https://www.anthropic.com/news`
   - **Name** (optional) – e.g. `OpenAI Blog`
   - **Agent** – choose:
     - **Competitors** – product blogs, changelog pages
     - **Model providers** – provider blogs (OpenAI, Anthropic, Google AI, etc.)
     - **Research** – lab blogs, research articles (added to curated list; arXiv is separate)
4. Click **Save source**.
5. Trigger a run (**Dashboard → Run now**). The pipeline will use YAML config **and** all sources you added in the UI.

Sources you add here are merged into the config for every run. Only **enabled** sources are used.

---

## Option 2: Edit the config file

1. Open `backend/config/radar.yaml`.
2. Under `agents`, add or edit entries.

**Competitors** (product/changelog URLs):

```yaml
agents:
  competitors:
    - name: OpenAI
      release_urls:
        - https://openai.com/blog
      rss_feeds: []
      keywords: [release, model, API, GPT]
```

**Model providers** (provider news/docs):

```yaml
  model_providers:
    - name: Anthropic
      urls:
        - https://www.anthropic.com/news
      rss_feeds: []
      focus: [models, api, safety]
```

**Research** (curated article URLs; arXiv is separate):

```yaml
  research:
    disable_arxiv: false
    curated_urls:
      - https://blog.research.google
```

3. Save the file and run the pipeline again (Dashboard → **Run now**).

---

## Tips

- **RSS feeds**: For competitors or model_providers, if the site has an RSS feed, add it to `rss_feeds` in YAML (the UI currently adds a single URL per source; RSS can be added in YAML).
- **Fewer arXiv papers**: In `config/radar.yaml` under `research`, set `disable_arxiv: true` to get only your configured URLs (and no arXiv).
- **Run from backend**: Ensure the server is started from the `backend` directory (or set `CONFIG_PATH` in `.env`) so `config/radar.yaml` is found.
