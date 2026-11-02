/* =========================================================
   Power Digits - builds the Top 30 and Top 138 graphics from
   rankings.json. build_graphics.py opens this page, waits for
   window.graphicReady, then saves a screenshot.
   ========================================================= */

const params = new URLSearchParams(window.location.search);
const WEEK_LABEL = params.get("week") || "";
const DATA_URL = "/docs/data/rankings.json";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function logoImg(team) {
  const img = document.createElement("img");
  img.alt = "";
  img.src = team.logo_dark_url || team.logo_url || "";
  img.onerror = () => (img.style.visibility = "hidden");
  return img;
}

function teamColors(node, team) {
  node.style.setProperty("--primary", team.primary_color || "#555555");
  node.style.setProperty("--secondary", team.secondary_color || "#ffffff");
}

function stripes(node) {
  for (const cls of ["g-stripe thick secondary", "g-stripe thin-p primary", "g-stripe thin secondary"]) {
    node.appendChild(el("span", cls));
  }
}

/* ---------- Top 30: logo tiles ---------- */

function buildTop30(teams) {
  const grid = document.getElementById("grid");
  for (const team of teams.slice(0, 30)) {
    const tile = el("div", "t30-tile");
    teamColors(tile, team);

    const plate = el("div", "g-plate");
    const inner = el("div", "g-unskew");
    inner.appendChild(logoImg(team));
    plate.appendChild(inner);

    tile.appendChild(plate);
    stripes(tile);
    tile.appendChild(el("span", "t30-rank metal-text", String(team.rank)));
    grid.appendChild(tile);
  }
}

/* ---------- Top 138: top 30 rows + compact rest ---------- */

function buildTop138(teams) {
  const top = document.getElementById("top");
  for (const team of teams.slice(0, 30)) {
    const row = el("div", "t138-row");
    teamColors(row, team);

    const plate = el("div", "g-plate");
    const inner = el("div", "g-unskew");
    inner.appendChild(el("span", "t138-rank", String(team.rank)));
    inner.appendChild(logoImg(team));
    inner.appendChild(el("span", "t138-name", team.school_short || team.school_name));
    plate.appendChild(inner);
    row.appendChild(plate);
    stripes(row);
    row.appendChild(el("span", "t138-value", Number(team.power_digits).toFixed(1)));
    top.appendChild(row);
  }

  const rest = document.getElementById("rest");
  for (const team of teams.slice(30)) {
    const item = el("div", "t138-mini");
    teamColors(item, team);
    item.appendChild(el("span", "rank metal-text", String(team.rank)));

    const chip = el("span", "t138-chip g-plate");
    const inner = el("span", "g-unskew");
    inner.appendChild(logoImg(team));
    chip.appendChild(inner);
    item.appendChild(chip);

    item.appendChild(el("span", "value", Number(team.power_digits).toFixed(1)));
    rest.appendChild(item);
  }
}

/* ---------- High Leverage: upcoming games, 4 per side ---------- */

const preload = [];   // helmet images to wait for before the screenshot

// helmet_url in team_aesthetics.json is just the file name, e.g. "Ohio State.png",
// for a file in docs/assets/img/helmets/. Full links ("https://...") also work.
function helmetUrl(team) {
  const value = (team.helmet_url || "").trim();
  if (!value) return "";
  if (/^https?:\/\//.test(value) || value.startsWith("/")) return value;
  return "/docs/assets/img/helmets/" + encodeURIComponent(value);
}

// How light a "#rrggbb" color is, 0 (black) to 1 (white)
function lightness(hex) {
  const value = parseInt((hex || "#000000").replace("#", ""), 16);
  const r = (value >> 16) & 255, g = (value >> 8) & 255, b = value & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

function leverageTeam(team, side) {
  const box = el("div", `hl-team ${side}`);
  teamColors(box, team);

  // school name in the secondary color, unless it would be too hard to read
  // on the primary color (e.g. black on dark red) - then white
  const primary = team.primary_color || "#555555";
  const secondary = team.secondary_color || "#ffffff";
  const readable = Math.abs(lightness(secondary) - lightness(primary)) > 0.3;
  box.style.setProperty("--name-color", readable ? secondary : "#ffffff");

  const plate = el("div", "hl-plate");
  const inner = el("div", "hl-inner");
  inner.appendChild(el("div", "hl-texture"));

  const helmet = el("div", "hl-helmet");
  const helmetSrc = helmetUrl(team);
  const src = helmetSrc || team.logo_dark_url || team.logo_url || "";
  if (!helmetSrc) helmet.classList.add("logo-only");
  if (src) {
    helmet.style.setProperty("--helmet", `url("${src}")`);
    preload.push(src);
  }
  inner.appendChild(helmet);
  inner.appendChild(el("div", "hl-line"));
  inner.appendChild(el("div", "hl-name", team.school_short || team.school_name));

  plate.appendChild(inner);
  box.appendChild(plate);
  box.appendChild(el("span", "hl-rank metal-text", String(team.rank)));
  return box;
}

// shrink long school names until they fit their space
function fitNames() {
  for (const name of document.querySelectorAll(".hl-name")) {
    let size = 28;
    while (name.scrollWidth > name.clientWidth && size > 17) {
      size -= 1;
      name.style.fontSize = `${size}px`;
    }
  }
}

async function buildLeverage() {
  const data = await (await fetch("/docs/data/upcoming.json", { cache: "no-cache" })).json();
  document.getElementById("leverage-title").textContent =
    `POWER DIGITS HIGH LEVERAGE - WEEK ${data.week}`;

  // reads across, then down: the two highest-leverage games are the top row
  const grid = document.getElementById("games");
  data.games.forEach((game, i) => {
    const pod = el("div", `hl-game ${i % 2 === 0 ? "hl-left" : "hl-right"}`);
    pod.appendChild(leverageTeam(game.away, "away"));   // road team on top
    pod.appendChild(leverageTeam(game.home, "home"));
    grid.appendChild(pod);
  });
}

/* ---------- Load, then signal ready ---------- */

async function waitForImages() {
  const images = [...document.images];
  await Promise.all([
    ...images.map((img) =>
      img.complete ? null : new Promise((done) => { img.onload = done; img.onerror = done; })
    ),
    ...preload.map((src) => new Promise((done) => {
      const img = new Image();
      img.onload = done;
      img.onerror = done;
      img.src = src;
    })),
  ]);
}

async function main() {
  for (const node of document.querySelectorAll("[data-week]")) {
    node.textContent = node.textContent.replace("{week}", WEEK_LABEL);
  }

  const kind = document.body.dataset.graphic;

  if (kind === "leverage") {
    await buildLeverage();
  } else {
    const teams = await (await fetch(DATA_URL, { cache: "no-cache" })).json();
    teams.sort((a, b) => a.rank - b.rank);
    if (kind === "top30") buildTop30(teams);
    if (kind === "top138") buildTop138(teams);
  }

  await waitForImages();
  await document.fonts.ready;
  if (kind === "leverage") fitNames();
  window.graphicReady = true;
}

main();
