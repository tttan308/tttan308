import json
import math
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BG = "#0d1117"
PANEL = "#12161d"
VIOLET = "#9692ff"
BLUE = "#0078d4"
ACCENT = "#8b86ff"
DIM = "#8b949e"
TEXT = "#e6edf3"
FONT = "'SF Mono','JetBrains Mono',Menlo,Consolas,monospace"
EXCLUDED_LANGS = {"HTML", "CSS", "Handlebars", "TSQL"}
FIRST_YEAR = 2021


def gql(query):
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)["data"]["viewer"]


def fetch():
    today = date.today()
    years = {}
    for year in range(FIRST_YEAR, today.year + 1):
        data = gql(
            '{viewer{contributionsCollection(from:"%d-01-01T00:00:00Z",to:"%d-12-31T23:59:59Z")'
            "{contributionCalendar{totalContributions}}}}" % (year, year)
        )
        years[year] = data["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    recent = gql(
        "{viewer{contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}"
        "}}"
    )["contributionsCollection"]["contributionCalendar"]
    repos = gql(
        "{viewer{repositories(ownerAffiliations:OWNER,first:100){totalCount nodes{isFork createdAt primaryLanguage{name} "
        "languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"
    )["repositories"]
    languages = {}
    timeline = {}
    for repo in repos["nodes"]:
        if repo["isFork"]:
            continue
        entry = timeline.setdefault(int(repo["createdAt"][:4]), {"repos": 0, "langs": {}})
        entry["repos"] += 1
        primary = (repo["primaryLanguage"] or {}).get("name")
        if primary and primary not in EXCLUDED_LANGS:
            entry["langs"][primary] = entry["langs"].get(primary, 0) + 1
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in EXCLUDED_LANGS:
                languages[name] = languages.get(name, 0) + edge["size"]
    return {
        "years": years,
        "last12": recent["totalContributions"],
        "days": [d for w in recent["weeks"] for d in w["contributionDays"]],
        "languages": sorted(languages.items(), key=lambda kv: -kv[1])[:7],
        "timeline": {
            year: {
                "repos": entry["repos"],
                "top": max(entry["langs"], key=entry["langs"].get) if entry["langs"] else "-",
            }
            for year, entry in timeline.items()
        },
        "average_this_year": years[today.year] / today.timetuple().tm_yday,
    }


def ease(t):
    return 1 - (1 - t) ** 3


def svg(width, height, body, defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"<defs>"
        f'<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        f'<feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
        f'<linearGradient id="barv" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
        f'<linearGradient id="wide" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{width}" y2="0"><stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>'
        f"{defs}</defs>"
        f'<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>'
        f"{body}</svg>"
    )


def counter(x, y, value, label, delay, size=40, suffix=""):
    frames = 28
    duration = 1.6
    parts = []
    for i in range(frames + 1):
        shown = round(value * ease(i / frames))
        begin = delay + duration * i / frames
        end = delay + duration * (i + 1) / frames
        text = f"{shown:,}{suffix}"
        last = i == frames
        parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="700" fill="url(#wide)" '
            f'filter="url(#glow)" visibility="hidden">{text}'
            f'<set attributeName="visibility" to="visible" begin="{begin:.3f}s" fill="freeze"/>'
            + ("" if last else f'<set attributeName="visibility" to="hidden" begin="{end:.3f}s" fill="freeze"/>')
            + "</text>"
        )
    parts.append(
        f'<text x="{x}" y="{y + 26}" font-family="{FONT}" font-size="10" letter-spacing="1.5" fill="{DIM}">{label}</text>'
    )
    return "".join(parts)


