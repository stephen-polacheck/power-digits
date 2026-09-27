from pathlib import Path
import json


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

input_path = (
    project_root
    / "data"
    / "raw"
    / "schools"
    / "cfbd_teams.json"
)

output_path = (
    project_root
    / "data"
    / "config"
    / "team_aesthetics.json"
)


# Schools that should appear between P4 and G5.
# Add/remove schools here as needed.
MANUAL_MIDDLE_SCHOOLS = {
    "Notre Dame",
    "BYU",
    "Army",
    "Connecticut",
    "Massachusetts",
    "Oregon State",
    "Washington State",
}


# Map CFBD classifications to the desired display order.
CLASSIFICATION_ORDER = {
    "fbs": 1,
    "fcs": 3,
    "ii": 4,
    "iii": 5,
}


P4_CONFERENCES = {
    "ACC": 1,
    "Big Ten": 2,
    "Big 12": 3,
    "SEC": 4,
}


G5_CONFERENCES = {
    "American Athletic": 1,
    "Conference USA": 2,
    "Mid-American": 3,
    "Mountain West": 4,
    "Pac-12": 5,
    "Sun Belt": 6,
}


def clean_color(value):
    """Convert invalid CFBD color values to None."""
    if not value:
        return None

    if value.lower() in {"#null", "null"}:
        return None

    return value


def get_logo(logos, dark=False):
    """
    Return the 500px CFBD logo.

    CFBD stores the logos in this pattern:
        logos/500/<id>.png
        logos-dark/500/<id>.png

    We construct the URL from the team ID rather than relying
    on the ordering of the logos array.
    """
    return None


def get_school_short(school):
    """
    Create a reasonable compact display name.

    This intentionally does not impose a hard character limit.
    The goal is a human-friendly abbreviated name that can
    subsequently be manually edited in team_aesthetics.json.
    """

    replacements = {
        "Arizona State": "Arizona St",
        "Appalachian State": "Appalachian St",
        "Arkansas State": "Arkansas St",
        "Boise State": "Boise St",
        "Colorado State": "Colorado St",
        "Florida State": "Florida St",
        "Fresno State": "Fresno St",
        "Georgia State": "Georgia St",
        "Iowa State": "Iowa St",
        "Jacksonville State": "Jacksonville St",
        "Kansas State": "Kansas St",
        "Kent State": "Kent St",
        "Michigan State": "Michigan St",
        "Mississippi State": "Mississippi St",
        "Montana State": "Montana St",
        "New Mexico State": "New Mexico St",
        "North Carolina State": "NC State",
        "Oklahoma State": "Oklahoma St",
        "Oregon State": "Oregon St",
        "Penn State": "Penn St",
        "Portland State": "Portland St",
        "Sacramento State": "Sacramento St",
        "San Diego State": "San Diego St",
        "San Jose State": "San Jose St",
        "South Dakota State": "South Dakota St",
        "Utah State": "Utah St",
        "Washington State": "Washington St",
        "Weber State": "Weber St",
        "Wichita State": "Wichita St",
        "Wright State": "Wright St",
    }

    return replacements.get(school, school)


def get_sort_group(team):
    """
    Determine the desired overall ordering:

        1 = Power 4
        2 = Other FBS / manual middle
        3 = Group of 5
        4 = FCS
        5 = Division II
        6 = Division III
        7 = everything else
    """

    conference = team.get("_conference")
    classification = team.get("_classification")

    if classification == "fbs":
        if conference in P4_CONFERENCES:
            return 1

        if conference in G5_CONFERENCES:
            return 3

        # Other FBS schools, including independents,
        # appear between P4 and G5.
        return 2

    if classification == "fcs":
        return 4

    if classification in {"ii", "d2"}:
        return 5

    if classification in {"iii", "d3"}:
        return 6

    return 7


def main():
    if not input_path.exists():
        raise FileNotFoundError(
            f"CFBD teams file not found: {input_path}"
        )

    print(f"Reading: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        teams = json.load(file)

    aesthetics = []

    for team in teams:
        school_id = team["id"]
        school_name = team["school"]

        # CFBD provides many logo sizes. We deliberately use
        # the 500px versions as the initial source.
        logo_url = (
            f"https://cdn.collegefootballdata.com/"
            f"logos/500/{school_id}.png"
        )

        logo_dark_url = (
            f"https://cdn.collegefootballdata.com/"
            f"logos-dark/500/{school_id}.png"
        )

        classification = team.get("classification")
        conference = team.get("conference")

        aesthetics_team = {
            "school_id": school_id,
            "school_name": school_name,
            "nickname": team.get("mascot"),
            "school_short": get_school_short(school_name),
            "school_abbrev": team.get("abbreviation"),
            "primary_color": clean_color(team.get("color")),
            "secondary_color": clean_color(
                team.get("alternateColor")
            ),
            "tertiary_color": None,
            "logo_url": logo_url,
            "logo_dark_url": logo_dark_url,
            "helmet_url": None,
            "wordmark_url": None,
            "twitter": team.get("twitter"),
            "instagram": None,
            "hashtag": None,

            # Temporary internal fields used only for sorting.
            "_conference": conference,
            "_classification": classification,
        }

        aesthetics.append(aesthetics_team)

    aesthetics.sort(
        key=lambda team: (
            get_sort_group(team),

            # P4 conference order
            P4_CONFERENCES.get(team["_conference"], 99),

            # G5 conference order
            G5_CONFERENCES.get(team["_conference"], 99),

            team["school_name"] or "",
        )
    )

    # Remove internal sorting fields before writing JSON.
    for team in aesthetics:
        team.pop("_conference", None)
        team.pop("_classification", None)

    # Make sure the output directory exists.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            aesthetics,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print(
        f"Successfully created {len(aesthetics)} team aesthetics records."
    )
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()