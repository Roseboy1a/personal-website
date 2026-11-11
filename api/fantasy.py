from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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


def format_seconds(sec):
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_chapter_segments(desc_text):
    """Extracts MM:SS chapter lines from a YouTube video description."""
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


from datetime import datetime, timezone, timedelta

def get_current_fantasy_week_cutoff(now_utc):
    """
    Returns the exact timestamp of the most recent Tuesday at 04:00 UTC 
    (right after Monday Night Football ends). Anything older is from LAST week!
    """
    # Python weekday(): Monday=0, Tuesday=1, Wednesday=2 ... Sunday=6
    days_since_tuesday = (now_utc.weekday() - 1) % 7
    most_recent_tuesday = now_utc - timedelta(days=days_since_tuesday)
    cutoff = most_recent_tuesday.replace(hour=4, minute=0, second=0, microsecond=0)
    # If it's currently Tuesday before 4 AM UTC (Monday night in US), go back a week
    if cutoff > now_utc:
        cutoff -= timedelta(days=7)
    return cutoff


def fetch_weekly_2026_videos(current_week, target_year=2026):
    # Bumped to _v5 to wipe any pre-Sunday videos from the cloud cache
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v5.json"
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
    week_tag = f"week {current_week}"

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

                # 1. STRICT 2026 CHECK
                if not pub_str.startswith(str(target_year)) or "2025" in title_lower:
                    continue

                # Parse exact upload timestamp
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                except Exception:
                    continue

                # 2. REJECT ANY OTHER WEEK NUMBER IN TITLE (e.g., "Week 9")
                mentions_other_week = any(
                    re.search(rf'\bweek\s+{w}\b', title_lower)
                    for w in range(1, 19) if w != current_week
                )
                if mentions_other_week:
                    continue

                # 3. THE TUESDAY RESET RULE:
                # Must be uploaded AFTER this week's Tuesday morning reset (post-MNF),
                # OR explicitly state the current "Week X" in the title (for Monday waiver shows)
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


# Common NFL surnames & team city names that MUST NEVER match without the player's first name
AMBIGUOUS_SURNAMES = {
    # NFL Cities / Team Names
    "washington", "dallas", "houston", "jacksonville", "CAROLINA", "miami",
    "denver", "chicago", "detroit", "atlanta", "arizona", "seattle", "tampa",
    "buffalo", "cleveland", "cincinnati", "pittsburgh", "baltimore", "indianapolis",
    "tennessee", "minnesota", "philadelphia", "commanders", "steelers", "browns",
    # Shared NFL Surnames
    "wilson", "williams", "smith", "brown", "jones", "johnson", "taylor", "thomas",
    "moore", "robinson", "allen", "hill", "cook", "hall", "walker", "mitchell",
    "white", "green", "adams", "carter", "davis", "jackson", "miller", "young",
    "anderson", "scott", "wright", "king", "baker", "nelson", "harris", "clark",
    "lewis", "lee", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    "perez", "sanchez", "ramirez", "torres", "flores", "rivera", "gomez", "diaz",
    "turner", "parker", "collins", "edwards", "stewart", "morris", "murphy",
    "rogers", "reed", "bell", "cooper", "richardson", "cox", "howard", "ward",
    "watson", "brooks", "wood", "james", "bennett", "gray", "mendoza", "hughes",
    "price", "MYERS", "long", "foster", "sanders", "ross", "morales", "powell",
    "sullivan", "russell", "ortiz", "jenkins", "gutierrez", "perry", "butler",
    "barnes", "fisher", "henderson", "coleman", "simmons", "patterson", "jordan",
    "reynolds", "hamilton", "graham", "kim", "gonzales", "alexander", "ramos",
    "wallace", "griffin", "west", "cole", "hayes", "chavez", "gibson", "bryant",
    "ellis", "stevens", "murray", "ford", "marshall", "owens", "mcdonald", "harrison",
    "ruiz", "kennedy", "wells", "alvarez", "woods", "ireland", "hunt", "palmer",
    "robertson", "boyd", "rose", "stone", "mason", "warren", "dixon", "burns",
    "gordon", "shaw", "holmes", "rice", "schmidt", "hunt", "black", "daniels",
    "palmer", "mills", "nichols", "grant", "knight", "ferguson", "rose", "hopkins",
    "jacobs", "pittman", "higbee", "stafford", "murray", "henry", "barkley",
    "elliott", "conner", "chubb", "mixon", "kamara", "montgomery", "gibbs",
    "stroud", "love", "purdy", "GOFF", "mayfield", "lawrence", "herbert", "burrow",
    "mahomes", "hurts", "prescott", "cousins", "rodgers", "carr", "geno", "ridley",
    "sutton", "pickens", "higgins", "waddle", "olave", "london", "metcalf", "lockett",
    "evans", "godwin", "diggs", "dell", "collins", "cooper", "jeudy", "hopkins",
    "kelce", "andrews", "kittle", "laporta", "mcbride", "kincaid", "engram", "ferguson",
    "njoku", "goedert", "pitts", "hockenson", "freiermuth", "kraft", "musgrave",
    "brooks", "benson", "corum", "wright", "lloyd", "davis", "vidal", "ali", "estime",
    "allen", "tracy", "irving", "guerendo", "steele", "vaki", "shipley", "laube",
    "worthy", "pearsall", "legette", "coleman", "mcconkey", "polk", "burton", "wilson",
    "mcmillan", "rice", "baker", "franklin", "corley", "washington", "thrash", "means"
}


