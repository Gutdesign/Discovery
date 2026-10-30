---
name: arxiv-collect
description: Collect new arXiv papers on the founder's topics (RAG, multimodal RAG, graph search, AI in AEC/ConTech, RAG x AEC, AEC data formats IFC/DXF/DWG/RVT) via the arXiv API and alphaXiv MCP, merge them into knowledge/papers/, save them to alphaXiv folders, and recommend the 5-10 most important papers to read. Use when asked to collect/update papers or for reading recommendations.
---

# arXiv collection run

Topics and queries: `knowledge/papers/topics.json`. Base: `knowledge/papers/papers.csv`. Recommendation criteria: `knowledge/papers/README.md`. Talk to the founder in Russian. The founder runs this manually (no scheduler).

## 0. Remember the previous dates

Before fetching, read `knowledge/papers/.state.json` and keep each topic's date — it is the `published_after` for alphaXiv. A topic absent from the state is on its first run: use its `backfill_from`. Note the run date (today) — it selects this run's papers below.

## 1. arXiv API (free)

```
py scripts/arxiv_collect.py fetch
```

Incremental. Note the counts per topic; if a topic hits `--max`, say so.

## 2. alphaXiv ranked search

For each topic call `mcp__alphaxiv__discover_papers` with exactly its `alphaxiv.question` and `alphaxiv.keywords`, `prioritize: "recency"`, `difficulty: 5`, `published_after` from step 0.

- alphaXiv allows 2 searches per message: do topics in pairs.
- Search spends the founder's alphaXiv quota. Run only the queries already in `topics.json` (approved). A new or changed query must be shown to the founder and approved first.
- Results come as `[ID=<id>]`. Keep only arXiv ids (`NNNN.NNNNN`), then:

```
py scripts/arxiv_collect.py merge --topic <slug> --source alphaxiv <id> <id> ...
```

## 3. Save to alphaXiv folders

For each topic:

1. `py scripts/arxiv_collect.py folder --topic <slug>` prints the folder_id. If empty: `mcp__alphaxiv__create_folder` with name `arXiv · <topic name>`, then `py scripts/arxiv_collect.py folder --topic <slug> --id <folder_id>`.
2. Ids of this run: `py scripts/arxiv_collect.py ids --topic <slug> --added <run date>`; add `--source alphaxiv` when the topic has `"folder": "alphaxiv"` (RAG — too many papers otherwise).
3. `mcp__alphaxiv__save_papers_to_folder` with that folder_id, at most 50 ids per call. Saving is idempotent.

## 4. Reading recommendations (5–10 papers)

Pick the 5–10 most important papers of this run across all topics, judged by the criteria in `knowledge/papers/README.md` (that section is the founder's — follow it, don't edit it).

1. Candidates: `knowledge/papers/digests/<run date>.md`. Go through every topic section; read abstracts, not only titles. Shortlist ~15–20.
2. For borderline shortlisted papers you may call `mcp__alphaxiv__get_paper_content` (AI report) to check what the paper actually delivers — at most ~5 calls.
3. Final list: no fewer than 5, no more than 10. Fewer is fine if the run is thin — don't pad.
4. Write `knowledge/papers/reading/<run date>.md` in Russian:

```
# Что прочитать — <run date>

Отобрано N из M новых статей. Критерии — knowledge/papers/README.md.

## 1. <название> — <тема>
<arxiv.org link> · <дата> · <источник: arXiv / alphaXiv / оба>
**Почему читать:** 1–2 предложения — что даёт именно нам (связь с гипотезами/картой рынка, если есть).
**Что взять:** метод / набор данных / вывод, который пригодится.
**Оговорка:** ограничения, если видны (маленький набор данных, только синтетика, нет кода).

## Почти попали
- <название> — <ссылка> — одна строка, почему не в основном списке.
```

5. Save the recommended papers to the alphaXiv folder `arXiv · Рекомендации` (create once, remember with `folder --topic reading --id ...`).

## 5. Report and commit

- In chat (Russian): new papers per topic and source; the recommendation list (titles + one line each + link to `reading/<date>.md`); obvious noise worth a query fix in `topics.json` — propose, don't change queries without approval.
- Commit only `knowledge/papers/` (and the script if changed): `knowledge: papers - arXiv update <date>`.

## Deep dive (only when asked)

`mcp__alphaxiv__get_paper_content` for the AI report of a paper; `mcp__alphaxiv__answer_pdf_queries` for specific questions with page citations. If a finding matters for a hypothesis or landscape, write it to `knowledge/` with the arXiv link as source.
