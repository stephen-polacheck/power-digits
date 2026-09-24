from pathlib import Path
import sys
import polars as pl

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = Path(__file__).resolve().parents[2]

TEAM_WEIGHTED_WIN_PCT_FILE = (
    ROOT
    / "data"
    / "processed"
    / "team_weighted_win_pct"
    / f"team_weighted_win_pct_{SEASON}.parquet"
)

STRENGTH_OF_WINS_FILE = (
    ROOT
    / "data"
    / "processed"
    / "strength_of_wins"
    / f"strength_of_wins_{SEASON}.parquet"
)

STRENGTH_OF_LOSSES_FILE = (
    ROOT
    / "data"
    / "processed"
    / "strength_of_losses"
    / f"strength_of_losses_{SEASON}.parquet"
)

STRENGTH_OF_SCHEDULE_FILE = (
    ROOT
    / "data"
    / "processed"
    / "strength_of_schedule"
    / f"strength_of_schedule_{SEASON}.parquet"
)

BEST_3_WINS_FILE = (
    ROOT
    / "data"
    / "processed"
    / "best_3_wins"
    / f"best_3_wins_{SEASON}.parquet"
)

TEAM_SEASONS_FILE = (
    ROOT
    / "data"
    / "processed"
    / "team_seasons"
    / f"team_seasons_{SEASON}.parquet"
)

OUTPUT_DIR = ROOT / "data" / "processed" / "power_digits"
OUTPUT_FILE = OUTPUT_DIR / f"power_digits_{SEASON}.parquet"


def main():
    twwp = pl.read_parquet(TEAM_WEIGHTED_WIN_PCT_FILE).select([
        "team_id",
        "team",
        "weighted_win_pct",
        "weighted_wins",
        "weighted_losses",
    ])

    sow = pl.read_parquet(STRENGTH_OF_WINS_FILE).select([
        "team_id",
        pl.col("weighted_win_pct").alias("strength_of_wins"),
    ])

    sol = pl.read_parquet(STRENGTH_OF_LOSSES_FILE).select([
        "team_id",
        pl.col("weighted_win_pct").alias("strength_of_losses"),
    ])

    sos = pl.read_parquet(STRENGTH_OF_SCHEDULE_FILE).select([
        "team_id",
        pl.col("weighted_win_pct").alias("strength_of_schedule"),
    ])

    b3w = pl.read_parquet(BEST_3_WINS_FILE).select([
        "team_id",
        "best_3_wins",
    ])

    team_seasons = pl.read_parquet(TEAM_SEASONS_FILE).select([
        "team_id",
        "conference",
    ]).unique(subset=["team_id"])

    # Start with the TWWP population and attach conference information.
    result = (
        twwp
        .join(team_seasons, on="team_id", how="left")
        .join(sow, on="team_id", how="left")
        .join(sol, on="team_id", how="left")
        .join(sos, on="team_id", how="left")
        .join(b3w, on="team_id", how="left")
    )

    # Match the SQL ISNULL behavior.
    result = result.with_columns([
        pl.col("weighted_win_pct")
        .fill_null(0.0)
        .alias("twwp"),

        pl.col("strength_of_wins")
        .fill_null(0.0),

        pl.col("strength_of_losses")
        .fill_null(1.0),

        pl.col("strength_of_schedule")
        .fill_null(0.0),

        pl.col("best_3_wins")
        .fill_null(0.0),
    ])

    # Final Power Digits calculation.
    result = result.with_columns(
        (
            (
                pl.col("twwp") * 0.55
                + pl.col("strength_of_wins") * 0.05
                + pl.col("strength_of_losses") * 0.05
                + pl.col("strength_of_schedule") * 0.25
                + pl.col("best_3_wins") * 0.10
            )
            * 100
        ).alias("power_digits")
    )

    # ---------------------------------------------------------
    # Legacy Power Digits ranking order
    #
    # ORDER BY:
    #   PowerDigitOvr DESC,
    #   twwp DESC,
    #   sos DESC,
    #   b3w DESC,
    #   ww DESC,
    #   wl ASC,
    #   schoolid ASC
    #
    # team_id is the current equivalent of schoolid.
    # ---------------------------------------------------------

    rank_columns = [
        "power_digits",
        "twwp",
        "strength_of_schedule",
        "best_3_wins",
        "weighted_wins",
        "weighted_losses",
        "team_id",
    ]

    rank_descending = [
        True,
        True,
        True,
        True,
        True,
        False,
        False,
    ]

    # Overall rank.
    result = (
        result
        .sort(rank_columns, descending=rank_descending)
        .with_columns(
            pl.int_range(
                1,
                pl.len() + 1,
            ).alias("power_digits_overall_rank")
        )
    )

    # Conference rank.
    #
    # This is equivalent to:
    # RANK() OVER (
    #   PARTITION BY conference
    #   ORDER BY ...
    # )
    #
    # Because team_id is the final tie-breaker, the ordering is
    # deterministic.
    result = (
        result
        .sort(
            ["conference"] + rank_columns,
            descending=[False] + rank_descending,
        )
        .with_columns(
            pl.int_range(1, pl.len() + 1)
            .over("conference")
            .alias("power_digits_conference_rank")
        )
    )

    # Independents are placed into conference group 99.
    result = result.with_columns(
        pl.when(pl.col("conference") == "FBS Independents")
        .then(pl.lit(99))
        .otherwise(pl.col("power_digits_conference_rank"))
        .alias("power_digits_conference_rank_2")
    )

    # Seed rank within the conference group.
    result = (
        result
        .sort(
            ["power_digits_conference_rank_2"] + rank_columns,
            descending=[False] + rank_descending,
        )
        .with_columns(
            pl.int_range(1, pl.len() + 1)
            .over("power_digits_conference_rank_2")
            .alias("power_digits_seed_rank")
        )
    )

    # Return to overall ranking order for the output file.
    result = result.sort("power_digits_overall_rank")

    result = result.select([
        "power_digits_overall_rank",
        "power_digits_conference_rank",
        "power_digits_conference_rank_2",
        "power_digits_seed_rank",
        "team_id",
        "team",
        "conference",
        "power_digits",
        "twwp",
        "strength_of_wins",
        "strength_of_losses",
        "strength_of_schedule",
        "best_3_wins",
        "weighted_wins",
        "weighted_losses",
    ])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.write_parquet(OUTPUT_FILE)

    print(f"Wrote {result.height} teams to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()