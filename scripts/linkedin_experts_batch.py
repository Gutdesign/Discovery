"""Run the expert-posts pipeline (tasks 3-5) for one batch of registry companies.

Usage: python scripts/linkedin_experts_batch.py <batch_dir> <company name> [<company name> ...]

Writes into <batch_dir>: in_t3/t3_companies.json, company_match.csv,
in_t4/t4_people.json, people_filtered.csv, in_t5/t5_posts.json.
"""
import csv
import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "knowledge" / "companies" / "registry.csv"
RUN = [sys.executable, "-I", str(ROOT / "scripts" / "apify_run.py")]

JOB_TITLES = ["CEO", "Founder", "Co-Founder", "Chief Product Officer", "Head of Product", "Product Manager",
              "Head of AI", "AI Lead", "Chief AI Officer", "Digital Transformation"]
KEEP = re.compile(r"\bceo\b|founder|chief product|product manager|head of product|\bai\b|digital transformation", re.I)
DROP = re.compile(r"investor|marketing|advisor|board member", re.I)
SINCE = "2025-10-21"


def domain(url):
    url = re.sub(r"^https?://", "", (url or "").strip().lower())
    return url.split("/")[0].removeprefix("www.")


def filter_people(people, companies, d):
    """Keep people whose CURRENT position at one of the batch companies has a target title."""
    slugs = {u.rstrip("/").rsplit("/", 1)[-1]: n for n, u in companies.items()}
    keep = []
    for p in people:
        role = next((x for x in p.get("currentPosition") or []
                     if (x.get("companyLinkedinUrl") or "").rstrip("/").rsplit("/", 1)[-1] in slugs
                     or (x.get("companyName") or "").lower().startswith(tuple(n.lower() for n in companies))), None)
        title = (role or {}).get("position") or ""
        if role and KEEP.search(title) and not DROP.search(title):
            p["_company"], p["_title"] = role.get("companyName"), title
            keep.append(p)
    with open(d / "people_filtered.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["имя", "компания", "должность", "подписчики", "linkedin"])
        for p in keep:
            w.writerow([f"{p.get('firstName', '')} {p.get('lastName', '')}", p["_company"], p["_title"],
                        p.get("followerCount", ""), p.get("linkedinUrl")])
    return keep


def run(actor, payload, out, cap, d):
    inp = d / f"in_{out.rsplit('.', 1)[0]}.json"
    inp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run(RUN + [actor, str(inp), str(d / out), str(cap)], check=True)
    return json.loads((d / out).read_text(encoding="utf-8"))


def main():
    d = pathlib.Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:]
    reg = {r["компания"]: r for r in csv.DictReader(open(REGISTRY, encoding="utf-8-sig"), delimiter=";")}

    # Task 3: resolve LinkedIn company pages, accept only if website domain matches the registry.
    # Second pass searches unmatched companies by their registry domain.
    found = run("harvestapi/linkedin-company", {"searches": names}, "t3_companies.json", 0.2 + 0.005 * len(names), d)

    def same(c, n):
        want, got = domain(reg[n]["сайт"]), domain(c.get("website"))
        return bool(want) and bool(got) and (got == want or got.endswith("." + want) or want.endswith("." + got))

    retry = [n for n in names if not any(same(c, n) for c in found) and "." in domain(reg[n]["сайт"])]
    if retry:
        found += run("harvestapi/linkedin-company", {"searches": [domain(reg[n]["сайт"]) for n in retry]},
                     "t3_companies_retry.json", 0.2 + 0.005 * len(retry), d)
    # Third pass: guess company page slugs from the domain and the name.
    retry = [n for n in names if not any(same(c, n) for c in found) and "." in domain(reg[n]["сайт"])]
    if retry:
        slugs = set()
        for n in retry:
            dom = domain(reg[n]["сайт"])
            stem = dom.split(".")[0]
            slugs |= {stem, dom.replace(".", "-"), dom.replace(".", ""), re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-"),
                      f"{stem}-{dom.split('.')[-1]}", f"{stem}hq", f"{stem}-hq", f"{stem}-inc"}
        found += run("harvestapi/linkedin-company",
                     {"companies": [f"https://www.linkedin.com/company/{s}/" for s in sorted(slugs)]},
                     "t3_companies_slugs.json", 0.2 + 0.005 * len(slugs), d)
    matched, rows = [], []
    for n in names:
        want = domain(reg[n]["сайт"])
        hit = next((c for c in found if same(c, n)), None) or next(
            (c for c in found if (c.get("originalQuery") or {}).get("search") == n), None)
        got = domain(hit.get("website")) if hit else ""
        ok = bool(hit) and same(hit, n)
        rows.append({"компания": n, "сайт_реестр": want, "linkedin": hit.get("linkedinUrl") if hit else "",
                     "сайт_linkedin": got, "совпадение": "да" if ok else "нет"})
        if ok:
            matched.append((n, hit["linkedinUrl"]))
    with open(d / "company_match.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"task 3: {len(matched)}/{len(names)} matched")
    if not matched:
        sys.exit("no companies matched; see company_match.csv")

    # Task 4: role holders, full profile (for follower counts).
    people = run("harvestapi/linkedin-company-employees", {
        "companies": [u for _, u in matched], "companyBatchMode": "one_by_one", "jobTitles": JOB_TITLES,
        "profileScraperMode": "Full ($8 per 1k)", "maxItemsPerCompany": 5, "maxItems": 6 * len(matched)},
        "t4_people.json", 0.2 + 0.05 * len(matched), d)
    keep = filter_people(people, dict(matched), d)
    print(f"task 4: {len(people)} people, {len(keep)} after title filter")
    if not keep:
        sys.exit("no people after filter; inspect t4_people.json field names")

    task5(d, [p["linkedinUrl"] for p in keep])


def task5(d, targets, start=0):
    """Posts for the last 12 months, no reactions/comments of other people.
    The actor sometimes drops targets with "Too many queued requests"; those are retried in small runs."""
    out = d / "t5_posts.json"
    posts = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    for attempt in range(start, start + 3):
        done = {x["query"]["targetUrl"].rstrip("/") for x in posts}
        todo = [u for u in targets if u.rstrip("/") not in done]
        if not todo:
            break
        chunk = 5 if attempt else len(todo)
        for i in range(0, len(todo), chunk):
            part = todo[i:i + chunk]
            posts += run("harvestapi/linkedin-profile-posts", {
                "targetUrls": part, "maxPosts": 30, "postedLimitDate": SINCE,
                "includeReposts": True, "includeQuotePosts": True, "scrapeReactions": False, "scrapeComments": False},
                f"t5_part_{attempt}_{i}.json", 0.2 + 0.07 * len(part), d)
    out.write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = [u for u in targets if u.rstrip("/") not in {x["query"]["targetUrl"].rstrip("/") for x in posts}]
    (d / "t5_no_posts.txt").write_text("\n".join(missing), encoding="utf-8")
    print(f"task 5: {len(posts)} items, {len(missing)} targets without posts (no posts in 12 months or failed)")


if __name__ == "__main__":
    main()
