"""Build a markdown table of own (non-repost) expert LinkedIn posts across batch folders.

Usage: python scripts/linkedin_posts_table.py <out.md> <batch_dir> [<batch_dir> ...]
Each batch_dir holds t5_posts.json and people_filtered.csv (имя;компания;должность;подписчики;linkedin).
"""
import csv
import json
import pathlib
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")


def fmt(x):
    if x.get("postVideo"):
        return "видео"
    if x.get("postImages"):
        return "картинка"
    if x.get("document") or "document" in json.dumps(x.get("contentAttributes") or "").lower():
        return "документ"
    return "текст"


def headline(text):
    first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    first = re.sub(r"\s+", " ", first).replace("|", "/")
    return first[:110] + ("…" if len(first) > 110 else "")


def load(dirs):
    own, people = [], {}
    for d in map(pathlib.Path, dirs):
        ppl = {r["linkedin"].rstrip("/"): r for r in csv.DictReader(open(d / "people_filtered.csv", encoding="utf-8-sig"), delimiter=";")}
        people.update({r["имя"]: r for r in ppl.values()})
        for x in json.load(open(d / "t5_posts.json", encoding="utf-8")):
            p = ppl.get(x["query"]["targetUrl"].rstrip("/"))
            if p and x["author"]["name"] == p["имя"]:
                own.append((x, p))
    return own, people


def main():
    out, dirs = sys.argv[1], sys.argv[2:]
    own, people = load(dirs)

    def per1k(x, p):
        f = int(p["подписчики"]) if p["подписчики"] else 0
        e = x["engagement"]
        return (e.get("likes", 0) + 3 * e.get("comments", 0)) / f * 1000 if f else None

    own.sort(key=lambda t: -t[0]["engagement"].get("likes", 0))
    lines = [f"# Посты экспертов ConTech\n",
             f"Собственные посты (без репостов): {len(own)}, авторов: {len({p['имя'] for _, p in own})}. "
             f"Источник: Apify (`harvestapi/linkedin-profile-posts`, `linkedin-company-employees`). "
             f"«Отдача» = (реакции + 3×комментарии) на 1000 подписчиков. Просмотров у чужих постов нет.\n",
             "## Авторы\n",
             "| Автор | Компания | Должность | Подписчики | Постов | Медиана реакций | Медиана комм. | Медиана отдачи |",
             "|---|---|---|---|---|---|---|---|"]
    by = {}
    for x, p in own:
        by.setdefault(p["имя"], []).append((x, p))
    for name, xs in sorted(by.items(), key=lambda kv: -statistics.median(t[0]["engagement"].get("likes", 0) for t in kv[1])):
        p = {k: (v or "").replace("|", "/") for k, v in xs[0][1].items()}
        sc = [s for s in (per1k(*t) for t in xs) if s is not None]
        med = f"{statistics.median(sc):.1f}" if sc else "н/д"
        lines.append(f"| {name} | {p['компания']} | {p['должность']} | {p['подписчики'] or 'н/д'} | {len(xs)} | "
                     f"{statistics.median(t[0]['engagement'].get('likes', 0) for t in xs):.0f} | "
                     f"{statistics.median(t[0]['engagement'].get('comments', 0) for t in xs):.0f} | {med} |")
    lines += ["\n## Посты (по реакциям)\n",
              "| # | Реакции | Комм. | Репосты | Отдача | Формат | Дата | Автор (компания) | Заголовок (первая строка) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for i, (x, p) in enumerate(own, 1):
        e, s = x["engagement"], per1k(x, p)
        lines.append(f"| {i} | {e.get('likes', 0)} | {e.get('comments', 0)} | {e.get('shares', 0)} | "
                     f"{'н/д' if s is None else f'{s:.1f}'} | {fmt(x)} | {x['postedAt']['date'][:10]} | "
                     f"{p['имя']} ({p['компания']}) | [{headline(x.get('content'))}]({x['linkedinUrl']}) |")
    pathlib.Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(own)} posts, {len(by)} authors -> {out}")


if __name__ == "__main__":
    main()
