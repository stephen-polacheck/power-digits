import json
from pathlib import Path

import polars as pl


SEASON = 2026
CONFERENCE_STRENGTH_START_SEASON = 2023

REGULAR_SEASON_WEIGHT = 1.00
BOWL_WEIGHT = 0.25
PLAYOFF_WEIGHT = 10.00

SAME_LEVEL_WEIGHT = 0.40
CROSS_LEVEL_WEIGHT = 0.60


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_configuration(project_root: Path) -> dict:
    config_path = (
        project_root
        / "data"
        / "config"
        / "team_seasons.json"
    )

    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_games(project_root: Path) -> pl.DataFrame:
    game_files = [
        project_root
        / "data"
        / "processed"
        / "games"
        / f"games_{season}.parquet"
        for season in range(
            CONFERENCE_STRENGTH_START_SEASON,
            SEASON + 1,
        )
    ]

    games = pl.concat(
        [pl.read_parquet(path) for path in game_files],
        how="vertical",
    )

    return games


def load_current_team_context(
    project_root: Path,
) -> pl.DataFrame:
    team_seasons_path = (
        project_root
        / "data"
        / "processed"
        / "team_seasons"
        / f"team_seasons_{SEASON}.parquet"
    )

    return pl.read_parquet(team_seasons_path)


def add_game_weight(games: pl.DataFrame) -> pl.DataFrame:
    return games.with_columns(
        pl.when(pl.col("playoff_game"))
        .then(pl.lit(PLAYOFF_WEIGHT))
        .when(pl.col("season_type") == "postseason")
        .then(pl.lit(BOWL_WEIGHT))
        .otherwise(pl.lit(REGULAR_SEASON_WEIGHT))
        .alias("game_weight")
    )


def classify_conference(
    conference: pl.Expr,
    p4_conferences: list[str],
    g5_conferences: list[str],
) -> pl.Expr:
    return (
        pl.when(conference.is_in(p4_conferences))
        .then(pl.lit("P4"))
        .when(conference.is_in(g5_conferences))
        .then(pl.lit("G5"))
        .otherwise(pl.lit(None))
    )


def add_current_conference_context(
    games: pl.DataFrame,
    team_context: pl.DataFrame,
    config: dict,
) -> pl.DataFrame:
    p4_conferences = config["conference_groups"]["P4"]
    g5_conferences = config["conference_groups"]["G5"]

    current_context = team_context.select(
        [
            pl.col("team_id"),
            pl.col("conference").alias("current_conference"),
        ]
    )

    # Apply 2026 conference membership to the HOME team.
    games = games.join(
        current_context,
        left_on="home_team_id",
        right_on="team_id",
        how="left",
    ).rename(
        {
            "current_conference": "home_current_conference",
        }
    )

    # Apply 2026 conference membership to the AWAY team.
    games = games.join(
        current_context,
        left_on="away_team_id",
        right_on="team_id",
        how="left",
    ).rename(
        {
            "current_conference": "away_current_conference",
        }
    )

    # P4/G5 classification is based entirely on current membership.
    games = games.with_columns(
        classify_conference(
            pl.col("home_current_conference"),
            p4_conferences,
            g5_conferences,
        ).alias("home_level"),

        classify_conference(
            pl.col("away_current_conference"),
            p4_conferences,
            g5_conferences,
        ).alias("away_level"),
    )

    return games


def build_conference_matchups(
    games: pl.DataFrame,
) -> pl.DataFrame:
    return (
        games
        .filter(
            pl.col("completed")
            & pl.col("home_current_conference").is_not_null()
            & pl.col("away_current_conference").is_not_null()
            & (
                pl.col("home_current_conference")
                != pl.col("away_current_conference")
            )
            & pl.col("home_level").is_in(["P4", "G5"])
            & pl.col("away_level").is_in(["P4", "G5"])
        )
        .with_columns(
            pl.when(
                pl.col("home_level") == pl.col("away_level")
            )
            .then(pl.lit("same_level"))
            .otherwise(pl.lit("cross_level"))
            .alias("matchup_type")
        )
    )


def build_conference_results(
    games: pl.DataFrame,
) -> pl.DataFrame:
    home_results = games.select(
        [
            pl.col("home_current_conference").alias("conference"),
            pl.col("away_current_conference").alias(
                "opponent_conference"
            ),
            pl.col("home_level").alias("conference_level"),
            pl.col("away_level").alias("opponent_level"),
            pl.col("matchup_type"),
            pl.col("game_weight"),

            pl.when(
                pl.col("home_points") > pl.col("away_points")
            )
            .then(pl.col("game_weight"))
            .otherwise(0.0)
            .alias("weighted_wins"),

            pl.when(
                pl.col("home_points") < pl.col("away_points")
            )
            .then(pl.col("game_weight"))
            .otherwise(0.0)
            .alias("weighted_losses"),
        ]
    )

    away_results = games.select(
        [
            pl.col("away_current_conference").alias("conference"),
            pl.col("home_current_conference").alias(
                "opponent_conference"
            ),
            pl.col("away_level").alias("conference_level"),
            pl.col("home_level").alias("opponent_level"),
            pl.col("matchup_type"),
            pl.col("game_weight"),

            pl.when(
                pl.col("away_points") > pl.col("home_points")
            )
            .then(pl.col("game_weight"))
            .otherwise(0.0)
            .alias("weighted_wins"),

            pl.when(
                pl.col("away_points") < pl.col("home_points")
            )
            .then(pl.col("game_weight"))
            .otherwise(0.0)
            .alias("weighted_losses"),
        ]
    )

    return pl.concat(
        [home_results, away_results],
        how="vertical",
    )


