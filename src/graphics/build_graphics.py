"""
Builds the Power Digits social-media graphics.

Each graphic is a small web page in src/graphics/templates/ that uses the
website's own styling (site.css, and playoffs.css/playoffs.js for brackets).
This script serves the project folder on a private local web server, opens
each page in a hidden Chromium browser (Playwright), and saves a PNG.

It is NOT part of run_pipeline.py: each graphic is made on its own posting day.

Output (outside docs/, so it is NOT part of the website):
    graphics/<season>/week_<NN>/<name>.png   archive of every week
    graphics/latest/<name>.png               always the newest

The ranking graphics are filed under the week just played. High Leverage is
filed under the upcoming week it previews (it refreshes upcoming.json first).

Usage:
    python src/graphics/build_graphics.py 2026                      all graphics
    python src/graphics/build_graphics.py 2026 top30 top138         just these
    python src/graphics/build_graphics.py 2026 high_leverage

Graphic names: top30, top138, bracket_12, bracket_24, high_leverage
"""

import functools
import json
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
REQUESTED = sys.argv[2:]   # graphic names; empty = all of them

project_root = Path(__file__).resolve().parents[2]
rankings_path = project_root / "docs" / "data" / "rankings.json"
upcoming_path = project_root / "docs" / "data" / "upcoming.json"
build_upcoming_script = project_root / "src" / "website" / "build_upcoming.py"
graphics_dir = project_root / "graphics"

SCALE = 2  # save at 2x the design size, so images stay sharp

# name -> (template page, width, height, extra URL parameters)
GRAPHICS = {
    "top30": ("top30.html", 1080, 1080, {}),
    "top138": ("top138.html", 1080, 1620, {}),
    "bracket_12": ("bracket.html", 1600, 900, {"format": "12"}),
    "bracket_24": ("bracket.html", 1600, 900, {"format": "24"}),
    "high_leverage": ("leverage.html", 1080, 1080, {}),
}


def week_label(teams):
    """Label for the most recently played week, e.g. "WEEK 10"."""
    weeks = [game["week"] for team in teams for game in team.get("games", [])]
    week = max(weeks) if weeks else 0
    return f"WEEK {week}", f"week_{week:02d}"


def upcoming_week_label():
    """Rebuild upcoming.json, then label the graphic with the week it previews."""
    subprocess.run([sys.executable, str(build_upcoming_script), str(SEASON)], check=True)
    with upcoming_path.open("r", encoding="utf-8") as file:
        week = json.load(file)["week"]
    return f"WEEK {week}", f"week_{week:02d}"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the console clean


def start_server():
    """Serve the project folder on a free local port (only reachable from this computer)."""
    handler = functools.partial(QuietHandler, directory=str(project_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    unknown = [name for name in REQUESTED if name not in GRAPHICS]
    if unknown:
        sys.exit(f"Unknown graphic(s): {', '.join(unknown)}. Choose from: {', '.join(GRAPHICS)}")
    names = REQUESTED or list(GRAPHICS)

    with rankings_path.open("r", encoding="utf-8") as file:
        teams = json.load(file)
    played = week_label(teams)
    upcoming = upcoming_week_label() if "high_leverage" in names else None

    latest_dir = graphics_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    server = start_server()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/src/graphics/templates/"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            for name in names:
                template, width, height, extra = GRAPHICS[name]
                label, folder = upcoming if name == "high_leverage" else played
                week_dir = graphics_dir / str(SEASON) / folder
                week_dir.mkdir(parents=True, exist_ok=True)

                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=SCALE,
                )
                query = urlencode({"week": label, **extra})
                page.goto(f"{base_url}{template}?{query}")
                page.wait_for_function("window.graphicReady === true", timeout=60_000)

                output_path = week_dir / f"{name}.png"
                page.screenshot(path=str(output_path))
                shutil.copyfile(output_path, latest_dir / f"{name}.png")
                print(f"Saved {output_path.relative_to(project_root)}")
                page.close()

            browser.close()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
