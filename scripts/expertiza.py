"""Expertise registry (реестр заключений экспертизы) processor.

  python scripts/expertiza.py extract [SRC.csv] stage 1: parse the big export once into data/expertiza/slim.csv
  python scripts/expertiza.py build [SRC.csv]   stage 2: classify from slim.csv (re-extracts if SRC is newer)
  python scripts/expertiza.py site DIR          static dashboard (expertiza_site.html + CSVs) for GitHub Pages

Input: the public registry export (';'-delimited, UTF-8 with BOM), default
data/Реестр (общедоступные сведения).csv. Unit of counting = one conclusion; year = conclusion date.

Outputs (data/expertiza/, ';'-delimited, UTF-8 with BOM):
  rows.csv              every conclusion with derived columns (вид, площадной/линейный, тип, орг-ключи)
  genproektirovshiki.csv, zakazchiki.csv   org lists for the dashboard scope (площадные, без капремонта)
  dashboard/*.csv       aggregates for the interactive dashboard (facts, org_facts, orgs, dims)
"""
import csv
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "Реестр (общедоступные сведения).csv"
OUT = ROOT / "data" / "expertiza"
csv.field_size_limit(10**9)

# column indexes in the registry export
C_ID, C_NUM, C_DATE, C_RES, C_FORM, C_OBJ, C_REG = 0, 1, 2, 3, 4, 5, 6
C_NAME, C_FUNC, C_ZASTR, C_L48, C_TZ, C_PROJ, C_VID = 8, 9, 16, 17, 18, 19, 28

# classification patterns are matched against lowercased text (re.I on Cyrillic is several times slower)
lc = lambda p: re.compile(p.lower())

# only used when the «Вид работ» field is empty (2018–2020)
VID_RX = [
    ("Капитальный ремонт", r"\bремонт|кап\.?\s*ремонт|замен\w+ лифт|лифтов\w* оборудован"),
    ("Реконструкция", r"реконструкц"),
    ("Снос объекта капитального строительства", r"\bснос|демонтаж"),
    ("Сохранение объекта культурного наследия", r"сохранени\w+ объект\w+ культурн|реставрац"),
    ("Строительство", r"строительств|возведени|\bнов\w+ "),
]
VID_RX = [(n, lc(p)) for n, p in VID_RX]
VID_NORM = {"Снос": "Снос объекта капитального строительства",
            "Сохранение объекта культурного наследия (памятника истории и культуры) народов Российской Федерации":
                "Сохранение объекта культурного наследия"}

LIN_EXPLICIT = lc(r"линейн")
LIN = lc(
    r"\bсет[ьиейя]\w*\b|газопровод|водовод|трубопровод|нефтепровод|продуктопровод|теплотрасс|теплопровод|"
    r"водопровод|канализац\w+ коллектор|коллектор|\bЛЭП\b|\bВЛ\b|\bКЛ\b|\bВЛИ\b|лини\w+ электропередач|"
    r"кабельн\w+ лини|лини\w+ связи|волс|автомобильн\w+ дорог|автодорог|\bдорог|\bулиц|проезд|тротуар|"
    r"\bмост|путепровод|эстакад|тоннел|железнодорожн\w+ пут|\bж/д пут|трамвайн\w+ лини|канал\b")
BLD = lc(
    r"здани|\bдом\b|\bдома\b|домов|многоквартир|\bжил|общежит|котельн|школ|детск\w+ сад|больниц|поликлин|"
    r"корпус|комплекс|центр|станци|подстанц|резервуар|склад|цех|ангар|гараж|стоянк|парковк|магазин|"
    r"торгов|офис|гостиниц|площадк|сквер|парк\b|стадион|бассейн|храм|очистн\w+ сооруж|водозабор|насосн")

