from pathlib import Path

import polars as pl


# Season to build
SEASON = 2026


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

input_path = (
    project_root
    / "data"
    / "processed"
    / "team_games"
    / "team_games.parquet"
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


# Build team-season records from actual game data
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
    .sort(
        [
            "classification",
            "conference",
            "team",
        ]
    )
)


# Ensure output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)


# Save team-season data
team_seasons.write_parquet(output_path)


print(f"Successfully created {len(team_seasons)} team-season records.")
print(f"Saved to: {output_path}")