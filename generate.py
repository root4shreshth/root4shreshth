#!/usr/bin/env python3
"""
Renders the profile's SVG kit into ../assets.

  python build/generate.py            live data (needs GITHUB_TOKEN or PROFILE_TOKEN)
  python build/generate.py --demo     synthetic data, for local previews only

Without a token and without --demo, data-driven panels render in a
"pending first sync" state so nothing on the profile is ever broken.
"""
import base64, datetime as dt, io, json, math, os, random, re, sys, urllib.request
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset as ftsubset

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import config as C  # noqa: E402

OUT = ROOT.parent / "assets"
FONTS = ROOT / "fonts"

# ── palette ────────────────────────────────────────────────────────────────
BG, SURF, SURF2, LINE = "#0A0C11", "#10131A", "#151923", "#1F2430"
MUTED, DIM, TEXT, BRIGHT = "#5D6878", "#8893A4", "#C6CEDA", "#EEF2F7"
CYAN, VIOLET, PINK, GREEN, AMBER = "#22D3EE", "#A855F7", "#F72585", "#34D399", "#FBBF24"

FONT_FILES = {
    ("mono", 400): "jetbrains-mono-latin-400-normal.woff2",
    ("mono", 700): "jetbrains-mono-latin-700-normal.woff2",
    ("sans", 500): "space-grotesk-latin-500-normal.woff2",
    ("sans", 700): "space-grotesk-latin-700-normal.woff2",
}
FAMILY = {"mono": "JBM", "sans": "SG"}
_fonts = {k: TTFont(FONTS / v) for k, v in FONT_FILES.items()}


def advance(text, kind="mono", weight=400, size=14):
    """Text width in px from the real font metrics."""
    f = _fonts[(kind, weight)]
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    w = 0
    for ch in text:
        g = cmap.get(ord(ch))
        w += hmtx[g][0] if g else upm * 0.6
    return w * size / upm


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def font_css(body):
    """Embed only the glyphs this SVG actually uses, per font face."""
    used = {}
    for m in re.finditer(r'<text[^>]*class="([^"]*)"[^>]*>(.*?)</text>', body, re.S):
        cls, txt = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        txt = (txt.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
               .replace("&amp;", "&"))
        kind = "sans" if " s5" in f" {cls}" or " s7" in f" {cls}" else "mono"
        weight = 700 if (" m7" in f" {cls}" or " s7" in f" {cls}") else (500 if " s5" in f" {cls}" else 400)
        used.setdefault((kind, weight), set()).update(txt)
    css = []
    for (kind, weight), chars in used.items():
        chars = "".join(sorted(chars | {" "}))
        opts = ftsubset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern"]
        font = TTFont(FONTS / FONT_FILES[(kind, weight)])
        sub = ftsubset.Subsetter(opts); sub.populate(text=chars); sub.subset(font)
        buf = io.BytesIO(); font.flavor = "woff2"; font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css.append(f"@font-face{{font-family:{FAMILY[kind]}{weight};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    return "".join(css)


BASE_CSS = f"""
.m4{{font-family:JBM400,'JetBrains Mono',Consolas,monospace;font-weight:400}}
.m7{{font-family:JBM700,'JetBrains Mono',Consolas,monospace;font-weight:700}}
.s5{{font-family:SG500,'Space Grotesk','Segoe UI',sans-serif;font-weight:500}}
.s7{{font-family:SG700,'Space Grotesk','Segoe UI',sans-serif;font-weight:700}}
.in{{opacity:0;animation:in .45s ease-out forwards}}
.up{{opacity:0;animation:up .6s cubic-bezier(.2,.7,.2,1) forwards}}
.blink{{animation:blink 1.05s steps(1) infinite}}
.breathe{{animation:breathe 2.6s ease-in-out infinite}}
@keyframes in{{to{{opacity:1}}}}
@keyframes up{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
@keyframes blink{{50%{{opacity:0}}}}
@keyframes breathe{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
"""


def svg(w, h, body, extra_css="", defs=""):
    doc_defs = f"""
  <linearGradient id="neon" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{CYAN}"/><stop offset=".55" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/>
  </linearGradient>
  <pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="1" fill="#ffffff" opacity=".045"/>
  </pattern>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>{defs}"""
    css = font_css(body) + BASE_CSS + extra_css
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none">'
            f"<style>{css}</style><defs>{doc_defs}</defs>{body}</svg>")


