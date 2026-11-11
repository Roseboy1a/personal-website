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


def fetch_sleeper_trending_adds():
    """Fetches the top 60 trending waiver wire adds in the last 24h from Sleeper's public API."""
    cache_path = "/tmp/sleeper_trending_cache_v1.json"
    now_ts = datetime.now(timezone.utc).timestamp()

    # Use cached Sleeper map if updated within the last 60 minutes
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            if now_ts - cached.get("timestamp", 0) < 3600:
                return cached.get("trending", {})
        except Exception:
            pass

    trending_by_name = {}
    try:
        # 1. Fetch trending add IDs and counts (very small payload)
        t_url = "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=60"
        req1 = urllib.request.Request(t_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req1, timeout=2.0) as res1:
            trending_list = json.loads(res1.read().decode('utf-8'))

        if not trending_list:
            return {}

        target_ids = {str(item["player_id"]): (idx + 1, item["count"]) for idx, item in enumerate(trending_list)}

        # 2. Check if we already cached Sleeper's player ID -> Name dictionary in /tmp
        id_map_path = "/tmp/sleeper_id_to_name.json"
        id_to_name = {}
        if os.path.exists(id_map_path):
            try:
                with open(id_map_path, "r") as f:
                    id_to_name = json.load(f)
            except Exception:
                id_to_name = {}

        if not id_to_name:
            p_url = "https://api.sleeper.app/v1/players/nfl"
            req2 = urllib.request.Request(p_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req2, timeout=3.5) as res2:
                players_data = json.loads(res2.read().decode('utf-8'))
            for pid, pinfo in players_data.items():
                full_n = pinfo.get("full_name") or f"{pinfo.get('first_name', '')} {pinfo.get('last_name', '')}".strip()
                if full_n:
                    clean_n, _ = clean_player_name(full_n)
                    id_to_name[str(pid)] = clean_n
            try:
                with open(id_map_path, "w") as f:
                    json.dump(id_to_name, f)
            except Exception:
                pass

        for pid, (rank, count) in target_ids.items():
            cname = id_to_name.get(pid)
            if cname:
                trending_by_name[cname] = {"rank": rank, "adds": count}

        try:
            with open(cache_path, "w") as f:
                json.dump({"timestamp": now_ts, "trending": trending_by_name}, f)
        except Exception:
            pass
    except Exception:
        pass

    return trending_by_name


