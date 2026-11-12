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

# Phrase weights for Context-Window Sentiment Analysis
BULLISH_PHRASES = {
    "must add": 1.5, "league winner": 1.5, "priority add": 1.4, "priority pickup": 1.4,
    "number one waiver": 1.5, "top waiver": 1.3, "smash start": 1.4, "must start": 1.3,
    "breakout": 1.1, "workhorse": 1.2, "bellcow": 1.2, "every down back": 1.2,
    "target hog": 1.1, "alpha": 1.0, "steal": 0.9, "love him": 1.0, "love this matchup": 1.1,
    "smash play": 1.3, "smash spot": 1.2, "fire him up": 1.2, "starting with confidence": 1.2,
    "high ceiling": 0.9, "huge upside": 1.0, "upside": 0.6, "stash": 0.6, "pickup": 0.6,
    "pick up": 0.6, "waiver add": 0.8, "buy low": 0.8, "flex play": 0.6, "great matchup": 0.9,
    "juicy matchup": 1.0, "volume": 0.5, "snap share": 0.5, "route participation": 0.6,
    "red zone role": 0.7, "goal line": 0.6, "clear starter": 0.9, "wr1": 0.8, "rb1": 0.8,
    "wr2": 0.5, "rb2": 0.5, "streaming option": 0.6, "top streamer": 0.8
}

BEARISH_PHRASES = {
    "do not start": -1.6, "dont start": -1.6, "do not add": -1.6, "dont add": -1.6,
    "stay away": -1.5, "easy drop": -1.6, "safe drop": -1.5, "drop him": -1.5,
    "dropping": -1.2, "bench him": -1.4, "must sit": -1.5, "sit him": -1.3,
    "fade": -1.1, "avoid": -1.2, "bust": -1.3, "trap": -1.2, "fool's gold": -1.4,
    "fools gold": -1.4, "touchdown dependent": -1.0, "td dependent": -1.0,
    "low floor": -0.9, "terrible matchup": -1.2, "brutal matchup": -1.2,
    "tough matchup": -0.8, "shadow coverage": -0.8, "injured": -1.2, "out this week": -1.8,
    "doubtful": -1.5, "hamstring": -0.8, "ankle": -0.7, "concussion": -1.2,
    "ir": -1.5, "committee": -0.6, "split backfield": -0.7, "losing snaps": -1.2,
    "benched": -1.5, "cannot trust": -1.3, "cant trust": -1.3, "panic": -0.9, "worry": -0.7
}

NEGATION_WORDS = {"not", "dont", "don't", "never", "no", "cant", "can't", "wouldnt", "wouldn't", "avoid", "stop"}

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

