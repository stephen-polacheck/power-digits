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

OUTPUT_DIR = ROOT / "data" / "processed" / "best_3_wins"
OUTPUT_FILE = OUTPUT_DIR / f"best_3_wins_{SEASON}.parquet"


def main():
    team_games = pl.read_parquet(TEAM_GAMES_FILE)
    team_weighted_win_pct = pl.read_parquet(TEAM_WEIGHTED_WIN_PCT_FILE)

    # Current-season completed wins by FBS teams against FBS opponents.
    games = team_games.filter(
        (pl.col("season") == SEASON)
        & (pl.col("completed") == True)
        & (pl.col("team_classification") == "fbs")
        & (pl.col("opponent_classification") == "fbs")
        & (pl.col("result") == "W")
    )

    # Bring in the opponent's TWWP.
    opponent_twwp = team_weighted_win_pct.select([
        pl.col("team_id").alias("opponent_id"),
        pl.col("weighted_win_pct").alias("opponent_weighted_win_pct"),
    ])

    games = games.join(
        opponent_twwp,
        on="opponent_id",
        how="left",
    )

    # ------------------------------------------------------------------
    # Rank each team's wins.
    #
    # Primary:
    #   opponent TWWP descending
    #
    # Secondary:
    #   opponent team_id ascending
    #
    # Tertiary:
    #   week descending
    #
    # This gives us a deterministic ordering matching the intended
    # Best 3 Wins selection.
    # ------------------------------------------------------------------

    games = games.sort(
        [
            "team_id",
            "opponent_weighted_win_pct",
            "opponent_id",
            "week",
        ],
        descending=[
            False,
            True,
            False,
            True,
        ],
    )

    games = games.with_columns(
        pl.col("opponent_weighted_win_pct")
        .cum_count()
        .over("team_id")
        .alias("win_rank")
    )

    # Keep only the three best wins.
    best_three = games.filter(
        pl.col("win_rank") <= 3
    )

    # ------------------------------------------------------------------
    # Average the best three opponent TWWPs.
    #
    # IMPORTANT:
    # The denominator is always 3, even when a team has fewer than
    # three qualifying wins.
    # ------------------------------------------------------------------

    result = (
        best_three
        .group_by(["team_id", "team"])
        .agg([
            pl.col("opponent_weighted_win_pct")
            .sum()
            .alias("_best_three_sum"),

            pl.len().alias("_wins_used"),
        ])
        .with_columns(
            (
                pl.col("_best_three_sum") / 3.0
            ).alias("best_3_wins")
        )
        .select([
            "team_id",
            "team",
            "best_3_wins",
        ])
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.write_parquet(OUTPUT_FILE)

    print(f"Wrote {result.height} teams to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()