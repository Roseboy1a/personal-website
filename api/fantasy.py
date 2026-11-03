from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import xml.etree.ElementTree as ET

# Top Fantasy Football YouTube Channels
YT_CHANNELS = {
    "The Fantasy Footballers": "UC-No2ITxJsNt50oJQ3fLmUA",
    "FantasyPros": "UCZYaxEBdyKDsZfq_JGZwIeQ",
    "Flock Fantasy": "UC3jkBCIA687DNpQOZFSbtsg",
    "Fantasy Football Today": "UCviK78rIWXhZdFzJ1Woi7Fg"
}

TARGET_KEYWORDS = ["waiver", "pickup", "add", "must", "stash", "buy", "rank", "start", "week", "sleeper", "target"]

def fetch_recent_youtube_videos():
    """Fetches recent video titles & transcripts safely within Vercel's timeout limit."""
    video_data = []
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015', 'media': 'http://search.yahoo.com/mrss/'}

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        has_yt_lib = True
    except Exception:
        has_yt_lib = False

    for channel_name, channel_id in YT_CHANNELS.items():
        try:
            playlist_id = "UULF" + channel_id[2:]
            url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2.0) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            entries = root.findall('atom:entry', ns)[:2]  # Check 2 newest videos per channel for speed

            for entry in entries:
                title = entry.find('atom:title', ns).text or ""
                vid_id = entry.find('yt:videoId', ns).text or ""
                desc_elem = entry.find('media:group/media:description', ns)
                desc_text = (desc_elem.text if desc_elem is not None and desc_elem.text else "").lower()

                if any(k in title.lower() for k in TARGET_KEYWORDS):
                    combined_text = f"{title.lower()} {desc_text}"
                    if has_yt_lib:
                        try:
                            # Supports both old and new versions of youtube-transcript-api
                            if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                                t_list = YouTubeTranscriptApi.get_transcript(vid_id, languages=['en'])
                                combined_text += " " + " ".join([t['text'] for t in t_list]).lower()
                            else:
                                ytt = YouTubeTranscriptApi()
                                fetched = ytt.fetch(vid_id)
                                combined_text += " " + " ".join([snippet.text for snippet in fetched]).lower()
                        except Exception:
                            pass

                    video_data.append({
                        "channel": channel_name,
                        "title": title,
                        "text": combined_text
                    })
        except Exception:
            continue

    return video_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from espn_api.football import League

            league_id_raw = os.environ.get("LEAGUE_ID", "").strip()
            if not league_id_raw:
                raise ValueError("LEAGUE_ID is missing in Vercel Environment Variables.")

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

            roster = []
            for p in my_team.roster:
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": get_proj(p),
                    "status": p.injuryStatus
                })

            yt_videos = fetch_recent_youtube_videos()
            free_agents = league.free_agents(week=week, size=60)
            recommendations = []

            for pos in ['QB', 'RB', 'WR', 'TE']:
                my_pos = [p for p in roster if p["pos"] == pos]
                if not my_pos:
                    continue
                weakest = min(my_pos, key=lambda x: x["proj"])

                scored_fas = []
                for fa in free_agents:
                    if fa.position != pos:
                        continue

                    espn_proj = get_proj(fa)
                    name_lower = fa.name.lower()
                    last_name = name_lower.split()[-1] if " " in name_lower else name_lower

                    mentioned_channels = set()
                    total_mentions = 0
                    for v in yt_videos:
                        count = v["text"].count(name_lower)
                        if count == 0 and len(last_name) > 4:
                            count = v["text"].count(last_name)
                        if count > 0:
                            mentioned_channels.add(v["channel"])
                            total_mentions += count

                    yt_bonus = min(len(mentioned_channels) * 0.8 + (total_mentions * 0.15), 2.5)
                    blended_score = round(espn_proj + yt_bonus, 1)

                    if blended_score > weakest["proj"] or len(mentioned_channels) >= 1:
                        scored_fas.append({
                            "pos": pos,
                            "add": fa.name,
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
                    recommendations.extend(scored_fas[:2])

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "team": my_team.team_name,
                "week": week,
                "videos_scanned": [{"channel": v["channel"], "title": v["title"]} for v in yt_videos],
                "recommendations": recommendations
            }).encode('utf-8'))

        except Exception as e:
            # Always return 200 with JSON error so the frontend displays the exact reason
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