def build_live_defense_matrix(league=None, current_week=10):
    """
    Clones the base 32-team scheme matrix and dynamically updates ratings 24/7 using:
    1. ESPN's live NFL Injury API (penalizing CB, DL, EDGE, LB, and S injuries)
    2. Live ESPN Fantasy D/ST performance & recent scoring form
    """
    cache_path = f"/tmp/live_def_matrix_wk{current_week}_v1.json"
    now_ts = datetime.now(timezone.utc).timestamp()

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            if now_ts - cached.get("timestamp", 0) < 1800:  # Refreshes every 30 mins
                return cached["matrix"]
        except Exception:
            pass

    # Start with a fresh copy of the base scheme tendencies
    live_matrix = {}
    for team_abbr, base_data in NFL_DEFENSE_MATRIX.items():
        live_matrix[team_abbr] = dict(base_data)
        live_matrix[team_abbr]["injuries"] = []
        live_matrix[team_abbr]["live_adj_summary"] = "Full Strength"

    # 1. Fetch Live NFL Defensive Injuries from ESPN's Public API
    try:
        inj_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
        req = urllib.request.Request(inj_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            inj_json = json.loads(resp.read().decode('utf-8'))

        for team_entry in inj_json.get("injuries", []):
            raw_abbr = team_entry.get("team", {}).get("abbreviation", "")
            if not raw_abbr:
                # Fallback: parse team displayName if abbreviation isn't at top level
                d_name = team_entry.get("displayName", "")
                for k in live_matrix:
                    if k == raw_abbr:
                        break
            t_abbr = normalize_team_abbrev(raw_abbr)

            for item in team_entry.get("injuries", []):
                athlete = item.get("athlete", {})
                if not t_abbr:
                    t_abbr = normalize_team_abbrev(athlete.get("team", {}).get("abbreviation", ""))
                if t_abbr not in live_matrix:
                    continue

                pos = athlete.get("position", {}).get("abbreviation", "").upper()
                name = athlete.get("displayName", "Defender")
                status = item.get("status", "")

                # Only process defensive positions
                if pos not in ("CB", "DB", "S", "FS", "SS", "LB", "ILB", "MLB", "OLB", "DE", "DT", "NT", "DL", "EDGE"):
                    continue

                # Weight impact by injury severity
                status_low = status.lower()
                if any(s in status_low for s in ("out", "injured reserve", "ir", "doubtful", "suspension")):
                    sev = 1.0
                    short_stat = "OUT/IR" if "reserve" in status_low or "out" in status_low else "Doubtful"
                elif "questionable" in status_low:
                    sev = 0.45
                    short_stat = "Q"
                else:
                    continue

                d_team = live_matrix[t_abbr]
                d_team["injuries"].append(f"{name} ({pos} - {short_stat})")

                # Apply position-specific rating downgrades to the defense
                if pos in ("CB", "DB"):
                    d_team["perim_cb"] = max(72, round(d_team["perim_cb"] - (6.5 * sev)))
                    d_team["slot_cov"] = max(72, round(d_team["slot_cov"] - (3.5 * sev)))
                elif pos in ("DT", "NT", "DL"):
                    d_team["dline_run_stop"] = max(72, round(d_team["dline_run_stop"] - (6.5 * sev)))
                    d_team["pass_rush"] = max(72, round(d_team["pass_rush"] - (2.5 * sev)))
                elif pos in ("DE", "EDGE", "OLB"):
                    d_team["pass_rush"] = max(72, round(d_team["pass_rush"] - (6.5 * sev)))
                    d_team["dline_run_stop"] = max(72, round(d_team["dline_run_stop"] - (3.0 * sev)))
                elif pos in ("LB", "ILB", "MLB"):
                    d_team["slot_cov"] = max(72, round(d_team["slot_cov"] - (5.5 * sev)))
                    d_team["dline_run_stop"] = max(72, round(d_team["dline_run_stop"] - (3.5 * sev)))
                    d_team["lb_mismatch_rate"] = min(45, round(d_team["lb_mismatch_rate"] + (4.5 * sev)))
                elif pos in ("S", "FS", "SS"):
                    d_team["slot_cov"] = max(72, round(d_team["slot_cov"] - (4.5 * sev)))
                    d_team["perim_cb"] = max(72, round(d_team["perim_cb"] - (3.0 * sev)))
                    d_team["lb_mismatch_rate"] = min(45, round(d_team["lb_mismatch_rate"] + (3.0 * sev)))
    except Exception:
        pass

    # 2. Calibrate with Live ESPN Fantasy D/ST Scoring Form (if league object is available)
    if league is not None:
        try:
            dst_players = league.free_agents(week=current_week, size=40, position='D/ST')
            for t in league.teams:
                for p in t.roster:
                    if p.position == 'D/ST':
                        dst_players.append(p)

            for dst in dst_players:
                pro_t = normalize_team_abbrev(getattr(dst, 'proTeam', ''))
                if pro_t in live_matrix:
                    avg_pts = float(getattr(dst, 'avg_points', 6.0) or 6.0)
                    # NFL D/ST average is ~6.5 fantasy pts/game; scale ratings slightly by real-time form
                    form_delta = round((avg_pts - 6.5) * 1.1)
                    d_team = live_matrix[pro_t]
                    d_team["dline_run_stop"] = max(72, min(120, d_team["dline_run_stop"] + form_delta))
                    d_team["pass_rush"] = max(72, min(120, d_team["pass_rush"] + form_delta))
                    d_team["perim_cb"] = max(72, min(120, d_team["perim_cb"] + form_delta))
        except Exception:
            pass

    for t_abbr, d_team in live_matrix.items():
        if d_team["injuries"]:
            top_inj = ", ".join(d_team["injuries"][:4])
            extra = f" +{len(d_team['injuries']) - 4} more" if len(d_team["injuries"]) > 4 else ""
            d_team["live_adj_summary"] = f"{top_inj}{extra}"

    try:
        with open(cache_path, "w") as f:
            json.dump({"timestamp": now_ts, "matrix": live_matrix}, f)
    except Exception:
        pass

    return live_matrix

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


def analyze_micro_matchup(player, pos, espn_proj, recent_avg, is_desperate=False, live_matrix=None):
    active_matrix = live_matrix or NFL_DEFENSE_MATRIX
    raw_opp = getattr(player, 'pro_opponent', '') or ''
    opp = normalize_team_abbrev(raw_opp)

    if not opp or opp == "BYE" or opp not in active_matrix:
        return 0.0, "N/A", {
            "opponent": opp or "BYE",
            "headline": "Bye Week or Unscheduled Opponent",
            "coverage_shell": "N/A",
            "personnel_split": "N/A",
            "individual_battle": "No active matchup this week.",
            "trench_or_lb_note": "N/A",
            "injury_impact": "None"
        }

    d = active_matrix[opp]
    base_d = NFL_DEFENSE_MATRIX.get(opp, d)
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

        if is_slot:
            cov_edge = ((zone_pct - 70) * 0.065) + ((d["blitz"] - 27) * 0.05)
        else:
            cov_edge = ((man_pct - 30) * 0.045) if d["perim_cb"] < 102 else -((man_pct - 30) * 0.045)
        adj += cov_edge

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

        trench_diff = 100 - d["dline_run_stop"]
        trench_pts = trench_diff * 0.15
        adj += trench_pts

        if d["dline_run_stop"] >= 109:
            battle = f"RB vs Elite Interior Run Wall ({d['key_defender']}, Stuff Rating: {d['dline_run_stop']}) — Tough Trench Sledding ({round(trench_pts, 1)} pts)"
        elif d["dline_run_stop"] <= 92:
            battle = f"RB vs Soft Interior D-Line (Run Stop Rating: {d['dline_run_stop']}) — High Yards-Before-Contact Smash (+{round(trench_pts, 1)} pts)"
        else:
            battle = f"RB vs {opp} Defensive Front (Run Stop Rating: {d['dline_run_stop']} | Key: {d['key_defender']})"

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

    else:
        rush_diff = (100 - d["pass_rush"]) * 0.12
        sec_diff = (100 - ((d["perim_cb"] + d["slot_cov"]) / 2)) * 0.11
        adj += (rush_diff + sec_diff)
        battle = f"QB vs {opp} Pass Rush (Pressure Rating: {d['pass_rush']}, Blitz: {d['blitz']}%)"
        trench_lb_note = f"Coverage Shell Read: {opp} runs {d['shell']} ({zone_pct}% Zone / {man_pct}% Man)."

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

    # Calculate how much live defensive injuries downgraded this defense compared to baseline
    cb_drop = base_d["perim_cb"] - d["perim_cb"]
    dl_drop = base_d["dline_run_stop"] - d["dline_run_stop"]
    lb_jump = d["lb_mismatch_rate"] - base_d["lb_mismatch_rate"]

    inj_list = d.get("injuries", [])
    if inj_list:
        impacts = []
        if cb_drop > 0:
            impacts.append(f"CB Cov -{cb_drop}")
        if dl_drop > 0:
            impacts.append(f"Run Stop -{dl_drop}")
        if lb_jump > 0:
            impacts.append(f"LB Mismatch +{lb_jump}%")
        impact_str = f" ({', '.join(impacts)})" if impacts else ""
        injury_report_str = f"🏥 {d.get('live_adj_summary', '')}{impact_str}"
    else:
        injury_report_str = "✓ No Major Defensive Starters Listed Out/IR"

    report = {
        "opponent": opp,
        "grade": grade,
        "scheme_adj": adj,
        "coverage_shell": f"{d['shell']} ({man_pct}% Man / {zone_pct}% Zone)",
        "personnel_split": f"{base_pct}% Base • {nickel_pct}% Nickel • {dime_pct}% Dime (Blitz: {d['blitz']}%)",
        "individual_battle": battle,
        "trench_or_lb_note": trench_lb_note,
        "injury_impact": injury_report_str
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
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v9.json"
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


def score_segment_context(seg_text, video_title=""):
    """
    Analyzes the exact spoken context around a player's mention.
    Returns (net_sentiment_score, verdict_tag, matched_signals_list).
    A plain name-drop with no positive/negative signals scores 0.0.
    """
    clean_s = seg_text.lower().replace(".", "").replace("'", "").replace("-", " ")
    words = clean_s.split()
    score = 0.0
    signals = []

    # 1. Check multi-word and single-word Bearish signals first
    for phrase, weight in BEARISH_PHRASES.items():
        if phrase in clean_s:
            score += weight
            signals.append(f"-{phrase}")

    # 2. Check Bullish signals, verifying they aren't negated ("don't start", "not a pickup")
    for phrase, weight in BULLISH_PHRASES.items():
        idx = clean_s.find(phrase)
        if idx != -1:
            # Check the 3 words immediately preceding the bullish phrase for negation
            prefix_words = clean_s[:idx].split()[-3:]
            if any(nw in prefix_words for nw in NEGATION_WORDS):
                score -= weight
                signals.append(f"-not {phrase}")
            else:
                score += weight
                signals.append(f"+{phrase}")

    # 3. If the segment itself is a brief chapter timestamp or neutral sentence,
    # check the video title for overarching context (e.g., "Must Add Waiver Targets" vs "Players to Drop")
    title_low = video_title.lower()
    if score == 0.0:
        if any(w in title_low for w in ("drop", "bust", "sit", "avoid", "panic", "sell")):
            score -= 0.6
            signals.append("-video topic: sit/drop")
        elif any(w in title_low for w in ("waiver", "add", "pickup", "buy", "breakout", "start", "sleeper")):
            score += 0.35
            signals.append("+video topic: waiver/start")

    score = round(max(-2.5, min(2.5, score)), 2)
    if score >= 0.5:
        verdict = f"🟢 Bullish Praise (+{score})"
    elif score > 0.0:
        verdict = f"🟢 Mild Endorsement (+{score})"
    elif score <= -0.5:
        verdict = f"🔴 Bearish Warning ({score})"
    elif score < 0.0:
        verdict = f"🔴 Caution ({score})"
    else:
        verdict = "⚪ Neutral Name-Drop (+0.0)"

    return score, verdict, signals[:4]


def find_player_clips(player_name, yt_videos, is_desperate=False):
    """
    Finds full-name player mentions and computes YT points STRICTLY from how well
    the analysts talk about the player in that exact segment.
    Neutral name-drops earn 0.0 pts. Bearish segments subtract points.
    """
    clean_full, parts = clean_player_name(player_name)
    if len(parts) < 2:
        return [], 0, [], 0.0, "No Mentions"

    first_name = parts[0]
    last_name = parts[-1]

    full_name_pattern = re.compile(r'\b' + re.escape(first_name) + r'\s+' + re.escape(last_name) + r'\b')
    is_unique_surname = (len(last_name) >= 8) and (last_name.lower() not in AMBIGUOUS_SURNAMES)
    surname_pattern = re.compile(r'\b' + re.escape(last_name) + r'\b')
    other_first_plus_surname = re.compile(r'\b([a-z]{3,})\s+' + re.escape(last_name) + r'\b')

    mentioned_channels = set()
    bullish_channels = set()
    bearish_channels = set()
    total_mentions = 0
    clips = []
    cumulative_sentiment_pts = 0.0

    for v in yt_videos:
        txt = v["text"].lower().replace(".", "").replace("'", "").replace("-", " ")
        full_matches = full_name_pattern.findall(txt)
        if not full_matches:
            continue

        mentioned_channels.add(v["channel"])
        total_mentions += len(full_matches)

        segments = v.get("segments", [])
        for idx, seg in enumerate(segments):
            seg_clean = seg["text"].lower().replace(".", "").replace("'", "").replace("-", " ")
            has_full = bool(full_name_pattern.search(seg_clean))

            has_safe_surname = False
            if not has_full and is_unique_surname and surname_pattern.search(seg_clean):
                preceding_matches = other_first_plus_surname.findall(seg_clean)
                if all(w == first_name or w in ("the", "and", "for", "with", "from", "like", "over", "start", "add", "drop") for w in preceding_matches):
                    has_safe_surname = True

            if has_full or has_safe_surname:
                # Combine current 18s segment with the next 18s segment (~36 seconds of spoken context after their name)
                context_window = seg["text"]
                if idx + 1 < len(segments):
                    context_window += " " + segments[idx + 1]["text"]

                seg_score, verdict, signals = score_segment_context(context_window, v["title"])
                cumulative_sentiment_pts += seg_score

                if seg_score >= 0.3:
                    bullish_channels.add(v["channel"])
                elif seg_score <= -0.3:
                    bearish_channels.add(v["channel"])

                sec = max(0, int(seg["start"]) - 3)
                snippet = context_window.strip()
                if len(snippet) > 165:
                    snippet = snippet[:162] + "..."

                clips.append({
                    "video_id": v["video_id"],
                    "channel": v["channel"],
                    "title": v["title"],
                    "seconds": sec,
                    "timestamp": format_seconds(sec),
                    "snippet": snippet,
                    "verdict": verdict,
                    "signals": ", ".join(signals) if signals else "plain mention"
                })
                if len([c for c in clips if c["video_id"] == v["video_id"]]) >= 2:
                    break

    # Add multi-channel consensus bonus ONLY for channels that actually praised the player
    consensus_boost = len(bullish_channels) * (0.75 if is_desperate else 0.45)
    consensus_penalty = len(bearish_channels) * 0.65

    raw_yt_bonus = cumulative_sentiment_pts + consensus_boost - consensus_penalty
    if is_desperate and raw_yt_bonus > 0:
        raw_yt_bonus *= 1.25

    max_cap = 5.5 if is_desperate else 3.0
    yt_bonus = round(max(-3.0, min(max_cap, raw_yt_bonus)), 1)

    if yt_bonus >= 1.5:
        sentiment_label = f"🟢 Strong Analyst Endorsement ({len(bullish_channels)} Bullish Ch)"
    elif yt_bonus >= 0.4:
        sentiment_label = f"🟢 Positive Film Consensus"
    elif yt_bonus <= -0.5:
        sentiment_label = f"🔴 Analyst Sit/Drop Warning ({len(bearish_channels)} Bearish Ch)"
    elif total_mentions > 0:
        sentiment_label = "⚪ Neutral Name-Drop Only (0.0 Bonus)"
    else:
        sentiment_label = "No Mentions"

    return list(mentioned_channels), total_mentions, clips[:6], yt_bonus, sentiment_label


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
                opp = normalize_team_abbrev(getattr(player, 'pro_opponent', ''))
                if opp and opp != "BYE" and opp in NFL_DEFENSE_MATRIX:
                    return opp
                if player.name in box_player_opp:
                    b_opp = box_player_opp[player.name]
                    if b_opp and b_opp != "BYE" and b_opp in NFL_DEFENSE_MATRIX:
                        return b_opp
                sched = getattr(player, 'schedule', {})
                if isinstance(sched, dict):
                    w_sched = sched.get(week) or sched.get(str(week))
                    if isinstance(w_sched, dict):
                        s_opp = normalize_team_abbrev(w_sched.get('team', ''))
                        if s_opp and s_opp in NFL_DEFENSE_MATRIX:
                            return s_opp
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
                mode_desc = "Playoff odds are critical (<35%). Exploiting Nickel/LB coverage mismatches, D-Line trench edges, and verified bullish analyst breakouts."
            elif playoff_pct < 60.0:
                mode = "AGGRESSIVE PUSH"
                mode_desc = "Playoff race is tight. Blending scheme-specific coverage/trench edges with weekly usage and verified positive film study."
            else:
                mode = "CONTENDER MODE"
                mode_desc = "Strong playoff position. Prioritizing high-floor scheme fits and blocking league rivals."

            is_desperate = playoff_pct < 45.0

            yt_videos = fetch_weekly_2026_videos(current_week=week, target_year=year)
            live_def_matrix = build_live_defense_matrix(league=league, current_week=week)

            def score_player_full(player):
                player.pro_opponent = resolve_player_opponent(player)
                espn_proj, recent_avg, true_base = get_true_baseline(player)

                scheme_adj, matchup_grade, matchup_report = analyze_micro_matchup(
                    player, player.position, espn_proj, recent_avg, is_desperate, live_def_matrix
                )

                # Context-Window Sentiment Scoring: only awards YT points when spoken context is genuinely positive
                channels, mentions, clips, yt_bonus, sent_label = find_player_clips(
                    player.name, yt_videos, is_desperate
                )

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
                    "yt_bonus": sc["yt_bonus"],
                    "sentiment": sc["sentiment"],
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
                        if sc["scheme_adj"] >= 1.5 and sc["yt_bonus"] >= 1.0:
                            tag = "🎯 Elite Scheme + Bullish Film Smash"
                        elif sc["scheme_adj"] >= 1.5:
                            tag = "🛡️ Defensive Scheme Mismatch"
                        elif sc["yt_bonus"] >= 1.8:
                            tag = "🔥 Verified Bullish Analyst Target"

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
