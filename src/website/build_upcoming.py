"""
Builds docs/data/upcoming.json: the 8 highest-leverage games of the
upcoming week, for the "High Leverage" graphic (4 games per side).

  Upcoming week:  the week of the earliest regular-season game that hasn't
                  been played yet. Only games that haven't been played are listed.
  Leverage:       the Power Digits rating of the LOWER-rated team in the game,
                  so a game is only as big as its weaker team.
  Group of 5:     at least 2 of the 8 games must be Group of 5 vs Group of 5
                  (at least 1 before week 4).

Usage:
    python src/website/build_upcoming.py 2026
    python src/website/build_upcoming.py 2026 2026-11-05   (pretend today is this date)
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

# "Now", for deciding which games are still upcoming (optional override for testing)
AS_OF = (
    datetime.fromisoformat(sys.argv[2]).replace(tzinfo=timezone.utc)
    if len(sys.argv) > 2
    else datetime.now(timezone.utc)
)

project_root = Path(__file__).resolve().parents[2]
games_path = project_root / "data" / "raw" / "games" / f"cfbd_games_{SEASON}.json"
rankings_path = project_root / "docs" / "data" / "rankings.json"
config_path = project_root / "data" / "config" / "team_seasons.json"
cfbd_teams_path = project_root / "data" / "raw" / "schools" / "cfbd_teams.json"
output_path = project_root / "docs" / "data" / "upcoming.json"

GAME_COUNT = 8
G5_MINIMUM = 2          # Group of 5 vs Group of 5 games required...
G5_MINIMUM_EARLY = 1    # ...or this many before week G5_FULL_FROM_WEEK
G5_FULL_FROM_WEEK = 4

# Team fields copied into upcoming.json for the graphic
TEAM_FIELDS = [
    "rank", "team_id", "school_name", "school_short", "record", "power_digits",
    "primary_color", "secondary_color", "logo_url", "logo_dark_url", "helmet_url",
]


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def kickoff(game):
    return datetime.fromisoformat(game["startDate"].replace("Z", "+00:00"))


def is_upcoming(game):
    """An FBS regular-season game that hasn't been played and hasn't kicked off yet."""
    return (
        game.get("seasonType") == "regular"
        and not game.get("completed")
        and "fbs" in (game.get("homeClassification"), game.get("awayClassification"))
        and kickoff(game) > AS_OF - timedelta(hours=1)
    )


def upcoming_week(games):
    """Week of the earliest upcoming FBS game (None if the regular season is over)."""
    upcoming = [g for g in games if is_upcoming(g)]
    if not upcoming:
        return None
    return min(upcoming, key=kickoff)["week"]


def main():
    games = load_json(games_path)
    teams = {t["team_id"]: t for t in load_json(rankings_path)}
    group_of_5 = set(load_json(config_path)["conference_groups"]["G5"])
    actual_conference = {t["id"]: t.get("conference") for t in load_json(cfbd_teams_path)}

    week = upcoming_week(games)
    if week is None:
        print("No upcoming regular-season games - nothing to build.")
        return

    # Unplayed games this week between two ranked (FBS) teams
    candidates = []
    for g in games:
        if g["week"] != week or not is_upcoming(g):
            continue
        away, home = teams.get(g["awayId"]), teams.get(g["homeId"])
        if away is None or home is None:
            continue

        g5_game = (
            actual_conference.get(g["awayId"]) in group_of_5
            and actual_conference.get(g["homeId"]) in group_of_5
        )
        candidates.append({
            "game_id": g["id"],
            "start_date": g["startDate"],
            "start_time_tbd": bool(g.get("startTimeTBD")),
            "neutral_site": bool(g.get("neutralSite")),
            "g5_game": g5_game,
            # leverage = rating of the weaker team
            "leverage": round(min(away["power_digits"], home["power_digits"]), 1),
            "away": {key: away.get(key) for key in TEAM_FIELDS},
            "home": {key: home.get(key) for key in TEAM_FIELDS},
        })

    candidates.sort(key=lambda c: c["leverage"], reverse=True)
    chosen = candidates[:GAME_COUNT]

    # Make sure enough Group of 5 vs Group of 5 games are included
    required = G5_MINIMUM if week >= G5_FULL_FROM_WEEK else G5_MINIMUM_EARLY
    extra_g5 = [c for c in candidates[GAME_COUNT:] if c["g5_game"]]
    while sum(c["g5_game"] for c in chosen) < required and extra_g5:
        # replace the lowest-leverage game that isn't a G5 game
        for i in range(len(chosen) - 1, -1, -1):
            if not chosen[i]["g5_game"]:
                chosen[i] = extra_g5.pop(0)
                break
        else:
            break

    chosen.sort(key=lambda c: c["leverage"], reverse=True)

    output = {"season": SEASON, "week": week, "games": chosen}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print(f"Week {week}: {len(candidates)} upcoming games, kept {len(chosen)} "
          f"({sum(c['g5_game'] for c in chosen)} Group of 5 vs Group of 5)")
    for c in chosen:
        mark = "  [G5]" if c["g5_game"] else ""
        print(f"  {c['leverage']:5.1f}  #{c['away']['rank']} {c['away']['school_short']} "
              f"{'vs' if c['neutral_site'] else '@'} #{c['home']['rank']} "
              f"{c['home']['school_short']}{mark}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
