"""Разбор HTML-выгрузки Telegram-канала Arcars в рабочие таблицы.

    .tools\\venv\\Scripts\\python.exe .tools\\projects\\arcars\\telegram\\parse_channel.py [export_dir]

Вход: export/<дата>/ — выгрузка Telegram Desktop (messages*.html + photos/), по
умолчанию самая свежая. Выгрузка — сырые данные: в git не идёт, лежит здесь же.
Выход в out/ (тоже вне git, пересобирается этим скриптом):

  posts.jsonl   все посты: дата, рубрика, хештеги, текст, фото, ссылка t.me
  offers.csv    рубрика #готовое_предложение: модель, год, мотор, пробег, цена.
                Цена в канале — «расчётная стоимость с доставкой до Самары» на
                дату поста, то есть расчёт, а не закрытая сделка.
  gallery.html  витрина фото по рубрикам (выдача, отзывы, процесс, люди) с
                подписью из поста; отметь фото галочками → «Скопировать список».

Альбом в выгрузке — несколько сообщений с одной секундой во времени: склеиваем
их в один пост. Ссылка на пост — номер сообщения с текстом.
"""
import csv
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = "ARCarsSamara"

KINDS = [  # (рубрика, хештеги-признаки) — первая совпавшая побеждает
    ("delivery", {"вручение_автомобиля"}),
    ("review", {"отзыв_клиента", "отзыв"}),
    ("offer", {"готовое_предложение"}),
    ("stock", {"авто_в_наличии", "в_наличии"}),
    ("process", {"в_процессе"}),
    ("overview", {"автообзор", "тестдрайв", "тест_драйв", "обзор"}),
    ("news", {"автоновости", "чё_происходит_то"}),
]
KIND_RU = {"delivery": "Выдача", "review": "Отзывы", "offer": "Готовые предложения", "stock": "В наличии",
           "process": "В процессе", "overview": "Обзоры", "news": "Новости", "other": "Прочее", "people": "Люди"}

MSG_RE = re.compile(r'<div class="message default[^"]*" id="message(\d+)">(.*?)(?=<div class="message (?:default|service)|\Z)', re.S)
# Подпись-контакты в конце поста: имена менеджеров там есть всегда, людьми их не считаем.
SIGNATURE_RE = re.compile(r"(По всем интересующим.*|Заинтересовались автомобилем.*|Команда ARCars желает.*)", re.S | re.I)
PEOPLE_RE = re.compile(r"меня зовут|наша команда|знакомьтесь|основател|менеджер\w* (антон|андрей|максим|сем[её]н)|"
                       r"(антон|андрей|максим|сем[её]н)\w*,? (наш|который|рассказ|провер|встретил|осмотр)", re.I)


