"""Generate SYNTHETIC YouTube-API-shaped sample data for offline demos/tests.

Nothing here is real: channel names, titles, numbers and comments are all
invented. Run:  python tests/fixtures/make_youtube_fixture.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).with_name("youtube_sample.json")
REF = datetime(2026, 10, 1, tzinfo=timezone.utc)

CHANNELS = [f"Demo Channel {n}" for n in
            ["Maple", "Birch", "Cedar", "Willow", "Aspen", "Juniper", "Hazel", "Rowan", "Alder", "Laurel"]]
TEMPLATES = [
    ("Counting {r} Song for Kids", 150, 240, 1.4, False),
    ("Learn to Count {r} | Numbers for Toddlers", 180, 300, 1.0, False),
    ("Numbers {r} Nursery Rhyme", 120, 210, 1.1, False),
    ("{r} Counting Song + More Kids Songs", 1500, 3600, 0.9, True),
    ("Count with Zibbo! Numbers {r}", 160, 260, 1.6, False),       # recurring 'character' in one channel
    ("A Counting Story Adventure {r}", 240, 420, 1.8, False),       # rare but strong pattern
    ("NUMBERS {r} for Babies 🍎", 90, 180, 0.8, False),
    ("Count {r} #shorts", 20, 58, 1.2, False),
    ("Learning Numbers {r} | 30 Minutes", 1800, 2400, 0.7, True),
]
COMMENT_POOL = [
    "My daughter loves this song, she counts along every morning",
    "Thank you! My 2 year old learned to count to ten",
    "The music is a bit too loud compared to the voice",
    "Too fast for my toddler, please slow down",
    "Best counting video, the animation colours are beautiful",
    "My son asks for this every day",
    "So many ads in the middle",
    "Cute characters and a nice voice",
]


def main(seed: int = 7) -> None:
    rng = random.Random(seed)
    channels = []
    for i, name in enumerate(CHANNELS):
        channels.append({"id": f"UCdemo{i:02d}", "snippet": {"title": name},
                         "statistics": {"subscriberCount": str(rng.randint(5_000, 3_000_000)),
                                        "hiddenSubscriberCount": False}})
    videos, comments = [], {}
    for n in range(140):
        tpl, dmin, dmax, strength, compilation = rng.choice(TEMPLATES)
        ch = 2 if "Zibbo" in tpl else rng.randrange(len(CHANNELS))
        dur = rng.randint(dmin, dmax)
        age = rng.randint(10, 2200)
        vpd = max(1.0, rng.lognormvariate(5.5, 1.1) * strength)
        views = int(vpd * age)
        mfk = rng.random() < 0.85
        vid = f"demo{n:04d}"
        stats = {"viewCount": str(views), "likeCount": str(int(views * rng.uniform(0.002, 0.012)))}
        if not mfk:
            stats["commentCount"] = str(rng.randint(5, 400))
            comments[vid] = rng.sample(COMMENT_POOL, k=5)
        title = tpl.format(r=rng.choice(["1-10", "1 to 10", "One to Ten"]))
        videos.append({
            "id": vid,
            "snippet": {
                "title": title,
                "channelId": f"UCdemo{ch:02d}",
                "channelTitle": CHANNELS[ch],
                "publishedAt": (REF - timedelta(days=age)).isoformat().replace("+00:00", "Z"),
                "liveBroadcastContent": "none",
                "defaultAudioLanguage": "en",
                "tags": ["kids"] * rng.randint(0, 12),
            },
            "statistics": stats,
            "contentDetails": {"duration": f"PT{dur // 60}M{dur % 60}S"},
            "status": {"madeForKids": mfk},
        })
    ids = [v["id"] for v in videos]
    data = {
        "_note": "SYNTHETIC demo data — not real YouTube videos.",
        "searches": {"_default": ids},
        # overlapping but different result sets per market, like real searches
        "searches_by_region": {"GLOBAL": ids, "US": ids[:90], "IN": ids[50:]},
        "videos": videos,
        "channels": channels,
        "comments": comments,
    }
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"Wrote {OUT} ({len(videos)} synthetic videos)")


if __name__ == "__main__":
    main()
