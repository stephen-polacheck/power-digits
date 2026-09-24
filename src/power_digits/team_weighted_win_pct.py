from pathlib import Path
import sys
import polars as pl


SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

ROOT = Path(__file__).resolve().parents[2]

TEAM_GAMES_FILE = (
    ROOT / "data" / "processed" / "team_games" / "team_games.parquet"
)
TEAM_SEASONS_FILE = (
    ROOT / "data" / "processed" / "team_seasons" / f"team_seasons_{SEASON}.parquet"
)
CONFERENCE_STRENGTH_FILE = (
    ROOT
    / "data"
    / "processed"
    / "conference_strength"
    / f"conference_strength_{SEASON}.parquet"
)

OUTPUT_DIR = ROOT / "data" / "processed" / "team_weighted_win_pct"
OUTPUT_FILE = OUTPUT_DIR / f"team_weighted_win_pct_{SEASON}.parquet"


def main():
    # ------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------
    team_games = pl.read_parquet(TEAM_GAMES_FILE)
    team_seasons = pl.read_parquet(TEAM_SEASONS_FILE)
    conference_strength = pl.read_parquet(CONFERENCE_STRENGTH_FILE)

    # ------------------------------------------------------------
    # Current-season completed FBS games
    #
    # This mirrors:
    #   where vtg.team_division = 'fbs'
    #   and vtg.season = cs.Season
    #   and vtg.Completed = 1
    # ------------------------------------------------------------
    games = (
        team_games
        .filter(
            (pl.col("season") == SEASON)
            & (pl.col("completed") == True)
            & (pl.col("team_classification") == "fbs")
        )
    )

    # ------------------------------------------------------------
    # Add current-season conference for each opponent.
    #
    # Conference strength is based on the opponent's conference.
    # ------------------------------------------------------------
    opponent_conferences = (
        team_seasons
        .select(
            [
                pl.col("team_id").alias("opponent_id"),
                pl.col("conference").alias("opponent_conference"),
            ]
        )
        .unique(subset=["opponent_id"])
    )

    games = games.join(
        opponent_conferences,
        on="opponent_id",
        how="left",
    )

    # ------------------------------------------------------------
    # Add conference-strength values for the opponent's conference.
    # ------------------------------------------------------------
    conference_strength = conference_strength.select(
        [
            "conference",
            "win_home",
            "win_neutral",
            "win_road",
            "loss_home",
            "loss_neutral",
            "loss_road",
        ]
    )

    games = games.join(
        conference_strength,
        left_on="opponent_conference",
        right_on="conference",
        how="left",
    )

    # ------------------------------------------------------------
    # Calculate weighted wins and weighted losses.
    #
    # This mirrors the CASE statements in vwTeamWeightedWinPct.
    #
    # FCS:
    #   Win  = 0.5
    #   Loss = 1.5
    #
    # FBS:
    #   Use opponent conference strength + location.
    # ------------------------------------------------------------
    games = games.with_columns(
        [
            pl.when(
                (pl.col("result") == "W")
                & (pl.col("opponent_classification") == "fcs")
            )
            .then(pl.lit(0.5))
            .when(
                (pl.col("result") == "W")
                & (pl.col("location") == "Home")
            )
            .then(pl.col("win_home"))
            .when(
                (pl.col("result") == "W")
                & (pl.col("location") == "Neutral")
            )
            .then(pl.col("win_neutral"))
            .when(
                (pl.col("result") == "W")
                & (pl.col("location") == "Road")
            )
            .then(pl.col("win_road"))
            .otherwise(pl.lit(0.0))
            .alias("weighted_win"),

            pl.when(
                (pl.col("result") == "L")
                & (pl.col("opponent_classification") == "fcs")
            )
            .then(pl.lit(1.5))
            .when(
                (pl.col("result") == "L")
                & (pl.col("location") == "Home")
            )
            .then(pl.col("loss_home"))
            .when(
                (pl.col("result") == "L")
                & (pl.col("location") == "Neutral")
            )
            .then(pl.col("loss_neutral"))
            .when(
                (pl.col("result") == "L")
                & (pl.col("location") == "Road")
            )
            .then(pl.col("loss_road"))
            .otherwise(pl.lit(0.0))
            .alias("weighted_loss"),
        ]
    )

    # ------------------------------------------------------------
    # Aggregate by team.
    #
    # This mirrors:
    #   group by vtg.team_name, vtg.team_id
    # ------------------------------------------------------------
    teams = (
        games
        .group_by(["team_id", "team"])
        .agg(
            [
                pl.col("weighted_win").sum().alias("weighted_wins"),
                pl.col("weighted_loss").sum().alias("weighted_losses"),
            ]
        )
    )

    # ------------------------------------------------------------
    # Calculate WeightedWinPct.
    #
    # SQL:
    #
    #   WeightedWins /
    #   (WeightedWins + WeightedLosses)
    #
    #   NULL -> 0
    #
    # Then the outer query clamps:
    #   >= .999 -> 1
    #   <= .001 -> 0
    # ------------------------------------------------------------
    teams = teams.with_columns(
        pl.when(
            (pl.col("weighted_wins") + pl.col("weighted_losses")) == 0
        )
        .then(pl.lit(0.0))
        .otherwise(
            pl.col("weighted_wins")
            / (pl.col("weighted_wins") + pl.col("weighted_losses"))
        )
        .alias("weighted_win_pct")
    )

    teams = teams.with_columns(
        pl.when(pl.col("weighted_win_pct") >= 0.999)
        .then(pl.lit(1.0))
        .when(pl.col("weighted_win_pct") <= 0.001)
        .then(pl.lit(0.0))
        .otherwise(pl.col("weighted_win_pct"))
        .alias("weighted_win_pct")
    )

    # ------------------------------------------------------------
    # Reproduce SQL WorstRank.
    #
    # SQL orders by:
    #
    #   WeightedWinPct + 0.000000001 * team_id
    #
    # Because team_id is unique, this provides a deterministic
    # tiebreaker while preserving WeightedWinPct ordering.
    #
    # SQL RANK() is therefore effectively equivalent here to
    # assigning the sorted position.
    # ------------------------------------------------------------
    teams = (
        teams
        .with_columns(
            (
                pl.col("weighted_win_pct")
                + pl.col("team_id") * 0.000000001
            ).alias("_rank_value")
        )
        .sort("_rank_value", descending=False)
        .with_row_index("_rank_index")
        .with_columns(
            (pl.col("_rank_index") + 1).alias("worst_rank")
        )
        .drop(["_rank_value", "_rank_index"])
    )

    # ------------------------------------------------------------
    # Final column order
    # ------------------------------------------------------------
    teams = teams.select(
        [
            "team_id",
            "team",
            "weighted_wins",
            "weighted_losses",
            "weighted_win_pct",
            "worst_rank",
        ]
    )

    # ------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    teams.write_parquet(OUTPUT_FILE)

    print(f"Wrote {len(teams)} teams to:")
    print(OUTPUT_FILE)
    print()
    print(teams.head(20))


if __name__ == "__main__":
    main()