def to_text(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"</?(blockquote|p|div)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def parse_messages(export: Path) -> list[dict]:
    files = sorted(export.glob("messages*.html"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 1))
    out = []
    for f in files:
        for mid, body in MSG_RE.findall(f.read_text(encoding="utf-8")):
            dt = re.search(r'class="pull_right date details" title="([^"]+)"', body)
            txt = re.search(r'<div class="text">(.*?)</div>', body, re.S)
            out.append({
                "id": int(mid),
                "dt": dt.group(1) if dt else "",
                "text": to_text(txt.group(1)) if txt else "",
                "tags": [t.lower() for t in re.findall(r"ShowHashtag\(&quot;([^&]+)&quot;\)", body)],
                "photos": re.findall(r'class="photo_wrap[^"]*" href="(photos/[^"]+)"', body),
                "video": "Video file" in body,
            })
    return out


def group_posts(msgs: list[dict]) -> list[dict]:
    posts: list[dict] = []
    for m in msgs:
        if posts and m["dt"] and m["dt"] == posts[-1]["dt"]:
            p = posts[-1]
            p["photos"] += m["photos"]
            p["video"] = p["video"] or m["video"]
            if m["text"] and not p["text"]:
                p.update(id=m["id"], text=m["text"], tags=m["tags"])
        else:
            posts.append(dict(m, photos=list(m["photos"])))
    for p in posts:
        p["date"] = p["dt"][:10]
        p["url"] = f"https://t.me/{CHANNEL}/{p['id']}"
        tags = set(p["tags"])
        p["kind"] = next((k for k, keys in KINDS if any(t == key or t.startswith(key + "_") for t in tags for key in keys)), "other")
        p["people"] = bool(PEOPLE_RE.search(SIGNATURE_RE.sub("", p["text"])))
    return posts


def num(s: str) -> int | None:
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else None


def country_of(t: str) -> str:
    """«Рынок Кореи» → флаг → валюта курса (в старых постах страна названа только так)."""
    m = re.search(r"Рынок (Японии|Кореи|Китая)", t)
    if m:
        return {"Японии": "Япония", "Кореи": "Корея", "Китая": "Китай"}[m.group(1)]
    for name, pat in (("Япония", r"🇯🇵|иен|йен"), ("Корея", r"🇰🇷|\bвон[аы]?\b"), ("Китай", r"🇨🇳|юан")):
        if re.search(pat, t, re.I):
            return name
    for name, pat in (("Япония", r"япон"), ("Корея", r"коре"), ("Китай", r"кита")):
        if re.search(pat, t, re.I):
            return name
    return ""


def parse_offer(p: dict) -> dict:
    # Цифры-эмодзи «1⃣6⃣3⃣…» в старых постах → обычные цифры
    t = p["text"].replace("⃣", "").replace("️", "")
    head = re.search(r"([A-Z][\w\-]+(?: [\w\-\.]+){0,4}?)\s*,?\s*(\d{4}) ?г", t)
    # Подпись цены бывает разорвана переносом («Стоимость автомобиля под\nключ в г. Самара:»),
    # поэтому между ней и числом — до 120 любых знаков, кроме цифр.
    price = re.search(r"(Расч[её]тная стоимость|[Сс]тоимость|[Ии]того|под ключ)([^\d]{0,120}?)"
                      r"(\d{1,3}(?:[  ]\d{3})+|\d{6,})\s*(₽|руб)", t)
    # Цена бывает и во Владивостоке (без доставки по России): смешивать с Самарой нельзя.
    where = (price.group(1) + price.group(2)) if price else ""
    near = t[max(0, price.start() - 200):price.start()] if price else ""
    city = next((c for c in ("Владивосток", "Самара", "Москва") if c[:-1] in where), "") or \
           next((c for c in ("Владивосток", "Самара", "Москва") if c[:-1] in near), "")
    engine = re.search(r"(\d[.,]\d)\s*л?\.?,?\s*(\d{2,3})\s*л\.с\.?,?\s*(бензин|дизель|гибрид|электро\w*)?", t, re.I)
    mileage = re.search(r"Пробег:?\s*([\d\s ]+)\s*(тыс|тысяч|км)", t, re.I)
    country = country_of(t)
    budget = next((tg.replace("готовое_предложение_", "") for tg in p["tags"] if tg.startswith("готовое_предложение_")), "")
    km = num(mileage.group(1)) if mileage else None
    if km is not None and mileage.group(2).lower().startswith("тыс"):
        km *= 1000
    return {
        "date": p["date"], "url": p["url"],
        "model": head.group(1).strip() if head else "", "year": head.group(2) if head else "",
        "country": country,
        "engine_l": engine.group(1).replace(",", ".") if engine else "", "hp": engine.group(2) if engine else "",
        "fuel": (engine.group(3) or "").lower() if engine else "",
        "drive": "4WD" if re.search(r"4WD|AWD|полн\w+ привод", t, re.I) else "",
        "mileage_km": km or "",
        "price_rub": num(price.group(3)) if price else "",
        "price_city": city,
        "price_kind": ("расчёт" if price and "асч" in price.group(1) else "стоимость" if price else ""),
        # Подборка: несколько машин в одном посте — в строке только первая
        "multi": len(re.findall(r"\d{4} ?г\.", t)) > 1,
        "budget_tag": budget, "lgotny": "льготный" in p["tags"], "photos": len(p["photos"]),
        "excerpt": re.sub(r"\s+", " ", t)[:160],
    }


GALLERY_CSS = """
body{margin:0;font:15px/1.45 system-ui,Segoe UI,sans-serif;background:#E6E9EC;color:#0F1317}
header{position:sticky;top:0;background:#0F1317;color:#EEF0F2;padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:2}
header a{color:#F2692B;text-decoration:none;font-weight:600}header button{font:inherit;padding:8px 14px;border:0;background:#C4470F;color:#fff;cursor:pointer}
main{padding:20px}h2{margin:32px 0 12px;font-size:24px}
.post{background:#F4F5F6;padding:14px;margin:0 0 14px}.meta{font-size:13px;color:#444C55;margin-bottom:6px}
.meta a{color:#C4470F}.txt{white-space:pre-wrap;max-height:7.5em;overflow:auto;font-size:14px;margin-bottom:8px}
.ph{display:flex;flex-wrap:wrap;gap:8px}.ph label{position:relative;cursor:pointer}
.ph img{display:block;height:150px;width:auto;outline:3px solid transparent}.ph input{position:absolute;left:6px;top:6px;transform:scale(1.4)}
.ph input:checked+img{outline-color:#C4470F}#n{font-weight:600}
"""

GALLERY_JS = """
const boxes=[...document.querySelectorAll('.ph input')];const n=document.getElementById('n');
const upd=()=>{n.textContent=boxes.filter(b=>b.checked).length};boxes.forEach(b=>b.addEventListener('change',upd));
document.getElementById('copy').onclick=async()=>{const s=boxes.filter(b=>b.checked).map(b=>b.value+'  '+b.dataset.post).join('\\n');
try{await navigator.clipboard.writeText(s);alert('Скопировано: '+boxes.filter(b=>b.checked).length+' фото')}catch(e){prompt('Скопируйте список:',s)}};
"""


def gallery(posts: list[dict], export: Path, out: Path) -> None:
    rel = Path("..") / "export" / export.name
    sections = [("delivery", [p for p in posts if p["kind"] == "delivery"]),
                ("review", [p for p in posts if p["kind"] == "review"]),
                ("people", [p for p in posts if p["people"] and p["photos"]]),
                ("process", [p for p in posts if p["kind"] == "process"]),
                ("stock", [p for p in posts if p["kind"] == "stock"])]
    parts = [f"<!doctype html><meta charset=utf-8><title>Канал Arcars — фото</title><style>{GALLERY_CSS}</style>",
             "<header><b>Канал ARCars — фото по рубрикам</b>",
             " ".join(f'<a href="#{k}">{KIND_RU[k]} ({len(ps)})</a>' for k, ps in sections),
             '<span>Отмечено: <span id="n">0</span></span><button id="copy">Скопировать список</button></header><main>']
    for k, ps in sections:
        parts.append(f'<h2 id="{k}">{KIND_RU[k]} — {len(ps)} постов</h2>')
        for p in reversed(ps):  # свежие сверху
            imgs = "".join(
                f'<label><input type="checkbox" value="{html.escape(ph)}" data-post="{p["url"]}">'
                f'<img loading="lazy" src="{html.escape((rel / ph.replace(".jpg", "_thumb.jpg")).as_posix())}" '
                f'onclick="window.open(\'{html.escape((rel / ph).as_posix())}\')" title="открыть крупно"></label>'
                for ph in p["photos"])
            parts.append(f'<div class="post"><div class="meta">{p["date"]} · <a href="{p["url"]}" target="_blank">пост {p["id"]}</a>'
                         f' · {", ".join("#" + t for t in p["tags"])}</div><div class="txt">{html.escape(p["text"])}</div>'
                         f'<div class="ph">{imgs}</div></div>')
    parts.append(f"</main><script>{GALLERY_JS}</script>")
    (out / "gallery.html").write_text("".join(parts), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    exports = sorted((HERE / "export").glob("*/messages.html"))
    export = Path(sys.argv[1]) if len(sys.argv) > 1 else (exports[-1].parent if exports else None)
    if not export or not (export / "messages.html").is_file():
        print("нет выгрузки: положи папку Telegram в export/<дата>/")
        return 1
    out = HERE / "out"
    out.mkdir(exist_ok=True)

    posts = group_posts(parse_messages(export))
    with open(out / "posts.jsonl", "w", encoding="utf-8") as f:
        for p in posts:
            f.write(json.dumps({k: p[k] for k in ("id", "date", "kind", "tags", "text", "photos", "video", "people", "url")},
                               ensure_ascii=False) + "\n")
    offers = [parse_offer(p) for p in posts if p["kind"] == "offer"]
    with open(out / "offers.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(offers[0].keys()) if offers else ["date"], delimiter=";")
        w.writeheader()
        w.writerows(offers)
    gallery(posts, export, out)

    from collections import Counter
    kinds = Counter(p["kind"] for p in posts)
    print(f"выгрузка {export.name}: постов {len(posts)} (с текстом {sum(1 for p in posts if p['text'])}), "
          f"фото {sum(len(p['photos']) for p in posts)}")
    print("рубрики: " + ", ".join(f"{KIND_RU[k]} {v}" for k, v in kinds.most_common()))
    print(f"предложений {len(offers)}: с ценой {sum(1 for o in offers if o['price_rub'])}, с моделью {sum(1 for o in offers if o['model'])}, "
          f"со страной {sum(1 for o in offers if o['country'])}")
    print(f"посты с людьми и фото: {sum(1 for p in posts if p['people'] and p['photos'])}")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
