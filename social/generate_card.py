"""
Generates card.svg and formation.svg from a GitHub user's real public stats.

Requires:
  - GITHUB_TOKEN env var (in Actions, secrets.GITHUB_TOKEN works fine for public data)
  - GITHUB_USERNAME env var (e.g. "prasanga101")

Run locally:
  GITHUB_TOKEN=ghp_xxx GITHUB_USERNAME=prasanga101 python generate_card.py
"""

import os
import sys
import requests

TOKEN = os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GITHUB_USERNAME", "prasanga101")

if not TOKEN:
    sys.exit("Set GITHUB_TOKEN before running.")

REST_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def rest(path, params=None):
    r = requests.get(f"https://api.github.com{path}", headers=REST_HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def graphql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        headers=GQL_HEADERS,
        json={"query": query, "variables": variables},
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def clamp(n, lo=40, hi=99):
    return max(lo, min(hi, round(n)))


def fetch_profile():
    user = rest(f"/users/{USERNAME}")
    repos = rest(f"/users/{USERNAME}/repos", params={"per_page": 100})
    total_stars = sum(r["stargazers_count"] for r in repos)
    languages = {}
    for r in repos:
        if r.get("language"):
            languages[r["language"]] = languages.get(r["language"], 0) + 1
    top_repo_stars = max((r["stargazers_count"] for r in repos), default=0)

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          contributionCalendar { totalContributions }
        }
        pinnedItems(first: 6, types: [REPOSITORY]) {
          nodes {
            ... on Repository {
              name
              description
              stargazerCount
              primaryLanguage { name }
            }
          }
        }
      }
    }
    """
    gql = graphql(query, {"login": USERNAME})["user"]
    contrib = gql["contributionsCollection"]
    pinned = [n for n in gql["pinnedItems"]["nodes"] if n]

    return {
        "login": user["login"],
        "name": user.get("name") or user["login"],
        "followers": user["followers"],
        "following": user["following"],
        "public_repos": user["public_repos"],
        "avatar_url": user["avatar_url"],
        "total_stars": total_stars,
        "languages": languages,
        "commits": contrib["totalCommitContributions"],
        "prs": contrib["totalPullRequestContributions"],
        "issues": contrib["totalIssueContributions"],
        "contributions": contrib["contributionCalendar"]["totalContributions"],
        "top_repo_stars": top_repo_stars,
        "pinned": pinned,
    }


def download_avatar(url, dest="avatar.jpg"):
    r = requests.get(url)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)


def fetch_avatar_data_uri(url):
    import base64
    r = requests.get(url)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "image/png").split(";")[0]
    b64 = base64.b64encode(r.content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


def bar(x, y, w, value, max_value, fill="#f0d9a8", track="#4a3d28"):
    pct = 0 if max_value == 0 else min(1, value / max_value)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="3" rx="1.5" fill="{track}"/>'
        f'<rect x="{x}" y="{y}" width="{round(w * pct)}" height="3" rx="1.5" fill="{fill}"/>'
    )


def build_card_svg(p, avatar_data_uri):
    pac = clamp(40 + p["commits"] / 4)
    sho = clamp(40 + p["total_stars"] * 6)
    pas = clamp(40 + p["followers"] * 3)
    dri = clamp(40 + len(p["languages"]) * 8)
    df = clamp(40 + p["prs"] * 2)
    phy = clamp(40 + p["contributions"] / 6)
    overall = clamp((pac + sho + pas + dri + df + phy) / 6)
    tier = "GOLD" if overall >= 75 else "SILVER" if overall >= 65 else "BRONZE"
    tier_fill = "#f0d9a8" if tier == "GOLD" else "#d7dee4" if tier == "SILVER" else "#e8d3a0"
    tier_text = "#5a4a1a" if tier == "GOLD" else "#22303a" if tier == "SILVER" else "#3a2c14"

    canvas_h = 480
    shield_bottom_abs = 452  # matches path below: translate(224,136) + local bottom 316

    metrics = [
        ("Commits", p["commits"], max(p["commits"], 100)),
        ("Stars earned", p["total_stars"], max(p["total_stars"], 20)),
        ("Top repo stars", p["top_repo_stars"], max(p["top_repo_stars"], 10)),
        ("Pull requests", p["prs"], max(p["prs"], 60)),
        ("Followers", p["followers"], max(p["followers"], 20)),
        ("Languages", len(p["languages"]), max(len(p["languages"]), 10)),
        ("Issues", p["issues"], max(p["issues"], 40)),
        ("Contributions", p["contributions"], max(p["contributions"], 300)),
    ]
    metric_svg = ""
    row_y = 180
    step = 35
    last_bar_bottom = row_y
    for label, val, mx in metrics:
        metric_svg += f'<text x="492" y="{row_y}">{label}</text><text x="660" y="{row_y}" text-anchor="end">{val}</text>'
        metric_svg += bar(492, row_y + 6, 168, val, mx)
        last_bar_bottom = row_y + 6 + 3
        row_y += step
    metrics_panel_bottom = last_bar_bottom + 16
    metrics_panel_height = metrics_panel_bottom - 136

    attributes_panel_height = 210
    playstyle_panel_top = 136 + attributes_panel_height + 16
    playstyle_panel_height = shield_bottom_abs - playstyle_panel_top

    return f"""<svg width="700" height="{canvas_h}" viewBox="0 0 700 {canvas_h}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="700" height="{canvas_h}" rx="16" fill="#181410"/>

  <rect x="24" y="24" width="88" height="88" rx="8" fill="#2a2f36" stroke="#4a5560" stroke-width="0.5"/>
  <text x="68" y="66" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="28" font-weight="600" fill="#dfe8f0">{overall}</text>
  <text x="68" y="84" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="9" letter-spacing="1" fill="#8ea3b5">{tier}</text>

  <text x="128" y="42" font-family="Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1" fill="#7fb87a">SCOUT REPORT</text>
  <text x="128" y="68" font-family="Helvetica, Arial, sans-serif" font-size="26" font-weight="600" letter-spacing="1" fill="#f5efe0">{p['login'].upper()}</text>

  <rect x="128" y="78" width="34" height="18" rx="4" fill="#7fb87a"/>
  <text x="145" y="91" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="11" font-weight="600" fill="#183014">CAM</text>
  <text x="172" y="91" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#c9bd9e">@{p['login']} &#183; {p['public_repos']} repos</text>

  <text x="128" y="112" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#a88f5e"><tspan font-weight="600" fill="#f0d9a8">LIVE STATS </tspan>generated from the GitHub API.</text>

  <rect x="24" y="136" width="180" height="{attributes_panel_height}" rx="8" fill="#20190f" stroke="#4a3d28" stroke-width="0.5"/>
  <text x="40" y="158" font-family="Helvetica, Arial, sans-serif" font-size="10" letter-spacing="1" fill="#a88f5e">ATTRIBUTES</text>
  <text x="40" y="182" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#e8dfc8">Following</text>
  <text x="188" y="182" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#f0d9a8">{p['following']}</text>
  <text x="40" y="206" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#e8dfc8">Public repos</text>
  <text x="188" y="206" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#f0d9a8">{p['public_repos']}</text>
  <line x1="40" y1="222" x2="188" y2="222" stroke="#4a3d28" stroke-width="0.5"/>
  <text x="40" y="246" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#e8dfc8">Top language</text>
  <text x="188" y="246" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#f0d9a8">{(max(p['languages'], key=p['languages'].get) if p['languages'] else '-')}</text>
  <text x="40" y="270" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#e8dfc8">Issues opened</text>
  <text x="188" y="270" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#f0d9a8">{p['issues']}</text>

  <rect x="24" y="{playstyle_panel_top}" width="180" height="{playstyle_panel_height}" rx="8" fill="#20190f" stroke="#4a3d28" stroke-width="0.5"/>
  <text x="40" y="{playstyle_panel_top + 22}" font-family="Helvetica, Arial, sans-serif" font-size="10" letter-spacing="1" fill="#a88f5e">PLAYSTYLE</text>
  <text x="40" y="{playstyle_panel_top + 44}" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#f0d9a8">Polyglot</text>

  <g transform="translate(224,136)">
    <path d="M0,18 L110,0 L220,18 L220,290 L110,316 L0,290 Z" fill="{tier_fill}"/>
    <text x="110" y="46" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="30" font-weight="600" fill="{tier_text}">{overall}</text>
    <text x="110" y="66" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" font-weight="600" fill="{tier_text}">CAM</text>

    <clipPath id="photoClip"><rect x="60" y="78" width="100" height="100" rx="6"/></clipPath>
    <rect x="60" y="78" width="100" height="100" rx="6" fill="#aebac2"/>
    <image href="{avatar_data_uri}" x="60" y="78" width="100" height="100" clip-path="url(#photoClip)" preserveAspectRatio="xMidYMid slice"/>

    <text x="110" y="202" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="15" font-weight="600" letter-spacing="1" fill="{tier_text}">{p['login'].upper()}</text>

    <line x1="14" y1="214" x2="206" y2="214" stroke="#5c6a74" stroke-width="0.5"/>
    <text x="14" y="234" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{pac}</tspan> PAC</text>
    <text x="118" y="234" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{dri}</tspan> DRI</text>
    <text x="14" y="254" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{sho}</tspan> SHO</text>
    <text x="118" y="254" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{df}</tspan> DEF</text>
    <text x="14" y="274" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{pas}</tspan> PAS</text>
    <text x="118" y="274" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{tier_text}"><tspan font-weight="600">{phy}</tspan> PHY</text>
  </g>

  <rect x="476" y="136" width="200" height="{metrics_panel_height}" rx="8" fill="#20190f" stroke="#4a3d28" stroke-width="0.5"/>
  <text x="492" y="158" font-family="Helvetica, Arial, sans-serif" font-size="10" letter-spacing="1" fill="#a88f5e">SCOUTING METRICS (LIVE)</text>
  <g font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#e8dfc8">
    {metric_svg}
  </g>