def panel(w, h, r=18):
    return (f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{r}" fill="{BG}" stroke="{LINE}"/>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{r}" fill="url(#dots)"/>')


def t(x, y, s, cls="m4", size=14, fill=TEXT, extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" fill="{fill}" {extra}>{esc(s)}</text>'


def check(x, y, color=GREEN, s=1.0):
    return (f'<path d="M{x} {y} l{4*s} {4*s} l{8*s} {-9*s}" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow(x, y, color=DIM):
    return (f'<path d="M{x} {y} h10 m-4 -4 l4 4 l-4 4" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def star(cx, cy, r=6, color=AMBER):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append(f"{cx + rr*math.cos(a):.2f},{cy + rr*math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{color}"/>'


def now_local():
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=C.TIMEZONE_OFFSET_MIN)


# ── data ───────────────────────────────────────────────────────────────────
QUERY = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    pinnedItems(first:6,types:REPOSITORY){nodes{...R}}
    repositories(first:100,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,
                 orderBy:{field:STARGAZERS,direction:DESC}){
      totalCount
      nodes{...R languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
    }
    contributionsCollection{
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions restrictedContributionsCount
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
    }
  }
}
fragment R on Repository{name description url stargazerCount forkCount
  primaryLanguage{name color} pushedAt}
"""


def fetch():
    token = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": C.LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-kit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def demo():
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 51 * 7)
    weeks, d = [], start
    for w in range(52):
        days = []
        for _ in range(7):
            if d <= today:
                base = 2 + 6 * (0.5 + 0.5 * math.sin(w / 5.0)) + w * 0.12
                days.append({"date": d.isoformat(),
                             "contributionCount": max(0, int(rnd.gauss(base, 3))) if rnd.random() > .18 else 0})
            d += dt.timedelta(days=1)
        weeks.append({"contributionDays": days})
    langs = [("Python", "#3572A5", 520), ("TypeScript", "#3178c6", 410), ("JavaScript", "#f1e05a", 190),
             ("HTML", "#e34c26", 80), ("CSS", "#663399", 60), ("C", "#555555", 25)]
    repo = lambda n, dsc, lang, col, s: {"name": n, "description": dsc, "url": "#", "stargazerCount": s,
                                         "forkCount": s // 3, "primaryLanguage": {"name": lang, "color": col}}
    pinned = [repo("voice-agent-runtime", "Sub-second, interruptible voice agents over WebRTC with tool use.", "Python", "#3572A5", 42),
              repo("llm-eval-harness", "Regression tests for prompts: datasets, graders and CI gates.", "Python", "#3572A5", 27),
              repo("agentic-workflows", "n8n + FastAPI recipes for production agent pipelines.", "TypeScript", "#3178c6", 18),
              repo("next-ai-starter", "Next.js starter with streaming chat, auth and usage metering.", "TypeScript", "#3178c6", 11)]
    nodes = [dict(p, languages={"edges": [{"size": s * 1000, "node": {"name": n, "color": c}} for n, c, s in langs]})
             for p in pinned[:1]] + pinned[1:]
    return {"followers": {"totalCount": 120}, "pinnedItems": {"nodes": pinned},
            "repositories": {"totalCount": 31, "nodes": nodes},
            "contributionsCollection": {"totalCommitContributions": 1180, "totalPullRequestContributions": 96,
                                        "totalIssueContributions": 34, "restrictedContributionsCount": 210,
                                        "contributionCalendar": {"totalContributions": sum(
                                            x["contributionCount"] for w in weeks for x in w["contributionDays"]),
                                            "weeks": weeks}}}


def streaks(weeks):
    days = [d for w in weeks for d in w["contributionDays"]]
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i]["contributionCount"] == 0:
        i -= 1  # today not counted yet
    while i >= 0 and days[i]["contributionCount"] > 0:
        cur += 1; i -= 1
    return cur, longest


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


# ── 00 hero ────────────────────────────────────────────────────────────────
def hero():
    W, H = 1000, 470
    b = [panel(W, H, 20)]
    # glow blobs
    b.append(f'<circle cx="820" cy="210" r="190" fill="url(#halo)"/>')
    # chrome
    b.append(f'<path d="M1 46 H{W-1}" stroke="{LINE}"/>')
    for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        b.append(f'<circle cx="{28+i*20}" cy="24" r="6" fill="{c}" opacity=".85"/>')
    b.append(t(W / 2, 29, f"{C.LOGIN}@prod: ~/inference", "m4", 12, MUTED, 'text-anchor="middle"'))
    b.append(f'<circle cx="{W-86}" cy="24" r="4" fill="{GREEN}" class="breathe"/>')
    b.append(t(W - 74, 28.5, "LIVE", "m7", 11, GREEN, 'letter-spacing="2"'))

    # prompt line, typed
    px, py = 48, 92
    b.append(t(px, py, "$", "m7", 15, PINK))
    pw = advance(C.PROMPT, size=15)
    b.append(f'<clipPath id="type"><rect x="{px+18}" y="{py-16}" width="0" height="22">'
             f'<animate attributeName="width" from="0" to="{pw+4:.0f}" begin=".2s" dur="1.4s" fill="freeze" '
             f'calcMode="discrete" values="{";".join(str(round(pw*k/len(C.PROMPT))) for k in range(len(C.PROMPT)+1))}"/></rect></clipPath>')
    b.append(f'<g clip-path="url(#type)">{t(px+18, py, C.PROMPT, "m4", 15, BRIGHT)}</g>')

    # name, letter by letter
    nx, ny, ns = 46, 196, 104
    x = nx
    for i, ch in enumerate(C.NAME):
        b.append(f'<text x="{x:.1f}" y="{ny}" class="s7 up" font-size="{ns}" fill="url(#neonName)" '
                 f'letter-spacing="0" style="animation-delay:{1.7+i*0.07:.2f}s">{esc(ch)}</text>')
        x += advance(ch, "sans", 700, ns) + 4
    name_w = x - nx
    b.append(f'<rect x="{nx+2}" y="{ny+18}" width="0" height="3" rx="1.5" fill="url(#neon)">'
             f'<animate attributeName="width" to="{name_w:.0f}" begin="2.4s" dur=".9s" fill="freeze" '
             f'calcMode="spline" keySplines=".2 .7 .2 1" keyTimes="0;1" values="0;{name_w:.0f}"/></rect>')
    b.append(t(nx + 2, ny + 50, f"{C.ROLE.upper()}   ·   {C.LOCATION.upper()}", "m7 in", 13, DIM,
               'letter-spacing="3" style="animation-delay:2.6s"'))

    # streamed answer: each token gets a chip, like a tokenizer view
    words = re.findall(r"\S+\s*", C.ANSWER)
    tx0, ty, maxw, size, lh = 48, 312, 560, 15.5, 30
    xcur, line, delay = tx0, 0, 3.0
    chip_cols = [CYAN, VIOLET, PINK]
    ntok = 0
    for i, wd in enumerate(words):
        word = wd.rstrip()
        ww = advance(word, size=size)
        if xcur + ww > tx0 + maxw:
            xcur, line = tx0, line + 1
        y = ty + line * lh
        col = chip_cols[i % 3]
        b.append(f'<g class="in" style="animation-delay:{delay:.2f}s">'
                 f'<rect x="{xcur-3:.1f}" y="{y-16:.1f}" width="{ww+6:.1f}" height="22" rx="4" fill="{col}" opacity=".09"/>'
                 f'<rect x="{xcur-3:.1f}" y="{y+6:.1f}" width="{ww+6:.1f}" height="1.5" fill="{col}" opacity=".55"/>'
                 f'{t(xcur, y, word, "m4", size, TEXT)}</g>')
        xcur += ww + advance(" ", size=size) + 4
        delay += 0.075
        ntok += 1
    last_y = ty + line * lh
    b.append(f'<rect x="{xcur-2:.1f}" y="{last_y-15:.1f}" width="9" height="19" fill="{CYAN}" class="blink"/>')
    b.append(t(tx0, last_y + 40, f"[ {ntok} tokens  ·  finish_reason: stop  ·  temperature: 0.2 ]",
               "m4 in", 12, MUTED, f'style="animation-delay:{delay+.2:.2f}s"'))

    # right: a small transformer, pulses flowing through it
    layers = [[130, 180, 230, 280, 330], [110, 160, 210, 260, 310, 360], [145, 205, 265, 325]]
    lx = [700, 810, 920]
    edges = []
    for li in range(2):
        for ai, ay in enumerate(layers[li]):
            for bi, by in enumerate(layers[li + 1]):
                edges.append((lx[li], ay, lx[li + 1], by, (ai + bi) % 3))
    for x1, y1, x2, y2, k in edges:
        b.append(f'<path d="M{x1} {y1} C{(x1+x2)/2} {y1} {(x1+x2)/2} {y2} {x2} {y2}" stroke="{LINE}" stroke-width="1"/>')
    rnd = random.Random(3)
    for n, (x1, y1, x2, y2, k) in enumerate(rnd.sample(edges, 14)):
        col = [CYAN, VIOLET, PINK][n % 3]
        d = f"M{x1} {y1} C{(x1+x2)/2} {y1} {(x1+x2)/2} {y2} {x2} {y2}"
        b.append(f'<path d="{d}" stroke="{col}" stroke-width="1.4" opacity=".55" stroke-dasharray="20 400">'
                 f'<animate attributeName="stroke-dashoffset" values="20;-180" dur="{2.2+n%4*0.4:.1f}s" '
                 f'begin="{n*0.23:.2f}s" repeatCount="indefinite"/></path>')
    for li, ys in enumerate(layers):
        for j, y in enumerate(ys):
            col = [CYAN, VIOLET, PINK][li]
            b.append(f'<circle cx="{lx[li]}" cy="{y}" r="9" fill="{SURF}" stroke="{col}" stroke-width="1.4"/>')
            b.append(f'<circle cx="{lx[li]}" cy="{y}" r="3.2" fill="{col}" class="breathe" '
                     f'style="animation-delay:{(li*0.5+j*0.3)%2.6:.2f}s"/>')
    for li, lab in enumerate(["embed", "attend", "emit"]):
        b.append(t(lx[li], 400, lab, "m4", 11, MUTED, 'text-anchor="middle"'))

    # status bar
    b.append(f'<path d="M1 {H-40} H{W-1}" stroke="{LINE}"/>')
    stamp = now_local().strftime(f"%Y-%m-%d %H:%M {C.TIMEZONE_LABEL}")
    items = [("model", "shreshth-v1"), ("ctx", C.LOCATION.lower()), ("mode", "0 to 1"), ("synced", stamp)]
    sx = 28
    b.append(f'<circle cx="{sx}" cy="{H-20}" r="3.5" fill="{GREEN}"/>'); sx += 12
    b.append(t(sx, H - 16, "ONLINE", "m7", 11, GREEN, 'letter-spacing="1.5"')); sx += 74
    for k, v in items:
        b.append(t(sx, H - 16, k, "m4", 11, MUTED)); sx += advance(k, size=11) + 8
        b.append(t(sx, H - 16, v, "m4", 11, DIM)); sx += advance(v, size=11) + 30
    defs = (f'<radialGradient id="halo"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".16"/>'
            f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="neonName" gradientUnits="userSpaceOnUse" x1="{nx}" y1="0" x2="{nx+name_w}" y2="0">'
            f'<stop offset="0" stop-color="{CYAN}"/><stop offset=".55" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>')
    return svg(W, H, "".join(b), defs=defs)


# ── stage headers ──────────────────────────────────────────────────────────
STAGES = [
    ("01", "SYSTEM PROMPT", "the instructions I run on", "init()"),
    ("02", "ATTENTION", "where my weights are tuned", "attend(q, k)"),
    ("03", "TOOL CALLS", "what I reach for to get it done", "tools.resolve()"),
    ("04", "OUTPUTS", "things that made it to prod", "generate()"),
    ("05", "TELEMETRY", "live from the GitHub API, refreshed daily", "observe()"),
    ("06", "HANDOFF", "your turn", "return"),
]


def stage(i, num, label, sub, fn):
    W, H = 1000, 78
    b = [panel(W, H, 16)]
    b.append(t(24, 51, num, "m7", 32, "url(#neon)"))
    b.append(t(68, 51, f"/{len(STAGES):02d}", "m4", 13, MUTED))
    lx = 122
    b.append(t(lx, 37, label, "s7", 22, BRIGHT, 'letter-spacing="3"'))
    b.append(t(lx, 58, sub, "m4", 12.5, DIM))
    lw = advance(label, "sans", 700, 22) + len(label) * 3
    line_x = max(lx + lw, lx + advance(sub, size=12.5)) + 28
    fw = advance(fn, size=12)
    line_end = W - fw - 66
    b.append(f'<path d="M{line_x:.0f} 33 H{line_end:.0f}" stroke="{LINE}" stroke-width="1.2"/>')
    b.append(f'<path d="M{line_x:.0f} 33 H{line_end:.0f}" stroke="url(#neon)" stroke-width="1.6" '
             f'stroke-dasharray="80 2000" stroke-linecap="round">'
             f'<animate attributeName="stroke-dashoffset" values="80;-{line_end-line_x:.0f}" dur="3.4s" '
             f'begin="{i*0.35:.2f}s" repeatCount="indefinite"/></path>')
    b.append(f'<rect x="{W-fw-48:.0f}" y="20" width="{fw+24:.0f}" height="26" rx="13" fill="{SURF}" stroke="{LINE}"/>')
    b.append(t(W - fw - 36, 37.5, fn, "m4", 12, CYAN))
    return svg(W, H, "".join(b))


# ── 02 attention ───────────────────────────────────────────────────────────
def mix(c1, c2, k):
    a = [int(c1[i:i+2], 16) for i in (1, 3, 5)]; b_ = [int(c2[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a[i]+(b_[i]-a[i])*k):02X}" for i in range(3))


def heat(v):
    if v < .5:
        return mix(SURF2, VIOLET, v / .5 * .85)
    return mix(mix(SURF2, VIOLET, .85), CYAN, (v - .5) / .5)


def attention():
    rows, cols, A = C.ATTN_ROWS, C.ATTN_COLS, C.ATTN
    lw, top, cw, ch, gap = 190, 104, 70, 38, 6
    W = 1000
    gx = 32 + lw
    cw = (W - gx - 32 - (len(cols) - 1) * gap) / len(cols)
    H = top + len(rows) * (ch + gap) + 70
    b = [panel(W, H)]
    b.append(t(32, 40, "attention.weights", "m7", 15, BRIGHT))
    b.append(t(32 + advance("attention.weights", size=15) + 14, 40, "softmax( Q · K^T / sqrt(d) )", "m4", 13, MUTED))
    b.append(t(W - 32, 40, f"{len(rows)} queries  x  {len(cols)} keys", "m4", 12, MUTED, 'text-anchor="end"'))
    for j, c in enumerate(cols):
        x = gx + j * (cw + gap) + cw / 2
        b.append(t(x, top - 16, c, "m4", 11.5, DIM, 'text-anchor="middle"'))
    for i, r in enumerate(rows):
        y = top + i * (ch + gap)
        b.append(t(32, y + ch / 2 + 5, r, "m4", 13.5, TEXT))
        for j in range(len(cols)):
            v = A[i][j]
            x = gx + j * (cw + gap)
            delay = 0.2 + (i + j) * 0.06
            b.append(f'<g class="in" style="animation-delay:{delay:.2f}s">'
                     f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" rx="7" fill="{heat(v)}" '
                     f'opacity="{0.35 + 0.65*v:.2f}"/>')
            if v >= .8:
                b.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" rx="7" fill="none" '
                         f'stroke="{CYAN}" stroke-opacity=".5"/>')
            if v >= .6:
                b.append(t(x + cw / 2, y + ch / 2 + 4.5, f"{v:.2f}", "m7" if v >= .8 else "m4", 12,
                           BG if v >= .8 else BRIGHT, 'text-anchor="middle"'))
            b.append("</g>")
    # scanning query cursor
    gh = len(rows) * (ch + gap) - gap
    vals = ";".join(str(top + k * (ch + gap) - 3) for k in range(len(rows))) + f";{top-3}"
    b.append(f'<rect x="{gx-6}" y="{top-3}" width="{W-gx-26}" height="{ch+6}" rx="9" fill="none" stroke="{PINK}" '
             f'stroke-width="1.4" opacity=".8"><animate attributeName="y" values="{vals}" dur="{len(rows)*1.1:.1f}s" '
             f'calcMode="discrete" repeatCount="indefinite" begin="1.2s"/></rect>')
    b.append(f'<rect x="20" y="{top-3}" width="4" height="{ch+6}" rx="2" fill="{PINK}">'
             f'<animate attributeName="y" values="{vals}" dur="{len(rows)*1.1:.1f}s" calcMode="discrete" '
             f'repeatCount="indefinite" begin="1.2s"/></rect>')
    # legend
    ly = top + gh + 40
    b.append(t(32, ly + 4, "low", "m4", 11, MUTED))
    for k in range(40):
        b.append(f'<rect x="{68+k*4}" y="{ly-6}" width="4" height="10" fill="{heat(k/39)}"/>')
    b.append(t(236, ly + 4, "high", "m4", 11, MUTED))
    b.append(t(W - 32, ly + 4, "pink cursor = the query being attended right now", "m4", 11, MUTED, 'text-anchor="end"'))
    return svg(W, H, "".join(b))


# ── 03 tool calls ──────────────────────────────────────────────────────────
def toolcalls():
    W, lh, top = 1000, 40, 82
    H = top + len(C.TOOLS) * lh + 74
    b = [panel(W, H)]
    b.append(t(32, 40, "trace", "m7", 14, PINK))
    meta = f"agent={C.LOGIN}   tools={len(C.TOOLS)}   parallel=true"
    b.append(t(88, 40, meta, "m4", 13, DIM))
    b.append(f'<path d="M32 58 H{W-32}" stroke="{LINE}"/>')
    rnd = random.Random(11)
    for i, (fn, args) in enumerate(C.TOOLS):
        y = top + i * lh + 12
        d = 0.3 + i * 0.32
        g = [f'<g class="in" style="animation-delay:{d:.2f}s">']
        g.append(arrow(40, y - 4.5, MUTED))
        g.append(t(62, y, "tool_call", "m4", 12.5, MUTED))
        g.append(t(160, y, fn, "m7", 13.5, CYAN))
        x = 380
        g.append(t(x, y, "[", "m4", 13.5, DIM)); x += advance("[", size=13.5) + 2
        for k, a in enumerate(args):
            s = f'"{a}"'
            if x + advance(s, size=13.5) > W - 150:
                g.append(t(x, y, "...", "m4", 13.5, MUTED)); x += advance("...", size=13.5); break
            g.append(t(x, y, s, "m4", 13.5, GREEN if k % 2 == 0 else "#7EE0B5")); x += advance(s, size=13.5)
            if k < len(args) - 1:
                g.append(t(x, y, ",", "m4", 13.5, DIM)); x += advance(", ", size=13.5)
        g.append(t(x + 2, y, "]", "m4", 13.5, DIM))
        g.append("</g>")
        # spinner then check
        g.append(f'<g class="in" style="animation-delay:{d:.2f}s">'
                 f'<circle cx="{W-118}" cy="{y-5}" r="6" stroke="{LINE}" stroke-width="2" style="animation:hide 0s {d+0.55:.2f}s forwards"/>'
                 f'<circle cx="{W-118}" cy="{y-5}" r="6" stroke="{AMBER}" stroke-width="2" stroke-dasharray="10 30" '
                 f'style="opacity:1;animation:hide 0s {d+0.55:.2f}s forwards">'
                 f'<animateTransform attributeName="transform" type="rotate" from="0 {W-118} {y-5}" to="360 {W-118} {y-5}" '
                 f'dur=".6s" repeatCount="indefinite"/></circle></g>')
        g.append(f'<g class="in" style="animation-delay:{d+0.55:.2f}s">{check(W-124, y-5)}'
                 f'{t(W-32, y, f"{rnd.randint(4, 38)}ms", "m4", 12, MUTED, chr(32)+"text-anchor=\"end\"")}</g>')
        b.extend(g)
    fy = top + len(C.TOOLS) * lh + 30
    fd = 0.3 + len(C.TOOLS) * 0.32 + 0.6
    b.append(f'<path d="M32 {fy-26} H{W-32}" stroke="{LINE}"/>')
    b.append(f'<g class="in" style="animation-delay:{fd:.2f}s">{check(36, fy-5)}'
             f'{t(58, fy, f"{len(C.TOOLS)}/{len(C.TOOLS)} tools resolved", "m7", 13, GREEN)}'
             f'{t(58 + advance(f"{len(C.TOOLS)}/{len(C.TOOLS)} tools resolved", weight=700, size=13) + 18, fy, "0 errors  ·  exit 0", "m4", 13, DIM)}</g>')
    return svg(W, H, "".join(b), extra_css="@keyframes hide{to{opacity:0}}")


# ── 04 outputs (one card per repo so each can link) ────────────────────────
def wrap(text, width, size):
    words, lines, cur = text.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if advance(nxt, size=size) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def card(i, repo):
    W, H = 490, 178
    b = [panel(W, H, 16)]
    b.append(f'<clipPath id="cc"><rect width="{W}" height="{H}" rx="16"/></clipPath>'
             f'<rect x="0" y="0" width="{W}" height="3" fill="url(#neon)" opacity=".8" clip-path="url(#cc)"/>')
    b.append(t(24, 36, f"output[{i}]", "m4", 11.5, MUTED))
    if repo is None:
        b.append(t(24, 76, "awaiting first sync", "s7", 22, DIM))
        b.append(t(24, 104, "Run the 'profile' workflow once to render", "m4", 12.5, MUTED))
        b.append(t(24, 124, "your pinned repositories here.", "m4", 12.5, MUTED))
        return svg(W, H, "".join(b))
    name = repo["name"]
    size = 22
    while advance(name, "sans", 700, size) > W - 90 and size > 14:
        size -= 1
    b.append(t(24, 72, name, "s7", size, BRIGHT))
    b.append(f'<g class="breathe">{arrow(W-40, 66, CYAN)}</g>')
    desc = (repo.get("description") or "No description yet.").strip()
    lines = wrap(desc, W - 48, 13)
    if len(lines) > 2:
        lines = lines[:2]
        while advance(lines[1] + "...", size=13) > W - 48:
            lines[1] = lines[1].rsplit(" ", 1)[0]
        lines[1] += "..."
    for k, ln in enumerate(lines):
        b.append(t(24, 102 + k * 21, ln, "m4", 13, DIM))
    fy = H - 24
    x = 24
    lang = repo.get("primaryLanguage")
    if lang:
        b.append(f'<circle cx="{x+5}" cy="{fy-4.5}" r="5" fill="{lang.get("color") or DIM}"/>')
        b.append(t(x + 16, fy, lang["name"], "m4", 12, TEXT)); x += 16 + advance(lang["name"], size=12) + 22
    b.append(star(x + 6, fy - 4.5)); b.append(t(x + 17, fy, fmt(repo["stargazerCount"]), "m4", 12, TEXT))
    x += 17 + advance(fmt(repo["stargazerCount"]), size=12) + 22
    b.append(f'<path d="M{x+2} {fy-10} v4 a3 3 0 0 0 3 3 h4 a3 3 0 0 1 3 3 v1 M{x+12} {fy-10} v4 a3 3 0 0 1 -3 3" '
             f'stroke="{DIM}" stroke-width="1.5" fill="none" stroke-linecap="round"/>')
    b.append(t(x + 19, fy, fmt(repo["forkCount"]), "m4", 12, TEXT))
    return svg(W, H, "".join(b))


def pick_repos(data):
    if not data:
        return [None] * C.MAX_CARDS
    by_name = {r["name"]: r for r in data["repositories"]["nodes"]}
    if C.FEATURED_REPOS:
        chosen = [by_name[n] for n in C.FEATURED_REPOS if n in by_name]
    else:
        chosen = data["pinnedItems"]["nodes"] or [r for r in data["repositories"]["nodes"] if r["name"] != C.LOGIN]
    chosen = chosen[:C.MAX_CARDS]
    return chosen + [None] * (C.MAX_CARDS - len(chosen)) if chosen else [None] * C.MAX_CARDS


# ── 05 telemetry ───────────────────────────────────────────────────────────
def telemetry(data):
    W, H = 1000, 470
    b = [panel(W, H)]
    b.append(t(32, 40, "metrics", "m7", 14, PINK))
    b.append(t(100, 40, f"source=api.github.com/graphql   window=365d   user={C.LOGIN}", "m4", 13, DIM))
    if not data:
        b.append(t(W / 2, H / 2, "awaiting first sync", "s7", 26, DIM, 'text-anchor="middle"'))
        b.append(t(W / 2, H / 2 + 30, "the profile workflow fills this panel with live numbers", "m4", 13, MUTED,
                   'text-anchor="middle"'))
        return svg(W, H, "".join(b))

    cc = data["contributionsCollection"]
    weeks = cc["contributionCalendar"]["weeks"]
    cur, longest = streaks(weeks)
    stars = sum(r["stargazerCount"] for r in data["repositories"]["nodes"])
    total = cc["contributionCalendar"]["totalContributions"]
    kpis = [("contributions", fmt(total), "last 365 days", CYAN),
            ("current streak", f"{cur}d", "days in a row", VIOLET),
            ("longest streak", f"{longest}d", "past 365 days", PINK),
            ("pull requests", fmt(cc["totalPullRequestContributions"]), "opened", GREEN),
            ("stars earned", fmt(stars), f'{data["repositories"]["totalCount"]} public repos', AMBER)]
    kw, kg, ky = (W - 64 - 4 * 14) / 5, 14, 62
    for i, (lab, val, sub, col) in enumerate(kpis):
        x = 32 + i * (kw + kg)
        b.append(f'<g class="up" style="animation-delay:{0.15+i*0.1:.2f}s">'
                 f'<rect x="{x:.1f}" y="{ky}" width="{kw:.1f}" height="96" rx="12" fill="{SURF}" stroke="{LINE}"/>'
                 f'<rect x="{x+16:.1f}" y="{ky+18}" width="14" height="3" rx="1.5" fill="{col}"/>'
                 f'{t(x+38, ky+23, lab.upper(), "m4", 10.5, MUTED, chr(32)+"letter-spacing=\"1\"")}'
                 f'{t(x+16, ky+62, val, "s7", 32, BRIGHT)}'
                 f'{t(x+16, ky+83, sub, "m4", 11, DIM)}</g>')

    # weekly waveform
    vals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks][-52:]
    gx, gy, gw, gh = 32, 200, W - 64, 150
    peak = max(vals) or 1
    b.append(t(gx, gy - 6, "contributions per week, as a signal", "m4", 12, DIM))
    for k in range(4):
        yy = gy + 12 + gh * k / 3
        b.append(f'<path d="M{gx} {yy:.1f} H{gx+gw}" stroke="{LINE}" stroke-dasharray="2 5"/>')
    n = len(vals)
    pts = [(gx + gw * i / (n - 1), gy + 12 + gh - gh * v / peak) for i, v in enumerate(vals)]

    def smooth(p):
        d = f"M{p[0][0]:.1f} {p[0][1]:.1f}"
        for i in range(1, len(p)):
            x0, y0 = p[i-1]; x1, y1 = p[i]; mx = (x0 + x1) / 2
            d += f" C{mx:.1f} {y0:.1f} {mx:.1f} {y1:.1f} {x1:.1f} {y1:.1f}"
        return d
    line = smooth(pts)
    base = gy + 12 + gh
    b.append(f'<path d="{line} L{gx+gw} {base} L{gx} {base} Z" fill="url(#area)" class="in" style="animation-delay:1.4s"/>')
    b.append(f'<path d="{line}" stroke="url(#neon)" stroke-width="2.2" stroke-linecap="round" pathLength="1" '
             f'stroke-dasharray="1 1" stroke-dashoffset="1">'
             f'<animate attributeName="stroke-dashoffset" values="1;0" dur="1.8s" begin=".5s" fill="freeze" '
             f'calcMode="spline" keySplines=".3 .6 .2 1" keyTimes="0;1"/></path>')
    pi = vals.index(peak)
    px, py = pts[pi]
    b.append(f'<g class="in" style="animation-delay:2.2s"><circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{BG}" stroke="{PINK}" stroke-width="2"/>'
             f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11" stroke="{PINK}" opacity=".35" class="breathe"/>'
             f'{t(px + (10 if px < W-160 else -10), py - 12, f"peak  {peak}/wk", "m7", 11.5, PINK, chr(32)+("" if px < W-160 else "text-anchor=\"end\""))}</g>')
    # scan line
    b.append(f'<rect x="{gx}" y="{gy+8}" width="1.5" height="{gh+6}" fill="{CYAN}" opacity=".5">'
             f'<animate attributeName="x" values="{gx};{gx+gw}" dur="6s" begin="2.4s" repeatCount="indefinite"/></rect>')
    # month labels
    seen = set()
    for i, w in enumerate(weeks[-52:]):
        d0 = w["contributionDays"][0]["date"]
        m = d0[:7]
        if m not in seen and dt.date.fromisoformat(d0).day <= 7:
            seen.add(m)
            b.append(t(gx + gw * i / (n - 1), base + 20, dt.date.fromisoformat(d0).strftime("%b").lower(),
                       "m4", 10.5, MUTED, 'text-anchor="middle"'))

    # language composition
    agg = {}
    for r in data["repositories"]["nodes"]:
        for e in (r.get("languages") or {}).get("edges", []):
            nm = e["node"]["name"]
            agg.setdefault(nm, [0, e["node"].get("color") or DIM])[0] += e["size"]
    langs = sorted(agg.items(), key=lambda kv: -kv[1][0])[:6]
    tot = sum(v[0] for _, v in langs) or 1
    ly = H - 52
    b.append(t(gx, ly - 14, "bytes by language", "m4", 12, DIM))
    x = gx
    lw_total = 360
    for k, (nm, (sz, col)) in enumerate(langs):
        w = lw_total * sz / tot
        b.append(f'<rect x="{x:.1f}" y="{ly}" width="{max(w-2,1):.1f}" height="10" rx="3" fill="{col}" '
                 f'class="in" style="animation-delay:{1.6+k*0.08:.2f}s"/>')
        x += w
    lx = gx + lw_total + 30
    for k, (nm, (sz, col)) in enumerate(langs):
        label = f"{nm} {100*sz/tot:.0f}%"
        lwid = advance(label, size=11.5) + 30
        if lx + lwid > W - 32:
            break
        b.append(f'<circle cx="{lx+4}" cy="{ly+5}" r="4" fill="{col}"/>')
        b.append(t(lx + 13, ly + 9, nm, "m4", 11.5, TEXT))
        b.append(t(lx + 13 + advance(nm + " ", size=11.5), ly + 9, f"{100*sz/tot:.0f}%", "m4", 11.5, MUTED))
        lx += lwid
    stamp = now_local().strftime(f"sampled %Y-%m-%d %H:%M {C.TIMEZONE_LABEL}")
    b.append(t(W - 32, 40, stamp, "m4", 12, MUTED, 'text-anchor="end"'))
    defs = (f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></linearGradient>')
    return svg(W, H, "".join(b), defs=defs)


# ── 06 footer ──────────────────────────────────────────────────────────────
def footer():
    W, H = 1000, 120
    b = [panel(W, H, 16)]
    b.append(t(W / 2, 46, "EOF", "s7", 30, "url(#neon)", 'text-anchor="middle" letter-spacing="10"'))
    msg = "process exited with code 0  ·  thanks for reading the trace"
    b.append(t(W / 2, 80, msg, "m4", 12.5, MUTED, 'text-anchor="middle"'))
    mw = advance(msg, size=12.5)
    b.append(f'<rect x="{W/2 + mw/2 + 6:.1f}" y="69" width="7" height="14" fill="{CYAN}" class="blink"/>')
    b.append(f'<path d="M{W/2-60} 100 H{W/2+60}" stroke="url(#neon)" stroke-width="1.5" stroke-linecap="round" opacity=".6"/>')
    return svg(W, H, "".join(b))


def main():
    mode = "demo" if "--demo" in sys.argv else "live"
    data = demo() if mode == "demo" else fetch()
    OUT.mkdir(exist_ok=True)
    files = {"hero.svg": hero(), "attention.svg": attention(), "toolcalls.svg": toolcalls(),
             "telemetry.svg": telemetry(data), "footer.svg": footer()}
    for i, s in enumerate(STAGES):
        files[f"stage_{s[0]}.svg"] = stage(i, *s)
    for i, r in enumerate(pick_repos(data)):
        files[f"card_{i}.svg"] = card(i, r)
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    links = [r["url"] if r else f"https://github.com/{C.LOGIN}?tab=repositories" for r in pick_repos(data)]
    readme = ROOT.parent / "README.md"
    if readme.exists():
        cells = "\n".join(
            f'<a href="{u}"><img src="assets/card_{i}.svg" width="49%" alt="output {i}" /></a>'
            for i, u in enumerate(links))
        txt = readme.read_text(encoding="utf-8")
        txt = re.sub(r"(<!-- outputs:start -->).*?(<!-- outputs:end -->)",
                     lambda m: f"{m.group(1)}\n{cells}\n{m.group(2)}", txt, flags=re.S)
        readme.write_text(txt, encoding="utf-8")
    print(f"[{mode}{'' if data else ', no data'}] wrote {len(files)} files to {OUT}")


if __name__ == "__main__":
    main()
