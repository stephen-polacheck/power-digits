"""
Sanity checks that run after the ranking engine.
If anything looks wrong, the pipeline stops with an error.

Usage:
    python src/validation/validate_season.py 2026
"""

import sys
from pathlib import Path

import polars as pl


SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"


def check_two_rows_per_game(team_games: pl.DataFrame) -> list[str]:
    """Every game should appear exactly twice (once per team)."""
    bad = (
        team_games
        .group_by("game_id")
        .len()
        .filter(pl.col("len") != 2)
    )

    if bad.height == 0:
        return []

    return [
        f"{bad.height} games do not have exactly 2 team-game rows "
        f"(example game_ids: {bad['game_id'].head(5).to_list()})"
    ]


def check_completed_games_have_scores(team_games: pl.DataFrame) -> list[str]:
    """
    A completed FBS game with a missing score would be counted as a tie.
    Lower-division games are ignored because they never affect the rankings.
    """
    bad = team_games.filter(
        pl.col("completed")
        & (pl.col("team_classification") == "fbs")
        & (
            pl.col("team_points").is_null()
            | pl.col("opponent_points").is_null()
        )
    )

    if bad.height == 0:
        return []

    return [
        f"{bad.height} completed FBS team-games are missing a score "
        f"(example game_ids: {bad['game_id'].unique().head(5).to_list()})"
    ]


def check_every_opponent_is_weighted(
    team_games: pl.DataFrame,
    team_seasons: pl.DataFrame,
    conference_strength: pl.DataFrame,
) -> list[str]:
    """
    A win or loss only counts if the opponent's Power Digits conference
    has a conference-strength row (FCS opponents use the fixed 0.5 / 1.5).
    Otherwise the game silently counts as zero.
    """
    completed = team_games.filter(
        pl.col("completed")
        & (pl.col("team_classification") == "fbs")
        & ~pl.col("opponent_classification").eq_missing("fcs")
    )

    opponent_conferences = (
        team_seasons
        .select(
            pl.col("team_id").alias("opponent_id"),
            pl.col("conference").alias("opponent_conference"),
        )
        .unique(subset=["opponent_id"])
    )

    known_conferences = conference_strength.select(
        "conference",
        pl.lit(True).alias("_has_strength"),
    )

    unweighted = (
        completed
        .join(opponent_conferences, on="opponent_id", how="left")
        .join(
            known_conferences,
            left_on="opponent_conference",
            right_on="conference",
            how="left",
        )
        .filter(pl.col("_has_strength").is_null())
    )

    if unweighted.height == 0:
        return []

    examples = (
        unweighted
        .select("opponent", "opponent_conference", "opponent_classification")
        .unique()
        .head(10)
        .to_dicts()
    )

    return [
        f"{unweighted.height} completed games would count as zero because "
        f"the opponent has no conference strength. Add a conference "
        f"override in data/config/team_seasons.json. Opponents: {examples}"
    ]


def check_rankings(power_digits: pl.DataFrame) -> list[str]:
    problems = []

    if power_digits.height == 0:
        return ["Power Digits output has zero teams."]

    null_scores = power_digits.filter(pl.col("power_digits").is_null())
    if null_scores.height > 0:
        problems.append(
            f"{null_scores.height} teams have no Power Digits score: "
            f"{null_scores['team'].head(10).to_list()}"
        )

    ranks = sorted(power_digits["power_digits_overall_rank"].to_list())
    if ranks != list(range(1, power_digits.height + 1)):
        problems.append("Overall ranks are not a clean 1..N sequence.")

    return problems


def main() -> None:
    team_games = pl.read_parquet(
        PROCESSED / "team_games" / "team_games.parquet"
    ).filter(pl.col("season") == SEASON)

    team_seasons = pl.read_parquet(
        PROCESSED / "team_seasons" / f"team_seasons_{SEASON}.parquet"
    )
    conference_strength = pl.read_parquet(
        PROCESSED / "conference_strength" / f"conference_strength_{SEASON}.parquet"
    )
    power_digits = pl.read_parquet(
        PROCESSED / "power_digits" / f"power_digits_{SEASON}.parquet"
    )

    problems = []
    problems += check_two_rows_per_game(team_games)
    problems += check_completed_games_have_scores(team_games)
    problems += check_every_opponent_is_weighted(
        team_games, team_seasons, conference_strength
    )
    problems += check_rankings(power_digits)

    completed = team_games.filter(pl.col("completed"))
    print(f"Season {SEASON}: {completed.height // 2} completed games")
    if completed.height > 0:
        print(f"Latest completed week: {completed['week'].max()}")

    if problems:
        print()
        print("VALIDATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    print("All validation checks passed.")


if __name__ == "__main__":
    main()