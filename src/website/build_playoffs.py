"""
Builds docs/data/playoffs.json: the field for every playoff format,
using the finished Power Digits rankings in docs/data/rankings.json.

Usage:
    python src/website/build_playoffs.py 2026
"""

import json
import sys
from pathlib import Path

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

project_root = Path(__file__).resolve().parents[2]
rankings_path = project_root / "docs" / "data" / "rankings.json"
config_path = project_root / "data" / "config" / "team_seasons.json"
cfbd_teams_path = project_root / "data" / "raw" / "schools" / "cfbd_teams.json"
output_path = project_root / "docs" / "data" / "playoffs.json"

POWER_CONFERENCES = ["Big Ten", "SEC", "ACC", "Big 12"]
NOTRE_DAME_ID = 87  # CFBD team id

# Team fields copied into playoffs.json so the bracket page needs no other file.
TEAM_FIELDS = [
    "rank",
    "team_id",
    "school_name",
    "school_short",
    "conference",
    "record",
    "power_digits",
    "primary_color",
    "secondary_color",
    "logo_url",
    "logo_dark_url",
]

# ---------------------------------------------------------------------
# Descriptions shown under each bracket
# ---------------------------------------------------------------------
P4_G5_TEXT = (
    "Automatic bids go to the top-ranked Big Ten, SEC, ACC and Big 12 teams "
    "and the top-ranked Group of 5 team; the rest are at-large. "
    "All teams are seeded by Power Digits rank"
)
ALL_CHAMPS_TEXT = (
    "All 10 conference champions (each conference's top-ranked team) get "
    "automatic bids; the rest are at-large. All teams are seeded by Power Digits rank"
)
REGIONS_TEXT = (
    "All 10 conference champions get in. The top {n} Big Ten and SEC teams play "
    "their own regions; the ACC and Big 12 regions add three Group of 5 champions "
    "in a play-in round. Region winners meet in the semifinals. "
    "Numbers shown are Power Digits ranks."
)

# ---------------------------------------------------------------------
# Formats
#   type "seeded":  pick a field, seed it by Power Digits rank
#     size              teams in the field
#     champions         conferences whose top-ranked team gets an automatic bid
#                       ("G5" = every Group of 5 conference gets its own bid)
#     group_of_5_bid    True = one extra bid for the best Group of 5 team
#   type "regions": conference regions (see regions() below)
# ---------------------------------------------------------------------


def regions(power_region_size):
    """Region definitions for the conference formats."""
    return [
        {"name": "Big Ten", "conference": "Big Ten", "conference_teams": power_region_size, "champions": []},
        {"name": "SEC", "conference": "SEC", "conference_teams": power_region_size, "champions": []},
        {
            "name": "ACC",
            "conference": "ACC",
            "conference_teams": 3,
            "champions": ["Sun Belt", "American Athletic", "Mid-American"],
            # Notre Dame plays in the ACC region but can never be its #1
            "extra_teams": [NOTRE_DAME_ID],
            "never_first": [NOTRE_DAME_ID],
        },
        {
            "name": "Big 12",
            "conference": "Big 12",
            "conference_teams": 3,
            "champions": ["Pac-12", "Mountain West", "Conference USA"],
        },
    ]


FORMATS = {
    "4": {
        "name": "4-Team Playoff", "tab": "4-Team", "type": "seeded",
        "size": 4, "champions": [], "group_of_5_bid": False,
        "description": "The top 4 teams in the Power Digits rankings, seeded 1-4. "
                       "No automatic bids.",
    },
    "8": {
        "name": "8-Team Playoff", "tab": "8-Team", "type": "seeded",
        "size": 8, "champions": POWER_CONFERENCES, "group_of_5_bid": True,
        "description": P4_G5_TEXT + ".",
    },
    "12": {
        "name": "12-Team Playoff", "tab": "12-Team", "type": "seeded",
        "size": 12, "champions": POWER_CONFERENCES, "group_of_5_bid": True,
        "description": P4_G5_TEXT + ", and seeds 1-4 get first-round byes.",
    },
    "24": {
        "name": "24-Team Playoff", "tab": "24-Team", "type": "seeded",
        "size": 24, "champions": POWER_CONFERENCES, "group_of_5_bid": True,
        "description": P4_G5_TEXT + ", and seeds 1-8 get first-round byes.",
    },
    "24c": {
        "name": "24-Team Champions Playoff", "tab": "24-Team Champs", "type": "seeded",
        "size": 24, "champions": POWER_CONFERENCES + ["G5"], "group_of_5_bid": False,
        "description": ALL_CHAMPS_TEXT + ", and seeds 1-8 get first-round byes.",
    },
    "32": {
        "name": "32-Team Playoff", "tab": "32-Team", "type": "seeded",
        "size": 32, "champions": POWER_CONFERENCES + ["G5"], "group_of_5_bid": False,
        "description": ALL_CHAMPS_TEXT + ", with no byes.",
    },
    "20conf": {
        "name": "20-Team Conference Playoff", "tab": "20-Conferences", "type": "regions",
        "regions": regions(4),
        "description": REGIONS_TEXT.format(n=4),
    },
    "24conf": {
        "name": "24-Team Conference Playoff", "tab": "24-Conferences", "type": "regions",
        "regions": regions(6),
        "description": REGIONS_TEXT.format(n=6),
    },
}


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def team_entry(team, seed, bid):
    entry = {"seed": seed, "bid": bid}
    entry.update({key: team.get(key) for key in TEAM_FIELDS})
    return entry


