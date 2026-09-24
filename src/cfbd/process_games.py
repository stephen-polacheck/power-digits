import json
import sys
from pathlib import Path

import polars as pl


SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


project_root = get_project_root()

input_path = (
    project_root
    / "data"
    / "raw"
    / "games"
    / f"cfbd_games_{SEASON}.json"
)

output_path = (
    project_root
    / "data"
    / "processed"
    / "games"
    / f"games_{SEASON}.parquet"
)


with input_path.open("r", encoding="utf-8") as file:
    games = json.load(file)


rows = []

for game in games:
    playoff = game.get("playoff")

    rows.append(
        {
            "game_id": game.get("id"),
            "season": game.get("season"),
            "week": game.get("week"),
            "season_type": game.get("seasonType"),
            "start_date": game.get("startDate"),
            "completed": game.get("completed"),
            "neutral_site": game.get("neutralSite"),
            "conference_game": game.get("conferenceGame"),
            "venue_id": game.get("venueId"),
            "venue": game.get("venue"),

            "home_team_id": game.get("homeId"),
            "home_team": game.get("homeTeam"),
            "home_conference_actual": game.get("homeConference"),
            "home_classification": game.get("homeClassification"),
            "home_points": game.get("homePoints"),

            "away_team_id": game.get("awayId"),
            "away_team": game.get("awayTeam"),
            "away_conference_actual": game.get("awayConference"),
            "away_classification": game.get("awayClassification"),
            "away_points": game.get("awayPoints"),

            "playoff_game": playoff is not None,
            "playoff_competition": (
                playoff.get("competition")
                if playoff is not None
                else None
            ),
            "playoff_format": (
                playoff.get("format")
                if playoff is not None
                else None
            ),
            "playoff_round": (
                playoff.get("round")
                if playoff is not None
                else None
            ),
            "playoff_round_name": (
                playoff.get("roundName")
                if playoff is not None
                else None
            ),
            "playoff_bowl_name": (
                playoff.get("bowlName")
                if playoff is not None
                else None
            ),
        }
    )


df = pl.DataFrame(
    rows,
    schema={
        "game_id": pl.Int64,
        "season": pl.Int64,
        "week": pl.Int64,
        "season_type": pl.String,
        "start_date": pl.String,
        "completed": pl.Boolean,
        "neutral_site": pl.Boolean,
        "conference_game": pl.Boolean,
        "venue_id": pl.Int64,
        "venue": pl.String,

        "home_team_id": pl.Int64,
        "home_team": pl.String,
        "home_conference_actual": pl.String,
        "home_classification": pl.String,
        "home_points": pl.Int64,

        "away_team_id": pl.Int64,
        "away_team": pl.String,
        "away_conference_actual": pl.String,
        "away_classification": pl.String,
        "away_points": pl.Int64,

        "playoff_game": pl.Boolean,
        "playoff_competition": pl.String,
        "playoff_format": pl.String,
        "playoff_round": pl.String,
        "playoff_round_name": pl.String,
        "playoff_bowl_name": pl.String,
    },
)


output_path.parent.mkdir(parents=True, exist_ok=True)

df.write_parquet(output_path)


print(f"Successfully processed {len(df)} games for {SEASON}.")
print(f"Saved to: {output_path}")

print("\nPlayoff games:")
print(
    df
    .filter(pl.col("playoff_game"))
    .select(
        [
            "game_id",
            "week",
            "home_team",
            "away_team",
            "playoff_competition",
            "playoff_format",
            "playoff_round",
            "playoff_round_name",
            "playoff_bowl_name",
        ]
    )
)