TYPES = [
    ("Жильё (МКД, общежития)", r"многоквартир|общежит|жил\w* дом|жил\w+ здани|жилой комплекс|жилая застройк|жилищн|\bЖК\b"),
    ("Образование", r"школ|детск\w+ сад|дошкольн|\bдоу\b|образоват|гимнази|лицей|колледж|университет|техникум|училищ|интернат"),
    ("Здравоохранение", r"больниц|поликлиник|диспансер|фельдшер|\bФАП\b|медицин|госпитал|амбулатор|роддом|перинат|здравоохран|санатор"),
    ("Религия", r"храм|церк|мечет|собор\b|соборн|часовн|монастыр|синагог|молельн|религиозн|духовно-просвет|епархи|подворь"),
    ("Спорт", r"спорт|стадион|бассейн|физкультур|\bФОК\b|ледов|каток|манеж|теннис|фитнес|футбол|хоккей|гимнастич|тренажер"),
    ("Культура", r"дом\w* культуры|дворц\w* культуры|культурно-(досуг|развлек|просвет|образоват|спорт)|центр\w* культур|культурн\w+ центр|клуб|библиотек|музе|театр|"
                 r"выставоч|экспозиц|филармон|концерт|кинотеатр|цирк|галере|планетари|зоопарк|школ\w+ искусств"),
    ("Гостиницы", r"гостиниц|\bотел|апарт-?отел|хостел|мотел|\bапартамент|кемпинг|глэмпинг|база отдыха|турбаз"),
    ("Офисы, бизнес-центры", r"офис|бизнес|делов\w+ центр|административн(?!о-бытов)|деловой"),
    ("Торговля, коммерческие и встроенно-пристроенные помещения",
     r"торгов|магазин|супермаркет|гипермаркет|\bТЦ\b|\bТРЦ\b|\bТРК\b|рынок|рынка|коммерческ|встроен|пристроен|"
     r"нежил\w* помещени|ресторан|кафе|столов|общественного питания|бытового обслуживания|автосалон|автоцентр|"
     r"автомойк|\bАЗС\b|\bАГЗС\b|заправоч|шиномонтаж|техническ\w+ обслуживани"),
    ("Склады, логистика", r"склад|логистич|терминал|ангар|хранилищ"),
    ("Промышленность, добыча", r"завод|цех|производств|фабрик|комбинат|скважин|месторожд|кустов|нефт|газ\w* промысл|рудник|карьер|шахт|обогатит|промышлен"),
    ("Энергетика, ЖКХ-объекты", r"котельн|подстанц|электростанц|\bТЭЦ\b|\bГРЭС\b|\bПС\b|очистн|водозабор|насосн|водоочист|\bКНС\b|полигон|мусор|отход"),
    ("Сельское хозяйство", r"ферм|животновод|птицефабр|свиноком|теплиц|сельскохоз|зернохран|элеватор|молочн"),
    ("Госорганы, безопасность", r"пожарн|\bМЧС\b|полици|\bМВД\b|суд\b|судебн|прокуратур|исправит|воинск|военн|пограничн|таможен"),
    ("Транспорт (здания, вокзалы, аэропорты)", r"вокзал|аэропорт|аэровокзал|\bдепо\b|автостанц|автовокзал|причал|порт\b|взлетн"),
    ("Гаражи, парковки", r"гараж|парковк|паркинг|автостоянк"),
    ("Благоустройство", r"благоустр|сквер|\bпарк\b|набережн|детск\w+ площадк|кладбищ"),
]
TYPES = [(n, lc(p)) for n, p in TYPES]

ADDR_CUT = re.compile(r",?\s*(Почтовый адрес|расположенн|по адресу|адрес:)", re.I)
BARE_CODE = re.compile(r"^[\d.\s]+$")
CODE_PREFIX = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,3}\.\d{1,3}\s*")
ORG_NAME = re.compile(r"^(.*?)\s*\((ОГРН|ОГРНИП|МЕСТО)")
INN = re.compile(r"ИНН:\s*(\d{10,12})")
OGRN = re.compile(r"ОГРН(?:ИП)?:\s*(\d{13,15})")
EMPTY = {"", "нет данных", "не требуется"}
MIN_ORG = 3  # orgs with fewer conclusions stay in the CSV lists but not in dashboard.json


def year_of(date):
    return date[-4:] if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date.strip()) else "н/д"


def object_core(name):
    return ADDR_CUT.split(name, 1)[0][:300]


def func_text(func):
    """Functional purpose without the classifier code; '' if the field carries no meaning."""
    f = func.strip()
    if not f or f.startswith("Функциональное назначение по классификатору") or BARE_CODE.match(f):
        return ""
    return CODE_PREFIX.sub("", f)


def vid_of(vid, core):
    v = vid.strip()
    if v:
        return VID_NORM.get(v, v), "поле"
    for name, rx in VID_RX:
        if rx.search(core[:200]):
            return name, "название"
    return "неясно", "название"


def geometry_of(func, core):
    """площадной / линейный / неясно."""
    if func:
        if LIN_EXPLICIT.search(func):
            return "линейный"
        if BLD.search(func):
            return "площадной"
        if LIN.search(func):
            return "линейный"
    lin, bld = LIN.search(core), BLD.search(core)
    if lin and bld:
        return "неясно"
    if lin:
        return "линейный"
    return "площадной"


def type_of(func, core):
    for text in (func, core):
        if text:
            for name, rx in TYPES:
                if rx.search(text):
                    return name
    return "Прочее / не определено"


