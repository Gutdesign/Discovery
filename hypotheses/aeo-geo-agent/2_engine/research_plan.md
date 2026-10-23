# Research Plan

> **Zone:** 2_engine (machine-led, Claude Code generates this)
> **When to fill:** at the start of the engine zone, after the frame zone is complete.
> **Purpose:** make collection reproducible, source choices explicit, and budget bounded.

---

## Mode

<!-- lean: minimize Parallel queries, prefer Apify + web_fetch + web_search.
            Single data collection, dual adversarial read at the interpretation layer.
     full: separate collection passes for pro and skeptic optics. Roughly 2x cost. -->

Mode: lean | full

## Budget cap

Target: $ 
Hard ceiling: $ 

## Questions to answer

<!-- Pulled directly from 04_devils_advocate.md → "Questions the engine zone MUST answer".
     If a question can't be tied to a source below, the plan is incomplete. -->

1. 
2. 
3. 

---

## Sources by category

### Competitive landscape

| Question | Source | Tool | Estimated cost |
|----------|--------|------|----------------|
|          |        |      |                |

<!-- Examples of source choices:
     - Parallel.ai with structured prompt for direct/indirect/adjacent competitors → $20-40
     - web_fetch on competitor websites for positioning language → free
     - web_search for recent funding announcements → free -->

### Market structure & sizing

| Question | Source | Tool | Estimated cost |
|----------|--------|------|----------------|
|          |        |      |                |

<!-- For B2C / consumer:
     - Parallel.ai for industry analyst reports and regulatory context → $15-30
     - Public market data (statista summaries via search) → free
     - Bottom-up estimation needs proxy data (App Store rankings, community sizes) -->

### Voice of customer & signals

| Question | Source | Tool | Estimated cost |
|----------|--------|------|----------------|
|          |        |      |                |

<!-- For B2C / consumer:
     - Apify Reddit scraper (lookup by subreddit + keyword) → ~$1-5
     - Apify App Store reviews scraper → ~$1-5
     - Product Hunt and Hacker News via web_fetch → free
     - Google Trends data → free

     For professional/B2B audiences:
     - LinkedIn manual searches via web_fetch on specific posts → free
     - Niche forum scraping via Apify → varies
     - Industry-specific community archives via web_fetch → free -->

### Trends, regulatory, technological context

| Question | Source | Tool | Estimated cost |
|----------|--------|------|----------------|
|          |        |      |                |

---

## External tool tasks — for approval before running

<!-- List the exact prompt/query text for every planned Parallel/Apify/Wordstat call,
     BEFORE running it. Show this section to the founder and wait for a go-ahead —
     don't flip status to "выполнено" until they've said yes. Free/local tools
     (web_fetch, web_search) don't need this. -->

| # | Инструмент | Точный текст задания | Статус |
|---|-----------|----------------------|--------|
| 1 |           |                       | на согласовании |

<!-- Статусы: "на согласовании" → "одобрено" → "выполнено". -->

---

## Out of scope

<!-- Explicitly list things that COULD be researched but are intentionally not in this run.
     Naming them protects against scope creep later. -->

- 
- 

---

## Adversarial read configuration

### Lean mode (default)

Single collection pass. Two independent Claude reads over the same corpus:
- `adversarial/supporting.md` — pro reading
- `adversarial/disconfirming.md` — skeptic reading
- `adversarial/symmetry_check.md` — meta-comparison

### Full mode

Each Parallel/Apify query is run twice with mirrored framing. Raw outputs are stored separately. Reads operate on different corpora.

Configuration for THIS hypothesis: 

---

## Re-run conditions

<!-- Conditions under which this research plan would need to be re-executed.
     For example: priors significantly diverge from initial data, new competitor emerges,
     market signal shifts. -->

- 
- 
