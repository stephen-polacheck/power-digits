from pathlib import Path
import json
import sys
import polars as pl


SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

project_root = Path(__file__).resolve().parents[2]

team_games_path = (
    project_root
    / "data"
    / "processed"
    / "team_games"
    / "team_games.parquet"
)

power_digits_path = (
    project_root
    / "data"
    / "processed"
    / "power_digits"
    / f"power_digits_{SEASON}.parquet"
)

aesthetics_path = (
    project_root
    / "data"
    / "config"
    / "team_aesthetics.json"
)

output_path = (
    project_root
    / "data"
    / "website"
    / "rankings.json"
)


def load_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    print(f"Reading: {path}")

    return pl.read_parquet(path)


def load_aesthetics(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    print(f"Reading: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return pl.DataFrame(data)


def main():

    team_games = load_parquet(team_games_path)
    power_digits = load_parquet(power_digits_path)
    aesthetics = load_aesthetics(aesthetics_path)

    expected_teams = power_digits.height

    if expected_teams == 0:
        raise ValueError("Power Digits file contains zero teams.")

    print()
    print(f"Power Digits source contains {expected_teams} teams.")

    required_power_digits_columns = [
        "power_digits_overall_rank",
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
    ]

    missing_power_digits_columns = [
        column
        for column in required_power_digits_columns
        if column not in power_digits.columns
    ]

    if missing_power_digits_columns:
        raise ValueError(
            "Power Digits file is missing required columns: "
            + ", ".join(missing_power_digits_columns)
        )

    expected_ranks = list(range(1, expected_teams + 1))

    actual_ranks = (
        power_digits
        .select("power_digits_overall_rank")
        .to_series()
        .to_list()
    )

    if sorted(actual_ranks) != expected_ranks:
        raise ValueError(
            "Power Digits overall ranks are not sequential "
            f"from 1 through {expected_teams}."
        )

    current_season_games = (
        team_games
        .filter(
            (pl.col("season") == SEASON)
            & (pl.col("completed") == True)
        )
    )

    records = (
        current_season_games
        .group_by("team_id")
        .agg(
            [
                pl.col("result")
                .eq("W")
                .sum()
                .alias("wins"),

                pl.col("result")
                .eq("L")
                .sum()
                .alias("losses"),

                pl.col("result")
                .eq("T")
                .sum()
                .alias("ties"),
            ]
        )
        .with_columns(
            pl.when(pl.col("ties") > 0)
            .then(
                pl.concat_str(
                    [
                        pl.col("wins").cast(pl.String),
                        pl.lit("-"),
                        pl.col("losses").cast(pl.String),
                        pl.lit("-"),
                        pl.col("ties").cast(pl.String),
                    ]
                )
            )
            .otherwise(
                pl.concat_str(
                    [
                        pl.col("wins").cast(pl.String),
                        pl.lit("-"),
                        pl.col("losses").cast(pl.String),
                    ]
                )
            )
            .alias("record")
        )
    )

    rankings = (
        power_digits
        .select(
            [
                "power_digits_overall_rank",
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
            ]
        )
        .with_columns(
            pl.col("twwp").alias("weighted_win_pct")
        )
        .drop("twwp")
    )

    rankings = rankings.join(
        records.select(
            [
                "team_id",
                "record",
            ]
        ),
        on="team_id",
        how="left",
    )

    rankings = rankings.with_columns(
        [
            (
                pl.col("weighted_win_pct") * 100
            ).alias("weighted_win_pct"),

            (
                pl.col("strength_of_wins") * 100
            ).alias("strength_of_wins"),

            (
                pl.col("strength_of_losses") * 100
            ).alias("strength_of_losses"),

            (
                pl.col("strength_of_schedule") * 100
            ).alias("strength_of_schedule"),

            (
                pl.col("best_3_wins") * 100
            ).alias("best_3_wins"),
        ]
    )

    rankings = rankings.join(
        aesthetics.select(
            [
                "school_id",
                "school_name",
                "nickname",
                "school_short",
                "school_abbrev",
                "primary_color",
                "secondary_color",
                "tertiary_color",
                "logo_url",
                "logo_dark_url",
                "helmet_url",
                "wordmark_url",
                "twitter",
                "instagram",
                "hashtag",
            ]
        ),
        left_on="team_id",
        right_on="school_id",
        how="left",
    )

    rankings = rankings.rename(
        {
            "power_digits_overall_rank": "rank"
        }
    )

    rankings = rankings.select(
        [
            "rank",
            "team_id",
            "school_name",
            "nickname",
            "school_short",
            "school_abbrev",
            "conference",
            "primary_color",
            "secondary_color",
            "tertiary_color",
            "logo_url",
            "logo_dark_url",
            "helmet_url",
            "wordmark_url",
            "twitter",
            "instagram",
            "hashtag",
            "record",
            "power_digits",
            "weighted_wins",
            "weighted_losses",
            "weighted_win_pct",
            "strength_of_schedule",
            "strength_of_wins",
            "strength_of_losses",
            "best_3_wins",
        ]
    )

    rankings = rankings.with_columns(
        [
            pl.col("power_digits").round(1),
            pl.col("weighted_wins").round(1),
            pl.col("weighted_losses").round(1),
            pl.col("weighted_win_pct").round(1),
            pl.col("strength_of_schedule").round(1),
            pl.col("strength_of_wins").round(1),
            pl.col("strength_of_losses").round(1),
            pl.col("best_3_wins").round(1),
        ]
    )

    rankings = rankings.sort("rank")

    records = rankings.to_dicts()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print()
    print(f"Successfully created {len(records)} ranking records.")
    print(f"Saved to: {output_path}")

    print()
    print("Top 10:")

    print(
        rankings
        .select(
            [
                "rank",
                "school_name",
                "record",
                "power_digits",
                "weighted_win_pct",
                "strength_of_schedule",
                "strength_of_wins",
                "strength_of_losses",
                "best_3_wins",
            ]
        )
        .head(10)
    )

    if len(records) != expected_teams:
        raise ValueError(
            f"Expected {expected_teams} teams, "
            f"but generated {len(records)}."
        )

    if rankings["rank"].to_list() != expected_ranks:
        raise ValueError(
            "Website ranking numbers are not sequential "
            f"from 1 through {expected_teams}."
        )

    source_rank_order = (
        power_digits
        .sort("power_digits_overall_rank")
        .select("team_id")
        .to_series()
        .to_list()
    )

    website_rank_order = (
        rankings
        .sort("rank")
        .select("team_id")
        .to_series()
        .to_list()
    )

    if source_rank_order != website_rank_order:
        raise ValueError(
            "Website team ordering does not match the "
            "authoritative Power Digits overall ranking."
        )

    missing_aesthetics = rankings.filter(
        pl.col("school_name").is_null()
    )

    if missing_aesthetics.height > 0:
        print()
        print("WARNING: Teams missing aesthetics:")

        print(
            missing_aesthetics.select(
                [
                    "rank",
                    "team_id",
                    "school_name",
                ]
            )
        )


if __name__ == "__main__":
    main()