#!/usr/bin/env python3
"""Render the Awesome JEV gallery from the files in this directory.

    python3 site/build.py            -> site/dist/ (index.html, assets/)

entries.json holds the entries that have a picture (one card each), blurbs.json the one-line
description each card shows (keyed by slug), sections.json the section labels and hues, tiles/ the 16:10 pictures, avatars/ the owners' GitHub avatars. Star counts are
read from the GitHub API at build time (GITHUB_TOKEN or GH_TOKEN raises the rate limit; without one
the anonymous limit of 60 requests an hour still covers a build) and the footer says when. The
GitHub Actions workflow in .github/workflows/site.yml runs this daily and on every push to main.
Only the standard library is needed.
"""
import datetime, html, json, os, shutil, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dist")
REPO = "https://github.com/OmniJev/awesome-jev-gallery"
SITE = "https://omnijev.github.io/awesome-jev-gallery/"
TAGLINE = "Papers, open models and evaluations behind System One models and Jev."
FONTS = ("DepartureMono-Regular.otf", "PressStart2P-Regular.ttf")
# the Awesome JEV mark: a pixel bolt on the same 16-wide monitor as the OneJev eye
LOGO = ["################",
        "#..............#",
        "#.......pmm....#",
        "#......pmm.....#",
        "#.....pmm......#",
        "#....pmmmmm....#",
        "#.......pmm....#",
        "#......pmm.....#",
        "#.....mm.......#",
        "#....m.........#",
        "#..............#",
        "################",
        "......####......"]
LOGO_INK = {"m": "#d45bb6", "p": "#f386a1"}


def logo(animate=False):
    """The mark as inline SVG; the frame takes currentColor, animate=True draws the bolt pixel by pixel."""
    sq = lambda x, y: f"M{x} {y}h1v1h-1z"
    frame = "".join(sq(x, y) for y, r in enumerate(LOGO) for x, ch in enumerate(r) if ch == "#")
    bolt = [(x, y, ch) for y, r in enumerate(LOGO) for x, ch in enumerate(r) if ch in LOGO_INK]
    if animate:
        inner = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{LOGO_INK[ch]}" style="--d:{i}"/>'
                        for i, (x, y, ch) in enumerate(bolt))
    else:
        inner = "".join(f'<path fill="{c}" d="{"".join(sq(x, y) for x, y, ch in bolt if ch == k)}"/>' for k, c in LOGO_INK.items())
    return (f'<svg class="px" viewBox="0 0 16 13" aria-hidden="true"><path fill="currentColor" d="{frame}"/>'
            f'{inner}</svg>')


def esc(s):
    return html.escape(s or "", quote=True)


def live_stars(repos, max_age=3600):
    """Star counts from the GitHub API, cached for an hour in stars.json next to this file."""
    path = os.path.join(HERE, "stars.json")
    cache = json.load(open(path)) if os.path.exists(path) else {}
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    now = time.time()
    out, fetched = {}, 0
    for repo in repos:
        c = cache.get(repo)
        if c and now - c["t"] < max_age:
            out[repo] = c["stars"]
            continue
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={
                "Accept": "application/vnd.github+json", "User-Agent": "awesome-jev-gallery",
                **({"Authorization": "Bearer " + tok} if tok else {})})
            r = json.load(urllib.request.urlopen(req, timeout=30))
            out[repo] = r["stargazers_count"]
            cache[repo] = {"stars": r["stargazers_count"], "t": now}
            fetched += 1
        except Exception as ex:
            print(f"  stars {repo}: {ex}")
            out[repo] = c["stars"] if c else None
    json.dump(cache, open(path, "w"), indent=1)
    print(f"stars: {fetched} fetched, {len(repos) - fetched} from cache")
    return out


