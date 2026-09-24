from pathlib import Path
import sys
import polars as pl

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = Path(__file__).resolve().parents[2]

TEAM_GAMES_FILE = (
    ROOT / "data" / "processed" / "team_games" / "team_games.parquet"
)
TEAM_WEIGHTED_WIN_PCT_FILE = (
    ROOT
    / "data"
    / "processed"
    / "team_weighted_win_pct"
    / f"team_weighted_win_pct_{SEASON}.parquet"
)
CAUSED_WINS_LOSSES_FILE = (
    ROOT
    / "data"
    / "processed"
    / "weighted_caused_wins_losses"
    / f"weighted_caused_wins_losses_{SEASON}.parquet"
)

OUTPUT_DIR = ROOT / "data" / "processed" / "strength_of_schedule"
OUTPUT_FILE = OUTPUT_DIR / f"strength_of_schedule_{SEASON}.parquet"


def main():
    team_games = pl.read_parquet(TEAM_GAMES_FILE)
    team_weighted_win_pct = pl.read_parquet(TEAM_WEIGHTED_WIN_PCT_FILE)
    caused = pl.read_parquet(CAUSED_WINS_LOSSES_FILE)

    # Current-season completed games by FBS teams.
    games = team_games.filter(
        (pl.col("season") == SEASON)
        & (pl.col("completed") == True)
        & (pl.col("team_classification") == "fbs")
    )

    # ------------------------------------------------------------------
    # For each game:
    #
    # FBS opponent:
    #   use opponent's WeightedWins and WeightedLosses
    #
    # FCS opponent:
    #   use the worst-ranked FBS team's WeightedWins and WeightedLosses
    #   (WorstRank = 1)
    # ------------------------------------------------------------------

    fcs_fallback = (
        team_weighted_win_pct
        .filter(pl.col("worst_rank") == 1)
        .select([
            pl.col("weighted_wins").alias("fcs_weighted_wins"),
            pl.col("weighted_losses").alias("fcs_weighted_losses"),
        ])
    )

    fcs_fallback = fcs_fallback.to_dicts()[0]

    opponent_twwp = team_weighted_win_pct.select([
        pl.col("team_id").alias("opponent_id"),
        pl.col("weighted_wins").alias("opponent_weighted_wins"),
        pl.col("weighted_losses").alias("opponent_weighted_losses"),
    ])

    games = games.join(
        opponent_twwp,
        on="opponent_id",
        how="left",
    )

    # Replace FCS opponents with the worst FBS team's values.
    games = games.with_columns([
        pl.when(pl.col("opponent_classification") == "fcs")
        .then(pl.lit(fcs_fallback["fcs_weighted_wins"]))
        .otherwise(pl.col("opponent_weighted_wins"))
        .alias("opponent_weighted_wins"),

        pl.when(pl.col("opponent_classification") == "fcs")
        .then(pl.lit(fcs_fallback["fcs_weighted_losses"]))
        .otherwise(pl.col("opponent_weighted_losses"))
        .alias("opponent_weighted_losses"),
    ])

    # ------------------------------------------------------------------
    # Remove the results directly caused by the team being evaluated.
    #
    # caused_weighted_wins:
    #   wins that the evaluated team caused its opponents to receive
    #
    # caused_weighted_losses:
    #   losses that the evaluated team caused its opponents to receive
    # ------------------------------------------------------------------

    caused_adjustment = caused.select([
        pl.col("oppteam_id").alias("team_id"),
        pl.col("weighted_wins").alias("caused_weighted_wins"),
        pl.col("weighted_losses").alias("caused_weighted_losses"),
    ])

    games = games.join(
        caused_adjustment,
        on="team_id",
        how="left",
    )

    games = games.with_columns([
        pl.col("caused_weighted_wins")
        .fill_null(0.0)
        .alias("caused_weighted_wins"),

        pl.col("caused_weighted_losses")
        .fill_null(0.0)
        .alias("caused_weighted_losses"),
    ])

    # ------------------------------------------------------------------
    # Aggregate all opponent records.
    #
    # Then remove the total wins and losses caused by the evaluated team.
    # ------------------------------------------------------------------

    strength = (
        games.group_by(["team_id", "team"])
        .agg([
            (
                pl.col("opponent_weighted_wins").sum()
                - pl.col("caused_weighted_wins").first()
            ).alias("weighted_wins"),

            (
                pl.col("opponent_weighted_losses").sum()
                - pl.col("caused_weighted_losses").first()
            ).alias("weighted_losses"),
        ])
    )

    # ------------------------------------------------------------------
    # Calculate adjusted weighted win percentage.
    #
    # Denominator of zero => 0.5, matching the SQL behavior.
    # ------------------------------------------------------------------

    strength = strength.with_columns(
        pl.when(
            (pl.col("weighted_wins") + pl.col("weighted_losses")) == 0
        )
        .then(pl.lit(0.5))
        .when(
            pl.col("weighted_wins")
            / (pl.col("weighted_wins") + pl.col("weighted_losses"))
            >= 1
        )
        .then(pl.lit(1.0))
        .when(
            pl.col("weighted_wins")
            / (pl.col("weighted_wins") + pl.col("weighted_losses"))
            <= 0
        )
        .then(pl.lit(0.0))
        .otherwise(
            pl.col("weighted_wins")
            / (pl.col("weighted_wins") + pl.col("weighted_losses"))
        )
        .alias("weighted_win_pct")
    )

    # Outer SQL clamp.
    strength = strength.with_columns(
        pl.when(pl.col("weighted_win_pct") >= 0.999)
        .then(pl.lit(1.0))
        .when(pl.col("weighted_win_pct") <= 0.001)
        .then(pl.lit(0.0))
        .otherwise(pl.col("weighted_win_pct"))
        .alias("weighted_win_pct")
    )

    strength = strength.select([
        "team_id",
        "team",
        "weighted_wins",
        "weighted_losses",
        "weighted_win_pct",
    ])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    strength.write_parquet(OUTPUT_FILE)

    print(f"Wrote {strength.height} teams to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()