def build_counters(data):
    total = sum(data["years"].values())
    days = data["days"]
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    width, height = 880, 150
    cell = width / 4
    panels = []
    items = [
        (total, "ALL-TIME CONTRIBUTIONS", ""),
        (data["last12"], "CONTRIBUTIONS / 12 MO", ""),
        (longest, "LONGEST STREAK / DAYS", ""),
        (round(data["average_this_year"]), f"AVG PER DAY / {max(data['years'])}", ""),
    ]
    for i, (value, label, suffix) in enumerate(items):
        x = i * cell + 28
        panels.append(counter(x, 88, value, label, 0.2 + i * 0.25, suffix=suffix))
        if i:
            panels.append(
                f'<line x1="{i * cell}" y1="40" x2="{i * cell}" y2="118" stroke="#30363d" stroke-width="1"/>'
            )
    scan = (
        f'<rect x="0" y="0" width="{width}" height="2" fill="url(#wide)" opacity="0.7" filter="url(#glow)">'
        f'<animate attributeName="y" values="0;{height};0" dur="6s" repeatCount="indefinite"/></rect>'
    )
    border = (
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="10" fill="none" stroke="url(#wide)" stroke-width="1.5">'
        f'<animate attributeName="stroke-opacity" values="0.25;1;0.25" dur="3s" repeatCount="indefinite"/></rect>'
    )
    head = f'<text x="28" y="26" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}">[ LIVE TELEMETRY / tttan308 ]</text>'
    return svg(width, height, border + head + "".join(panels) + scan)


def build_growth(data):
    years = data["years"]
    width, height = 880, 330
    left, bottom, top = 60, 250, 90
    peak = max(years.values())
    slot = (width - left - 40) / len(years)
    bar_w = slot * 0.5
    body = [
        f'<text x="28" y="30" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}">[ EVOLUTION / PER YEAR ]</text>',
        f'<text x="28" y="52" font-family="{FONT}" font-size="13" fill="{DIM}">{years[FIRST_YEAR + 1]:,} in {FIRST_YEAR + 1} to {years[max(years)]:,} in {max(years)} so far</text>',
        f'<line x1="{left - 10}" y1="{bottom}" x2="{width - 20}" y2="{bottom}" stroke="#30363d"/>',
    ]
    era_start = left + (len(years) - 2) * slot + 10
    era_end = left + len(years) * slot - 10
    body.append(
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="2s" dur="0.6s" fill="freeze"/>'
        f'<path d="M{era_start:.0f},50 V44 H{era_end:.0f} V50" fill="none" stroke="url(#wide)" stroke-width="1.5"/>'
        f'<text x="{(era_start + era_end) / 2:.0f}" y="36" text-anchor="middle" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}">AI AGENT ERA</text></g>'
    )
    for i, (year, count) in enumerate(years.items()):
        h = max(2, (bottom - top) * count / peak)
        x = left + i * slot + (slot - bar_w) / 2
        begin = 0.3 + i * 0.25
        body.append(
            f'<rect x="{x:.1f}" y="{bottom}" width="{bar_w:.1f}" height="0" rx="3" fill="url(#barv)" filter="url(#glow)">'
            f'<animate attributeName="height" from="0" to="{h:.1f}" begin="{begin}s" dur="0.9s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/>'
            f'<animate attributeName="y" from="{bottom}" to="{bottom - h:.1f}" begin="{begin}s" dur="0.9s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></rect>'
        )
        label = f"{year}" + (" YTD" if year == max(years) else "")
        body.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{bottom + 22}" text-anchor="middle" font-family="{FONT}" font-size="12" fill="{DIM}">{label}</text>'
        )
        info = data["timeline"].get(year, {"repos": 0, "top": "-"})
        body.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{bottom + 40}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{DIM}">{info["repos"]} new repos</text>'
            f'<text x="{x + bar_w / 2:.1f}" y="{bottom + 56}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{VIOLET}">{info["top"]}</text>'
        )
        body.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{bottom - h - 10:.1f}" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="700" fill="{TEXT}" opacity="0">{count:,}'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin + 0.8}s" dur="0.4s" fill="freeze"/></text>'
        )
    return svg(width, height, "".join(body))


