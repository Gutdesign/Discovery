# Research Plan

> **Zone:** 2_engine (machine-led, Claude Code generates this)
> **When to fill:** at the start of the engine zone, after the frame zone is complete.
> **Purpose:** make collection reproducible, source choices explicit, and budget bounded.

---

## Mode

<!-- lean: minimize Parallel queries, prefer Apify + web_fetch + web_search.
            Single data collection, dual adversarial read at the interpretation layer.
     full: separate collection passes for pro and skeptic optics. Roughly 2x cost. -->

Mode: lean

## Budget cap

Target: $10
Hard ceiling: $25

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

**Исключение из правила CLAUDE.md «избегать LinkedIn-скраперов»:** основатель прямо попросил Apify для LinkedIn. Выбран актор без cookies и логина, $0.002 за пост — правило про дороговизну и антибот здесь не срабатывает. Риск: сбор публичных данных LinkedIn противоречит пользовательскому соглашению LinkedIn; аккаунт основателя не используется. Реакции/комментарии (персональные данные чужих людей) не собираются.

**Пилот до завершения 1_frame** — по прямой просьбе основателя, только собственный профиль. Задачи по экспертам — после одобрения рамки.

| # | Инструмент | Точный текст задания | Статус |
|---|-----------|----------------------|--------|
| 1 | Apify `harvestapi/linkedin-profile-posts` ($0.002/пост, лимит расходов `maxTotalChargeUsd: 2`) | `{"targetUrls": ["https://www.linkedin.com/in/agutev/"], "maxPosts": 0, "includeReposts": true, "includeQuotePosts": true, "scrapeReactions": false, "scrapeComments": false}` → `2_engine/collection/raw/apify_agutev_posts_2026-10-21.json`. Репосты помечаются отдельно и не идут в рейтинг собственных постов. | на согласовании |
| 2 | Экспорт аналитики LinkedIn (делает основатель вручную, бесплатно) | LinkedIn → Аналитика → Публикации → Экспорт (XLSX, максимальный период) → `2_engine/collection/raw/linkedin_export_agutev.xlsx`. Даёт показы и прирост подписчиков, которых нет в Apify. | ждёт файла от основателя |
| 3 | Apify `harvestapi/linkedin-company` ($0.004/компания, лимит `maxTotalChargeUsd: 1`) | `{"searches": [98 названий из raw/experts_companies_input.csv]}` → `raw/apify_companies_linkedin.json`. Найденная страница принимается, только если сайт на ней совпадает с `сайт` в реестре; несовпадения — в отдельный список на проверку. | на согласовании |
| 4 | Apify `harvestapi/linkedin-company-employees` (короткий профиль $0.003, лимит `maxTotalChargeUsd: 3`) | `{"companies": [LinkedIn-страницы из задачи 3], "companyBatchMode": "one_by_one", "jobTitles": ["CEO", "Founder", "Co-Founder", "Chief Product Officer", "Head of Product", "Product Manager", "Head of AI", "AI Lead", "Chief AI Officer", "Digital Transformation"], "profileScraperMode": "short", "maxItemsPerCompany": 5}` → `raw/apify_experts_people.json`. Список людей показывается основателю до задачи 5. | на согласовании |
| 5 | Apify `harvestapi/linkedin-profile-posts` ($0.002/пост) | Посты людей из задачи 4 за 12 месяцев, `maxPosts` и лимит расходов — после того как основатель увидит список людей (оценка: ≤300 чел. × ≤30 постов → ≤$18). | будет предложено после задачи 4 |

Отбор компаний: из 185 строк реестра — только «список 1 / список 2 / оба списка» (карта стартапов основателя), без «крупный вендор» (7) и без компаний >500 сотрудников (Attentive.ai, VTS, Brick & Bolt). Итог — 98 компаний. Под вопросом: IDOM и Grupo Alava (инжиниринговые группы, размер в реестре н/д, вероятно крупные).

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