</svg>"""


def build_formation_svg(p):
    positions = ["GK", "CB", "CB", "CAM", "ST"]
    coords = [(350, 460), (190, 340), (510, 340), (350, 200), (350, 80)]
    pinned = p["pinned"][:5]
    while len(pinned) < 5:
        pinned.append({"name": "-", "stargazerCount": 0, "primaryLanguage": None})

    cards = ""
    for (x, y), pos, repo in zip(coords, positions, pinned):
        name = repo["name"]
        stars = repo.get("stargazerCount", 0)
        lang = (repo.get("primaryLanguage") or {}).get("name", "-") if repo.get("primaryLanguage") else "-"
        width = max(200, 24 + len(name) * 8 + 60)
        highlight = pos == "ST"
        fill = "#1a4d2a" if highlight else "#123a20"
        stroke = "#f0d9a8" if highlight else "#3f6b4c"
        sw = "1" if highlight else "0.5"
        cards += f"""
  <g transform="translate({x},{y})">
    <rect x="{-width/2}" y="-24" width="{width}" height="48" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>
    <rect x="{-width/2+6}" y="-16" width="28" height="16" rx="3" fill="#e8dfc8"/>
    <text x="{-width/2+20}" y="-4" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="9" font-weight="600" fill="#123a20">{pos}</text>
    <text x="{-width/2+42}" y="-6" font-family="Helvetica, Arial, sans-serif" font-size="13" font-weight="600" fill="#f5efe0">{name}</text>
    <text x="{-width/2+42}" y="11" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="#c9bd9e">{lang} &#183; &#9733; {stars}</text>
  </g>"""

    return f"""<svg width="700" height="560" viewBox="0 0 700 560" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="700" height="560" rx="16" fill="#0e2e18"/>
  <rect x="30" y="30" width="640" height="500" fill="none" stroke="#3f6b4c" stroke-width="1.5"/>
  <line x1="30" y1="280" x2="670" y2="280" stroke="#3f6b4c" stroke-width="1.5"/>
  <circle cx="350" cy="280" r="55" fill="none" stroke="#3f6b4c" stroke-width="1.5"/>
  <circle cx="350" cy="280" r="3" fill="#3f6b4c"/>
  <rect x="200" y="30" width="300" height="90" fill="none" stroke="#3f6b4c" stroke-width="1.5"/>
  <rect x="270" y="30" width="160" height="36" fill="none" stroke="#3f6b4c" stroke-width="1.5"/>
  <path d="M 260 120 A 55 55 0 0 0 440 120" fill="none" stroke="#3f6b4c" stroke-width="1.5"/>
  <text x="350" y="500" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" letter-spacing="1" fill="#6f9e7f">STARTING XI &#183; PINNED REPOS (LIVE)</text>
  {cards}
</svg>"""


def main():
    p = fetch_profile()
    avatar_data_uri = fetch_avatar_data_uri(p["avatar_url"])
    with open("card.svg", "w") as f:
        f.write(build_card_svg(p, avatar_data_uri))
    with open("formation.svg", "w") as f:
        f.write(build_formation_svg(p))
    print("wrote card.svg, formation.svg (avatar embedded inline, no separate file needed)")


if __name__ == "__main__":
    main()