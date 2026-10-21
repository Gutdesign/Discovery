"""Build a markdown table of own (non-repost) LinkedIn posts from Apify output.

Usage: python scripts/linkedin_posts_table.py <posts.json> <people.json> <out.md>
"""
import json
import re
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
    return first[:120] + ("…" if len(first) > 120 else "")


def main():
    posts = json.load(open(sys.argv[1], encoding="utf-8"))
    people = {p["linkedinUrl"].rstrip("/"): (f"{p['firstName']} {p['lastName']}", p["currentPositions"][0].get("companyName", ""))
              for p in json.load(open(sys.argv[2], encoding="utf-8"))}
    own = []
    for x in posts:
        name, company = people.get(x["query"]["targetUrl"].rstrip("/"), ("", ""))
        if x["author"]["name"] == name:
            own.append((x, name, company))
    own.sort(key=lambda t: -t[0]["engagement"].get("likes", 0))
    rows = ["| # | Реакции | Комм. | Репосты | Формат | Дата | Автор (компания) | Заголовок (первая строка) |",
            "|---|---|---|---|---|---|---|---|"]
    for i, (x, name, company) in enumerate(own, 1):
        e = x["engagement"]
        rows.append(f"| {i} | {e.get('likes', 0)} | {e.get('comments', 0)} | {e.get('shares', 0)} | {fmt(x)} | "
                    f"{x['postedAt']['date'][:10]} | {name} ({company}) | [{headline(x.get('content'))}]({x['linkedinUrl']}) |")
    head = (f"# Посты экспертов — пилот (5 компаний)\n\nСобственные посты, без репостов: {len(own)}. "
            f"Сортировка по реакциям. Источник: Apify `harvestapi/linkedin-profile-posts`, 2026-10-21.\n"
            f"«Реакции» — все типы реакций (поле `likes`). Просмотров у чужих постов нет.\n\n")
    open(sys.argv[3], "w", encoding="utf-8").write(head + "\n".join(rows) + "\n")
    print(f"{len(own)} rows -> {sys.argv[3]}")


if __name__ == "__main__":
    main()
