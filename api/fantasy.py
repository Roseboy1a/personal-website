from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

YT_CHANNELS = {
    "The Fantasy Footballers": "UC-No2ITxJsNt50oJQ3fLmUA",
    "FantasyPros": "UCZYaxEBdyKDsZfq_JGZwIeQ",
    "Flock Fantasy": "UC3jkBCIA687DNpQOZFSbtsg",
    "BDGE Fantasy": "UCunM5df2213-M20G9f25L6w",
    "Underdog Fantasy": "UC7T153_022p3N2P4N02I6vQ",
    "Fantasy Football Today": "UCviK78rIWXhZdFzJ1Woi7Fg",
    "Establish The Run": "UC4TsBB8cvgXXqw8GzI3162A",
    "Yahoo Fantasy Sports": "UCbPP6F-3QvBwGZR9OBQaM1g",
    "PlayerProfiler": "UCfT0PM813c3F2B0PjP2V29A",
    "Fantasy Headliners": "UCClRnPtjFEm7sMa0Nv02f2Q"
}

TARGET_KEYWORDS = [
    "waiver", "pickup", "add", "must", "stash", "buy", "rank",
    "start", "sit", "sleeper", "target", "drop", "breakout", "wire",
    "trade", "lineup", "rb", "wr", "qb", "te", "injury", "preview", "week"
]

POSITIVE_WORDS = {
    "add", "pickup", "pick up", "buy", "must", "start", "smash", "breakout",
    "upside", "league winner", "love", "target", "volume", "stash", "priority",
    "steal", "fire", "boom", "starter", "number one", "wr1", "rb1", "workhorse"
}

NEGATIVE_WORDS = {
    "drop", "avoid", "sit", "bench", "injured", "injury", "out", "bust",
    "terrible", "awful", "worry", "panic", "fade", "stay away", "trap",
    "concerning", "downgrade", "cutting", "cut", "sell"
}

AMBIGUOUS_SURNAMES = {
    "washington", "dallas", "houston", "jacksonville", "carolina", "miami",
    "denver", "chicago", "detroit", "atlanta", "arizona", "seattle", "tampa",
    "buffalo", "cleveland", "cincinnati", "pittsburgh", "baltimore", "indianapolis",
    "tennessee", "minnesota", "philadelphia", "commanders", "steelers", "browns",
    "wilson", "williams", "smith", "brown", "jones", "johnson", "taylor", "thomas",
    "moore", "robinson", "allen", "hill", "cook", "hall", "walker", "mitchell",
    "white", "green", "adams", "carter", "davis", "jackson", "miller", "young",
    "anderson", "scott", "wright", "king", "baker", "nelson", "harris", "clark",
    "lewis", "lee", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    "perez", "sanchez", "ramirez", "torres", "flores", "rivera", "gomez", "diaz",
    "turner", "parker", "collins", "edwards", "stewart", "morris", "murphy",
    "rogers", "reed", "bell", "cooper", "richardson", "cox", "howard", "ward",
    "watson", "brooks", "wood", "james", "bennett", "gray", "mendoza", "hughes",
    "price", "myers", "long", "foster", "sanders", "ross", "morales", "powell",
    "sullivan", "russell", "ortiz", "jenkins", "gutierrez", "perry", "butler",
    "barnes", "fisher", "henderson", "coleman", "simmons", "patterson", "jordan",
    "reynolds", "hamilton", "graham", "kim", "gonzales", "alexander", "ramos",
    "wallace", "griffin", "west", "cole", "hayes", "chavez", "gibson", "bryant",
    "ellis", "stevens", "murray", "ford", "marshall", "owens", "mcdonald", "harrison",
    "ruiz", "kennedy", "wells", "alvarez", "woods", "ireland", "hunt", "palmer",
    "robertson", "boyd", "rose", "stone", "mason", "warren", "dixon", "burns",
    "gordon", "shaw", "holmes", "rice", "schmidt", "black", "daniels", "mills",
    "nichols", "grant", "knight", "ferguson", "hopkins", "jacobs", "pittman",
    "higbee", "stafford", "henry", "barkley", "elliott", "conner", "chubb",
    "mixon", "kamara", "montgomery", "gibbs", "stroud", "love", "purdy", "goff",
    "mayfield", "lawrence", "herbert", "burrow", "mahomes", "hurts", "prescott",
    "cousins", "rodgers", "carr", "geno", "ridley", "sutton", "pickens", "higgins",
    "waddle", "olave", "london", "metcalf", "lockett", "evans", "godwin", "diggs",
    "dell", "jeudy", "kelce", "andrews", "kittle", "laporta", "mcbride", "kincaid",
    "engram", "njoku", "goedert", "pitts", "hockenson", "freiermuth", "kraft",
    "musgrave", "benson", "corum", "lloyd", "vidal", "ali", "estime", "tracy",
    "irving", "guerendo", "steele", "vaki", "shipley", "laube", "worthy", "pearsall",
    "legette", "mcconkey", "polk", "burton", "mcmillan", "franklin", "corley", "thrash", "means"
}

