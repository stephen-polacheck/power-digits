from pathlib import Path

import polars as pl


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

input_path = (
    project_root
    / "data"
    / "processed"
    / "games"
    / "games.parquet"
)

output_path = (
    project_root
    / "data"
    / "processed"
    / "team_games"
    / "team_games.parquet"
)


# Load canonical game data
games = pl.read_parquet(input_path)


# Create home-team perspective
home_games = games.select(
    [
        pl.col("game_id"),
        pl.col("season"),
        pl.col("week"),
        pl.col("season_type"),
        pl.col("start_date"),
        pl.col("completed"),

        pl.col("home_team_id").alias("team_id"),
        pl.col("home_team").alias("team"),
        pl.col("away_team_id").alias("opponent_id"),
        pl.col("away_team").alias("opponent"),

        pl.col("home_points").alias("team_points"),
        pl.col("away_points").alias("opponent_points"),

        pl.col("home_conference_actual").alias("team_conference_actual"),
        pl.col("away_conference_actual").alias("opponent_conference_actual"),

        pl.col("home_classification").alias("team_classification"),
        pl.col("away_classification").alias("opponent_classification"),

        pl.when(pl.col("neutral_site"))
        .then(pl.lit("Neutral"))
        .otherwise(pl.lit("Home"))
        .alias("location"),

        pl.when(pl.col("home_points") > pl.col("away_points"))
        .then(pl.lit("W"))
        .when(pl.col("home_points") < pl.col("away_points"))
        .then(pl.lit("L"))
        .otherwise(pl.lit("T"))
        .alias("result"),
    ]
)


# Create away-team perspective
away_games = games.select(
    [
        pl.col("game_id"),
        pl.col("season"),
        pl.col("week"),
        pl.col("season_type"),
        pl.col("start_date"),
        pl.col("completed"),

        pl.col("away_team_id").alias("team_id"),
        pl.col("away_team").alias("team"),
        pl.col("home_team_id").alias("opponent_id"),
        pl.col("home_team").alias("opponent"),

        pl.col("away_points").alias("team_points"),
        pl.col("home_points").alias("opponent_points"),

        pl.col("away_conference_actual").alias("team_conference_actual"),
        pl.col("home_conference_actual").alias("opponent_conference_actual"),

        pl.col("away_classification").alias("team_classification"),
        pl.col("home_classification").alias("opponent_classification"),

        pl.when(pl.col("neutral_site"))
        .then(pl.lit("Neutral"))
        .otherwise(pl.lit("Road"))
        .alias("location"),

        pl.when(pl.col("away_points") > pl.col("home_points"))
        .then(pl.lit("W"))
        .when(pl.col("away_points") < pl.col("home_points"))
        .then(pl.lit("L"))
        .otherwise(pl.lit("T"))
        .alias("result"),
    ]
)


# Combine both perspectives
team_games = pl.concat(
    [
        home_games,
        away_games,
    ]
)


# Sort for easier inspection
team_games = team_games.sort(
    [
        "season",
        "week",
        "game_id",
        "team_id",
    ]
)


# Ensure output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)


# Save the team-game data
team_games.write_parquet(output_path)


print(f"Successfully created {len(team_games)} team-game records.")
print(f"Saved to: {output_path}")