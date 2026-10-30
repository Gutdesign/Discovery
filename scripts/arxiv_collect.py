"""arXiv paper collector for topics in knowledge/papers/topics.json.

  py scripts/arxiv_collect.py fetch [--topic SLUG] [--since YYYY-MM-DD] [--max N] [--dry-run]
      query the public arXiv API, append new papers to papers.csv, write a digest of what was added
  py scripts/arxiv_collect.py merge --topic SLUG [--source alphaxiv] ID [ID ...]
      add papers found elsewhere (e.g. alphaXiv MCP) by arXiv id; metadata is pulled from arXiv
  py scripts/arxiv_collect.py ids --topic SLUG [--added YYYY-MM-DD] [--source alphaxiv]
      print arXiv ids added on/after the date (default today) — for saving to alphaXiv folders
  py scripts/arxiv_collect.py folder --topic SLUG [--id UUID]
      show or remember the alphaXiv folder_id of a topic (kept in .state.json)
  py scripts/arxiv_collect.py build
      regenerate knowledge/papers/papers.md from papers.csv
  py scripts/arxiv_collect.py stats

Storage: knowledge/papers/papers.csv (';'-delimited, UTF-8 with BOM, like registry.csv),
.state.json keeps the last fetched date per topic so runs are incremental.
arXiv API terms: no key, at most 1 request per 3 seconds.
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "knowledge" / "papers"
TOPICS_PATH = DIR / "topics.json"
CSV_PATH = DIR / "papers.csv"
MD_PATH = DIR / "papers.md"
STATE_PATH = DIR / ".state.json"
DIGEST_DIR = DIR / "digests"

API = "https://export.arxiv.org/api/query"
PAGE = 200
DELAY = 3.1
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "os": "http://a9.com/-/spec/opensearch/1.1/"}

COLUMNS = ["arxiv_id", "название", "авторы", "дата_публикации", "дата_обновления", "категория",
           "темы", "аннотация", "ссылка", "pdf", "источник", "добавлено"]

_last_call = 0.0


def read_rows():
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write_rows(rows):
    rows.sort(key=lambda r: r["дата_публикации"], reverse=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def load_topics():
    return json.loads(TOPICS_PATH.read_text(encoding="utf-8"))["topics"]


def load_state():
    return json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}


def base_id(raw):
    """'http://arxiv.org/abs/2401.01234v2' -> '2401.01234'."""
    raw = raw.rsplit("/abs/", 1)[-1]
    return re.sub(r"v\d+$", "", raw)


def or_group(field_terms):
    return "(" + " OR ".join(field_terms) + ")"


def phrase(term):
    term = term.replace('"', "")
    return f'"{term}"' if " " in term or "-" in term else term


def build_query(topic, since, until):
    q = [or_group([f"{f}:{phrase(t)}" for t in topic["terms"] for f in ("ti", "abs")])]
    if topic.get("require"):
        q.append(or_group([f"{f}:{phrase(t)}" for t in topic["require"] for f in ("ti", "abs")]))
    if topic.get("cats"):
        q.append(or_group([f"cat:{c}" for c in topic["cats"]]))
    q.append(f"submittedDate:[{since:%Y%m%d}0000 TO {until:%Y%m%d}2359]")
    return " AND ".join(q)


def call(params):
    global _last_call
    url = API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for attempt in range(5):
        wait = DELAY - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return ET.fromstring(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  arXiv: {e}; повтор {attempt + 1}/5", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise SystemExit("arXiv API не отвечает")


def text(el, path):
    found = el.find(path, NS)
    return " ".join(found.text.split()) if found is not None and found.text else ""


def parse_entry(e):
    links = {l.get("title") or l.get("rel"): l.get("href") for l in e.findall("a:link", NS)}
    prim = e.find("arxiv:primary_category", NS)
    aid = base_id(text(e, "a:id"))
    return {
        "arxiv_id": aid,
        "название": text(e, "a:title"),
        "авторы": ", ".join(text(a, "a:name") for a in e.findall("a:author", NS)),
        "дата_публикации": text(e, "a:published")[:10],
        "дата_обновления": text(e, "a:updated")[:10],
        "категория": prim.get("term") if prim is not None else "",
        "аннотация": text(e, "a:summary"),
        "ссылка": f"https://arxiv.org/abs/{aid}",
        "pdf": links.get("pdf", f"https://arxiv.org/pdf/{aid}"),
    }


def search(query, limit):
    out, start, total = [], 0, None
    while start < min(limit, total if total is not None else limit):
        root = call({"search_query": query, "start": start, "max_results": min(PAGE, limit - start),
                     "sortBy": "submittedDate", "sortOrder": "descending"})
        total = int(text(root, "os:totalResults") or 0)
        entries = root.findall("a:entry", NS)
        if not entries:
            # arXiv sometimes returns an empty page mid-way; one retry, then stop
            root = call({"search_query": query, "start": start, "max_results": min(PAGE, limit - start),
                         "sortBy": "submittedDate", "sortOrder": "descending"})
            entries = root.findall("a:entry", NS)
            if not entries:
                break
        out += [parse_entry(e) for e in entries if text(e, "a:id")]
        start += len(entries)
    return out, total or 0


def by_ids(ids):
    out = []
    for i in range(0, len(ids), 100):
        root = call({"id_list": ",".join(ids[i:i + 100]), "max_results": 100})
        out += [parse_entry(e) for e in root.findall("a:entry", NS) if text(e, "a:title") != "Error"]
    return out


def add(rows, found, slug, source):
    """Merge found papers into rows; return list of newly added rows."""
    index = {r["arxiv_id"]: r for r in rows}
    today = date.today().isoformat()
    new = []
    for p in found:
        r = index.get(p["arxiv_id"])
        if r:
            topics = r["темы"].split(", ") if r["темы"] else []
            if slug not in topics:
                r["темы"] = ", ".join(topics + [slug])
            sources = r["источник"].split(", ")
            if source not in sources:
                r["источник"] = ", ".join(sources + [source])
            r["дата_обновления"] = p["дата_обновления"] or r["дата_обновления"]
            continue
        r = {**p, "темы": slug, "источник": source, "добавлено": today}
        rows.append(r)
        index[p["arxiv_id"]] = r
        new.append(r)
    return new


def short(s, n):
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def authors_short(a):
    names = a.split(", ")
    return ", ".join(names[:3]) + (" и др." if len(names) > 3 else "")


def write_digest(new_by_topic, topics):
    DIGEST_DIR.mkdir(exist_ok=True)
    path = DIGEST_DIR / f"{date.today().isoformat()}.md"
    names = {t["slug"]: t["name"] for t in topics}
    lines = [f"# Новые статьи arXiv — {date.today().isoformat()}", ""]
    for slug, new in new_by_topic.items():
        lines += [f"## {names.get(slug, slug)} — {len(new)}", ""]
        for r in sorted(new, key=lambda r: r["дата_публикации"], reverse=True):
            lines += [f"- **[{r['название']}]({r['ссылка']})** — {r['дата_публикации']}, "
                      f"{authors_short(r['авторы'])}, `{r['категория']}`",
                      f"  {short(r['аннотация'], 400)}"]
        lines.append("")
    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        f.write("\n".join(lines if mode == "w" else lines[2:]) + "\n")
    return path


def build(rows=None, topics=None):
    rows = rows if rows is not None else read_rows()
    topics = topics or load_topics()
    lines = ["# Статьи arXiv", "",
             "Сгенерировано `py scripts/arxiv_collect.py build` из `papers.csv` — вручную не править.", ""]
    for t in topics:
        sel = [r for r in rows if t["slug"] in r["темы"].split(", ")]
        sel.sort(key=lambda r: r["дата_публикации"], reverse=True)
        lines += [f"## {t['name']} ({len(sel)})", "", "| дата | статья | авторы | кат. |", "|---|---|---|---|"]
        lines += [f"| {r['дата_публикации']} | [{r['название'].replace('|', '/')}]({r['ссылка']}) | "
                  f"{authors_short(r['авторы'])} | {r['категория']} |" for r in sel]
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def cmd_fetch(args):
    topics = load_topics()
    if args.topic:
        topics = [t for t in topics if t["slug"] == args.topic] or sys.exit(f"нет темы {args.topic}")
    state, rows = load_state(), read_rows()
    until = date.today()
    new_by_topic = {}
    for t in topics:
        since = date.fromisoformat(args.since or state.get(t["slug"]) or t["backfill_from"])
        query = build_query(t, since, until)
        print(f"[{t['slug']}] с {since} по {until}")
        if args.dry_run:
            print(f"  {query}")
            continue
        found, total = search(query, args.max)
        new = add(rows, found, t["slug"], "arxiv_api")
        print(f"  найдено {total}, получено {len(found)}, новых {len(new)}"
              + (f" — упёрлись в --max {args.max}, часть пропущена" if total > len(found) else ""))
        if new:
            new_by_topic[t["slug"]] = new
        # next run re-checks the last day: papers announced late still get picked up
        state[t["slug"]] = until.isoformat()
    if args.dry_run:
        return
    write_rows(rows)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    build(rows, load_topics())
    if new_by_topic:
        print(f"дайджест: {write_digest(new_by_topic, load_topics()).relative_to(ROOT)}")
    print(f"всего в базе: {len(rows)}")


def cmd_merge(args):
    ids = sorted({base_id(i.strip()) for i in args.ids if i.strip()})
    rows = read_rows()
    found = by_ids(ids)
    missing = set(ids) - {p["arxiv_id"] for p in found}
    new = add(rows, found, args.topic, args.source)
    write_rows(rows)
    build(rows)
    if new:
        print(f"дайджест: {write_digest({args.topic: new}, load_topics()).relative_to(ROOT)}")
    print(f"получено {len(found)}, новых {len(new)}" + (f", не найдены на arXiv: {', '.join(sorted(missing))}" if missing else ""))


def cmd_ids(args):
    rows = [r for r in read_rows() if args.topic in r["темы"].split(", ") and r["добавлено"] >= args.added
            and (not args.source or args.source in r["источник"].split(", "))]
    print(" ".join(r["arxiv_id"] for r in rows))


def cmd_folder(args):
    state = load_state()
    folders = state.setdefault("alphaxiv_folders", {})
    if args.id:
        folders[args.topic] = args.id
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(folders.get(args.topic, ""))


def cmd_stats(_):
    rows = read_rows()
    print(f"всего: {len(rows)}")
    for k, v in Counter(t for r in rows for t in r["темы"].split(", ")).most_common():
        print(f"  {k}: {v}")
    months = Counter(r["дата_публикации"][:7] for r in rows)
    for m in sorted(months)[-6:]:
        print(f"  {m}: {months[m]}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--topic")
    f.add_argument("--since", help="YYYY-MM-DD; по умолчанию — из .state.json или backfill_from")
    f.add_argument("--max", type=int, default=1000, help="предел статей на тему за запуск")
    f.add_argument("--dry-run", action="store_true", help="только показать запросы")
    m = sub.add_parser("merge")
    m.add_argument("--topic", required=True)
    m.add_argument("--source", default="alphaxiv")
    m.add_argument("ids", nargs="+")
    i = sub.add_parser("ids")
    i.add_argument("--topic", required=True)
    i.add_argument("--added", default=date.today().isoformat(), help="добавленные в этот день или позже")
    i.add_argument("--source", help="только с этим источником, напр. alphaxiv")
    fo = sub.add_parser("folder")
    fo.add_argument("--topic", required=True)
    fo.add_argument("--id", help="сохранить folder_id alphaXiv для темы; без него — показать")
    sub.add_parser("build")
    sub.add_parser("stats")
    args = p.parse_args()
    {"fetch": cmd_fetch, "merge": cmd_merge, "ids": cmd_ids, "folder": cmd_folder,
     "build": lambda a: build(), "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()