# ==============================================================================
# 32-TEAM NFL DEFENSIVE SCHEME, PERSONNEL & TRENCH MATCHUP MATRIX
# ==============================================================================
NFL_DEFENSE_MATRIX = {
    "ARI": {"man": 24, "zone": 76, "base": 22, "nickel": 64, "dime": 14, "shell": "Cover 3 / Quarters", "dline_run_stop": 89, "pass_rush": 90, "blitz": 27, "perim_cb": 88, "slot_cov": 90, "lb_mismatch_rate": 24, "key_defender": "Budda Baker (Box/Slot S)"},
    "ATL": {"man": 22, "zone": 78, "base": 24, "nickel": 65, "dime": 11, "shell": "Cover 3 / Cover 4", "dline_run_stop": 94, "pass_rush": 87, "blitz": 23, "perim_cb": 99, "slot_cov": 91, "lb_mismatch_rate": 26, "key_defender": "A.J. Terrell (Perim CB)"},
    "BAL": {"man": 31, "zone": 69, "base": 26, "nickel": 58, "dime": 16, "shell": "Split-Safety / Disguised Zone", "dline_run_stop": 114, "pass_rush": 109, "blitz": 30, "perim_cb": 103, "slot_cov": 108, "lb_mismatch_rate": 14, "key_defender": "Kyle Hamilton (Slot/Apex) & Roquan Smith"},
    "BUF": {"man": 21, "zone": 79, "base": 12, "nickel": 76, "dime": 12, "shell": "Nickel Cover 2 / Cover 4", "dline_run_stop": 95, "pass_rush": 104, "blitz": 24, "perim_cb": 104, "slot_cov": 106, "lb_mismatch_rate": 16, "key_defender": "Taron Johnson (Elite Nickel CB)"},
    "CAR": {"man": 26, "zone": 74, "base": 28, "nickel": 60, "dime": 12, "shell": "3-4 Cover 3 / Quarters", "dline_run_stop": 86, "pass_rush": 86, "blitz": 29, "perim_cb": 92, "slot_cov": 87, "lb_mismatch_rate": 29, "key_defender": "Jaycee Horn (Perim CB)"},
    "CHI": {"man": 25, "zone": 75, "base": 23, "nickel": 67, "dime": 10, "shell": "4-3 Cover 2 / Tampa 2", "dline_run_stop": 98, "pass_rush": 99, "blitz": 22, "perim_cb": 111, "slot_cov": 105, "lb_mismatch_rate": 18, "key_defender": "Jaylon Johnson (Shadow CB) & Kyler Gordon"},
    "CIN": {"man": 30, "zone": 70, "base": 22, "nickel": 66, "dime": 12, "shell": "Cover 3 / Man-Match", "dline_run_stop": 91, "pass_rush": 97, "blitz": 26, "perim_cb": 93, "slot_cov": 89, "lb_mismatch_rate": 25, "key_defender": "Trey Hendrickson (Edge Rush)"},
    "CLE": {"man": 44, "zone": 56, "base": 20, "nickel": 64, "dime": 16, "shell": "Aggressive Press Cover 1 Man", "dline_run_stop": 107, "pass_rush": 113, "blitz": 33, "perim_cb": 109, "slot_cov": 98, "lb_mismatch_rate": 19, "key_defender": "Myles Garrett (Edge) & Denzel Ward (Man CB)"},
    "DAL": {"man": 36, "zone": 64, "base": 24, "nickel": 61, "dime": 15, "shell": "Cover 1 / Cover 3 Press", "dline_run_stop": 88, "pass_rush": 107, "blitz": 31, "perim_cb": 101, "slot_cov": 92, "lb_mismatch_rate": 24, "key_defender": "Interior D-Line (Vulnerable vs Inside Run)"},
    "DEN": {"man": 42, "zone": 58, "base": 25, "nickel": 60, "dime": 15, "shell": "Heavy Blitz Cover 1 / Cover 3", "dline_run_stop": 104, "pass_rush": 110, "blitz": 39, "perim_cb": 116, "slot_cov": 101, "lb_mismatch_rate": 21, "key_defender": "Pat Surtain II (Elite Shadow CB1)"},
    "DET": {"man": 41, "zone": 59, "base": 29, "nickel": 59, "dime": 12, "shell": "Base/Nickel Press Man Cover 1", "dline_run_stop": 115, "pass_rush": 105, "blitz": 34, "perim_cb": 95, "slot_cov": 94, "lb_mismatch_rate": 27, "key_defender": "Elite Run Wall (Funnels teams to Slot/Pass)"},
    "GB": {"man": 27, "zone": 73, "base": 25, "nickel": 63, "dime": 12, "shell": "4-3 Single-High Cover 3", "dline_run_stop": 99, "pass_rush": 102, "blitz": 25, "perim_cb": 101, "slot_cov": 95, "lb_mismatch_rate": 23, "key_defender": "Xavier McKinney (Centerfield Safety)"},
    "HOU": {"man": 32, "zone": 68, "base": 24, "nickel": 65, "dime": 11, "shell": "4-3 Quarters / Cover 3 Press", "dline_run_stop": 106, "pass_rush": 111, "blitz": 24, "perim_cb": 110, "slot_cov": 96, "lb_mismatch_rate": 22, "key_defender": "Derek Stingley Jr. (Perim CB) & Will Anderson"},
    "IND": {"man": 19, "zone": 81, "base": 23, "nickel": 68, "dime": 9, "shell": "Static Cover 3 Zone", "dline_run_stop": 93, "pass_rush": 96, "blitz": 20, "perim_cb": 90, "slot_cov": 94, "lb_mismatch_rate": 26, "key_defender": "Kenny Moore II (Slot CB)"},
    "JAX": {"man": 38, "zone": 62, "base": 27, "nickel": 61, "dime": 12, "shell": "Press Man Cover 1", "dline_run_stop": 96, "pass_rush": 95, "blitz": 29, "perim_cb": 91, "slot_cov": 88, "lb_mismatch_rate": 28, "key_defender": "Vulnerable Secondary vs Motion/Slot"},
    "KC": {"man": 39, "zone": 61, "base": 22, "nickel": 62, "dime": 16, "shell": "Spagnuolo Disguised Blitz / Man", "dline_run_stop": 111, "pass_rush": 108, "blitz": 37, "perim_cb": 112, "slot_cov": 106, "lb_mismatch_rate": 19, "key_defender": "Trent McDuffie (CB1) & Chris Jones (Interior DL)"},
    "LAC": {"man": 23, "zone": 77, "base": 21, "nickel": 63, "dime": 16, "shell": "Minter Two-High Quarters / Zone", "dline_run_stop": 103, "pass_rush": 103, "blitz": 25, "perim_cb": 98, "slot_cov": 102, "lb_mismatch_rate": 17, "key_defender": "Derwin James (Hybrid Box/Slot Defender)"},
    "LAR": {"man": 24, "zone": 76, "base": 25, "nickel": 61, "dime": 14, "shell": "Cover 3 / Quarters Zone", "dline_run_stop": 95, "pass_rush": 104, "blitz": 26, "perim_cb": 89, "slot_cov": 88, "lb_mismatch_rate": 27, "key_defender": "Jared Verse (Edge) / Vulnerable Secondary"},
    "LV": {"man": 28, "zone": 72, "base": 26, "nickel": 62, "dime": 12, "shell": "Cover 3 / Cover 1 Mix", "dline_run_stop": 96, "pass_rush": 103, "blitz": 27, "perim_cb": 92, "slot_cov": 94, "lb_mismatch_rate": 24, "key_defender": "Maxx Crosby (Edge Rush)"},
    "MIA": {"man": 29, "zone": 71, "base": 23, "nickel": 63, "dime": 14, "shell": "Split-Safety Cover 4 / Cover 3", "dline_run_stop": 97, "pass_rush": 98, "blitz": 28, "perim_cb": 102, "slot_cov": 97, "lb_mismatch_rate": 21, "key_defender": "Jalen Ramsey (Perim/Apex CB)"},
    "MIN": {"man": 18, "zone": 82, "base": 19, "nickel": 57, "dime": 24, "shell": "Flores Zero-Blitz / Drop-8 Zone", "dline_run_stop": 112, "pass_rush": 112, "blitz": 42, "perim_cb": 96, "slot_cov": 101, "lb_mismatch_rate": 18, "key_defender": "42% Blitz Rate (Forces Quick Slot/Hot-Read Throws)"},
    "NE": {"man": 40, "zone": 60, "base": 28, "nickel": 58, "dime": 14, "shell": "Cover 1 Man / Pattern-Match", "dline_run_stop": 97, "pass_rush": 94, "blitz": 31, "perim_cb": 111, "slot_cov": 93, "lb_mismatch_rate": 25, "key_defender": "Christian Gonzalez (Shadow Perim CB1)"},
    "NO": {"man": 35, "zone": 65, "base": 25, "nickel": 63, "dime": 12, "shell": "Cover 1 / Cover 4 Match", "dline_run_stop": 93, "pass_rush": 95, "blitz": 25, "perim_cb": 98, "slot_cov": 95, "lb_mismatch_rate": 23, "key_defender": "Demario Davis (LB Coverage)"},
    "NYG": {"man": 31, "zone": 69, "base": 24, "nickel": 64, "dime": 12, "shell": "Cover 3 / Cover 1 Blitz", "dline_run_stop": 92, "pass_rush": 108, "blitz": 32, "perim_cb": 90, "slot_cov": 92, "lb_mismatch_rate": 25, "key_defender": "Dexter Lawrence (Nose Tackle) & Brian Burns"},
    "NYJ": {"man": 34, "zone": 66, "base": 20, "nickel": 68, "dime": 12, "shell": "4-2-5 Nickel Cover 3 / Quarters", "dline_run_stop": 96, "pass_rush": 105, "blitz": 23, "perim_cb": 114, "slot_cov": 104, "lb_mismatch_rate": 19, "key_defender": "Sauce Gardner (Lockdown Perim CB)"},
    "PHI": {"man": 26, "zone": 74, "base": 21, "nickel": 66, "dime": 13, "shell": "Fangio Two-High Quarters / Cover 6", "dline_run_stop": 110, "pass_rush": 109, "blitz": 21, "perim_cb": 110, "slot_cov": 105, "lb_mismatch_rate": 17, "key_defender": "Jalen Carter (DT) & Quinyon Mitchell / Cooper DeJean"},
    "PIT": {"man": 36, "zone": 64, "base": 27, "nickel": 59, "dime": 14, "shell": "Single-High Cover 3 / Cover 1", "dline_run_stop": 108, "pass_rush": 112, "blitz": 33, "perim_cb": 105, "slot_cov": 94, "lb_mismatch_rate": 24, "key_defender": "T.J. Watt (Edge) & Joey Porter Jr. (Press CB)"},
    "SEA": {"man": 25, "zone": 75, "base": 20, "nickel": 65, "dime": 15, "shell": "Macdonald Disguised Split-Safety Zone", "dline_run_stop": 98, "pass_rush": 102, "blitz": 28, "perim_cb": 106, "slot_cov": 103, "lb_mismatch_rate": 18, "key_defender": "Devon Witherspoon (Nickel/Perim CB)"},
    "SF": {"man": 22, "zone": 78, "base": 24, "nickel": 66, "dime": 10, "shell": "Wide-9 4-3 Cover 3 / Cover 4", "dline_run_stop": 104, "pass_rush": 107, "blitz": 20, "perim_cb": 103, "slot_cov": 98, "lb_mismatch_rate": 16, "key_defender": "Fred Warner (Elite Middle-of-Field LB)"},
    "TB": {"man": 23, "zone": 77, "base": 25, "nickel": 61, "dime": 14, "shell": "Bowles Heavy Zone-Blitz / Cover 3", "dline_run_stop": 109, "pass_rush": 104, "blitz": 40, "perim_cb": 91, "slot_cov": 87, "lb_mismatch_rate": 30, "key_defender": "Vita Vea (Run Stopper) / Vulnerable Middle Zone vs Slot & TE"},
    "TEN": {"man": 33, "zone": 67, "base": 26, "nickel": 62, "dime": 12, "shell": "Aggressive Press / Cover 3", "dline_run_stop": 102, "pass_rush": 97, "blitz": 30, "perim_cb": 99, "slot_cov": 95, "lb_mismatch_rate": 22, "key_defender": "Jeffery Simmons (Interior D-Line)"},
    "WAS": {"man": 34, "zone": 66, "base": 26, "nickel": 62, "dime": 12, "shell": "Quinn Cover 3 / Man-Press", "dline_run_stop": 92, "pass_rush": 96, "blitz": 29, "perim_cb": 89, "slot_cov": 88, "lb_mismatch_rate": 27, "key_defender": "Vulnerable Outside CBs vs Vertical/Perim WRs"}
}