def calculate_conference_strength(
    results: pl.DataFrame,
) -> pl.DataFrame:

    conference_results = (
        results
        .group_by(
            [
                "conference",
                "conference_level",
                "matchup_type",
            ]
        )
        .agg(
            pl.col("weighted_wins")
            .sum()
            .alias("weighted_wins"),

            pl.col("weighted_losses")
            .sum()
            .alias("weighted_losses"),
        )
    )

    same_level = (
        conference_results
        .filter(pl.col("matchup_type") == "same_level")
        .select(
            [
                "conference",
                pl.col("weighted_wins").alias(
                    "same_level_wins"
                ),
                pl.col("weighted_losses").alias(
                    "same_level_losses"
                ),
            ]
        )
    )

    cross_level = (
        conference_results
        .filter(pl.col("matchup_type") == "cross_level")
        .select(
            [
                "conference",
                pl.col("weighted_wins").alias(
                    "cross_level_wins"
                ),
                pl.col("weighted_losses").alias(
                    "cross_level_losses"
                ),
            ]
        )
    )

    conferences = (
        results
        .select(
            [
                "conference",
                "conference_level",
            ]
        )
        .unique()
    )

    output = (
        conferences
        .join(
            same_level,
            on="conference",
            how="left",
        )
        .join(
            cross_level,
            on="conference",
            how="left",
        )
        .with_columns(
            pl.col("same_level_wins").fill_null(0.0),
            pl.col("same_level_losses").fill_null(0.0),
            pl.col("cross_level_wins").fill_null(0.0),
            pl.col("cross_level_losses").fill_null(0.0),
        )
        .with_columns(
            pl.when(
                (
                    pl.col("same_level_wins")
                    + pl.col("same_level_losses")
                ) > 0
            )
            .then(
                pl.col("same_level_wins")
                /
                (
                    pl.col("same_level_wins")
                    + pl.col("same_level_losses")
                )
            )
            .otherwise(0.5)
            .alias("same_level_win_pct"),

            pl.when(
                (
                    pl.col("cross_level_wins")
                    + pl.col("cross_level_losses")
                ) > 0
            )
            .then(
                pl.col("cross_level_wins")
                /
                (
                    pl.col("cross_level_wins")
                    + pl.col("cross_level_losses")
                )
            )
            .otherwise(0.5)
            .alias("cross_level_win_pct"),
        )
        .with_columns(
            (
                pl.col("same_level_win_pct")
                * SAME_LEVEL_WEIGHT
                +
                pl.col("cross_level_win_pct")
                * CROSS_LEVEL_WEIGHT
            ).alias("derived_pct")
        )
        .with_columns(
            (
                pl.col("derived_pct") + 0.50
            ).alias("base_win"),

            (
                1.0
                /
                (pl.col("derived_pct") + 0.50)
            ).alias("base_loss"),
        )
        .with_columns(
            (
                pl.col("base_win") - 0.03
            ).alias("win_home"),

            pl.col("base_win")
            .alias("win_neutral"),

            (
                pl.col("base_win") + 0.03
            ).alias("win_road"),

            (
                pl.col("base_loss") + 0.03
            ).alias("loss_home"),

            pl.col("base_loss")
            .alias("loss_neutral"),

            (
                pl.col("base_loss") - 0.03
            ).alias("loss_road"),
        )
        .sort("base_win", descending=True)
    )

    return output


def main() -> None:
    project_root = get_project_root()

    config = load_configuration(project_root)

    games = load_games(project_root)

    current_team_context = load_current_team_context(
        project_root
    )

    print(
        f"Loaded {len(games)} games from "
        f"{CONFERENCE_STRENGTH_START_SEASON}-{SEASON}."
    )

    games = add_game_weight(games)

    games = add_current_conference_context(
        games,
        current_team_context,
        config,
    )

    conference_games = build_conference_matchups(games)

    print(
        f"Found {len(conference_games)} completed "
        f"interconference games."
    )

    results = build_conference_results(
        conference_games
    )

    conference_strength = calculate_conference_strength(
        results
    )

    output_path = (
        project_root
        / "data"
        / "processed"
        / "conference_strength"
        / f"conference_strength_{SEASON}.parquet"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conference_strength.write_parquet(
        output_path
    )

    print(
        f"\nSuccessfully calculated conference strength "
        f"for {len(conference_strength)} conferences."
    )

    print(f"Saved to: {output_path}")

    print("\nConference strength:")
    print(conference_strength)


if __name__ == "__main__":
    main()