import json
from pathlib import Path

import polars as pl


# Season to process
SEASON = 2026


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

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
    / "games.parquet"
)


# Load raw CFBD game data
with input_path.open("r", encoding="utf-8") as file:
    games = json.load(file)


# Convert to a Polars DataFrame
df = pl.DataFrame(games)


# Select and rename the fields needed by Power Digits
games_processed = df.select(
    [
        pl.col("id").alias("game_id"),
        pl.col("season"),
        pl.col("week"),
        pl.col("seasonType").alias("season_type"),
        pl.col("startDate").alias("start_date"),
        pl.col("completed"),
        pl.col("neutralSite").alias("neutral_site"),
        pl.col("conferenceGame").alias("conference_game"),
        pl.col("venueId").alias("venue_id"),
        pl.col("venue"),

        pl.col("homeId").alias("home_team_id"),
        pl.col("homeTeam").alias("home_team"),
        pl.col("homeConference").alias("home_conference_actual"),
        pl.col("homeClassification").alias("home_classification"),
        pl.col("homePoints").alias("home_points"),

        pl.col("awayId").alias("away_team_id"),
        pl.col("awayTeam").alias("away_team"),
        pl.col("awayConference").alias("away_conference_actual"),
        pl.col("awayClassification").alias("away_classification"),
        pl.col("awayPoints").alias("away_points"),
    ]
)


# Ensure the output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)


# Save the processed game data
games_processed.write_parquet(output_path)


print(f"Successfully processed {len(games_processed)} games.")
print(f"Saved to: {output_path}")