SLOT_HEAVY_WRS = {
    "amon ra st brown", "cooper kupp", "chris godwin", "cee dee lamb", "jayden reed",
    "khalil shakir", "rashee rice", "stefon diggs", "jaxon smith njigba", "josh downs",
    "wan dale robinson", "jakobi meyers", "christian kirk", "ladd mcconkey", "zay flowers",
    "devaughn vele", "demario douglas", "caleb douglas", "malik washington", "jauan jennings",
    "parker washington", "tank dell", "xavier worthy", "ricky pearsall", "rome odunze"
}

PASS_CATCHING_RBS = {
    "de von achane", "jahmyr gibbs", "bijan robinson", "alvin kamara", "breece hall",
    "christian mccaffrey", "rachaad white", "chase brown", "austin ekeler", "tyjae spears",
    "jaylen warren", "justice hill", "bucky irving", "tyrone tracy", "javonte williams",
    "travis etienne", "kenneth walker", "aaron jones", "james cook", "d andre swift"
}


def format_seconds(sec):
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def clean_player_name(name):
    cleaned = name.lower().replace(".", "").replace("'", "").replace("-", " ").strip()
    parts = [p for p in cleaned.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(parts), parts


def normalize_team_abbrev(raw_opp):
    if not raw_opp:
        return ""
    s = str(raw_opp).upper().replace("@", "").strip()
    mapping = {
        "WSH": "WAS", "JAC": "JAX", "GNB": "GB", "KAN": "KC",
        "LVR": "LV", "NOR": "NO", "NWE": "NE", "SFO": "SF", "TAM": "TB"
    }
    return mapping.get(s, s)


def analyze_micro_matchup(player, pos, espn_proj, recent_avg, is_desperate=False):
    """
    Deep NFL Scheme & Micro-Matchup Engine (Expanded Weight: -4.0 to +5.0 pts).
    Evaluates Man/Zone coverage shells, Base/Nickel/Dime sub-packages,
    WR vs CB/LB alignments, and RB vs D-Line trench stuff rates.
    """
    raw_opp = getattr(player, 'pro_opponent', '') or ''
    opp = normalize_team_abbrev(raw_opp)

    if not opp or opp == "BYE" or opp not in NFL_DEFENSE_MATRIX:
        return 0.0, "N/A", {
            "opponent": opp or "BYE",
            "headline": "Bye Week or Unscheduled Opponent",
            "coverage_shell": "N/A",
            "personnel_split": "N/A",
            "individual_battle": "No active matchup this week.",
            "trench_or_lb_note": "N/A"
        }

    d = NFL_DEFENSE_MATRIX[opp]
    clean_n, _ = clean_player_name(player.name)
    adj = 0.0

    man_pct = d["man"]
    zone_pct = d["zone"]
    base_pct = d["base"]
    nickel_pct = d["nickel"]
    dime_pct = d["dime"]

    if pos == "WR":
        is_slot = (clean_n in SLOT_HEAVY_WRS) or (espn_proj < 11.2 and recent_avg >= espn_proj)
        alignment = "Slot / Motion Alignment" if is_slot else "Perimeter (X/Z) Alignment"

        # 1. Coverage Shell Fit (Man vs Zone)
        if is_slot:
            cov_edge = ((zone_pct - 70) * 0.065) + ((d["blitz"] - 27) * 0.05)
        else:
            cov_edge = ((man_pct - 30) * 0.045) if d["perim_cb"] < 102 else -((man_pct - 30) * 0.045)
        adj += cov_edge

        # 2. Specific CB vs WR Battle & Shadow Check
        if not is_slot:
            cb_diff = 100 - d["perim_cb"]
            cb_pts = cb_diff * 0.13
            adj += cb_pts
            if d["perim_cb"] >= 110:
                battle = f"Perimeter WR vs Elite Lockdown Corner ({d['key_defender']}) — Shadow Risk ({round(cb_pts, 1)} pts)"
            elif d["perim_cb"] <= 91:
                battle = f"Perimeter WR vs Burnable Outside CBs (Rating: {d['perim_cb']}) — Advantage WR (+{round(cb_pts, 1)} pts)"
            else:
                battle = f"Perimeter WR vs {opp} Outside CBs ({d['key_defender']})"
        else:
            slot_diff = 100 - d["slot_cov"]
            slot_pts = slot_diff * 0.12
            adj += slot_pts
            if d["perim_cb"] >= 110:
                adj += 1.2
                battle = f"Slot Funnel Alert: {opp}'s outside lockdown ({d['key_defender']}) funnels targets inside to the Slot (+1.2 pts)"
            else:
                battle = f"Slot WR vs {opp} Nickel Package (Slot Coverage Rating: {d['slot_cov']})"

        # 3. Nickel / Base Linebacker Coverage Mismatch Check
        if d["lb_mismatch_rate"] >= 24 and (is_slot or nickel_pct >= 62):
            lb_boost = round((d["lb_mismatch_rate"] - 19) * 0.15, 1)
            adj += lb_boost
            trench_lb_note = (
                f"🔥 LB Coverage Mismatch ({d['lb_mismatch_rate']}% LB/Safety Slot Rate): "
                f"When {opp} transitions between Base ({base_pct}%) and Nickel ({nickel_pct}%), "
                f"motion/slot receivers isolate on Linebackers over the middle (+{lb_boost} pts)."
            )
        elif d["slot_cov"] >= 105 and is_slot:
            trench_lb_note = f"⚠️ Tight Nickel Coverage: {opp} uses {d['key_defender']} to erase slot seams (Dime {dime_pct}%)."
        else:
            trench_lb_note = f"Standard {alignment} vs {opp} ({nickel_pct}% Nickel / {dime_pct}% Dime)."

    elif pos == "RB":
        is_receiving_back = (clean_n in PASS_CATCHING_RBS) or (recent_avg > espn_proj + 1.5)

        # 1. Trench Battle: RB vs D-Line Run Stuff Rate
        trench_diff = 100 - d["dline_run_stop"]
        trench_pts = trench_diff * 0.15
        adj += trench_pts

        if d["dline_run_stop"] >= 109:
            battle = f"RB vs Elite Interior Run Wall ({d['key_defender']}, Stuff Rating: {d['dline_run_stop']}) — Tough Trench Sledding ({round(trench_pts, 1)} pts)"
        elif d["dline_run_stop"] <= 92:
            battle = f"RB vs Soft Interior D-Line (Run Stop Rating: {d['dline_run_stop']}) — High Yards-Before-Contact Smash (+{round(trench_pts, 1)} pts)"
        else:
            battle = f"RB vs {opp} Defensive Front (Run Stop Rating: {d['dline_run_stop']} | Key: {d['key_defender']})"

        # 2. Personnel Grouping (Light Boxes in Nickel/Dime vs Heavy Base Boxes)
        sub_pkg_pct = nickel_pct + dime_pct
        if sub_pkg_pct >= 77:
            adj += 1.3
            trench_lb_note = f"⚡ Light Box Advantage: {opp} plays {sub_pkg_pct}% Nickel/Dime (only {base_pct}% Base), creating 6-man light boxes for rushing lanes (+1.3 pts)."
        elif is_receiving_back and (d["blitz"] >= 31 or zone_pct >= 75):
            adj += 1.5
            trench_lb_note = f"🔥 Checkdown/LB Mismatch: {opp}'s {d['blitz']}% blitz & {zone_pct}% zone forces Linebackers to cover RBs in space (+1.5 pts)."
        else:
            trench_lb_note = f"Box Count Split: {opp} runs {base_pct}% Base (7+ man box) vs {nickel_pct}% Nickel."

    elif pos == "TE":
        seam_diff = (100 - d["slot_cov"]) * 0.11 + ((d["lb_mismatch_rate"] - 20) * 0.13)
        adj += seam_diff
        if d["blitz"] >= 32:
            adj += 1.0
            battle = f"TE Hot-Read Advantage vs {opp}'s {d['blitz']}% Blitz Rate (+1.0 pts)"
        else:
            battle = f"TE vs {opp} Seam/LB Coverage (Slot/Box Rating: {d['slot_cov']})"

        trench_lb_note = (
            f"Linebacker Seam Matchup: {opp} allows a {d['lb_mismatch_rate']}% LB coverage mismatch rate "
            f"in {d['shell']} ({zone_pct}% Zone / {man_pct}% Man)."
        )

    else:  # QB
        rush_diff = (100 - d["pass_rush"]) * 0.12
        sec_diff = (100 - ((d["perim_cb"] + d["slot_cov"]) / 2)) * 0.11
        adj += (rush_diff + sec_diff)
        battle = f"QB vs {opp} Pass Rush (Pressure Rating: {d['pass_rush']}, Blitz: {d['blitz']}%)"
        trench_lb_note = f"Coverage Shell Read: {opp} runs {d['shell']} ({zone_pct}% Zone / {man_pct}% Man)."

    # In Desperation Mode, amplify positive schematic mismatches by 20% to hunt ceiling plays
    if is_desperate and adj > 0:
        adj *= 1.20

    adj = round(max(-4.0, min(5.0, adj)), 1)

    if adj >= 2.2:
        grade = "A+ (Smash Scheme Mismatch)"
    elif adj >= 1.1:
        grade = "A (Strong Scheme Edge)"
    elif adj >= 0.3:
        grade = "B+ (Favorable Fit)"
    elif adj >= -0.4:
        grade = "B (Neutral Scheme)"
    elif adj >= -1.5:
        grade = "C (Tough Assignment)"
    else:
        grade = "D (Shadow / Trench Wall)"

    report = {
        "opponent": opp,
        "grade": grade,
        "scheme_adj": adj,
        "coverage_shell": f"{d['shell']} ({man_pct}% Man / {zone_pct}% Zone)",
        "personnel_split": f"{base_pct}% Base • {nickel_pct}% Nickel • {dime_pct}% Dime (Blitz: {d['blitz']}%)",
        "individual_battle": battle,
        "trench_or_lb_note": trench_lb_note
    }
    return adj, grade, report


def parse_chapter_segments(desc_text):
    segments = []
    if not desc_text:
        return segments
    for line in desc_text.splitlines():
        match = re.search(r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})', line)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2))
            s = int(match.group(3))
            total_sec = h * 3600 + m * 60 + s
            segments.append({
                "start": total_sec,
                "text": line.strip()
            })
    return segments