def build_languages(data):
    langs = data["languages"]
    total = sum(size for _, size in langs)
    width = 880
    row = 34
    height = 70 + row * len(langs)
    bar_x, bar_w = 170, 560
    body = [
        f'<text x="28" y="30" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}">[ LANGUAGE DNA / BY BYTES OF CODE ]</text>'
    ]
    for i, (name, size) in enumerate(langs):
        pct = size / total * 100
        y = 62 + i * row
        w = bar_w * size / langs[0][1]
        begin = 0.3 + i * 0.15
        body.append(
            f'<text x="28" y="{y + 13}" font-family="{FONT}" font-size="13" fill="{TEXT}">{name}</text>'
            f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="16" rx="3" fill="{PANEL}"/>'
            f'<rect x="{bar_x}" y="{y}" width="0" height="16" rx="3" fill="url(#bar)" filter="url(#glow)">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{begin}s" dur="1s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></rect>'
            f'<text x="{bar_x + bar_w + 16}" y="{y + 13}" font-family="{FONT}" font-size="13" font-weight="700" fill="{TEXT}" opacity="0">{pct:.1f}%'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin + 0.9}s" dur="0.4s" fill="freeze"/></text>'
        )
    return svg(width, height, "".join(body))


def build_heatmap(data):
    days = data["days"]
    peak = max(d["contributionCount"] for d in days)
    cell, gap = 12, 3
    cols = (len(days) + 6) // 7
    width = 28 + cols * (cell + gap) + 28
    height = 56 + 7 * (cell + gap) + 40
    body = [
        f'<text x="28" y="30" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}">[ ACTIVITY MATRIX / LAST 12 MONTHS ]</text>'
    ]
    for i, d in enumerate(days):
        col, row = divmod(i, 7)
        count = d["contributionCount"]
        x = 28 + col * (cell + gap)
        y = 50 + row * (cell + gap)
        if count == 0:
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="#161b22"/>')
            continue
        level = min(1.0, (count / peak) ** 0.5)
        opacity = 0.25 + 0.75 * level
        begin = 0.2 + col * 0.04
        body.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="url(#wide)" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="{opacity:.2f}" begin="{begin:.2f}s" dur="0.5s" fill="freeze"/></rect>'
        )
    legend_y = 50 + 7 * (cell + gap) + 16
    body.append(
        f'<text x="28" y="{legend_y}" font-family="{FONT}" font-size="11" fill="{DIM}">less</text>'
    )
    for i in range(5):
        body.append(
            f'<rect x="{62 + i * 16}" y="{legend_y - 10}" width="12" height="12" rx="2" fill="{VIOLET}" opacity="{0.25 + 0.75 * i / 4:.2f}"/>'
        )
    body.append(
        f'<text x="152" y="{legend_y}" font-family="{FONT}" font-size="11" fill="{DIM}">more</text>'
    )
    return svg(width, height, "".join(body))


TAGLINES = [
    "building agents that actually ship",
    "wiring Claude into the whole Mac",
    "automating helpdesk with AI agents",
    "learning in public, shipping in private",
]
NODES = [
    ("MCP", -90),
    ("CLAUDE CODE", -18),
    ("HELPDESK AI", 54),
    ("GRAPHRAG", 126),
    ("MAC CONTROL", 198),
]


def cycle_opacity(index, count, duration):
    start = index / count
    end = (index + 1) / count
    fade = 0.02
    points = [(0, 0), (start, 0), (start + fade, 1), (end - fade, 1), (end, 0), (1, 0)]
    cleaned = []
    for t, v in points:
        if cleaned and abs(cleaned[-1][0] - t) < 1e-9:
            cleaned[-1] = (t, max(v, cleaned[-1][1]) if t == 0 else v)
        else:
            cleaned.append((t, v))
    keytimes = ";".join(f"{t:.3f}" for t, _ in cleaned)
    values = ";".join(str(v) for _, v in cleaned)
    return f'<animate attributeName="opacity" values="{values}" keyTimes="{keytimes}" dur="{duration}s" repeatCount="indefinite"/>'


