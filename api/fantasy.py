from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from espn_api.football import League
from youtube_transcript_api import YouTubeTranscriptApi

# Top Fantasy Football YouTube Channels (Name: Channel ID)
YT_CHANNELS = {
    "The Fantasy Footballers": "UC-No2ITxJsNt50oJQ3fLmUA",
    "FantasyPros": "UCZYaxEBdyKDsZfq_JGZwIeQ",
    "Flock Fantasy": "UC3jkBCIA687DNpQOZFSbtsg"
    "Fantasy Football Today": "UCviK78rIWXhZdFzJ1Woi7Fg"
}

# Words in video titles that signal waiver/pickup/rankings advice
TARGET_KEYWORDS = ["waiver", "pickup", "add", "must", "stash", "buy", "rank", "start", "week", "sleeper", "target"]

def fetch_recent_youtube_transcripts():
    """Fetches recent video transcripts from top Fantasy Football YouTube channels."""
    video_data = []
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}

    for channel_name, channel_id in YT_CHANNELS.items():
        try:
            # Replace 'UC' with 'UULF' to pull only full-length videos (skips YouTube Shorts)
            playlist_id = "UULF" + channel_id[2:]
            url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            entries = root.findall('atom:entry', ns)[:4]  # Check the 4 newest full videos per channel

            for entry in entries:
                title = entry.find('atom:title', ns).text
                vid_id = entry.find('yt:videoId', ns).text

                if any(k in title.lower() for k in TARGET_KEYWORDS):
                    try:
                        # Pull English transcript of the video
                        transcript_list = YouTubeTranscriptApi.get_transcript(vid_id, languages=['en'])
                        full_text = " ".join([t['text'] for t in transcript_list]).lower()
                        video_data.append({
                            "channel": channel_name,
                            "title": title,
                            "video_id": vid_id,
                            "text": full_text
                        })
                    except Exception:
                        # Skip if captions aren't generated yet
                        continue
        except Exception:
            continue

    return video_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            league_id = int(os.environ.get("LEAGUE_ID", 0))
            year = int(os.environ.get("LEAGUE_YEAR", 2026))
            team_name = os.environ.get("TEAM_NAME", "")
            espn_s2 = os.environ.get("ESPN_S2", "")
            swid = os.environ.get("SWID", "")

            league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
            week = league.current_week

            my_team = next((t for t in league.teams if team_name.lower() in t.team_name.lower()), league.teams[0])

            def get_proj(player):
                stats = player.stats.get(week, {})
                return round(stats.get('projected_points', player.projected_total_points / 17), 1)

            # 1. Grab your current roster
            roster = []
            for p in my_team.roster:
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": get_proj(p),
                    "status": p.injuryStatus
                })

            # 2. Scan recent YouTube videos from fantasy channels
            yt_videos = fetch_recent_youtube_transcripts()

            # 3. Analyze top 75 free agents against YouTube transcripts + ESPN projections
            free_agents = league.free_agents(week=week, size=75)
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
                    
                    # Count how many videos & channels mention this player's full name
                    mentioned_channels = set()
                    total_mentions = 0
                    for v in yt_videos:
                        count = v["text"].count(name_lower)
                        if count > 0:
                            mentioned_channels.add(v["channel"])
                            total_mentions += count

                    # Calculate Blended Score: ESPN Projection + YouTube Hype Bonus (up to +2.5 pts)
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

                # Sort by highest Blended Score (ESPN Proj + YouTube Consensus)
                scored_fas.sort(key=lambda x: x["blended_score"], reverse=True)
                if scored_fas:
                    recommendations.extend(scored_fas[:2])  # Top 2 per position

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
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