def first_org(cell):
    """(key, name) of the first organization in a cell; orgs are separated by '<%>'."""
    v = cell.strip()
    if v.strip('"').lower() in EMPTY:
        return "", ""
    first = v.split("<%>")[0].strip()
    m = ORG_NAME.match(first)
    name = (m.group(1) if m else first[:200]).strip().strip(",")
    inn, ogrn = INN.search(first), OGRN.search(first)
    key = inn.group(1) if inn else ogrn.group(1) if ogrn else "имя:" + re.sub(r"\W+", " ", name.lower()).strip()
    return key, name


def n_orgs(cell):
    v = cell.strip()
    return 0 if v.lower() in EMPTY else len(v.split("<%>"))


ROW_COLS = ["id", "номер", "дата", "год", "результат", "форма", "объект_экспертизы", "регион",
            "вид", "вид_источник", "геометрия", "тип", "в_дашборде",
            "генпроект_ключ", "генпроект", "проектировщиков",
            "заказчик_ключ", "заказчик", "заказчик_источник", "застройщик_ключ", "застройщик",
            "функц_назначение", "наименование"]


SLIM = OUT / "slim.csv"
SLIM_COLS = ["id", "номер", "дата", "год", "результат", "форма", "объект", "регион", "наименование", "функц",
             "вид_поле", "gp_key", "gp_name", "n_proj", "z_key", "z_name", "l_key", "l_name", "t_key", "t_name"]


def extract(src):
    """Stage 1: parse the 1.4 GB export once into slim.csv (only what classification needs, orgs already parsed)."""
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(src, encoding="utf-8-sig", newline="") as f, open(SLIM, "w", encoding="utf-8", newline="") as fo:
        r = csv.reader(f, delimiter=";")
        hdr = next(r)
        w = csv.writer(fo, delimiter=";")
        w.writerow(SLIM_COLS)
        for row in r:
            row += [""] * (len(hdr) - len(row))
            res = "положительное" if row[C_RES].startswith("Полож") else "отрицательное" if row[C_RES].startswith("Отриц") else "н/д"
            w.writerow([row[C_ID], row[C_NUM], row[C_DATE], year_of(row[C_DATE]), res, row[C_FORM] or "н/д", row[C_OBJ],
                        re.sub(r"\s*-\s*\d+$", "", row[C_REG]) or "н/д", row[C_NAME][:400], row[C_FUNC][:300], row[C_VID],
                        *first_org(row[C_PROJ]), n_orgs(row[C_PROJ]), *first_org(row[C_ZASTR]),
                        *first_org(row[C_L48]), *first_org(row[C_TZ])])
            n += 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"slim.csv: {n} строк, {SLIM.stat().st_size / 2**20:.0f} МБ")