def in_conference(teams, conferences, actual_conference):
    """
    Teams (in rank order) that actually play in one of `conferences`.

    Uses the team's real CFBD conference, not its Power Digits conference,
    so independents with a conference override (e.g. Notre Dame) never
    count as conference members here.
    """
    return [t for t in teams if actual_conference.get(t["team_id"]) in conferences]


def champion(teams, conferences, actual_conference):
    """Top-ranked team in the given conference(s), or None."""
    members = in_conference(teams, conferences, actual_conference)
    return members[0] if members else None


def build_seeded(teams, rules, group_of_5, actual_conference):
    """Automatic bids first, then at-large by rank; seed everyone by rank."""
    selected = {}  # team_id -> bid label

    for conference in rules["champions"]:
        # "G5" expands to every Group of 5 conference
        names = group_of_5 if conference == "G5" else [conference]
        for name in names:
            team = champion(teams, [name], actual_conference)
            if team is not None:
                selected[team["team_id"]] = f"{name} champion"

    if rules["group_of_5_bid"]:
        team = champion(teams, group_of_5, actual_conference)
        if team is not None and team["team_id"] not in selected:
            selected[team["team_id"]] = "Group of 5"

    for team in teams:
        if len(selected) >= rules["size"]:
            break
        if team["team_id"] not in selected:
            selected[team["team_id"]] = "At-large"

    field = [team for team in teams if team["team_id"] in selected]
    return [team_entry(t, seed, selected[t["team_id"]]) for seed, t in enumerate(field, 1)]


def build_region(teams, region, actual_conference):
    """
    One conference region: the conference's top teams, then the listed
    Group of 5 champions (ordered by rank). Seeds are 1..N within the region.
    """
    by_id = {t["team_id"]: t for t in teams}

    pool = in_conference(teams, [region["conference"]], actual_conference)
    pool += [by_id[i] for i in region.get("extra_teams", []) if i in by_id]
    pool.sort(key=lambda t: t["rank"])
    members = pool[: region["conference_teams"]]

    # e.g. Notre Dame can be in the ACC region but never its #1 seed
    if len(members) > 1 and members[0]["team_id"] in region.get("never_first", []):
        members[0], members[1] = members[1], members[0]

    champs = [champion(teams, [c], actual_conference) for c in region["champions"]]
    champs = sorted((c for c in champs if c is not None), key=lambda t: t["rank"])

    entries = [team_entry(t, i, region["name"]) for i, t in enumerate(members, 1)]
    start = len(entries) + 1
    for i, team in enumerate(champs, start):
        conference = actual_conference.get(team["team_id"])
        entries.append(team_entry(team, i, f"{conference} champion"))
    return entries


def main():
    teams = load_json(rankings_path)
    config = load_json(config_path)
    cfbd_teams = load_json(cfbd_teams_path)

    group_of_5 = config["conference_groups"]["G5"]
    actual_conference = {team["id"]: team.get("conference") for team in cfbd_teams}
    teams.sort(key=lambda team: team["rank"])

    output = {"season": SEASON, "formats": {}}

    for key, rules in FORMATS.items():
        entry = {
            "name": rules["name"],
            "tab": rules["tab"],
            "description": rules["description"],
        }
        if rules["type"] == "seeded":
            entry["label"] = "seed"
            entry["seeds"] = build_seeded(teams, rules, group_of_5, actual_conference)
        else:
            entry["label"] = "rank"
            entry["regions"] = {
                region["name"]: build_region(teams, region, actual_conference)
                for region in rules["regions"]
            }
        output["formats"][key] = entry

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print(f"Saved to: {output_path}")
    for entry in output["formats"].values():
        print(f"  {entry['name']}:")
        groups = entry.get("regions") or {"": entry["seeds"]}
        for region_name, members in groups.items():
            if region_name:
                print(f"    {region_name} region:")
            for team in members:
                print(
                    f"    {team['seed']:>4}. {team['school_short']:<18}"
                    f" (rank {team['rank']}, {team['bid']})"
                )


if __name__ == "__main__":
    main()