def build_hero(data):
    width, height = 880, 280
    cx, cy, rx, ry = 700, 140, 120, 95
    defs = (
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1" fill="{VIOLET}" opacity="0.18"/></pattern>'
    )
    body = [
        f'<rect width="{width}" height="{height}" rx="10" fill="url(#dots)"/>',
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="10" fill="none" stroke="url(#wide)" stroke-width="1.5">'
        f'<animate attributeName="stroke-opacity" values="0.25;1;0.25" dur="3s" repeatCount="indefinite"/></rect>',
        f'<circle cx="{cx}" cy="{cy}" r="{rx + 10}" fill="none" stroke="url(#wide)" stroke-width="1" stroke-dasharray="3 9" opacity="0.5">'
        f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="40s" repeatCount="indefinite"/></circle>',
    ]
    for i, (label, angle) in enumerate(NODES):
        nx = cx + rx * math.cos(math.radians(angle))
        ny = cy + ry * math.sin(math.radians(angle))
        above = math.sin(math.radians(angle)) < -0.9
        ly = ny - 16 if above else ny + 26
        body.append(
            f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="url(#wide)" stroke-width="1.2" stroke-dasharray="4 6" opacity="0.7">'
            f'<animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite"/></line>'
            f'<circle r="2.6" fill="{TEXT}" filter="url(#glow)"><animateMotion path="M{cx},{cy} L{nx:.1f},{ny:.1f}" dur="{2 + i * 0.45:.2f}s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="7" fill="{BG}" stroke="{VIOLET}" stroke-width="2" filter="url(#glow)">'
            f'<animate attributeName="r" values="7;9;7" dur="{2.4 + i * 0.3:.1f}s" repeatCount="indefinite"/></circle>'
            f'<text x="{nx:.1f}" y="{ly:.1f}" text-anchor="middle" font-family="{FONT}" font-size="10" letter-spacing="1.5" fill="{TEXT}">{label}</text>'
        )
    body.append(
        f'<circle cx="{cx}" cy="{cy}" r="26" fill="{BG}" stroke="url(#wide)" stroke-width="2.5" filter="url(#glow)"/>'
        f'<circle cx="{cx}" cy="{cy}" r="26" fill="none" stroke="{VIOLET}" stroke-width="1">'
        f'<animate attributeName="r" values="26;48;26" dur="3s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0.8;0;0.8" dur="3s" repeatCount="indefinite"/></circle>'
        f'<text x="{cx}" y="{cy + 3}" text-anchor="middle" font-family="{FONT}" font-size="9" font-weight="700" letter-spacing="1.5" fill="url(#wide)">AGENT</text>'
    )
    body.append(
        f'<text x="40" y="58" font-family="{FONT}" font-size="11" letter-spacing="3" fill="{ACCENT}" opacity="0">[ AI AGENT BUILDER ]'
        f'<animate attributeName="opacity" from="0" to="1" begin="0.2s" dur="0.6s" fill="freeze"/></text>'
        f'<text x="40" y="112" font-family="{FONT}" font-size="44" font-weight="700" fill="url(#wide)" filter="url(#glow)" opacity="0">TRẦN THÁI TÂN'
        f'<animate attributeName="opacity" from="0" to="1" begin="0.5s" dur="0.9s" fill="freeze"/></text>'
        f'<text x="40" y="142" font-family="{FONT}" font-size="12" letter-spacing="2" fill="{DIM}" opacity="0">HO CHI MINH CITY / HCMUS / ON GITHUB SINCE {FIRST_YEAR}'
        f'<animate attributeName="opacity" from="0" to="1" begin="1s" dur="0.6s" fill="freeze"/></text>'
    )
    duration = 4 * len(TAGLINES)
    for i, line in enumerate(TAGLINES):
        body.append(
            f'<text x="40" y="204" font-family="{FONT}" font-size="16" fill="{TEXT}" opacity="0">'
            f'<tspan fill="{VIOLET}">$ </tspan>{line}{cycle_opacity(i, len(TAGLINES), duration)}</text>'
        )
    return svg(width, height, "".join(body), defs)


def main():
    data = fetch()
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "hero.svg").write_text(build_hero(data))
    (ASSETS / "counters.svg").write_text(build_counters(data))
    (ASSETS / "growth.svg").write_text(build_growth(data))
    (ASSETS / "languages.svg").write_text(build_languages(data))
    (ASSETS / "activity.svg").write_text(build_heatmap(data))
    print(json.dumps({"years": data["years"], "last12": data["last12"], "languages": data["languages"]}, indent=2))


main()
