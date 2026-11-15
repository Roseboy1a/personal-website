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

ESPN_TEAM_IDS = {
    "ARI": 22, "ATL": 1, "BAL": 33, "BUF": 2, "CAR": 29, "CHI": 3, "CIN": 4, "CLE": 5,
    "DAL": 6, "DEN": 7, "DET": 8, "GB": 9, "HOU": 34, "IND": 11, "JAX": 30, "KC": 12,
    "LAC": 24, "LAR": 14, "LV": 13, "MIA": 15, "MIN": 16, "NE": 17, "NO": 18, "NYG": 19,
    "NYJ": 20, "PHI": 21, "PIT": 23, "SEA": 26, "SF": 25, "TB": 27, "TEN": 10, "WAS": 28
}

NFL_DEFENSE_MATRIX = {
    "ARI": {"man": 28, "zone": 72, "base": 22, "nickel": 64, "dime": 14, "shell": "Cover 3 / Quarters", "dline_run_stop": 91, "pass_rush": 92, "blitz": 27, "perim_cb": 90, "slot_cov": 91, "lb_mismatch_rate": 24},
    "ATL": {"man": 25, "zone": 75, "base": 24, "nickel": 65, "dime": 11, "shell": "Cover 3 / Cover 4", "dline_run_stop": 92, "pass_rush": 91, "blitz": 24, "perim_cb": 98, "slot_cov": 92, "lb_mismatch_rate": 25},
    "BAL": {"man": 31, "zone": 69, "base": 25, "nickel": 59, "dime": 16, "shell": "Split-Safety / Disguised Zone", "dline_run_stop": 110, "pass_rush": 106, "blitz": 29, "perim_cb": 101, "slot_cov": 106, "lb_mismatch_rate": 16},
    "BUF": {"man": 29, "zone": 71, "base": 14, "nickel": 74, "dime": 12, "shell": "Nickel Cover 2 / Cover 4", "dline_run_stop": 96, "pass_rush": 104, "blitz": 25, "perim_cb": 103, "slot_cov": 105, "lb_mismatch_rate": 17},
    "CAR": {"man": 24, "zone": 76, "base": 27, "nickel": 61, "dime": 12, "shell": "3-4 Cover 3 / Quarters", "dline_run_stop": 89, "pass_rush": 88, "blitz": 28, "perim_cb": 93, "slot_cov": 89, "lb_mismatch_rate": 28},
    "CHI": {"man": 26, "zone": 74, "base": 23, "nickel": 67, "dime": 10, "shell": "4-3 Cover 2 / Cover 3", "dline_run_stop": 101, "pass_rush": 101, "blitz": 24, "perim_cb": 109, "slot_cov": 104, "lb_mismatch_rate": 18},
    "CIN": {"man": 32, "zone": 68, "base": 22, "nickel": 66, "dime": 12, "shell": "Cover 3 / Man-Match", "dline_run_stop": 93, "pass_rush": 98, "blitz": 27, "perim_cb": 95, "slot_cov": 92, "lb_mismatch_rate": 24},
    "CLE": {"man": 38, "zone": 62, "base": 23, "nickel": 63, "dime": 14, "shell": "Cover 1 / Cover 3 Mix", "dline_run_stop": 98, "pass_rush": 95, "blitz": 31, "perim_cb": 104, "slot_cov": 97, "lb_mismatch_rate": 22},
    "DAL": {"man": 35, "zone": 65, "base": 24, "nickel": 61, "dime": 15, "shell": "Cover 1 / Cover 3 Press", "dline_run_stop": 91, "pass_rush": 104, "blitz": 30, "perim_cb": 99, "slot_cov": 93, "lb_mismatch_rate": 24},
    "DEN": {"man": 45, "zone": 55, "base": 24, "nickel": 61, "dime": 15, "shell": "Heavy Blitz Cover 1 / Cover 3", "dline_run_stop": 103, "pass_rush": 111, "blitz": 38, "perim_cb": 114, "slot_cov": 101, "lb_mismatch_rate": 20},
    "DET": {"man": 46, "zone": 54, "base": 28, "nickel": 60, "dime": 12, "shell": "Press Man Cover 1", "dline_run_stop": 112, "pass_rush": 104, "blitz": 33, "perim_cb": 97, "slot_cov": 95, "lb_mismatch_rate": 25},
    "GB": {"man": 23, "zone": 77, "base": 25, "nickel": 63, "dime": 12, "shell": "4-3 Cover 3 / Quarters", "dline_run_stop": 104, "pass_rush": 105, "blitz": 25, "perim_cb": 103, "slot_cov": 99, "lb_mismatch_rate": 21},
    "HOU": {"man": 30, "zone": 70, "base": 24, "nickel": 65, "dime": 11, "shell": "4-3 Quarters / Cover 3", "dline_run_stop": 106, "pass_rush": 112, "blitz": 25, "perim_cb": 109, "slot_cov": 98, "lb_mismatch_rate": 21},
    "IND": {"man": 22, "zone": 78, "base": 23, "nickel": 68, "dime": 9, "shell": "Cover 3 Zone", "dline_run_stop": 95, "pass_rush": 97, "blitz": 22, "perim_cb": 92, "slot_cov": 95, "lb_mismatch_rate": 25},
    "JAX": {"man": 36, "zone": 64, "base": 26, "nickel": 62, "dime": 12, "shell": "Cover 1 / Cover 3", "dline_run_stop": 97, "pass_rush": 103, "blitz": 29, "perim_cb": 94, "slot_cov": 91, "lb_mismatch_rate": 26},
    "KC": {"man": 39, "zone": 61, "base": 22, "nickel": 62, "dime": 16, "shell": "Spagnuolo Disguised Blitz / Man", "dline_run_stop": 109, "pass_rush": 107, "blitz": 37, "perim_cb": 110, "slot_cov": 105, "lb_mismatch_rate": 19},
    "LAC": {"man": 24, "zone": 76, "base": 21, "nickel": 63, "dime": 16, "shell": "Two-High Quarters / Zone", "dline_run_stop": 99, "pass_rush": 100, "blitz": 25, "perim_cb": 96, "slot_cov": 100, "lb_mismatch_rate": 19},
    "LAR": {"man": 28, "zone": 72, "base": 24, "nickel": 62, "dime": 14, "shell": "Disguised Quarters / Cover 3", "dline_run_stop": 105, "pass_rush": 115, "blitz": 28, "perim_cb": 94, "slot_cov": 93, "lb_mismatch_rate": 24},
    "LV": {"man": 25, "zone": 75, "base": 26, "nickel": 62, "dime": 12, "shell": "Cover 3 / Cover 4 Mix", "dline_run_stop": 93, "pass_rush": 98, "blitz": 26, "perim_cb": 90, "slot_cov": 91, "lb_mismatch_rate": 26},
    "MIA": {"man": 27, "zone": 73, "base": 23, "nickel": 63, "dime": 14, "shell": "Split-Safety Cover 4 / Cover 3", "dline_run_stop": 96, "pass_rush": 98, "blitz": 28, "perim_cb": 100, "slot_cov": 96, "lb_mismatch_rate": 22},
    "MIN": {"man": 20, "zone": 80, "base": 19, "nickel": 57, "dime": 24, "shell": "Flores Zero-Blitz / Drop-8 Zone", "dline_run_stop": 110, "pass_rush": 111, "blitz": 41, "perim_cb": 99, "slot_cov": 102, "lb_mismatch_rate": 18},
    "NE": {"man": 31, "zone": 69, "base": 27, "nickel": 59, "dime": 14, "shell": "Pattern-Match Cover 1 / Cover 3", "dline_run_stop": 96, "pass_rush": 95, "blitz": 29, "perim_cb": 107, "slot_cov": 94, "lb_mismatch_rate": 24},
    "NO": {"man": 32, "zone": 68, "base": 25, "nickel": 63, "dime": 12, "shell": "Cover 1 / Cover 4 Match", "dline_run_stop": 94, "pass_rush": 96, "blitz": 26, "perim_cb": 96, "slot_cov": 95, "lb_mismatch_rate": 23},
    "NYG": {"man": 33, "zone": 67, "base": 24, "nickel": 64, "dime": 12, "shell": "Cover 3 / Cover 1 Blitz", "dline_run_stop": 95, "pass_rush": 106, "blitz": 31, "perim_cb": 92, "slot_cov": 93, "lb_mismatch_rate": 24},
    "NYJ": {"man": 35, "zone": 65, "base": 20, "nickel": 68, "dime": 12, "shell": "4-2-5 Nickel Cover 3 / Quarters", "dline_run_stop": 96, "pass_rush": 102, "blitz": 24, "perim_cb": 110, "slot_cov": 102, "lb_mismatch_rate": 20},
    "PHI": {"man": 27, "zone": 73, "base": 21, "nickel": 66, "dime": 13, "shell": "Two-High Quarters / Cover 6", "dline_run_stop": 107, "pass_rush": 106, "blitz": 22, "perim_cb": 106, "slot_cov": 103, "lb_mismatch_rate": 18},
    "PIT": {"man": 37, "zone": 63, "base": 27, "nickel": 59, "dime": 14, "shell": "Single-High Cover 3 / Cover 1", "dline_run_stop": 108, "pass_rush": 112, "blitz": 33, "perim_cb": 105, "slot_cov": 96, "lb_mismatch_rate": 23},
    "SEA": {"man": 26, "zone": 74, "base": 20, "nickel": 65, "dime": 15, "shell": "Disguised Split-Safety Zone", "dline_run_stop": 99, "pass_rush": 102, "blitz": 28, "perim_cb": 105, "slot_cov": 102, "lb_mismatch_rate": 19},
    "SF": {"man": 24, "zone": 76, "base": 24, "nickel": 66, "dime": 10, "shell": "Wide-9 4-3 Cover 3 / Cover 4", "dline_run_stop": 103, "pass_rush": 105, "blitz": 21, "perim_cb": 102, "slot_cov": 99, "lb_mismatch_rate": 17},
    "TB": {"man": 31, "zone": 69, "base": 25, "nickel": 61, "dime": 14, "shell": "Bowles Heavy Zone-Blitz / Cover 3", "dline_run_stop": 106, "pass_rush": 103, "blitz": 39, "perim_cb": 92, "slot_cov": 89, "lb_mismatch_rate": 28},
    "TEN": {"man": 27, "zone": 73, "base": 26, "nickel": 62, "dime": 12, "shell": "Cover 3 / Quarters", "dline_run_stop": 96, "pass_rush": 94, "blitz": 28, "perim_cb": 95, "slot_cov": 93, "lb_mismatch_rate": 24},
    "WAS": {"man": 33, "zone": 67, "base": 26, "nickel": 62, "dime": 12, "shell": "Cover 3 / Man-Press", "dline_run_stop": 94, "pass_rush": 97, "blitz": 29, "perim_cb": 91, "slot_cov": 90, "lb_mismatch_rate": 26}
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

DOME_TEAMS = {"ARI", "ATL", "DAL", "DET", "HOU", "IND", "LAC", "LAR", "LV", "MIN", "NO"}


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


def fetch_live_vegas_and_weather(current_week=10, target_year=2026):
    """
    Queries ESPN's live NFL Scoreboard API to extract:
    1. Live Vegas Point Spread, Over/Under, and Implied Team Totals
    2. Stadium Dome/Indoor status, Temperature, Wind Speed, and Precipitation
    3. Complete Week X NFL Team-to-Opponent mapping
    """
    cache_path = f"/tmp/vegas_weather_{target_year}_wk{current_week}_v14.json"
    now_ts = datetime.now(timezone.utc).timestamp()

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            if now_ts - cached.get("timestamp", 0) < 1800:
                return cached.get("env_map", {}), cached.get("opp_map", {})
        except Exception:
            pass

    env_map = {}
    opp_map = {}

    try:
        sb_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        req = urllib.request.Request(sb_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.2) as resp:
            sb_data = json.loads(resp.read().decode('utf-8'))

        for ev in sb_data.get("events", []):
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home_abbr = ""
            away_abbr = ""
            for c in competitors:
                abbr = normalize_team_abbrev(c.get("team", {}).get("abbreviation", ""))
                if c.get("homeAway") == "home":
                    home_abbr = abbr
                else:
                    away_abbr = abbr

            if home_abbr and away_abbr:
                opp_map[home_abbr] = away_abbr
                opp_map[away_abbr] = home_abbr

            # Venue & Weather extraction
            venue = comp.get("venue", {})
            is_indoor = bool(venue.get("indoor", False)) or (home_abbr in DOME_TEAMS)
            weather_obj = comp.get("weather", {}) or {}
            temp = weather_obj.get("temperature")
            w_desc = str(weather_obj.get("displayValue", "")).strip()

            wind_mph = 0
            wind_match = re.search(r'(\d+)\s*mph', w_desc.lower())
            if wind_match:
                wind_mph = int(wind_match.group(1))

            # Vegas Odds extraction
            over_under = 44.5
            home_spread = 0.0
            odds_list = comp.get("odds", [])
            if odds_list and isinstance(odds_list[0], dict):
                o_obj = odds_list[0]
                if o_obj.get("overUnder"):
                    try:
                        over_under = float(o_obj["overUnder"])
                    except Exception:
                        pass
                details = str(o_obj.get("details", "")).strip()  # e.g., "KC -6.5" or "EVEN"
                if details and details.upper() != "EVEN":
                    parts = details.split()
                    if len(parts) >= 2:
                        fav_team = normalize_team_abbrev(parts[0])
                        try:
                            sp_val = float(parts[1])
                            if fav_team == home_abbr:
                                home_spread = -abs(sp_val)
                            elif fav_team == away_abbr:
                                home_spread = abs(sp_val)
                        except Exception:
                            pass

            away_spread = -home_spread
            # Implied Total formula: (O/U / 2) - (Team Spread / 2)
            home_implied = round((over_under / 2.0) - (home_spread / 2.0), 1)
            away_implied = round((over_under / 2.0) - (away_spread / 2.0), 1)

            if is_indoor:
                weather_summary = "🏟️ Indoor Dome (Fast Track)"
            elif w_desc or temp:
                t_str = f"{temp}°F" if temp else ""
                weather_summary = f"🌤️ Outdoor {t_str} {w_desc}".strip()
            else:
                weather_summary = "🌤️ Standard Outdoor Stadium"

            env_map[home_abbr] = {
                "is_home": True,
                "opponent": away_abbr,
                "indoor": is_indoor,
                "temp": temp,
                "weather_desc": w_desc,
                "wind_mph": wind_mph,
                "weather_summary": weather_summary,
                "over_under": over_under,
                "spread": home_spread,
                "implied_total": home_implied
            }
            env_map[away_abbr] = {
                "is_home": False,
                "opponent": home_abbr,
                "indoor": is_indoor,
                "temp": temp,
                "weather_desc": w_desc,
                "wind_mph": wind_mph,
                "weather_summary": weather_summary,
                "over_under": over_under,
                "spread": away_spread,
                "implied_total": away_implied
            }
    except Exception:
        pass

    try:
        with open(cache_path, "w") as f:
            json.dump({"timestamp": now_ts, "env_map": env_map, "opp_map": opp_map}, f)
    except Exception:
        pass

    return env_map, opp_map


def fetch_team_live_depth_chart(item):
    abbr, team_id = item
    result = {
        "abbr": abbr,
        "base_front_name": "",
        "front_starters": [],
        "lb_starters": [],
        "cb_starters": [],
        "slot_safety_starters": []
    }
    try:
        dc_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"
        req = urllib.request.Request(dc_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            dc_data = json.loads(resp.read().decode('utf-8'))

        for chart in dc_data.get("depthchart", []):
            c_name = chart.get("name", "")
            positions = chart.get("positions", {})
            if any(k in positions for k in ("lcb", "rcb", "cb", "mlb", "wlb", "lde", "rde", "nt")):
                result["base_front_name"] = c_name
                for pos_key, pos_obj in positions.items():
                    athletes = pos_obj.get("athletes", [])
                    if not athletes:
                        continue
                    starter_name = athletes[0].get("displayName", "")
                    if not starter_name:
                        continue
                    pk = pos_key.lower()
                    if pk in ("lde", "rde", "de", "dt", "nt", "ldt", "rdt", "lolb", "rolb", "edge"):
                        if starter_name not in result["front_starters"]:
                            result["front_starters"].append(f"{starter_name} ({pk.upper()})")
                    elif pk in ("mlb", "wlb", "slb", "lilb", "rilb", "lb", "ilb"):
                        if starter_name not in result["lb_starters"]:
                            result["lb_starters"].append(f"{starter_name} ({pk.upper()})")
                    elif pk in ("lcb", "rcb", "cb"):
                        if starter_name not in result["cb_starters"]:
                            result["cb_starters"].append(f"{starter_name} (CB)")
                    elif pk in ("nb", "ss", "fs", "s", "db"):
                        if starter_name not in result["slot_safety_starters"]:
                            result["slot_safety_starters"].append(f"{starter_name} ({pk.upper()})")
                break
    except Exception:
        pass

    if not (result["front_starters"] or result["cb_starters"]):
        try:
            r_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
            req2 = urllib.request.Request(r_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req2, timeout=1.8) as resp2:
                r_data = json.loads(resp2.read().decode('utf-8'))

            for group in r_data.get("athletes", []):
                if "def" in str(group.get("position", "")).lower():
                    items = group.get("items", [])
                    items.sort(key=lambda x: x.get("experience", {}).get("years", 0), reverse=True)
                    for ath in items:
                        name = ath.get("displayName", "")
                        pos = ath.get("position", {}).get("abbreviation", "").upper()
                        if pos in ("DE", "DT", "NT", "DL", "EDGE") and len(result["front_starters"]) < 3:
                            result["front_starters"].append(f"{name} ({pos})")
                        elif pos in ("LB", "ILB", "MLB", "OLB") and len(result["lb_starters"]) < 2:
                            result["lb_starters"].append(f"{name} ({pos})")
                        elif pos == "CB" and len(result["cb_starters"]) < 2:
                            result["cb_starters"].append(f"{name} (CB)")
                        elif pos in ("S", "FS", "SS", "DB") and len(result["slot_safety_starters"]) < 2:
                            result["slot_safety_starters"].append(f"{name} ({pos})")
        except Exception:
            pass

    return result


def build_live_defense_and_offense_matrix(league=None, current_week=10, target_year=2026):
    """
    Builds both:
    1. live_matrix: 32-team defensive schemes, live starters, defensive injuries, & full-season D/ST form
    2. offense_inj_map: Offensive Line injuries (OT/OG/C) & vacated skill volume (RB/WR/TE Out/IR) per team
    """
    cache_path = f"/tmp/live_def_off_matrix_{target_year}_wk{current_week}_v14.json"
    now_ts = datetime.now(timezone.utc).timestamp()

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            if now_ts - cached.get("timestamp", 0) < 1800:
                return cached["matrix"], cached.get("offense_inj", {})
        except Exception:
            pass

    live_matrix = {}
    offense_inj = {}
    for team_abbr, base_data in NFL_DEFENSE_MATRIX.items():
        live_matrix[team_abbr] = dict(base_data)
        live_matrix[team_abbr]["injuries"] = []
        live_matrix[team_abbr]["live_adj_summary"] = "Full Strength"
        live_matrix[team_abbr]["front_starters"] = f"{team_abbr} Starting Front"
        live_matrix[team_abbr]["lb_starters"] = f"{team_abbr} Starting LBs"
        live_matrix[team_abbr]["cb_starters"] = f"{team_abbr} Outside CBs"
        live_matrix[team_abbr]["slot_starters"] = f"{team_abbr} Nickel/Safeties"
        live_matrix[team_abbr]["key_defender"] = f"{team_abbr} Active Starters"
        live_matrix[team_abbr]["weekly_trend_note"] = f"{target_year} Full-Season Overall Scheme"

        offense_inj[team_abbr] = {
            "ol_out": [],
            "ol_penalty": 0.0,
            "RB": [],
            "WR": [],
            "TE": [],
            "QB": []
        }

    # 1. Fetch Live Current-Week Depth Charts in Parallel
    try:
        with ThreadPoolExecutor(max_workers=16) as executor:
            dc_results = list(executor.map(fetch_team_live_depth_chart, ESPN_TEAM_IDS.items()))

        for res in dc_results:
            abbr = res["abbr"]
            if abbr not in live_matrix:
                continue
            d_team = live_matrix[abbr]

            if res["base_front_name"]:
                d_team["shell"] = f"{res['base_front_name']} • {d_team['shell']}"
                if "4-2-5" in res["base_front_name"] or "nickel" in res["base_front_name"].lower():
                    d_team["nickel"] = max(d_team["nickel"], 68)
                    d_team["base"] = min(d_team["base"], 18)

            if res["front_starters"]:
                d_team["front_starters"] = ", ".join(res["front_starters"][:3])
            if res["lb_starters"]:
                d_team["lb_starters"] = ", ".join(res["lb_starters"][:2])
            if res["cb_starters"]:
                d_team["cb_starters"] = ", ".join(res["cb_starters"][:2])
            if res["slot_safety_starters"]:
                d_team["slot_starters"] = ", ".join(res["slot_safety_starters"][:2])

            headline_parts = []
            if res["front_starters"]:
                headline_parts.append(res["front_starters"][0])
            if res["cb_starters"]:
                headline_parts.append(res["cb_starters"][0])
            if res["lb_starters"]:
                headline_parts.append(res["lb_starters"][0])
            if headline_parts:
                d_team["key_defender"] = " • ".join(headline_parts)
    except Exception:
        pass

    # 2. Fetch Live NFL Injuries (Both Defensive Matrix Downgrades AND Offensive Vacated Volume / O-Line)
    try:
        inj_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
        req = urllib.request.Request(inj_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            inj_json = json.loads(resp.read().decode('utf-8'))

        for team_entry in inj_json.get("injuries", []):
            raw_abbr = team_entry.get("team", {}).get("abbreviation", "")
            t_abbr = normalize_team_abbrev(raw_abbr)

            for item in team_entry.get("injuries", []):
                athlete = item.get("athlete", {})
                if not t_abbr:
                    t_abbr = normalize_team_abbrev(athlete.get("team", {}).get("abbreviation", ""))
                if t_abbr not in live_matrix:
                    continue

                pos = athlete.get("position", {}).get("abbreviation", "").upper()
                name = athlete.get("displayName", "Player")
                status = item.get("status", "")
                status_low = status.lower()

                if any(s in status_low for s in ("out", "injured reserve", "ir", "doubtful", "suspension")):
                    sev = 1.0
                    short_stat = "OUT/IR" if "reserve" in status_low or "out" in status_low else "Doubtful"
                elif "questionable" in status_low:
                    sev = 0.45
                    short_stat = "Q"
                else:
                    continue

                # A. Track Offensive Line & Offensive Skill Vacated Volume
                o_team = offense_inj[t_abbr]
                if pos in ("OT", "LT", "RT", "G", "OG", "LG", "RG", "C", "OL") and sev >= 1.0:
                    o_team["ol_out"].append(f"{name} ({pos})")
                    o_team["ol_penalty"] = round(min(1.2, o_team["ol_penalty"] + 0.35), 2)
                elif pos in ("RB", "WR", "TE", "QB") and sev >= 1.0:
                    if len(o_team[pos]) < 3:
                        o_team[pos].append(f"{name} ({short_stat})")

                # B. Track Defensive Injuries & Shift Coverage Tendencies
                if pos not in ("CB", "DB", "S", "FS", "SS", "LB", "ILB", "MLB", "OLB", "DE", "DT", "NT", "DL", "EDGE"):
                    continue

                d_team = live_matrix[t_abbr]
                d_team["injuries"].append(f"{name} ({pos} - {short_stat})")

                if pos in ("CB", "DB"):
                    d_team["perim_cb"] = max(70, round(d_team["perim_cb"] - (6.5 * sev)))
                    d_team["slot_cov"] = max(70, round(d_team["slot_cov"] - (3.5 * sev)))
                    man_shift = round(4.5 * sev)
                    d_team["man"] = max(14, d_team["man"] - man_shift)
                    d_team["zone"] = min(86, 100 - d_team["man"])
                elif pos in ("DT", "NT", "DL"):
                    d_team["dline_run_stop"] = max(70, round(d_team["dline_run_stop"] - (6.5 * sev)))
                    d_team["pass_rush"] = max(70, round(d_team["pass_rush"] - (2.5 * sev)))
                elif pos in ("DE", "EDGE", "OLB"):
                    d_team["pass_rush"] = max(70, round(d_team["pass_rush"] - (6.5 * sev)))
                    d_team["dline_run_stop"] = max(70, round(d_team["dline_run_stop"] - (3.0 * sev)))
                elif pos in ("LB", "ILB", "MLB"):
                    d_team["slot_cov"] = max(70, round(d_team["slot_cov"] - (5.5 * sev)))
                    d_team["dline_run_stop"] = max(70, round(d_team["dline_run_stop"] - (3.5 * sev)))
                    d_team["lb_mismatch_rate"] = min(45, round(d_team["lb_mismatch_rate"] + (4.5 * sev)))
                elif pos in ("S", "FS", "SS"):
                    d_team["slot_cov"] = max(70, round(d_team["slot_cov"] - (4.5 * sev)))
                    d_team["perim_cb"] = max(70, round(d_team["perim_cb"] - (3.0 * sev)))
                    d_team["lb_mismatch_rate"] = min(45, round(d_team["lb_mismatch_rate"] + (3.0 * sev)))
    except Exception:
        pass

    # 3. Calibrate 100% on Full 2026 Season Overall D/ST Performance
    if league is not None:
        try:
            dst_players = league.free_agents(week=current_week, size=40, position='D/ST')
            for t in league.teams:
                for p in t.roster:
                    if p.position == 'D/ST':
                        dst_players.append(p)

            seen_dst = set()
            for dst in dst_players:
                pro_t = normalize_team_abbrev(getattr(dst, 'proTeam', ''))
                if not pro_t or pro_t in seen_dst or pro_t not in live_matrix:
                    continue
                seen_dst.add(pro_t)

                season_avg = float(getattr(dst, 'avg_points', 6.5) or 6.5)
                total_pts = float(getattr(dst, 'total_points', 0.0) or 0.0)
                form_delta = round((season_avg - 6.5) * 1.35)

                d_team = live_matrix[pro_t]
                d_team["dline_run_stop"] = max(70, min(122, d_team["dline_run_stop"] + form_delta))
                d_team["pass_rush"] = max(70, min(122, d_team["pass_rush"] + form_delta))
                d_team["perim_cb"] = max(70, min(122, d_team["perim_cb"] + form_delta))
                d_team["slot_cov"] = max(70, min(122, d_team["slot_cov"] + round(form_delta * 0.8)))

                if season_avg >= 8.5:
                    tier_label = "Elite Top-Tier Unit"
                elif season_avg >= 6.8:
                    tier_label = "Solid Above-Avg Unit"
                elif season_avg >= 5.2:
                    tier_label = "Middle-of-Pack Unit"
                else:
                    tier_label = "Vulnerable Bottom-Tier Unit"

                d_team["weekly_trend_note"] = f"{target_year} Season Overall: {season_avg:.1f} D/ST PPG ({total_pts:.0f} Total Pts — {tier_label})"
        except Exception:
            pass

    for t_abbr, d_team in live_matrix.items():
        if d_team["injuries"]:
            top_inj = ", ".join(d_team["injuries"][:4])
            extra = f" +{len(d_team['injuries']) - 4} more" if len(d_team["injuries"]) > 4 else ""
            d_team["live_adj_summary"] = f"{top_inj}{extra}"

    try:
        with open(cache_path, "w") as f:
            json.dump({"timestamp": now_ts, "matrix": live_matrix, "offense_inj": offense_inj}, f)
    except Exception:
        pass

    return live_matrix, offense_inj


def evaluate_volume_and_vacated_context(player, pos, current_week, espn_proj, season_avg, offense_inj_map):
    """
    Calculates:
    1. Expected Fantasy Points (xFP) Opportunity Edge from raw Targets, Receptions & Carries
    2. Teammate Vacated Volume Boost (when a same-position starter on the player's team is Out/IR)
    3. Offensive Line Injury Trench Penalty (when 1+ starting O-Linemen on the player's team are Out/IR)
    """
    pro_team = normalize_team_abbrev(getattr(player, 'proTeam', ''))
    o_ctx = (offense_inj_map or {}).get(pro_team, {})

    vol_adj = 0.0
    notes = []
    has_vacated_boost = False

    # 1. Check Teammate Vacated Volume on Player's Own Offense
    missing_teammates = [
        tm for tm in o_ctx.get(pos, [])
        if player.name.lower().split()[-1] not in tm.lower()
    ]
    if missing_teammates and espn_proj >= 5.5:
        has_vacated_boost = True
        vac_pts = 0.85 if len(missing_teammates) == 1 else 1.35
        vol_adj += vac_pts
        notes.append(f"⚡ Vacated Volume (+{vac_pts} pts): {pro_team} {pos} {', '.join(missing_teammates[:2])} listed Out/IR")

    # 2. Check Offensive Line Injuries on Player's Own Offense
    ol_out = o_ctx.get("ol_out", [])
    ol_pen = float(o_ctx.get("ol_penalty", 0.0))
    if ol_out and pos in ("RB", "QB"):
        applied_ol_pen = ol_pen if pos == "RB" else round(ol_pen * 0.75, 2)
        vol_adj -= applied_ol_pen
        notes.append(f"⚠️ O-Line Trench Penalty (-{applied_ol_pen} pts): {pro_team} missing {', '.join(ol_out[:2])}")

    # 3. Extract Raw Targets, Receptions & Carries from ESPN Stat Breakdowns (xFP Volume Check)
    p_stats = getattr(player, 'stats', {}) or {}
    targets_list = []
    carries_list = []
    rec_list = []

    for w in range(1, current_week):
        w_obj = p_stats.get(w) or p_stats.get(str(w)) or {}
        bd = w_obj.get('breakdown', {}) or {}
        if not bd:
            continue
        t_val = bd.get('receivingTargets', bd.get('58', 0)) or 0
        r_val = bd.get('receivingReceptions', bd.get('53', 0)) or 0
        c_val = bd.get('rushingAttempts', bd.get('23', 0)) or 0
        if (t_val + c_val) > 0:
            targets_list.append(float(t_val))
            rec_list.append(float(r_val))
            carries_list.append(float(c_val))

    if targets_list or carries_list:
        games_n = max(1, len(targets_list))
        t_pg = round(sum(targets_list) / games_n, 1)
        r_pg = round(sum(rec_list) / games_n, 1)
        c_pg = round(sum(carries_list) / games_n, 1)

        if pos in ("WR", "TE"):
            xfp_pg = (t_pg * 1.35) + (r_pg * 0.35)
            if t_pg >= 7.0:
                vol_adj += 0.65
                notes.append(f"🎯 High Target Earner: {t_pg} Targets / {r_pg} Rec per game (+0.65 xFP)")
            elif t_pg <= 3.2 and season_avg >= 9.0:
                vol_adj -= 0.55
                notes.append(f"⚠️ Low-Volume TD Fluke Risk: Only {t_pg} Targets/gm (-0.55 xFP)")
            else:
                notes.append(f"📊 Season Usage: {t_pg} Targets & {r_pg} Catches/gm ({xfp_pg:.1f} xFP)")
        elif pos == "RB":
            touches_pg = round(c_pg + r_pg, 1)
            if touches_pg >= 15.0 or t_pg >= 4.0:
                vol_adj += 0.70
                notes.append(f"🔋 Workhorse Volume: {c_pg} Carries + {t_pg} Targets/gm (+0.70 xFP)")
            elif touches_pg <= 7.0 and not has_vacated_boost:
                vol_adj -= 0.45
                notes.append(f"⚠️ Low Touch Floor: {c_pg} Carries + {t_pg} Targets/gm (-0.45 xFP)")
            else:
                notes.append(f"📊 Season Usage: {c_pg} Carries & {t_pg} Targets/gm")

    if not notes:
        if espn_proj >= season_avg + 2.2:
            notes.append(f"📈 Projected Role Expansion (Wk Proj {espn_proj} vs {season_avg} Season Avg)")
        else:
            notes.append(f"📊 Steady Role ({season_avg} Season PPG | Healthy O-Line)")

    vol_adj = round(max(-1.5, min(1.8, vol_adj)), 1)
    return vol_adj, has_vacated_boost, " • ".join(notes)


def evaluate_vegas_and_weather_context(player, pos, vegas_weather_map):
    """
    Calculates Vegas Implied Team Total, Point Spread Game Script, and Stadium Weather adjustments.
    """
    pro_team = normalize_team_abbrev(getattr(player, 'proTeam', ''))
    env = (vegas_weather_map or {}).get(pro_team)
    if not env:
        return 0.0, "Standard Neutral Game Script (22.0 Implied Pts)"

    adj = 0.0
    implied = float(env.get("implied_total", 22.0))
    spread = float(env.get("spread", 0.0))
    ou = float(env.get("over_under", 44.5))
    indoor = bool(env.get("indoor", False))
    wind = int(env.get("wind_mph", 0))
    w_desc = str(env.get("weather_desc", "")).lower()
    w_summary = env.get("weather_summary", "Standard Stadium")

    # 1. Vegas Implied Team Total (TD & Red-Zone Equity)
    td_equity = (implied - 22.0) * 0.12
    adj += td_equity

    # 2. Point Spread 4th-Quarter Game Script
    clean_n, _ = clean_player_name(player.name)
    is_pass_rb = clean_n in PASS_CATCHING_RBS
    script_tag = "Balanced Script"

    if spread <= -5.5:
        if pos == "RB" and not is_pass_rb:
            adj += 0.45
            script_tag = f"Heavy Favorite ({spread}) → +4th Qtr Rush Volume"
        else:
            script_tag = f"Favorite ({spread})"
    elif spread >= 5.5:
        if pos in ("WR", "TE", "QB") or is_pass_rb:
            adj += 0.40
            script_tag = f"Trailing Underdog (+{spread}) → +Garbage-Time Pass Volume"
        elif pos == "RB":
            adj -= 0.45
            script_tag = f"Underdog (+{spread}) → Rushing Script Risk"
    else:
        script_tag = f"Competitive Spread ({spread if spread < 0 else '+' + str(spread)})"

    # 3. Dome vs Outdoor Wind/Precipitation
    if indoor and pos in ("QB", "WR", "TE"):
        adj += 0.30
    elif not indoor:
        has_precip = any(k in w_desc for k in ("rain", "snow", "storm", "showers", "sleet"))
        if wind >= 17 or has_precip:
            if pos in ("QB", "WR"):
                adj -= 0.55
            elif pos == "RB":
                adj += 0.30

    adj = round(max(-1.5, min(1.5, adj)), 1)
    summary_line = f"Vegas Implied: {implied} pts (O/U {ou}, {script_tag}) • {w_summary}"
    return adj, summary_line


def analyze_micro_matchup(player, pos, espn_proj, season_avg, is_desperate=False, live_matrix=None, scheme_weight=0.45):
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
            "injury_impact": "None",
            "weekly_trend": "N/A"
        }

    d = active_matrix[opp]
    base_d = NFL_DEFENSE_MATRIX.get(opp, d)
    clean_n, _ = clean_player_name(player.name)
    raw_adj = 0.0

    man_pct = d["man"]
    zone_pct = d["zone"]
    base_pct = d["base"]
    nickel_pct = d["nickel"]
    dime_pct = d["dime"]

    cb_names = d.get("cb_starters", f"{opp} Outside CBs")
    slot_names = d.get("slot_starters", f"{opp} Nickel/Safeties")
    lb_names = d.get("lb_starters", f"{opp} Linebackers")
    front_names = d.get("front_starters", f"{opp} Defensive Front")

    if pos == "WR":
        is_slot = (clean_n in SLOT_HEAVY_WRS) or (espn_proj < 11.2 and season_avg >= espn_proj)
        alignment = "Slot / Motion Alignment" if is_slot else "Perimeter (X/Z) Alignment"

        if is_slot:
            cov_edge = ((zone_pct - 70) * 0.065) + ((d["blitz"] - 27) * 0.05)
        else:
            cov_edge = ((man_pct - 30) * 0.045) if d["perim_cb"] < 102 else -((man_pct - 30) * 0.045)
        raw_adj += cov_edge

        if not is_slot:
            cb_diff = 100 - d["perim_cb"]
            cb_pts = cb_diff * 0.13
            raw_adj += cb_pts
            if d["perim_cb"] >= 109:
                battle = f"Perimeter WR vs {opp} Lockdown Outside CBs ({cb_names}) — Shadow/Bracket Risk"
            elif d["perim_cb"] <= 92:
                battle = f"Perimeter WR vs {opp} Burnable Outside CBs ({cb_names}, Rating: {d['perim_cb']}) — Advantage WR"
            else:
                battle = f"Perimeter WR vs {opp} Outside CBs ({cb_names}, Rating: {d['perim_cb']})"
        else:
            slot_diff = 100 - d["slot_cov"]
            slot_pts = slot_diff * 0.12
            raw_adj += slot_pts
            if d["perim_cb"] >= 109:
                raw_adj += 1.0
                battle = f"Slot Funnel Alert: {opp}'s outside CBs ({cb_names}) funnel targets inside vs {slot_names}"
            else:
                battle = f"Slot WR vs {opp} Nickel/Slot Defenders ({slot_names}, Rating: {d['slot_cov']})"

        if d["lb_mismatch_rate"] >= 24 and (is_slot or nickel_pct >= 62):
            lb_boost = round((d["lb_mismatch_rate"] - 19) * 0.14, 1)
            raw_adj += lb_boost
            trench_lb_note = (
                f"🔥 LB Coverage Mismatch ({d['lb_mismatch_rate']}% LB/Safety Slot Rate): "
                f"When {opp} transitions between Base ({base_pct}%) and Nickel ({nickel_pct}%), "
                f"motion/slot receivers isolate on LBs ({lb_names}) over the middle."
            )
        elif d["slot_cov"] >= 105 and is_slot:
            trench_lb_note = f"⚠️ Tight Nickel Coverage: {opp} uses {slot_names} & {lb_names} to erase slot seams (Dime {dime_pct}%)."
        else:
            trench_lb_note = f"Standard {alignment} vs {opp} ({nickel_pct}% Nickel / {dime_pct}% Dime | LBs: {lb_names})."

    elif pos == "RB":
        is_receiving_back = (clean_n in PASS_CATCHING_RBS) or (season_avg > espn_proj + 1.5)

        trench_diff = 100 - d["dline_run_stop"]
        trench_pts = trench_diff * 0.15
        raw_adj += trench_pts

        if d["dline_run_stop"] >= 108:
            battle = f"RB vs {opp} Elite Front ({front_names}, Run Stop Rating: {d['dline_run_stop']}) — Tough Trench Sledding"
        elif d["dline_run_stop"] <= 92:
            battle = f"RB vs {opp} Soft Interior Front ({front_names}, Rating: {d['dline_run_stop']}) — High Yards-Before-Contact Smash"
        else:
            battle = f"RB vs {opp} Defensive Front ({front_names} | LBs: {lb_names} | Rating: {d['dline_run_stop']})"

        sub_pkg_pct = nickel_pct + dime_pct
        if sub_pkg_pct >= 77:
            raw_adj += 1.2
            trench_lb_note = f"⚡ Light Box Advantage: {opp} plays {sub_pkg_pct}% Nickel/Dime (only {base_pct}% Base), creating 6-man light boxes."
        elif is_receiving_back and (d["blitz"] >= 30 or zone_pct >= 74):
            raw_adj += 1.3
            trench_lb_note = f"🔥 Checkdown/LB Mismatch: {opp}'s {d['blitz']}% blitz & {zone_pct}% zone forces LBs ({lb_names}) to cover RBs in space."
        else:
            trench_lb_note = f"Box Count Split: {opp} runs {base_pct}% Base (7+ man box) vs {nickel_pct}% Nickel (LBs: {lb_names})."

    elif pos == "TE":
        seam_diff = (100 - d["slot_cov"]) * 0.11 + ((d["lb_mismatch_rate"] - 20) * 0.13)
        raw_adj += seam_diff
        if d["blitz"] >= 31:
            raw_adj += 0.9
            battle = f"TE Hot-Read Advantage vs {opp}'s {d['blitz']}% Blitz Rate (covered by {lb_names} / {slot_names})"
        else:
            battle = f"TE vs {opp} Seam/LB Coverage ({lb_names} & {slot_names}, Rating: {d['slot_cov']})"

        trench_lb_note = (
            f"Linebacker Seam Matchup: {opp} allows a {d['lb_mismatch_rate']}% LB coverage mismatch rate "
            f"in {d['shell']} ({zone_pct}% Zone / {man_pct}% Man)."
        )

    else:
        rush_diff = (100 - d["pass_rush"]) * 0.12
        sec_diff = (100 - ((d["perim_cb"] + d["slot_cov"]) / 2)) * 0.11
        raw_adj += (rush_diff + sec_diff)
        battle = f"QB vs {opp} Pass Rush ({front_names}, Pressure Rating: {d['pass_rush']}, Blitz: {d['blitz']}%)"
        trench_lb_note = f"Coverage Shell Read: {opp} runs {d['shell']} ({zone_pct}% Zone / {man_pct}% Man | CBs: {cb_names})."

    adj = round(max(-2.5, min(2.5, raw_adj * scheme_weight)), 1)

    if adj >= 1.1:
        grade = "A+ (Smash Scheme Mismatch)"
    elif adj >= 0.6:
        grade = "A (Strong Scheme Edge)"
    elif adj >= 0.2:
        grade = "B+ (Favorable Fit)"
    elif adj >= -0.3:
        grade = "B (Neutral Scheme)"
    elif adj >= -0.9:
        grade = "C (Tough Assignment)"
    else:
        grade = "D (Shadow / Trench Wall)"

    cb_drop = base_d["perim_cb"] - d["perim_cb"]
    dl_drop = base_d["dline_run_stop"] - d["dline_run_stop"]
    lb_jump = d["lb_mismatch_rate"] - base_d["lb_mismatch_rate"]

    inj_list = d.get("injuries", [])
    if inj_list:
        impacts = []
        if cb_drop > 0:
            impacts.append(f"CB Net -{cb_drop}")
        if dl_drop > 0:
            impacts.append(f"Run Stop Net -{dl_drop}")
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
        "injury_impact": injury_report_str,
        "weekly_trend": d.get("weekly_trend_note", "2026 Full-Season Scheme")
    }
    return adj, grade, report


def run_self_learning_audit(roster_players, free_agents, current_week, live_def_matrix):
    """
    Audits completed weeks (Weeks 1 through current_week - 1) and computes
    POSITION-SPECIFIC ('QB', 'RB', 'WR', 'TE') calibration weights so a low-scoring
    TE week never distorts RB or WR projections.
    """
    audit_weeks = [w for w in range(max(1, current_week - 4), current_week)]
    default_pos_model = {"espn_w": 0.65, "season_w": 0.35, "scheme_mult": 0.45, "yt_mult": 0.38, "bias_offset": -0.4}

    if not audit_weeks:
        return {
            "espn_w": 0.65,
            "season_w": 0.35,
            "scheme_mult": 0.45,
            "yt_mult": 0.38,
            "bias_offset": 0.0,
            "pos_models": {p: dict(default_pos_model) for p in ("QB", "RB", "WR", "TE")},
            "old_mae": 0.0,
            "new_mae": 0.0,
            "old_bias": 0.0,
            "samples": 0,
            "summary": "Week 1 Baseline (No past completed weeks to audit yet).",
            "pos_summary": "Using default baseline weights across all positions.",
            "receipts": []
        }

    pool = list(roster_players) + list(free_agents[:45])
    seen_names = set()
    unique_pool = []
    for p in pool:
        if p.name not in seen_names and getattr(p, 'position', '') in ('QB', 'RB', 'WR', 'TE'):
            seen_names.add(p.name)
            unique_pool.append(p)

    roster_names = {p.name for p in roster_players}
    records = []

    for p in unique_pool:
        p_stats = getattr(p, 'stats', {}) or {}
        season_avg = float(getattr(p, 'avg_points', 0.0) or 0.0)

        for w in audit_weeks:
            w_data = p_stats.get(w) or p_stats.get(str(w)) or {}
            proj = w_data.get('projected_points')
            actual = w_data.get('points')
            if proj is None or actual is None:
                continue
            proj = float(proj)
            actual = float(actual)
            if proj < 4.5 or (actual == 0.0 and proj < 7.0):
                continue

            eff_season = season_avg if season_avg > 0 else proj
            old_base = (0.70 * proj) + (0.30 * eff_season)

            scheme_raw, _, _ = analyze_micro_matchup(
                p, p.position, proj, eff_season, is_desperate=True, live_matrix=live_def_matrix, scheme_weight=1.0
            )
            simulated_old_yt = 1.8 if p.name in roster_names else 1.2
            old_blended = round(old_base + max(0.0, scheme_raw) + simulated_old_yt, 1)

            records.append({
                "name": p.name,
                "pos": p.position,
                "week": w,
                "is_rostered": p.name in roster_names,
                "espn_proj": round(proj, 1),
                "season_avg": round(eff_season, 1),
                "scheme_raw": scheme_raw,
                "old_blended": old_blended,
                "actual": round(actual, 1),
                "old_error": round(old_blended - actual, 1)
            })

    if not records:
        return {
            "espn_w": 0.65,
            "season_w": 0.35,
            "scheme_mult": 0.45,
            "yt_mult": 0.38,
            "bias_offset": -0.5,
            "pos_models": {p: dict(default_pos_model) for p in ("QB", "RB", "WR", "TE")},
            "old_mae": 0.0,
            "new_mae": 0.0,
            "old_bias": 0.0,
            "samples": 0,
            "summary": "Calibrated with conservative anti-inflation weights.",
            "pos_summary": "Default conservative weights active.",
            "receipts": []
        }

    def calibrate_subset(sub_records):
        if not sub_records:
            return dict(default_pos_model)
        sub_bias = sum(r["old_blended"] - r["actual"] for r in sub_records) / len(sub_records)
        best_ew = 0.60
        best_mae = 999.0
        for wc in (0.35, 0.50, 0.65, 0.80):
            c_mae = sum(
                abs(((wc * r["espn_proj"]) + ((1.0 - wc) * r["season_avg"])) - r["actual"])
                for r in sub_records
            ) / len(sub_records)
            if c_mae < best_mae:
                best_mae = c_mae
                best_ew = wc
        best_sw = round(1.0 - best_ew, 2)

        if sub_bias > 1.2:
            df = max(0.25, min(0.50, 1.0 / (1.0 + (sub_bias * 0.45))))
        else:
            df = 0.48
        s_mult = round(df, 2)
        y_mult = round(df * 0.82, 2)

        errs = [
            ((best_ew * r["espn_proj"]) + (best_sw * r["season_avg"]) + (r["scheme_raw"] * s_mult)) - r["actual"]
            for r in sub_records
        ]
        res_bias = sum(errs) / len(errs)
        b_off = round(max(-2.2, min(0.5, -res_bias * 0.70)), 2)
        return {
            "espn_w": best_ew,
            "season_w": best_sw,
            "scheme_mult": s_mult,
            "yt_mult": y_mult,
            "bias_offset": b_off
        }

    global_model = calibrate_subset(records)
    pos_models = {}
    pos_notes = []
    for pos in ("QB", "RB", "WR", "TE"):
        pos_recs = [r for r in records if r["pos"] == pos]
        if len(pos_recs) >= 3:
            pos_models[pos] = calibrate_subset(pos_recs)
        else:
            pos_models[pos] = dict(global_model)
        pm = pos_models[pos]
        b_str = f"+{pm['bias_offset']}" if pm['bias_offset'] >= 0 else f"{pm['bias_offset']}"
        pos_notes.append(f"{pos}: {int(pm['espn_w']*100)}/{int(pm['season_w']*100)} Base, {pm['scheme_mult']}x Scheme, {b_str} Offset")

    old_bias = round(sum(r["old_blended"] - r["actual"] for r in records) / len(records), 2)
    old_mae = round(sum(abs(r["old_blended"] - r["actual"]) for r in records) / len(records), 2)

    new_mae_total = 0.0
    for r in records:
        pm = pos_models.get(r["pos"], global_model)
        new_base = (pm["espn_w"] * r["espn_proj"]) + (pm["season_w"] * r["season_avg"])
        new_proj = round(max(1.0, new_base + (r["scheme_raw"] * pm["scheme_mult"]) + pm["bias_offset"]), 1)
        r["new_blended"] = new_proj
        r["new_error"] = round(new_proj - r["actual"], 1)
        new_mae_total += abs(new_proj - r["actual"])

    new_mae = round(new_mae_total / len(records), 2)
    records.sort(key=lambda x: (not x["is_rostered"], -x["week"], -abs(x["old_error"])))

    summary_text = (
        f"Audited {len(records)} player-weeks (Wks {audit_weeks[0]}–{audit_weeks[-1]}). "
        f"Old uncalibrated model over-projected by {'+' if old_bias >= 0 else ''}{old_bias} pts/gm (MAE: {old_mae}). "
        f"Position-Specific Auto-Tuner reduced error to MAE {new_mae} pts."
    )

    return {
        "espn_w": global_model["espn_w"],
        "season_w": global_model["season_w"],
        "scheme_mult": global_model["scheme_mult"],
        "yt_mult": global_model["yt_mult"],
        "bias_offset": global_model["bias_offset"],
        "pos_models": pos_models,
        "old_mae": old_mae,
        "new_mae": new_mae,
        "old_bias": old_bias,
        "samples": len(records),
        "summary": summary_text,
        "pos_summary": " &nbsp;|&nbsp; ".join(pos_notes),
        "receipts": records[:10]
    }


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
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v11.json"
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
    clean_s = seg_text.lower().replace(".", "").replace("'", "").replace("-", " ")
    score = 0.0
    signals = []

    for phrase, weight in BEARISH_PHRASES.items():
        if phrase in clean_s:
            score += weight
            signals.append(f"-{phrase}")

    for phrase, weight in BULLISH_PHRASES.items():
        idx = clean_s.find(phrase)
        if idx != -1:
            prefix_words = clean_s[:idx].split()[-3:]
            if any(nw in prefix_words for nw in NEGATION_WORDS):
                score -= weight
                signals.append(f"-not {phrase}")
            else:
                score += weight
                signals.append(f"+{phrase}")

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


def find_player_clips(player_name, yt_videos, is_desperate=False, yt_mult=0.40):
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

    consensus_boost = len(bullish_channels) * (0.55 if is_desperate else 0.35)
    consensus_penalty = len(bearish_channels) * 0.65

    raw_yt_bonus = (cumulative_sentiment_pts + consensus_boost - consensus_penalty) * yt_mult

    max_cap = 2.4 if is_desperate else 1.6
    yt_bonus = round(max(-2.5, min(max_cap, raw_yt_bonus)), 1)

    if yt_bonus >= 0.9:
        sentiment_label = f"🟢 Strong Analyst Endorsement ({len(bullish_channels)} Bullish Ch)"
    elif yt_bonus >= 0.2:
        sentiment_label = "🟢 Positive Film Consensus"
    elif yt_bonus <= -0.3:
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

            # 1. Fetch Live Vegas Odds, Implied Totals, Weather & Scoreboard Matchups
            vegas_weather_map, sb_opp_map = fetch_live_vegas_and_weather(current_week=week, target_year=year)

            free_agents = league.free_agents(week=week, size=100)
            nfl_opp_map = dict(sb_opp_map)

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

            for p in my_team.roster:
                p.pro_opponent = resolve_player_opponent(p)
            for fa in free_agents[:85]:
                fa.pro_opponent = resolve_player_opponent(fa)

            yt_videos = fetch_weekly_2026_videos(current_week=week, target_year=year)
            live_def_matrix, offense_inj_map = build_live_defense_and_offense_matrix(
                league=league, current_week=week, target_year=year
            )

            # 2. Run Position-Specific Self-Learning Backtest Audit Across Completed Weeks
            calibration = run_self_learning_audit(
                my_team.roster, free_agents, current_week=week, live_def_matrix=live_def_matrix
            )
            pos_models = calibration.get("pos_models", {})

            playoff_data = calculate_playoff_odds(league, my_team, week)
            playoff_pct = playoff_data["playoff_pct"]

            if playoff_pct < 35.0:
                mode = "DESPERATION MODE"
                mode_desc = "Playoff odds are critical (<35%). Hunting vacated volume, Vegas shootout scripts, and scheme mismatches calibrated by position backtesting."
            elif playoff_pct < 60.0:
                mode = "AGGRESSIVE PUSH"
                mode_desc = "Playoff race is tight. Blending position-tuned baselines with Vegas implied totals, xFP usage, and scheme edges."
            else:
                mode = "CONTENDER MODE"
                mode_desc = "Strong playoff position. Prioritizing high-floor xFP volume, Vegas favorites, and scheme fits."

            is_desperate = playoff_pct < 45.0

            def score_player_full(player):
                pos = player.position
                pm = pos_models.get(pos, calibration)
                espn_w = pm.get("espn_w", 0.65)
                season_w = pm.get("season_w", 0.35)
                scheme_mult = pm.get("scheme_mult", 0.45)
                yt_mult = pm.get("yt_mult", 0.38)
                bias_offset = pm.get("bias_offset", -0.4)

                curr_stats = player.stats.get(week, {})
                espn_proj = float(curr_stats.get('projected_points', player.projected_total_points / 17))

                season_avg = float(getattr(player, 'avg_points', 0.0) or 0.0)
                if season_avg <= 0:
                    played_pts = [
                        float(player.stats.get(w, {}).get('points', 0))
                        for w in range(1, week)
                        if player.stats.get(w, {}).get('points') is not None and float(player.stats.get(w, {}).get('points', 0)) > 0
                    ]
                    season_avg = (sum(played_pts) / len(played_pts)) if played_pts else espn_proj

                # Evaluate xFP Opportunity Volume, Teammate Vacated Volume & O-Line Health
                vol_adj, has_vacated_boost, usage_note = evaluate_volume_and_vacated_context(
                    player, pos, week, espn_proj, season_avg, offense_inj_map
                )

                # If a starter ahead of this player is OUT/IR, weight 85% toward this week's expanded projection
                if has_vacated_boost and espn_proj > season_avg:
                    true_base = (0.85 * espn_proj) + (0.15 * season_avg)
                elif season_avg > 0 and espn_proj > 0:
                    true_base = (espn_w * espn_proj) + (season_w * season_avg)
                else:
                    true_base = espn_proj

                espn_proj = round(espn_proj, 1)
                season_avg = round(season_avg, 1)
                true_base = round(true_base, 1)

                # Evaluate Vegas Implied Team Total, Spread Game Script & Stadium Weather
                vegas_adj, vegas_note = evaluate_vegas_and_weather_context(
                    player, pos, vegas_weather_map
                )

                # Evaluate Opposing Defensive Scheme, Coverage Shell & 1-on-1 Matchup
                scheme_adj, matchup_grade, matchup_report = analyze_micro_matchup(
                    player, pos, espn_proj, season_avg, is_desperate, live_def_matrix, scheme_weight=scheme_mult
                )
                matchup_report["vegas_weather_note"] = vegas_note
                matchup_report["usage_ol_note"] = usage_note

                # Evaluate Context-Window YouTube Film Sentiment
                channels, mentions, clips, yt_bonus, sent_label = find_player_clips(
                    player.name, yt_videos, is_desperate, yt_mult=yt_mult
                )

                # Combine adjustments with Empirical Bayes Shrinkage so positive stacks don't over-inflate
                total_positive_stack = sum(x for x in (scheme_adj, yt_bonus, vol_adj, vegas_adj) if x > 0)
                total_negative_stack = sum(x for x in (scheme_adj, yt_bonus, vol_adj, vegas_adj) if x < 0)
                if total_positive_stack > 1.8:
                    total_positive_stack = 1.8 + ((total_positive_stack - 1.8) * 0.55)

                net_addons = round(total_positive_stack + total_negative_stack, 1)
                blended_score = round(max(0.0, true_base + net_addons + bias_offset), 1)

                return {
                    "espn_proj": espn_proj,
                    "recent_avg": season_avg,
                    "true_base": true_base,
                    "vol_adj": vol_adj,
                    "vegas_adj": vegas_adj,
                    "scheme_adj": scheme_adj,
                    "matchup_grade": matchup_grade,
                    "matchup_report": matchup_report,
                    "yt_bonus": yt_bonus,
                    "bias_offset": bias_offset,
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
                    "vol_adj": sc["vol_adj"],
                    "vegas_adj": sc["vegas_adj"],
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
                        tag = "Calibrated Multi-Factor Upgrade"
                        if sc["vol_adj"] >= 0.8 and sc["scheme_adj"] >= 0.5:
                            tag = "⚡ Vacated Volume + Scheme Smash"
                        elif sc["scheme_adj"] >= 0.8 and sc["yt_bonus"] >= 0.5:
                            tag = "🎯 Elite Scheme + Bullish Film Smash"
                        elif sc["vegas_adj"] >= 0.6 and sc["scheme_adj"] >= 0.5:
                            tag = "🎰 Vegas Shootout + Scheme Edge"
                        elif sc["scheme_adj"] >= 0.8:
                            tag = "🛡️ Defensive Scheme Mismatch"
                        elif sc["yt_bonus"] >= 0.8:
                            tag = "🔥 Verified Bullish Analyst Target"

                        scored_fas.append({
                            "pos": pos,
                            "add": fa.name,
                            "tag": tag,
                            "espn_proj": sc["espn_proj"],
                            "recent_avg": sc["recent_avg"],
                            "true_base": sc["true_base"],
                            "vol_adj": sc["vol_adj"],
                            "vegas_adj": sc["vegas_adj"],
                            "scheme_adj": sc["scheme_adj"],
                            "matchup_grade": sc["matchup_grade"],
                            "matchup_report": sc["matchup_report"],
                            "yt_bonus": sc["yt_bonus"],
                            "bias_offset": sc["bias_offset"],
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
                "calibration": calibration,
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
