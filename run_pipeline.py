import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PIPELINE = [
    ("Get schools", "src/cfbd/get_schools.py"),
    ("Process schools", "src/cfbd/process_schools.py"),
    ("Get games", "src/cfbd/get_games.py"),
    ("Process games", "src/cfbd/process_games.py"),
    ("Build team seasons", "src/cfbd/build_team_seasons.py"),
    ("Build team games", "src/cfbd/build_team_games.py"),
    ("Conference strength", "src/power_digits/conference_strength.py"),
    ("Weighted caused wins/losses", "src/power_digits/weighted_caused_wins_losses.py"),
    ("Team weighted win pct", "src/power_digits/team_weighted_win_pct.py"),
    ("Strength of wins", "src/power_digits/strength_of_wins.py"),
    ("Strength of losses", "src/power_digits/strength_of_losses.py"),
    ("Strength of schedule", "src/power_digits/strength_of_schedule.py"),
    ("Best 3 wins", "src/power_digits/best_3_wins.py"),
    ("Power Digits overall", "src/power_digits/power_digits_overall.py"),
]


def run_step(name, script, season):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    script_path = ROOT / script

    subprocess.run(
        [sys.executable, str(script_path), str(season)],
        cwd=ROOT,
        check=True,
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python run_pipeline.py <season>")
        sys.exit(1)

    try:
        season = int(sys.argv[1])
    except ValueError:
        print("Season must be a number, such as 2026.")
        sys.exit(1)

    print(f"Starting Power Digits pipeline for {season}")

    for name, script in PIPELINE:
        run_step(name, script, season)

    print()
    print("=" * 70)
    print(f"Power Digits pipeline completed successfully for {season}")
    print("=" * 70)


if __name__ == "__main__":
    main()