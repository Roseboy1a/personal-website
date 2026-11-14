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
    "reynolds", "
