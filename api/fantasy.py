from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
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


def fetch_weekly_2026_videos(current_week, target_year=2026):
    cache_path = f"/tmp/yt_knowledge_{target_year}_wk{current_week}_v2.json"
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

                # Strictly 2026 videos only; reject 2025
                if not pub_str.startswith(str(target_year)) or "2025" in title_lower:
                    continue

                days_old = 99
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                    days_old = (now - pub_dt).days
                except Exception:
                    pass

                # Reject if title explicitly mentions a different NFL week
                mentions_other_week = any(
                    f"week {w}" in title_lower and f"week {w}" != week_tag
                    for w in range(1, 19)
                )
                if mentions_other_week:
                    continue

                # Accept if it mentions the current week OR was uploaded within the last 6 days
                is_current_week = (week_tag in title_lower) or (days_old <= 6)
                is_fantasy_topic = (days_old <= 5) or any(k in title_lower for k in TARGET_KEYWORDS)

                if is_current_week and is_fantasy_topic:
                    desc_elem = entry.find('media:group/media:description', ns)
                    desc_text = (desc_elem.text if desc_elem is not None and desc_elem.text else "").lower()
                    combined_text = f"{title_lower} {desc_text}"

                    found.append({
                        "video_id": vid_id,
                        "channel": channel_name,
                        "title": title,
                        "published": pub_str[:10],
                        "text": combined_text
                    })
        except Exception:
            pass
        return found

    # 1. Fetch all 10 channel feeds in parallel (takes ~1.5 seconds total)
    new_videos = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for ch_list in executor.map(fetch_single_channel, YT_CHANNELS.items()):
            new_videos.extend(ch_list)

    # 2. Fetch spoken transcripts in parallel for up to 12 new videos per load
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        has_yt_lib = True
    except Exception:
        has_yt_lib = False

    if has_yt_lib and new_videos:
        def add_transcript(v):
            try:
                vid_id = v["video_id"]
                if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                    t_list = YouTubeTranscriptApi.get_transcript(vid_id, languages=['en'])
                    v["text"] += " " + " ".join([t['text'] for t in t_list]).lower()
                else:
                    ytt = YouTubeTranscriptApi()
                    fetched = ytt.fetch(vid_id)
                    v["text"] += " " + " ".join([s.text for s in fetched]).lower()
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
                    name_lower = fa.name.lower()
                    clean_name = name_lower.replace(".", "").replace("'", "")
                    last_name = name_lower.split()[-1] if " " in name_lower else name_lower

                    mentioned_channels = set()
                    total_mentions = 0
                    for v in yt_videos:
                        txt = v["text"].replace(".", "").replace("'", "")
                        count = txt.count(clean_name)
                        if count == 0 and len(last_name) >= 5:
                            count = txt.count(last_name)
                        if count > 0:
                            mentioned_channels.add(v["channel"])
                            total_mentions += count

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
                            "yt_channels": list(mentioned_channels),
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
