from http.server import BaseHTTPRequestHandler
import json
import os
from espn_api.football import League

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Pulls your secret ESPN keys safely from Vercel
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

            roster = []
            for p in my_team.roster:
                roster.append({
                    "name": p.name,
                    "pos": p.position,
                    "slot": p.lineupSlot,
                    "proj": get_proj(p),
                    "status": p.injuryStatus
                })

            free_agents = league.free_agents(week=week, size=60)
            recommendations = []

            for pos in ['QB', 'RB', 'WR', 'TE', 'D/ST', 'K']:
                my_pos = [p for p in roster if p["pos"] == pos]
                if not my_pos:
                    continue
                weakest = min(my_pos, key=lambda x: x["proj"])

                upgrades = [
                    fa for fa in free_agents
                    if fa.position == pos and get_proj(fa) > weakest["proj"]
                ]
                upgrades.sort(key=lambda x: get_proj(x), reverse=True)

                if upgrades:
                    best = upgrades[0]
                    best_proj = get_proj(best)
                    recommendations.append({
                        "pos": pos,
                        "add": best.name,
                        "add_proj": best_proj,
                        "drop": weakest["name"],
                        "drop_proj": weakest["proj"],
                        "diff": round(best_proj - weakest["proj"], 1)
                    })

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "team": my_team.team_name,
                "week": week,
                "recommendations": recommendations,
                "roster": roster
            }).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
