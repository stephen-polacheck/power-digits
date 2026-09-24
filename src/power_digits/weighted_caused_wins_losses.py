from pathlib import Path
import sys
import polars as pl


SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

ROOT = Path(__file__).resolve().parents[2]

TEAM_GAMES_FILE = (
    ROOT / "data" / "processed" / "team_games" / "team_games.parquet"
)

TEAM_SEASONS_FILE = (
    ROOT
    / "data"
    / "processed"
    / "team_seasons"
    / f"team_seasons_{SEASON}.parquet"
)

CONFERENCE_STRENGTH_FILE = (
    ROOT
    / "data"
    / "processed"
    / "conference_strength"
    / f"conference_strength_{SEASON}.parquet"
)

OUTPUT_DIR = ROOT / "data" / "processed" / "weighted_caused_wins_losses"
OUTPUT_FILE = (
    OUTPUT_DIR / f"weighted_caused_wins_losses_{SEASON}.parquet"
)


def main():
    # ------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------
    team_games = pl.read_parquet(TEAM_GAMES_FILE)
    team_seasons = pl.read_parquet(TEAM_SEASONS_FILE)
    conference_strength = pl.read_parquet(CONFERENCE_STRENGTH_FILE)

    # ------------------------------------------------------------
    # Current-season completed FBS vs FBS games
    #
    # SQL:
    #   where vtg.oppteam_division = 'fbs'
    #   and vtg.team_division = 'fbs'
    #   and vtg.Completed = 1
    #   and vtg.season = cs.Season
    # ------------------------------------------------------------
    games = (
        team_games
        .filter(
            (pl.col("season") == SEASON)
            & (pl.col("completed") == True)
            & (pl.col("team_classification") == "fbs")
            & (pl.col("opponent_classification") == "fbs")
        )
    )

    # ------------------------------------------------------------
    # Get the current-season conference of the opponent.
    #
    # This mirrors:
    #
    #   left join vwSchool vsopp
    #   on vsopp.schoolid = oppteam_id
    #
    # The conference used for the weight is therefore the
    # conference of the OPPONENT in the team_games row.
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
    # Add conference-strength values.
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
    # Calculate the values that the current team caused its
    # opponent to receive.
    #
    # This is a direct translation of the SQL:
    #
    # WeightedWins:
    #   when vtg.Win = 1
    #       Home    -> WinHome
    #       Neutral -> WinNeutral
    #       Road    -> WinRoad
    #
    # WeightedLosses:
    #   when vtg.Loss = 1
    #       Home    -> LossHome
    #       Neutral -> LossNeutral
    #       Road    -> LossRoad
    #
    # IMPORTANT:
    #
    # These are NOT the same value.
    #
    # Florida @ Auburn:
    #
    #   Florida perspective:
    #       Win + Road
    #       -> SEC WinRoad = 0.777144
    #
    #   Auburn perspective:
    #       Loss + Home
    #       -> SEC LossHome = 0.837144
    #
    # Since the SQL groups by oppteam_id:
    #
    #   Auburn receives WeightedWins = 0.777144
    #   Florida receives WeightedLosses = 0.837144
    #
    # We therefore calculate each from the original game row rather
    # than flipping or relabeling one value.
    # ------------------------------------------------------------
    games = games.with_columns(
        [
            pl.when(
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
            .alias("weighted_wins"),

            pl.when(
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
            .alias("weighted_losses"),
        ]
    )

    # ------------------------------------------------------------
    # Group by opponent.
    #
    # This is the critical part of vwWeightedCausedWinsLosses:
    #
    #   group by vtg.oppteam_id, vtg.oppteam_name
    #
    # So the row represents the weighted results caused BY the
    # team named in oppteam_name.
    # ------------------------------------------------------------
    caused = (
        games
        .group_by(["opponent_id", "opponent"])
        .agg(
            [
                pl.col("weighted_wins")
                .sum()
                .alias("weighted_wins"),

                pl.col("weighted_losses")
                .sum()
                .alias("weighted_losses"),
            ]
        )
        .rename(
            {
                "opponent_id": "oppteam_id",
                "opponent": "oppteam_name",
            }
        )
        .sort("oppteam_id")
    )

    # ------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    caused.write_parquet(OUTPUT_FILE)

    print(f"Wrote {len(caused)} teams to:")
    print(OUTPUT_FILE)
    print()
    print(caused.head(20))


if __name__ == "__main__":
    main()