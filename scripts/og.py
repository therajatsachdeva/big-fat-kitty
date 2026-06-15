#!/usr/bin/env python3
# Renders og.png (the WhatsApp/link preview card) from data.json and rewrites the
# Open Graph tags in index.html with the current pot, leader and next match.
# Pure Pillow — no native build steps. Safe to fail: the workflow runs it with
# continue-on-error, so the data update always lands even if this step hiccups.

import json, os, re, io, base64, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data.json")
INDEX = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "og.png")

FONTS = ["/usr/share/fonts/truetype/dejavu/", "/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/"]
def font(name, size):
    for base in FONTS:
        p = os.path.join(base, name)
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ---------- model (mirrors index.html) ----------
def owner_of(players, t):
    for p in players:
        if t in p["teams"]: return p["name"]
    return None

def reach_semi(td):
    if td.get("eliminated"): return 0.0
    base = td.get("strength", 0) / 100.0
    st = td.get("stage", "GROUP")
    if st in ("SEMI_FINALS", "FINAL", "THIRD_PLACE"): return 1.0
    if st == "QUARTER_FINALS": return min(1.0, 0.55 + 0.45 * base)
    if st == "LAST_16":        return min(1.0, 0.30 + 0.60 * base)
    if st == "LAST_32":        return min(1.0, 0.15 + 0.70 * base)
    gp, pts = td.get("gp", 0), td.get("pts", 0)
    perf = pts / (3 * gp) if gp > 0 else 0.5
    return max(0.0, min(0.95, base * (0.75 + 0.5 * perf)))

def compute(data):
    players, teams = data["players"], data["teams"]
    owed = {p["name"]: 0 for p in players}
    both_out = lambda p: all(teams.get(t, {}).get("eliminated") for t in p["teams"])
    for m in data["matches"]:
        evs = []
        oa, ob = owner_of(players, m["a"]), owner_of(players, m["b"])
        if m["as"] > m["bs"]:
            if oa: evs.append((oa, 500))
        elif m["bs"] > m["as"]:
            if ob: evs.append((ob, 500))
        else:
            if oa: evs.append((oa, 250))
            if ob: evs.append((ob, 250))
        for owner, amt in evs:
            for p in players:
                if p["name"] == owner or both_out(p): continue
                owed[p["name"]] += amt
    raw = {p["name"]: 1 - (1 - reach_semi(teams[p["teams"][0]])) * (1 - reach_semi(teams[p["teams"][1]])) for p in players}
    s = sum(raw.values()) or 1
    win = {n: raw[n] / s * 100 for n in raw}
    return owed, win

def rupees(n): return "Rs " + format(n, ",d")

# ---------- render ----------
def render(data, owed, win):
    W, H = 1200, 630
    INK, CARD, GOLD, TEXT, MUT = (11,15,30), (22,29,54), (244,201,93), (237,240,247), (139,149,178)
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    # soft gold glow up top
    glow = Image.new("RGB", (W, H), INK); gd = ImageDraw.Draw(glow)
    gd.ellipse([W//2-460, -360, W//2+460, 200], fill=(40,34,20))
    img = Image.blend(img, glow, 0.6); d = ImageDraw.Draw(img)

    f_eye = font("DejaVuSans-Bold.ttf", 26)
    f_pot = font("DejaVuSans-Bold.ttf", 88)
    f_name = font("DejaVuSans-Bold.ttf", 27)
    f_row = font("DejaVuSans-Bold.ttf", 25)
    f_sm = font("DejaVuSans.ttf", 22)
    f_foot = font("DejaVuSans.ttf", 23)

    d.text((60, 46), "THE BIG FAT KITTY", font=f_eye, fill=GOLD)
    d.text((60, 80), rupees(owed and sum(owed.values())), font=f_pot, fill=GOLD)
    till = data.get("meta", {}).get("updatedTill", "")
    date = data.get("meta", {}).get("updatedDate", "")
    d.text((63, 188), f"Updated till {till}" + (f"  ·  {date}" if date else ""), font=f_sm, fill=MUT)

    # standings (top by win%)
    players = data["players"]; avmap = {p["name"]: p.get("avatar") for p in players}
    order = sorted(players, key=lambda p: -win[p["name"]])
    x, y0, rowh = 60, 232, 34
    medals = {0:(244,201,93), 1:(190,198,214), 2:(205,139,90)}
    for i, p in enumerate(order):
        y = y0 + i * rowh
        n = p["name"]
        d.text((x, y), f"{i+1}", font=f_row, fill=medals.get(i, MUT))
        # avatar
        av = avmap.get(n)
        ax = x + 42
        if av:
            try:
                raw = base64.b64decode(av.split(",")[1])
                a = Image.open(io.BytesIO(raw)).convert("RGB").resize((28,28))
                mask = Image.new("L",(28,28),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,28,28),8,fill=255)
                img.paste(a,(ax,y),mask)
            except Exception: pass
        d.text((ax+40, y), n, font=f_name, fill=TEXT)
        d.text((x+430, y), f"{win[n]:.1f}%", font=f_row, fill=GOLD)
        d.text((x+560, y), rupees(owed[n]), font=f_sm, fill=MUT)

    # next match footer
    nx = (data.get("upcoming") or [None])[0]
    if nx:
        d.rectangle([0, H-54, W, H], fill=(16,22,43))
        d.text((63, H-40), f"Next up:  {nx['a']}  v  {nx['b']}", font=f_foot, fill=TEXT)
    img.save(OUT, "PNG")
    return True

# ---------- patch OG tags ----------
def patch_index(data, owed, win):
    if not os.path.exists(INDEX): return
    html = open(INDEX, encoding="utf-8").read()
    pot = sum(owed.values())
    order = sorted(data["players"], key=lambda p: -win[p["name"]])
    leader = order[0]["name"]; lpct = win[leader]
    light = min(data["players"], key=lambda p: owed[p["name"]])["name"]
    nx = (data.get("upcoming") or [None])[0]
    nxt = f"{nx['a']} v {nx['b']}" if nx else "TBD"
    stamp = (data.get("meta", {}).get("updatedDate") or "live").replace(" ", "").lower()

    base = ""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        base = f"https://{owner}.github.io/" + ("" if name.lower() == f"{owner.lower()}.github.io" else name + "/")

    title = f"The Big Fat Kitty \U0001F431 — \u20B9{pot:,} in the pot"
    desc = f"Leader: {leader} ({lpct:.1f}%)  ·  Lightest: {light}  ·  Next: {nxt}"
    img = (base + "og.png") if base else "og.png"
    img += f"?v={stamp}"

    def setmeta(html, prop, val, attr="property"):
        pat = re.compile(r'(<meta '+attr+r'="'+re.escape(prop)+r'" content=")[^"]*(">)')
        return pat.subn(lambda m: m.group(1)+val.replace("\\","")+m.group(2), html)[0]

    html = setmeta(html, "og:title", title)
    html = setmeta(html, "og:description", desc)
    html = setmeta(html, "og:image", img)
    if base: html = setmeta(html, "og:url", base)
    open(INDEX, "w", encoding="utf-8").write(html)

def main():
    data = json.load(open(DATA, encoding="utf-8"))
    owed, win = compute(data)
    render(data, owed, win)
    patch_index(data, owed, win)
    print(f"og.png rendered; pot Rs {sum(owed.values()):,}; leader {max(win,key=win.get)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("og.py failed (non-fatal):", e, file=sys.stderr)
        sys.exit(0)
