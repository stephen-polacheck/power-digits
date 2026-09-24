import json
from pathlib import Path

import polars as pl


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
    / "processed"
    / "schools"
    / "schools.parquet"
)


# Load raw CFBD school data
with input_path.open("r", encoding="utf-8") as file:
    schools = json.load(file)


# Convert to a Polars DataFrame
df = pl.DataFrame(schools)


# Select the school-level fields we want to retain
schools_processed = df.select(
    [
        pl.col("id").alias("team_id"),
        pl.col("school"),
        pl.col("mascot"),
        pl.col("abbreviation"),
        pl.col("alternateNames").alias("alternate_names"),
        pl.col("conference"),
        pl.col("division"),
        pl.col("classification"),
        pl.col("color"),
        pl.col("alternateColor").alias("alternate_color"),
        pl.col("logos"),
        pl.col("twitter"),

        pl.col("location")
        .struct.field("id")
        .alias("location_venue_id"),
    ]
)


# Ensure the output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)


# Save processed school data
schools_processed.write_parquet(output_path)


print(f"Successfully processed {len(schools_processed)} schools.")
print(f"Saved to: {output_path}")