def fetch_weekly_2026_videos(current_week, target_year=2026):
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v6.json"
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
    """Matches full player names and calculates quote sentiment (Positive vs Negative)."""
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
                # Score sentiment words in this segment
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

    # Calculate Sentiment Multiplier (Boosts bullish quotes, penalizes drop/injury warnings)
    if neg_hits > pos_hits + 1:
        sentiment_mult = 0.25
        sentiment_label = "⚠️ Caution/Negative"
    elif pos_hits >= neg_hits + 2:
        sentiment_mult = 1.25
        sentiment_label = " Bullish Buy"
    else:
        sentiment_mult = 1.0
        sentiment_label = "Neutral/Positive"

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

            def get_true_baseline(player):
                """Calculates True Usage Baseline: 70% ESPN Weekly Proj + 30% Recent 2-Week Scoring Form."""
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
                mode_desc = "Playoff odds are critical (<35%). Prioritizing high-ceiling YouTube breakout stashes, Sleeper market surges, and immediate lineup swings."
            elif playoff_pct < 60.0:
                mode = "AGGRESSIVE PUSH"
                mode_desc = "Playoff race is tight. Blending upside YouTube waiver targets and Sleeper trends with weekly matchup projections."
            else:
                mode = "CONTENDER MODE"
                mode_desc = "Strong playoff position. Prioritizing high-floor depth and blocking league rivals."

            is_desperate = playoff_pct < 45.0

            # Fetch YouTube videos & Sleeper live trending waiver adds in parallel
            yt_videos = fetch_weekly_2026_videos(current_week=week, target_year=year)
            sleeper_trending = fetch_sleeper_trending_adds()

            def score_player_full(player):
                espn_proj, recent_avg, true_base = get_true_baseline(player)
                channels, mentions, clips, sent_mult, sent_label = find_player_clips(player.name, yt_videos)

                # 1. Sentiment-Adjusted YouTube Bonus
                if is_desperate:
                    raw_yt = len(channels) * 1.6 + (mentions * 0.35)
                    yt_bonus = round(min(raw_yt * sent_mult, 6.0), 1)
                else:
                    raw_yt = len(channels) * 0.8 + (mentions * 0.15)
                    yt_bonus = round(min(raw_yt * sent_mult, 2.5), 1)

                # 2. Sleeper Live Market Surge Bonus
                clean_n, _ = clean_player_name(player.name)
                s_info = sleeper_trending.get(clean_n)
                sleeper_bonus = 0.0
                sleeper_rank = None
                sleeper_adds = 0
                if s_info:
                    sleeper_rank = s_info["rank"]
                    sleeper_adds = s_info["adds"]
                    # Top 10 trending gets biggest boost, scaling down through #60
                    base_surge = max(0.4, 2.5 - ((sleeper_rank - 1) * 0.035))
                    if is_desperate:
                        base_surge *= 1.35
                    sleeper_bonus = round(min(base_surge, 3.5), 1)

                blended_score = round(true_base + yt_bonus + sleeper_bonus, 1)
                return {
                    "espn_proj": espn_proj,
                    "recent_avg": recent_avg,
                    "true_base": true_base,
                    "yt_bonus": yt_bonus,
                    "sleeper_bonus": sleeper_bonus,
                    "sleeper_rank": sleeper_rank,
                    "sleeper_adds": sleeper_adds,
                    "blended_score": blended_score,
                    "yt_mentions": mentions,
                    "yt_channels": channels,
                    "sentiment": sent_label,
                    "clips": clips
                }

            # Score your own roster with the exact same 4-Factor model
            roster = []
            for p in my_team.roster:
                sc = score_player_full(p)
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": sc["espn_proj"],
                    "true_base": sc["true_base"],
                    "blended_score": sc["blended_score"],
                    "yt_mentions": sc["yt_mentions"],
                    "yt_channels": sc["yt_channels"],
                    "status": p.injuryStatus
                })

            free_agents = league.free_agents(week=week, size=85)
            recommendations = []

            for pos in ['QB', 'RB', 'WR', 'TE']:
                my_pos = [p for p in roster if p["pos"] == pos]
                if not my_pos:
                    continue

                starters = [p for p in my_pos if p["slot"] not in ['BE', 'IR']]
                weakest = min(starters if (is_desperate and starters) else my_pos, key=lambda x: x["blended_score"])

                scored_fas = []
                for fa in free_agents:
                    if fa.position != pos:
                        continue

                    sc = score_player_full(fa)

                    if sc["blended_score"] > weakest["blended_score"]:
                        tag = "Safe Floor Upgrade"
                        if is_desperate and (len(sc["yt_channels"]) >= 2 or (sc["sleeper_rank"] and sc["sleeper_rank"] <= 15)):
                            tag = "🚨 High-Ceiling Breakout Swing"
                        elif is_desperate and (len(sc["yt_channels"]) == 1 or sc["sleeper_rank"]):
                            tag = "⚡ Upside Lotto Ticket"
                        elif len(sc["yt_channels"]) >= 2:
                            tag = "🔥 Consensus Waiver Target"
                        elif sc["sleeper_rank"] and sc["sleeper_rank"] <= 20:
                            tag = "📈 Live Market Surge"

                        scored_fas.append({
                            "pos": pos,
                            "add": fa.name,
                            "tag": tag,
                            "espn_proj": sc["espn_proj"],
                            "recent_avg": sc["recent_avg"],
                            "true_base": sc["true_base"],
                            "yt_bonus": sc["yt_bonus"],
                            "sleeper_bonus": sc["sleeper_bonus"],
                            "sleeper_rank": sc["sleeper_rank"],
                            "sleeper_adds": sc["sleeper_adds"],
                            "blended_score": sc["blended_score"],
                            "yt_mentions": sc["yt_mentions"],
                            "yt_channels": sc["yt_channels"],
                            "sentiment": sc["sentiment"],
                            "clips": sc["clips"],
                            "drop": weakest["name"],
                            "drop_proj": weakest["proj"],
                            "drop_blended": weakest["blended_score"],
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