def slim_rows(src):
    if not SLIM.exists() or SLIM.stat().st_mtime < src.stat().st_mtime:
        extract(src)
    with open(SLIM, encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        next(r)
        yield from r


def build(src):
    """Stage 2: classify from slim.csv and write rows, org lists and dashboard sources."""
    OUT.mkdir(parents=True, exist_ok=True)
    names = defaultdict(Counter)          # org key -> name variants
    facts = Counter()                     # (y, res, form, reg, type, vid) -> n
    org_facts = defaultdict(lambda: [0, 0, 0])  # (role, key, y, form, reg, type) -> [pos, neg, explicit техзаказчик]
    org_tot = defaultdict(Counter)        # (role, key) -> counters
    org_regs = defaultdict(set)
    stats = Counter()
    with open(OUT / "rows.csv", "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo, delimiter=";")
        w.writerow(ROW_COLS)
        for (rid, num, date, year, res, form, obj, reg, name, func_raw, vid_field,
             gp_key, gp_name, n_proj, z_key, z_name, l_key, l_name, t_key, t_name) in slim_rows(src):
            core = object_core(name).lower()
            func = func_text(func_raw).lower()
            vid, vid_src = vid_of(vid_field, core)
            geom = geometry_of(func, core)
            typ = type_of(func, core)
            if t_key:
                k_key, k_name, k_src = t_key, t_name, "техзаказчик"
            elif l_key:
                k_key, k_name, k_src = l_key, l_name, "лицо ч.1.1-1.3 ст.48"
            else:
                k_key, k_name, k_src = z_key, z_name, "застройщик (техзаказчик не указан)"
            in_dash = geom == "площадной" and vid != "Капитальный ремонт" and res != "н/д"
            stats[(geom, vid == "Капитальный ремонт")] += 1
            w.writerow([rid, num, date, year, res, form, obj, reg,
                        vid, vid_src, geom, typ, "да" if in_dash else "нет",
                        gp_key, gp_name, n_proj, k_key, k_name, k_src, z_key, z_name,
                        func_raw[:200], name[:300]])
            if not in_dash:
                continue
            facts[(year, res, form, reg, typ, vid)] += 1
            for role, key, name, src_ in (("gp", gp_key, gp_name, ""), ("zk", k_key, k_name, k_src)):
                if not key:
                    continue
                names[key][name] += 1
                explicit = role == "zk" and src_ != "застройщик (техзаказчик не указан)"
                cell = org_facts[(role, key, year, form, reg, typ)]
                cell[0 if res == "положительное" else 1] += 1
                cell[2] += explicit
                t = org_tot[(role, key)]
                t["всего"] += 1
                t[res] += 1
                t["явный"] += explicit
                org_regs[(role, key)].add(reg)

    def org_name(key):
        return names[key].most_common(1)[0][0]

    for role, fname in (("gp", "genproektirovshiki.csv"), ("zk", "zakazchiki.csv")):
        rows = sorted(((k, t) for (rl, k), t in org_tot.items() if rl == role), key=lambda x: -x[1]["всего"])
        with open(OUT / fname, "w", encoding="utf-8-sig", newline="") as fo:
            w = csv.writer(fo, delimiter=";")
            head = ["ключ (ИНН/ОГРН)", "название", "заключений", "положительных", "отрицательных", "доля_отрицательных", "регионов"]
            if role == "zk":
                head.append("из них техзаказчик указан явно")
            w.writerow(head)
            for k, t in rows:
                line = [k, org_name(k), t["всего"], t["положительное"], t["отрицательное"],
                        f"{t['отрицательное'] / t['всего']:.3f}".replace(".", ","), len(org_regs[("" + role, k)])]
                if role == "zk":
                    line.append(t["явный"])
                w.writerow(line)

    # dashboard sources (plain CSV, comma-delimited, UTF-8): org facts are code-encoded to stay under 8 MB
    dash = OUT / "dashboard"
    dash.mkdir(exist_ok=True)

    def write_csv(name, head, rows):
        with open(dash / name, "w", encoding="utf-8", newline="") as fo:
            w = csv.writer(fo)
            w.writerow(head)
            w.writerows(rows)

    write_csv("facts.csv", ["год", "результат", "форма", "регион", "тип", "вид", "заключений"],
              [list(k) + [n] for k, n in sorted(facts.items())])
    regs = sorted({k[3] for k in facts})
    types = sorted({k[4] for k in facts})
    r_idx, t_idx = {v: i for i, v in enumerate(regs)}, {v: i for i, v in enumerate(types)}
    form_code = {"Государственная": "г", "Негосударственная": "н"}
    write_csv("dims.csv", ["измерение", "код", "значение"],
              [["регион", i, v] for i, v in enumerate(regs)] + [["тип", i, v] for i, v in enumerate(types)])
    orgs = {}
    org_rows = []
    for (role, key, year, form, reg, typ), (pos, neg, explicit) in org_facts.items():
        if org_tot[(role, key)]["всего"] < MIN_ORG:
            continue
        oid = orgs.setdefault((role, key), len(orgs))
        org_rows.append([oid, year, form_code.get(form, "?"), r_idx[reg], t_idx[typ], pos, neg, explicit])
    write_csv("org_facts.csv", ["o", "y", "f", "r", "t", "p", "n", "x"], sorted(org_rows))
    write_csv("orgs.csv", ["o", "роль", "ключ", "название"],
              [[oid, "генпроектировщик" if role == "gp" else "заказчик", key, org_name(key)]
               for (role, key), oid in sorted(orgs.items(), key=lambda x: x[1])])

    sys.stdout.reconfigure(encoding="utf-8")
    for (geom, kr), n in sorted(stats.items()):
        print(f"{n:>8}  {geom:<10} {'капремонт' if kr else ''}")
    print("в дашборде:", sum(facts.values()), "| строк фактов:", len(facts), "| орг-строк:", len(org_rows),
          "| организаций:", len(orgs))
    for p in sorted(dash.iterdir()):
        print(f"{p.name}: {p.stat().st_size / 2**20:.1f} МБ")


def site(dest):
    """Static GitHub Pages copy: the page template plus the dashboard CSVs."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("expertiza_site.html"), dest / "index.html")
    for name in ("facts.csv", "org_facts.csv", "orgs.csv", "dims.csv"):
        shutil.copyfile(OUT / "dashboard" / name, dest / name)
    print("site written to", dest)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "extract":
        extract(Path(sys.argv[2]) if len(sys.argv) > 2 else SRC)
    elif cmd == "build":
        build(Path(sys.argv[2]) if len(sys.argv) > 2 else SRC)
    elif cmd == "site" and len(sys.argv) > 2:
        site(Path(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)