def build():
    entries = json.load(open(os.path.join(HERE, "entries.json"), encoding="utf-8"))
    sections = json.load(open(os.path.join(HERE, "sections.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(HERE, "meta.json"), encoding="utf-8"))
    blurbs = json.load(open(os.path.join(HERE, "blurbs.json"), encoding="utf-8"))
    for e in entries:
        e["blurb"] = blurbs.get(e["slug"])
        if not e["blurb"]:
            print(f"  no blurb for {e['slug']}, the card shows its long description")
    fresh = live_stars(sorted({e["repo"] for e in entries if e.get("repo")}))
    for e in entries:
        if e.get("repo") and fresh.get(e["repo"]) is not None:
            e["stars"] = fresh[e["repo"]]
    counts = {}
    for e in entries:
        counts[e["section"]] = counts.get(e["section"], 0) + 1
    for s in sections:
        s["n"] = counts.get(s["key"], 0)
    sections = [s for s in sections if s["n"]]

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    for d in ("tiles", "avatars"):
        shutil.copytree(os.path.join(HERE, d), os.path.join(OUT, "assets", d))
    for f in ("gallery.css", "gallery.js", "favicon.svg", "og.png"):
        shutil.copy(os.path.join(HERE, f), os.path.join(OUT, "assets", f))
    shutil.copytree(os.path.join(HERE, "fonts"), os.path.join(OUT, "assets", "fonts"))
    hues = ("\n:root{" + "".join(f"--s-{s['key']}:{s['hue'][0]};" for s in sections) + "}"
            "\n:root[data-theme=\"dark\"]{" + "".join(f"--s-{s['key']}:{s['hue'][1]};" for s in sections) + "}\n")
    with open(os.path.join(OUT, "assets", "gallery.css"), "a", encoding="utf-8") as f:
        f.write(hues)

    n_readme = meta["readme_entries"]
    built = datetime.datetime.now(datetime.timezone.utc)
    data = {"built": built.isoformat(timespec="minutes"), "sections": sections, "entries": entries}
    pills = (f'<button type="button" data-sec="" aria-pressed="true">All <b>{len(entries)}</b></button>' + "".join(
        f'<button type="button" data-sec="{s["key"]}" aria-pressed="false" style="--sc:var(--s-{s["key"]})"><i></i>{esc(s["chip"])} <b>{s["n"]}</b></button>'
        for s in sections))
    sorts = "".join(f'<button type="button" data-sort="{k}" aria-pressed="false">{k}</button>'
                    for k in ("curated", "stars", "newest", "random"))
    body = f"""<header class="top">
  <a class="brand" href="{SITE}">{logo()}<span class="w">Awesome JEV</span></a>
  <nav><a href="{REPO}#readme" target="_blank" rel="noopener">Full list</a><button id="theme" type="button" aria-label="Switch colour theme">Dark</button><a class="hot" href="{REPO}" target="_blank" rel="noopener">GitHub</a></nav>
</header>
<section class="wrap banner">
  <div class="logo">{logo(animate=True)}</div>
  <div>
    <h1>Awesome JEV</h1>
    <p class="sub" id="sub">{esc(TAGLINE)}</p>
    <p class="meta">Every card opens its source <b>&gt;</b> the <a href="{REPO}#readme">README</a> holds the full list of {n_readme} entries.</p>
  </div>
</section>
<div class="wrap controls">
  <div class="tabs" id="pills">{pills}</div>
  <div class="tools">
    <label class="search"><span>find</span><input type="search" id="q" placeholder="press /" aria-label="Search"></label>
    <div class="grp"><span>sort</span><div class="tabs" id="sort">{sorts}</div></div>
    <div class="grp cols"><span>per row</span><button id="colDec" type="button" aria-label="Fewer per row">-</button><b id="colN">3</b><button id="colInc" type="button" aria-label="More per row">+</button></div>
    <span class="count" id="count"></span>
  </div>
</div>
<main class="wrap"><div id="grid"></div><div class="empty" id="empty" hidden>Nothing matches.</div></main>
<footer>
  <div class="foot-in">
    <div class="foot-logo">{logo()}</div>
    <div class="fwin">
      <div class="win-t"><span class="t">awesome-jev.txt</span></div>
      <div class="win-b">{meta["readme_line"]}<br>Curated at <a href="{REPO}">OmniJev/awesome-jev-gallery</a>, CC BY 4.0.<br>Star counts read from GitHub on {built:%d %B %Y}, {built:%H:%M} UTC.</div>
    </div>
  </div>
</footer>
<script id="data" type="application/json">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>"""

    desc = (f"System One models and typed decisions: {n_readme} papers, open-source rebuilds, independent "
            "evaluations and software built on Jev, each card with a picture of what is behind the link.")
    ld = json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": "Awesome JEV",
                     "description": desc, "url": SITE, "isPartOf": {"@type": "WebSite", "name": "Awesome JEV", "url": SITE}})
    preload = "\n".join(f'<link rel="preload" href="assets/fonts/{f}" as="font" type="font/{f.rsplit(".", 1)[1]}" crossorigin>'
                        for f in FONTS)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Awesome JEV: System One models and typed decisions</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}">
<meta property="og:type" content="website">
<meta property="og:title" content="Awesome JEV">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE}">
<meta property="og:image" content="{SITE}assets/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}assets/og.png">
<meta name="theme-color" content="#1e1e1e">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
{preload}
<link rel="stylesheet" href="assets/gallery.css">
<script type="application/ld+json">{ld}</script>
</head>
<body>
{body}
<script src="assets/gallery.js"></script>
</body>
</html>
"""
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}sitemap.xml\n")
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE}</loc><lastmod>{built:%Y-%m-%d}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n'
        "</urlset>\n")
    print(f"{OUT}/index.html: {len(entries)} cards, {len(sections)} sections")


if __name__ == "__main__":
    build()
