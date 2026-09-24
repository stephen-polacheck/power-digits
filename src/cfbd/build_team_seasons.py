import json
import sys
from pathlib import Path

import polars as pl


# Season to build
SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

input_path = (
    project_root
    / "data"
    / "processed"
    / "team_games"
    / "team_games.parquet"
)

config_path = (
    project_root
    / "data"
    / "config"
    / "team_seasons.json"
)

output_path = (
    project_root
    / "data"
    / "processed"
    / "team_seasons"
    / f"team_seasons_{SEASON}.parquet"
)


# Load team-game data
team_games = pl.read_parquet(input_path)


# Build base team-season records from CFBD game data
team_seasons = (
    team_games
    .filter(pl.col("season") == SEASON)
    .select(
        [
            pl.col("season"),
            pl.col("team_id"),
            pl.col("team"),
            pl.col("team_conference_actual").alias("conference"),
            pl.col("team_classification").alias("classification"),
        ]
    )
    .unique()
)


# Load Power Digits configuration
with config_path.open("r", encoding="utf-8") as file:
    config = json.load(file)


# Apply Power Digits conference overrides
for override in config.get("conference_overrides", []):
    if override["season"] != SEASON:
        continue

    team_id = override["team_id"]
    conference = override["conference"]

    team_seasons = team_seasons.with_columns(
        pl.when(pl.col("team_id") == team_id)
        .then(pl.lit(conference))
        .otherwise(pl.col("conference"))
        .alias("conference")
    )


# Sort for easier inspection
team_seasons = team_seasons.sort(
    [
        "classification",
        "conference",
        "team",
    ]
)


# Ensure output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)


# Save final team-season data
team_seasons.write_parquet(output_path)


print(f"Successfully created {len(team_seasons)} team-season records.")
print(f"Saved to: {output_path}")