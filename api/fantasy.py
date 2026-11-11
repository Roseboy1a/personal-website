from http.server import BaseHTTPRequestHandler
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
    "Fantasy Football Today": "UCviK78rIWXhZdFzJ1Woi7Fg"
}

TARGET_KEYWORDS = [
    "waiver", "pickup", "add", "must", "stash", "buy", "rank",
    "start", "sit", "sleeper", "target", "drop", "breakout", "wire"
]


def fetch_weekly_2026_videos(current_week, target_year=2026):
    cache_path = f"/tmp/yt_knowledge_{target_year}_week_{current_week}.json"
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

    for channel_name, channel_id in YT_CHANNELS.items():
        try:
            playlist_id = "UULF" + channel_id[2:]
            url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2.0) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            entries = root.findall('atom:entry', ns)[:10]

            for entry in entries:
                vid_id = entry.find('yt:videoId', ns).text or ""
                if not vid_id or vid_id in saved_videos:
                    continue

                title = entry.find('atom:title', ns).text or ""
                title_lower = title.lower()
                pub_str = entry.find('atom:published', ns).text or ""

                if not pub_str.startswith(str(target_year)) or "2025" in title_lower:
                    continue

                days_old = 99
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                    days_old = (now - pub_dt).days
                except Exception:
                    pass

                mentions_other_week = any(
                    f"week {w}" in title_lower for w in range(1, 19) if w != current_week
                )
                if mentions_other_week:
                    continue

                is_current_week = (week_tag in title_lower) or (days_old <= 6)
                is_fantasy_topic = any(k in title_lower for k in TARGET_KEYWORDS)

                if is_current_week and is_fantasy_topic:
                    desc_elem = entry.find('media:group/media:description', ns)
                    desc_text = (desc_elem.text if desc_elem is not None and desc_elem.text else "").lower()
                    combined_text = f"{title_lower} {desc_text}"

                    saved_videos[vid_id] = {
                        "video_id": vid_id,
                        "channel": channel_name,
                        "title": title,
                        "published": pub_str[:10],
                        "text": combined_text
                    }
        except Exception:
            continue

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
        if opp and opp.team_id != my_team.team_id