def get_current_fantasy_week_cutoff(now_utc):
    days_since_tuesday = (now_utc.weekday() - 1) % 7
    most_recent_tuesday = now_utc - timedelta(days=days_since_tuesday)
    cutoff = most_recent_tuesday.replace(hour=4, minute=0, second=0, microsecond=0)
    if cutoff > now_utc:
        cutoff -= timedelta(days=7)
    return cutoff


def fetch_weekly_2026_videos(current_week, target_year=2026):
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v8.json"
    saved_videos = {}

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                saved_videos = json.load(f)
        except Exception:
            saved_videos = {}

    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015',
        'media': 'http://search.yahoo.com/mrss/'
    }

    now = datetime.now(timezone.utc)
    tuesday_cutoff = get_current_fantasy_week_cutoff(now)

    def fetch_single_channel(item):
        channel_name, channel_id = item
        found = []
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2.5) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            entries = root.findall('atom:entry', ns)[:15]

            for entry in entries:
                vid_id = entry.find('yt:videoId', ns).text or ""
                if not vid_id or vid_id in saved_videos:
                    continue

                title = entry.find('atom:title', ns).text or ""
                title_lower = title.lower()
                pub_str = entry.find('atom:published', ns).text or ""

                if not pub_str.startswith(str(target_year)) or "2025" in title_lower:
                    continue

                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                except Exception:
                    continue

                mentions_other_week = any(
                    re.search(rf'\bweek\s+{w}\b', title_lower)
                    for w in range(1, 19) if w != current_week
                )
                if mentions_other_week:
                    continue

                explicitly_this_week = bool(re.search(rf'\bweek\s+{current_week}\b', title_lower))
                uploaded_after_mnf = (pub_dt >= tuesday_cutoff)

                if not (uploaded_after_mnf or (explicitly_this_week and (now - pub_dt).days <= 3)):
                    continue

                is_fantasy_topic = any(k in title_lower for k in TARGET_KEYWORDS)
                if is_fantasy_topic:
                    desc_elem = entry.find('media:group/media:description', ns)
                    raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                    combined_text = f"{title_lower} {raw_desc.lower()}"
                    chapter_segs = parse_chapter_segments(raw_desc)

                    found.append({
                        "video_id": vid_id,
                        "channel": channel_name,
                        "title": title,
                        "published": pub_str[:10],
                        "text": combined_text,
                        "segments": chapter_segs
                    })
        except Exception:
            pass
        return found

    new_videos = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for ch_list in executor.map(fetch_single_channel, YT_CHANNELS.items()):
            new_videos.extend(ch_list)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        has_yt_lib = True
    except Exception:
        has_yt_lib = False

    if has_yt_lib and new_videos:
        def add_transcript(v):
            try:
                vid_id = v["video_id"]
                raw_chunks = []
                if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                    t_list = YouTubeTranscriptApi.get_transcript(vid_id, languages=['en'])
                    raw_chunks = [{"start": int(t.get('start', 0)), "text": t.get('text', '')} for t in t_list]
                else:
                    ytt = YouTubeTranscriptApi()
                    fetched = ytt.fetch(vid_id)
                    raw_chunks = [{"start": int(getattr(s, 'start', 0)), "text": getattr(s, 'text', '')} for s in fetched]

                if raw_chunks:
                    v["text"] += " " + " ".join([c["text"] for c in raw_chunks]).lower()
                    grouped = []
                    curr_start = raw_chunks[0]["start"]
                    curr_words = []
                    for c in raw_chunks:
                        curr_words.append(c["text"].replace("\n", " "))
                        if c["start"] - curr_start >= 18:
                            grouped.append({"start": curr_start, "text": " ".join(curr_words)})
                            curr_start = c["start"]
                            curr_words = []
                    if curr_words:
                        grouped.append({"start": curr_start, "text": " ".join(curr_words)})
                    v["segments"].extend(grouped)
            except Exception:
                pass
            return v

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(add_transcript, new_videos[:12]))

    for v in new_videos:
        saved_videos[v["video_id"]] = v

    try:
        with open(cache_path, "w") as f:
            json.dump(saved_videos, f)
    except Exception:
        pass

    return list(saved_videos.values())