def clean_player_name(name):
    """Normalizes a player's name and strips Jr./Sr./II/III suffixes."""
    cleaned = name.lower().replace(".", "").replace("'", "").replace("-", " ").strip()
    parts = [p for p in cleaned.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(parts), parts


def find_player_clips(player_name, yt_videos):
    """Strictly matches full player names (First + Last) to eliminate surname/city collisions."""
    clean_full, parts = clean_player_name(player_name)
    if len(parts) < 2:
        return [], 0, []

    first_name = parts[0]
    last_name = parts[-1]

    # Regex requiring exact whole-word match for "First Last" (allows 1-2 spaces between)
    full_name_pattern = re.compile(r'\b' + re.escape(first_name) + r'\s+' + re.escape(last_name) + r'\b')

    # Only allow standalone last-name matching if the surname is rare (8+ letters and not in AMBIGUOUS_SURNAMES)
    # AND the full name was already explicitly confirmed in that exact same video
    is_unique_surname = (len(last_name) >= 8) and (last_name.lower() not in {s.lower() for s in AMBIGUOUS_SURNAMES})
    surname_pattern = re.compile(r'\b' + re.escape(last_name) + r'\b')
    # Rejects if preceded by a different capitalized/spoken first name
    other_first_Plus_surname = re.compile(r'\b([a-z]{3,})\s+' + re.escape(last_name) + r'\b')

    mentioned_channels = set()
    total_mentions = 0
    clips = []

    for v in yt_videos:
        txt = v["text"].lower().replace(".", "").replace("'", "").replace("-", " ")

        # STEP 1: The video MUST contain the player's exact FULL NAME ("malik washington") at least once
        full_matches = full_name_pattern.findall(txt)
        if not full_matches:
            continue

        count = len(full_matches)
        mentioned_channels.add(v["channel"])
        total_mentions += count

        matched_in_segments = False
        for seg in v.get("segments", []):
            seg_clean = seg["text"].lower().replace(".", "").replace("'", "").replace("-", " ")

            # Check for exact "First Last" in this 20-second segment
            has_full = bool(full_name_pattern.search(seg_clean))

            # Optional secondary check: if rare surname AND full name was already confirmed in this video,
            # ensure nobody else's first name is attached to that surname in this segment
            has_safe_surname = False
            if not has_full and is_unique_surname and surname_pattern.search(seg_clean):
                preceding_matches = other_first_Plus_surname.findall(seg_clean)
                # Only valid if no other first name precedes the surname
                if all(w == first_name or w in ("the", "and", "for", "with", "from", "like", "over", "start", "add", "drop") for w in preceding_matches):
                    has_safe_surname = True

            if has_full or has_safe_surname:
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

    return list(mentioned_channels), total_mentions, clips[:6]


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

            def get_proj(player):
                stats = player.stats.get(week, {})
                return round(stats.get('projected_points', player.projected_total_points / 17), 1)

            playoff_data = calculate_playoff_odds(league, my_team, week)
            playoff_pct = playoff_data["playoff_pct"]

            if playoff_pct < 35.0:
                mode = "DESPERATION MODE"
                mode_desc = "Playoff odds are critical (<35%). Prioritizing high-ceiling YouTube breakout stashes and immediate starting lineup swings."
            elif playoff_pct < 60.0:
                mode = "AGGRESSIVE PUSH"
                mode_desc = "Playoff race is tight. Blending upside YouTube waiver targets with weekly matchup projections."
            else:
                mode = "CONTENDER MODE"
                mode_desc = "Strong playoff position. Prioritizing high-floor depth and blocking league rivals."

            is_desperate = playoff_pct < 45.0

            roster = []
            for p in my_team.roster:
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": get_proj(p),
                    "status": p.injuryStatus
                })

            yt_videos = fetch_weekly_2026_videos(current_week=week, target_year=year)
            free_agents = league.free_agents(week=week, size=85)
            recommendations = []

            for pos in ['QB', 'RB', 'WR', 'TE']:
                my_pos = [p for p in roster if p["pos"] == pos]
                if not my_pos:
                    continue

                starters = [p for p in my_pos if p["slot"] not in ['BE', 'IR']]
                weakest = min(starters if (is_desperate and starters) else my_pos, key=lambda x: x["proj"])

                scored_fas = []
                for fa in free_agents:
                    if fa.position != pos:
                        continue

                    espn_proj = get_proj(fa)
                    mentioned_channels, total_mentions, clips = find_player_clips(fa.name, yt_videos)

                    if is_desperate:
                        yt_bonus = min(len(mentioned_channels) * 1.6 + (total_mentions * 0.35), 6.0)
                    else:
                        yt_bonus = min(len(mentioned_channels) * 0.8 + (total_mentions * 0.15), 2.5)

                    blended_score = round(espn_proj + yt_bonus, 1)

                    qualifies = (blended_score > weakest["proj"]) or (is_desperate and len(mentioned_channels) >= 1)
                    if qualifies:
                        tag = "Safe Floor Upgrade"
                        if is_desperate and len(mentioned_channels) >= 2:
                            tag = "🚨 High-Ceiling Breakout Swing"
                        elif is_desperate and len(mentioned_channels) == 1:
                            tag = "⚡ Upside Lotto Ticket"
                        elif len(mentioned_channels) >= 2:
                            tag = "🔥 Consensus Waiver Target"

                        scored_fas.append({
                            "pos": pos,
                            "add": fa.name,
                            "tag": tag,
                            "espn_proj": espn_proj,
                            "blended_score": blended_score,
                            "yt_mentions": total_mentions,
                            "yt_channels": mentioned_channels,
                            "clips": clips,
                            "drop": weakest["name"],
                            "drop_proj": weakest["proj"],
                            "diff": round(blended_score - weakest["proj"], 1)
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
                "recommendations": recommendations
            }).encode('utf-8'))

        except Exception as e:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