def find_player_clips(player_name, yt_videos):
    clean_full, parts = clean_player_name(player_name)
    if len(parts) < 2:
        return [], 0, [], 1.0, "Neutral"

    first_name = parts[0]
    last_name = parts[-1]

    full_name_pattern = re.compile(r'\b' + re.escape(first_name) + r'\s+' + re.escape(last_name) + r'\b')
    is_unique_surname = (len(last_name) >= 8) and (last_name.lower() not in AMBIGUOUS_SURNAMES)
    surname_pattern = re.compile(r'\b' + re.escape(last_name) + r'\b')
    other_first_plus_surname = re.compile(r'\b([a-z]{3,})\s+' + re.escape(last_name) + r'\b')

    mentioned_channels = set()
    total_mentions = 0
    clips = []
    pos_hits = 0
    neg_hits = 0

    for v in yt_videos:
        txt = v["text"].lower().replace(".", "").replace("'", "").replace("-", " ")
        full_matches = full_name_pattern.findall(txt)
        if not full_matches:
            continue

        count = len(full_matches)
        mentioned_channels.add(v["channel"])
        total_mentions += count

        matched_in_segments = False
        for seg in v.get("segments", []):
            seg_clean = seg["text"].lower().replace(".", "").replace("'", "").replace("-", " ")
            has_full = bool(full_name_pattern.search(seg_clean))

            has_safe_surname = False
            if not has_full and is_unique_surname and surname_pattern.search(seg_clean):
                preceding_matches = other_first_plus_surname.findall(seg_clean)
                if all(w == first_name or w in ("the", "and", "for", "with", "from", "like", "over", "start", "add", "drop") for w in preceding_matches):
                    has_safe_surname = True

            if has_full or has_safe_surname:
                for pw in POSITIVE_WORDS:
                    if pw in seg_clean:
                        pos_hits += 1
                for nw in NEGATIVE_WORDS:
                    if nw in seg_clean:
                        neg_hits += 1

                sec = max(0, int(seg["start"]) - 3)
                snippet = seg["text"].strip()
                if len(snippet) > 140:
                    snippet = snippet[:137] + "..."
                clips.append({
                    "video_id": v["video_id"],
                    "channel": v["channel"],
                    "title": v["title"],
                    "seconds": sec,
                    "timestamp": format_seconds(sec),
                    "snippet": snippet
                })
                matched_in_segments = True
                if len([c for c in clips if c["video_id"] == v["video_id"]]) >= 2:
                    break

        if not matched_in_segments:
            clips.append({
                "video_id": v["video_id"],
                "channel": v["channel"],
                "title": v["title"],
                "seconds": 0,
                "timestamp": "0:00 (Featured)",
                "snippet": f"Confirmed full-name mention of {player_name} in {v['channel']}"
            })

    if neg_hits > pos_hits + 1:
        sentiment_mult = 0.25
        sentiment_label = "⚠️ Caution/Negative"
    elif pos_hits >= neg_hits + 2:
        sentiment_mult = 1.25
        sentiment_label = "Bullish Buy"
    else:
        sentiment_mult = 1.0
        sentiment_label = "Positive"

    return list(mentioned_channels), total_mentions, clips[:6], sentiment_mult, sentiment_label


def calculate_playoff_odds(league, my_team, current_week):
    reg_season_weeks = getattr(league.settings, 'reg_season_count', 14)
    playoff_spots = getattr(league.settings, 'playoff_team_count', 6)

    games_played = max(1, current_week - 1)
    team_ppg = {}
    for t in league.teams:
        ppg = (t.points_for / games_played) if t.points_for > 0 else 110.0
        team_ppg[t.team_id] = ppg

    remaining_matchups = []
    sched = getattr(my_team, 'schedule', [])
    for w_idx in range(current_week - 1, min(reg_season_weeks, len(sched))):
        opp = sched[w_idx]
        if opp and opp.team_id != my_team.team_id:
            remaining_matchups.append({
                "week": w_idx + 1,
                "opponent": opp.team_name,
                "opp_ppg": round(team_ppg.get(opp.team_id, 110.0), 1)
            })

    simulations = 1000
    made_playoffs = 0
    total_sim_wins = 0

    for _ in range(simulations):
        sim_wins = {t.team_id: t.wins for t in league.teams}
        sim_pf = {t.team_id: t.points_for for t in league.teams}

        for w_idx in range(current_week - 1, reg_season_weeks):
            seen_pairs = set()
            for t in league.teams:
                t_sched = getattr(t, 'schedule', [])
                if w_idx >= len(t_sched):
                    continue
                opp = t_sched[w_idx]
                if not opp or opp.team_id == t.team_id:
                    continue
                pair = tuple(sorted([t.team_id, opp.team_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                score_t = random.gauss(team_ppg[t.team_id], 22.0)
                score_opp = random.gauss(team_ppg[opp.team_id], 22.0)

                sim_pf[t.team_id] += score_t
                sim_pf[opp.team_id] += score_opp

                if score_t >= score_opp:
                    sim_wins[t.team_id] += 1
                else:
                    sim_wins[opp.team_id] += 1

        total_sim_wins += sim_wins[my_team.team_id]
        standings = sorted(
            league.teams,
            key=lambda x: (sim_wins[x.team_id], sim_pf[x.team_id]),
            reverse=True
        )
        top_ids = [t.team_id for t in standings[:playoff_spots]]
        if my_team.team_id in top_ids:
            made_playoffs += 1

    playoff_pct = round((made_playoffs / simulations) * 100, 1)
    proj_wins = round(total_sim_wins / simulations, 1)
    proj_losses = round(reg_season_weeks - proj_wins, 1)

    return {
        "playoff_pct": playoff_pct,
        "current_record": f"{my_team.wins}-{my_team.losses}",
        "projected_record": f"{proj_wins}-{proj_losses}",
        "playoff_spots": playoff_spots,
        "remaining_schedule": remaining_matchups[:4]
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from espn_api.football import League

            league_id_raw = os.environ.get("LEAGUE_ID", "").strip()
            if not league_id_raw:
                raise ValueError("LEAGUE_ID is not set in Vercel Environment Variables.")

            league_id = int(league_id_raw)
            year = int(os.environ.get("LEAGUE_YEAR", "2026").strip())
            team_name = os.environ.get("TEAM_NAME", "").strip()
            espn_s2 = os.environ.get("ESPN_S2", "").strip()
            swid = os.environ.get("SWID", "").strip()

            league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
            week = league.current_week

            my_team = next((t for t in league.teams if team_name.lower() in t.team_name.lower()), league.teams[0])

            # --- BUILD LIVE WEEK X NFL SCHEDULE MAP SO ROSTER PLAYERS NEVER FALSELY SHOW 'BYE' ---
            free_agents = league.free_agents(week=week, size=100)
            nfl_opp_map = {}

            def register_nfl_matchup(pro_team, pro_opp):
                pt = normalize_team_abbrev(pro_team)
                po = normalize_team_abbrev(pro_opp)
                if pt and po and po != "BYE" and pt in NFL_DEFENSE_MATRIX and po in NFL_DEFENSE_MATRIX:
                    nfl_opp_map[pt] = po
                    nfl_opp_map[po] = pt

            for fa in free_agents:
                register_nfl_matchup(getattr(fa, 'proTeam', ''), getattr(fa, 'pro_opponent', ''))

            # Also scan weekly box_scores to capture all rostered players' opponents
            box_player_opp = {}
            try:
                for box in league.box_scores(week=week):
                    for bp in (box.home_lineup + box.away_lineup):
                        opp_str = normalize_team_abbrev(getattr(bp, 'pro_opponent', ''))
                        if opp_str:
                            box_player_opp[bp.name] = opp_str
                            register_nfl_matchup(getattr(bp, 'proTeam', ''), opp_str)
            except Exception:
                pass

            def resolve_player_opponent(player):
                # 1. Direct pro_opponent attribute
                opp = normalize_team_abbrev(getattr(player, 'pro_opponent', ''))
                if opp and opp != "BYE" and opp in NFL_DEFENSE_MATRIX:
                    return opp
                # 2. From weekly box_scores lineup
                if player.name in box_player_opp:
                    b_opp = box_player_opp[player.name]
                    if b_opp and b_opp != "BYE" and b_opp in NFL_DEFENSE_MATRIX:
                        return b_opp
                # 3. From player.schedule dictionary
                sched = getattr(player, 'schedule', {})
                if isinstance(sched, dict):
                    w_sched = sched.get(week) or sched.get(str(week))
                    if isinstance(w_sched, dict):
                        s_opp = normalize_team_abbrev(w_sched.get('team', ''))
                        if s_opp and s_opp in NFL_DEFENSE_MATRIX:
                            return s_opp
                # 4. From our live NFL team matchup map (using the player's NFL proTeam)
                pro_team = normalize_team_abbrev(getattr(player, 'proTeam', ''))
                if pro_team in nfl_opp_map:
                    return nfl_opp_map[pro_team]
                return "BYE"

            def get_true_baseline(player):
                curr_stats = player.stats.get(week, {})
                espn_proj = float(curr_stats.get('projected_points', player.projected_total_points / 17))

                recent_pts = []
                for past_w in (week - 1, week - 2):
                    if past_w >= 1:
                        w_data = player.stats.get(past_w, {})
                        pts = w_data.get('points')
                        if pts is not None and float(pts) > 0:
                            recent_pts.append(float(pts))

                if recent_pts:
                    recent_avg = sum(recent_pts) / len(recent_pts)
                    true_base = (0.70 * espn_proj) + (0.30 * recent_avg)
                else:
                    recent_avg = espn_proj
                    true_base = espn_proj

                return round(espn_proj, 1), round(recent_avg, 1), round(true_base, 1)

            playoff_data = calculate_playoff_odds(league, my_team, week)
            playoff_pct = playoff_data["playoff_pct"]

            if playoff_pct < 35.0:
                mode = "DESPERATION MODE"
                mode_desc = "Playoff odds are critical (<35%). Exploiting Nickel/LB coverage mismatches, D-Line trench edges, and film-backed YouTube breakouts."
            elif playoff_pct < 60.0:
                mode = "AGGRESSIVE PUSH"
                mode_desc = "Playoff race is tight. Blending scheme-specific coverage/trench edges with weekly usage and analyst film study."
            else:
                mode = "CONTENDER MODE"
                mode_desc = "Strong playoff position. Prioritizing high-floor scheme fits and blocking league rivals."

            is_desperate = playoff_pct < 45.0

            yt_videos = fetch_weekly_2026_videos(current_week=week, target_year=year)

            def score_player_full(player):
                # Inject resolved opponent so analyze_micro_matchup always has the real NFL opponent
                player.pro_opponent = resolve_player_opponent(player)

                espn_proj, recent_avg, true_base = get_true_baseline(player)

                scheme_adj, matchup_grade, matchup_report = analyze_micro_matchup(
                    player, player.position, espn_proj, recent_avg, is_desperate
                )

                channels, mentions, clips, sent_mult, sent_label = find_player_clips(player.name, yt_videos)
                if is_desperate:
                    raw_yt = len(channels) * 1.6 + (mentions * 0.35)
                    yt_bonus = round(min(raw_yt * sent_mult, 6.0), 1)
                else:
                    raw_yt = len(channels) * 0.8 + (mentions * 0.15)
                    yt_bonus = round(min(raw_yt * sent_mult, 2.5), 1)

                blended_score = round(true_base + scheme_adj + yt_bonus, 1)
                return {
                    "espn_proj": espn_proj,
                    "recent_avg": recent_avg,
                    "true_base": true_base,
                    "scheme_adj": scheme_adj,
                    "matchup_grade": matchup_grade,
                    "matchup_report": matchup_report,
                    "yt_bonus": yt_bonus,
                    "blended_score": blended_score,
                    "yt_mentions": mentions,
                    "yt_channels": channels,
                    "sentiment": sent_label,
                    "clips": clips
                }

            # Score your own roster with resolved NFL opponents
            roster = []
            for p in my_team.roster:
                sc = score_player_full(p)
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": sc["espn_proj"],
                    "true_base": sc["true_base"],
                    "scheme_adj": sc["scheme_adj"],
                    "matchup_grade": sc["matchup_grade"],
                    "matchup_report": sc["matchup_report"],
                    "blended_score": sc["blended_score"],
                    "yt_mentions": sc["yt_mentions"],
                    "yt_channels": sc["yt_channels"],
                    "status": p.injuryStatus
                })

            recommendations = []

            for pos in ['QB', 'RB', 'WR', 'TE']:
                my_pos = [p for p in roster if p["pos"] == pos]
                if not my_pos:
                    continue

                # Filter out players actually on an NFL BYE (0.0 projected points) when picking a starter to compare against
                active_starters = [p for p in my_pos if p["slot"] not in ['BE', 'IR'] and p["proj"] > 0]
                active_any = [p for p in my_pos if p["proj"] > 0]
                pool_to_compare = active_starters if (is_desperate and active_starters) else (active_any or my_pos)
                weakest = min(pool_to_compare, key=lambda x: x["blended_score"])

                scored_fas = []
                for fa in free_agents[:85]:
                    if fa.position != pos:
                        continue

                    sc = score_player_full(fa)

                    if sc["blended_score"] > weakest["blended_score"]:
                        tag = "Scheme & Floor Upgrade"
                        if sc["scheme_adj"] >= 1.5 and len(sc["yt_channels"]) >= 1:
                            tag = "🎯 Elite Scheme + Analyst Smash"
                        elif sc["scheme_adj"] >= 1.5:
                            tag = "🛡️ Defensive Scheme Mismatch"
                        elif is_desperate and len(sc["yt_channels"]) >= 2:
                            tag = "🚨 High-Ceiling Breakout Swing"
                        elif len(sc["yt_channels"]) >= 2:
                            tag = "🔥 Consensus Waiver Target"

                        scored_fas.append({
                            "pos": pos,
                            "add": fa.name,
                            "tag": tag,
                            "espn_proj": sc["espn_proj"],
                            "recent_avg": sc["recent_avg"],
                            "true_base": sc["true_base"],
                            "scheme_adj": sc["scheme_adj"],
                            "matchup_grade": sc["matchup_grade"],
                            "matchup_report": sc["matchup_report"],
                            "yt_bonus": sc["yt_bonus"],
                            "blended_score": sc["blended_score"],
                            "yt_mentions": sc["yt_mentions"],
                            "yt_channels": sc["yt_channels"],
                            "sentiment": sc["sentiment"],
                            "clips": sc["clips"],
                            "drop": weakest["name"],
                            "drop_proj": weakest["proj"],
                            "drop_blended": weakest["blended_score"],
                            "drop_scheme_adj": weakest["scheme_adj"],
                            "drop_report": weakest["matchup_report"],
                            "diff": round(sc["blended_score"] - weakest["blended_score"], 1)
                        })

                scored_fas.sort(key=lambda x: x["blended_score"], reverse=True)
                if scored_fas:
                    limit = 3 if is_desperate else 2
                    recommendations.extend(scored_fas[:limit])

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "team": my_team.team_name,
                "year": year,
                "week": week,
                "playoff_data": playoff_data,
                "mode": mode,
                "mode_desc": mode_desc,
                "videos_scanned": [
                    {"id": v["video_id"], "channel": v["channel"], "title": v["title"], "date": v["published"]}
                    for v in yt_videos
                ],
                "recommendations": recommendations,
                "roster": roster
            }).encode('utf-8'))

        except Exception as e:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
