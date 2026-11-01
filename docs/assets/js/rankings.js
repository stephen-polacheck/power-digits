/* =========================================================
   Power Digits - loads rankings.json, draws the table,
   handles column sorting and top/bottom highlighting.
   ========================================================= */

const DATA_URL = document.body.dataset.root + "data/rankings.json";

// How many teams get the green (best) / red (worst) highlight per stat.
const HIGHLIGHT_COUNT = 20;

// The rank lives inside the team banner but still sorts like a column.
const RANK_COLUMN = { field: "rank", label: "RANK", sort: "asc" };

// One entry per stat column, in display order.
//   label:     "\n" marks where the header breaks onto its second line
//   group:     "core" always shows, "wl" shows when there is room,
//              "extra" shows on desktop or after tapping "Show all stats"
//   sort:      first-click direction ("desc" = biggest first); omit = not sortable
//   highlight: color the top/bottom HIGHLIGHT_COUNT values green/red
//   highlight: color the top/bottom HIGHLIGHT_COUNT values green/red
//   tip:       pop-up listing games
//                games: "all", "W", "L" or "best3"
//                order: "date" (order played) or "rank" (opponent's Power Digits rank)
//                value: "weight" = each game's weighted win/loss value
//                       "wwp"    = the opponent's Weighted Win %
//                       "record" = the opponent's record

const STAT_COLUMNS = [
  { field: "power_digits", label: "POWER\nDIGITS", group: "core", css: "col-pd", decimals: 1, sort: "desc" },
  { field: "record", label: "RECORD", group: "core",
    tip: { games: "all", order: "date", value: "record" } },
  { field: "weighted_wins", label: "WEIGHTED\nWINS", group: "wl", decimals: 1, sort: "desc", highlight: true,
    tip: { games: "W", order: "rank", value: "weight" } },
  { field: "weighted_losses", label: "WEIGHTED\nLOSS", group: "wl", decimals: 1, sort: "asc", highlight: true,
    tip: { games: "L", order: "rank", value: "weight" } },
  { field: "weighted_win_pct", label: "WEIGHTED\nWIN %", group: "extra", sort: "desc", highlight: true },
  { field: "strength_of_schedule", label: "STRENGTH OF\nSCHEDULE", group: "extra", sort: "desc", highlight: true,
    tip: { games: "all", order: "rank", value: "wwp" } },
  { field: "strength_of_wins", label: "STRENGTH\nOF WINS", group: "extra", sort: "desc", highlight: true,
    tip: { games: "W", order: "rank", value: "wwp" } },
  { field: "strength_of_losses", label: "STRENGTH\nOF LOSS", group: "extra", sort: "desc", highlight: true,
    tip: { games: "L", order: "rank", value: "wwp" } },
  { field: "best_3_wins", label: "BEST 3\nWINS", group: "extra", sort: "desc", highlight: true,
    tip: { games: "best3", order: "rank", value: "wwp" } },
];

let teams = [];
let rowsByRank = new Map();
let currentSort = { field: "rank", dir: "asc" };

function groupClass(group) {
  if (group === "wl") return "col-wl";
  if (group === "extra") return "col-extra";
  return "";
}

function formatValue(value, decimals) {
  if (value === null || value === undefined) return "-";
  if (decimals !== undefined) return Number(value).toFixed(decimals);
  return String(value);
}

function makeCell(tag, className, text) {
  const cell = document.createElement(tag);
  if (className) cell.className = className;
  if (text !== undefined) cell.textContent = text;
  return cell;
}

/* ---------- Highlighting ---------- */

// Returns { good, bad } cut-off values for one column. A team is green if
// its value is at least as good as the Nth-best value (ties included),
// and red if it is at least as bad as the Nth-worst.
function highlightCutoffs(col) {
  const values = teams
    .map((t) => t[col.field])
    .filter((v) => v !== null && v !== undefined);

  if (values.length < HIGHLIGHT_COUNT * 2) return null;

  // best first
  values.sort((a, b) => (col.sort === "asc" ? a - b : b - a));

  return {
    good: values[HIGHLIGHT_COUNT - 1],
    bad: values[values.length - HIGHLIGHT_COUNT],
  };
}

function highlightClass(value, col, cutoffs) {
  if (!cutoffs || value === null || value === undefined) return "";

  const better = (a, b) => (col.sort === "asc" ? a <= b : a >= b);
  const worse = (a, b) => (col.sort === "asc" ? a >= b : a <= b);

  if (better(value, cutoffs.good)) return "stat-good";
  if (worse(value, cutoffs.bad)) return "stat-bad";
  return "";
}

/* ---------- Header ---------- */

function makeSortButton(col) {
  const button = makeCell("button", "sort-btn", col.label);
  button.type = "button";
  button.dataset.field = col.field;
  button.addEventListener("click", () => onSortClick(col));
  return button;
}

function buildHeaderRow() {
  const tr = document.createElement("tr");

  const rankTh = makeCell("th", "col-team");
  rankTh.appendChild(makeSortButton(RANK_COLUMN));
  tr.appendChild(rankTh);

  for (const col of STAT_COLUMNS) {
    const th = makeCell("th", groupClass(col.group));
    if (col.sort) {
      th.appendChild(makeSortButton(col));
    } else {
      th.appendChild(makeCell("span", "header-label", col.label));
    }
    tr.appendChild(th);
  }

  tr.appendChild(makeCell("th", "col-cap", ""));
  return tr;
}

/* ---------- Team rows ---------- */

function buildTeamRow(team, cutoffsByField) {
  const tr = document.createElement("tr");

  // Team colors come straight from team_aesthetics.json via rankings.json
  tr.style.setProperty("--primary", team.primary_color || "#555555");
  tr.style.setProperty("--secondary", team.secondary_color || "#ffffff");

  // Team banner: primary box (rank, logo, name), then the racing stripes:
  // thick secondary, thin primary, thin secondary, then a gray fill.
  const teamTd = makeCell("td", "col-team");
  const banner = makeCell("div", "banner");

  const plate = makeCell("div", "plate");
  const inner = makeCell("div", "plate-inner");
  inner.appendChild(makeCell("span", "rank", String(team.rank)));

  const logoUrl = team.logo_dark_url || team.logo_url;
  const img = document.createElement("img");
  img.alt = "";
  img.onerror = () => (img.style.visibility = "hidden");
  if (logoUrl) img.src = logoUrl;
  else img.style.visibility = "hidden";
  inner.appendChild(img);

  inner.appendChild(makeCell("span", "team-name", team.school_short || team.school_name));
  plate.appendChild(inner);
  banner.appendChild(plate);

  for (const stripe of ["stripe thick secondary", "stripe thin-primary primary", "stripe thin secondary", "stripe fill-right"]) {
    banner.appendChild(makeCell("span", stripe));
  }
  teamTd.appendChild(banner);
  tr.appendChild(teamTd);

  // Stat columns
  for (const col of STAT_COLUMNS) {
    const value = team[col.field];
    const highlight = col.highlight
      ? highlightClass(value, col, cutoffsByField[col.field])
      : "";
    const css = [col.css, groupClass(col.group), highlight].filter(Boolean).join(" ");
    const td = makeCell("td", css, formatValue(value, col.decimals));
    if (col.tip) attachTooltip(td, team, col);
    tr.appendChild(td);
  }

  // Right end: gray fill, thick primary, thin secondary
  const capTd = makeCell("td", "col-cap");
  const cap = makeCell("div", "cap");
  for (const stripe of ["stripe fill-left", "stripe thick primary", "stripe thin secondary"]) {
    cap.appendChild(makeCell("span", stripe));
  }
  capTd.appendChild(cap);
  tr.appendChild(capTd);
  return tr;
}

/* ---------- Game pop-ups (tooltips) ---------- */

// Desktop: hover. Phones/tablets (no hover): tap to open, tap elsewhere to close.
const CAN_HOVER = window.matchMedia("(hover: hover)").matches;
const tooltip = makeCell("div", "game-tip");
tooltip.setAttribute("role", "tooltip");
document.body.appendChild(tooltip);
let tooltipCell = null;

function selectGames(team, tip) {
  let games = team.games || [];

  if (tip.games === "W") games = games.filter((g) => g.result === "W");
  if (tip.games === "L") games = games.filter((g) => g.result === "L");
  if (tip.games === "best3") games = games.filter((g) => g.best_3);

  games = [...games];
  if (tip.order === "rank") {
    // best-ranked opponent first; FCS opponents last; ties by date
    const rankOf = (g) => (g.opponent_fcs || g.opponent_rank == null ? 9999 : g.opponent_rank);
    games.sort((a, b) => rankOf(a) - rankOf(b) || a.start_date.localeCompare(b.start_date));
  } else {
    games.sort((a, b) => a.start_date.localeCompare(b.start_date));
  }
  return games;
}

const EMPTY_MESSAGES = {
  all: "No games",
  W: "No wins",
  L: "No losses",
  best3: "No wins",
};

function tipValue(game, tip) {
  if (tip.value === "weight") return formatValue(game.value, 2);
  if (tip.value === "wwp") return formatValue(game.opponent_weighted_win_pct);
  if (tip.value === "record") return game.opponent_record || "-";
  return null;
}

// Footer text explaining the number on the right of each row
function tipNote(tip) {
  if (tip.value === "weight") {
    return tip.games === "L" ? "Stat: Weighted Loss Value" : "Stat: Weighted Win Value";
  }
  if (tip.value === "wwp") return "Stat: Weighted Win %";
  if (tip.value === "record") return "Stat: Opponent Record";
  return null;
}

function buildTooltip(team, col) {
  tooltip.replaceChildren();

  // Title: "23 - NORTHWESTERN" on the left, record on the right
  const title = makeCell("div", "tip-title");
  const left = makeCell("span", "tip-title-left");
  left.appendChild(makeCell("span", "tip-title-rank metal-text", String(team.rank)));
  left.appendChild(makeCell("span", "tip-title-sep", "-"));
  left.appendChild(makeCell("span", "tip-team", team.school_short || team.school_name));
  title.appendChild(left);
  title.appendChild(makeCell("span", "tip-record metal-text", team.record || ""));
  tooltip.appendChild(title);

  const games = selectGames(team, col.tip);
  if (games.length === 0) {
    tooltip.appendChild(makeCell("div", "tip-empty", EMPTY_MESSAGES[col.tip.games]));
    return;
  }

  const list = makeCell("div", "tip-list");
  for (const g of games) {
    const row = makeCell("div", "tip-row");

    // Opponent banner: their primary color, rank + logo, ending on a slash
    const banner = makeCell("div", "tip-banner");
    banner.style.setProperty("--opp-color", g.opponent_primary_color || "#555555");

    const fill = makeCell("div", "tip-fill");
    fill.appendChild(
      makeCell("span", "tip-rank", g.opponent_fcs ? "FCS" : String(g.opponent_rank ?? "-"))
    );

    const logo = makeCell("span", "tip-logo");
    if (g.opponent_logo) {
      const img = document.createElement("img");
      img.src = g.opponent_logo;
      img.alt = g.opponent;
      // only if the logo fails to load, fall back to the school's name
      img.onerror = () => logo.replaceChildren(makeCell("span", "tip-name", g.opponent));
      logo.appendChild(img);
    } else {
      logo.appendChild(makeCell("span", "tip-name", g.opponent));
    }
    fill.appendChild(logo);

    banner.appendChild(fill);
    banner.appendChild(makeCell("span", "tip-slash"));
    row.appendChild(banner);

    row.appendChild(
      makeCell("span", "tip-result " + (g.result === "W" ? "win" : "loss"), g.result)
    );

    const value = tipValue(g, col.tip);
    if (value !== null) {
      row.appendChild(makeCell("span", "tip-value", value));
    }

    list.appendChild(row);
  }
  tooltip.appendChild(list);

  const note = tipNote(col.tip);
  if (note) tooltip.appendChild(makeCell("div", "tip-footer", note));
}

function positionTooltip(cell) {
  const gap = 8;
  const rect = cell.getBoundingClientRect();
  const tipW = tooltip.offsetWidth;
  const tipH = tooltip.offsetHeight;

  // to the right of the cell if it fits, otherwise to the left
  let left = rect.right + gap;
  if (left + tipW > window.innerWidth - gap) left = rect.left - tipW - gap;
  left = Math.max(gap, left);

  // vertically centred on the cell, kept on screen
  let top = rect.top + rect.height / 2 - tipH / 2;
  top = Math.min(Math.max(gap, top), window.innerHeight - tipH - gap);

  tooltip.style.left = left + "px";
  tooltip.style.top = top + "px";
}

function showTooltip(cell, team, col) {
  buildTooltip(team, col);
  tooltip.classList.add("visible");
  positionTooltip(cell);
  tooltipCell = cell;
}

function hideTooltip() {
  tooltip.classList.remove("visible");
  tooltipCell = null;
}

function attachTooltip(cell, team, col) {
  cell.classList.add("has-tip");

  if (CAN_HOVER) {
    cell.addEventListener("mouseenter", () => showTooltip(cell, team, col));
    cell.addEventListener("mouseleave", hideTooltip);
  } else {
    cell.addEventListener("click", (event) => {
      event.stopPropagation();
      if (tooltipCell === cell) hideTooltip();
      else showTooltip(cell, team, col);
    });
  }
}

// close on tap elsewhere, and when the page or table scrolls
document.addEventListener("click", hideTooltip);
window.addEventListener("scroll", hideTooltip, { passive: true });
document.addEventListener("scroll", hideTooltip, { capture: true, passive: true });

/* ---------- Sorting ---------- */

function onSortClick(col) {
  if (currentSort.field === col.field) {
    // same column clicked again: flip the direction
    currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
  } else {
    currentSort = { field: col.field, dir: col.sort };
  }
  applySort();
}

function applySort() {
  const { field, dir } = currentSort;

  const sorted = [...teams].sort((a, b) => {
    const av = a[field];
    const bv = b[field];

    // teams without a value always go to the bottom
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;

    if (av !== bv) return dir === "asc" ? av - bv : bv - av;
    return a.rank - b.rank; // ties: keep Power Digits order
  });

  const tbody = document.querySelector("table.rankings tbody");
  for (const team of sorted) {
    tbody.appendChild(rowsByRank.get(team.rank)); // moves the existing row
  }

  // show which column is sorted, and which way
  for (const button of document.querySelectorAll(".sort-btn")) {
    const active = button.dataset.field === field;
    button.classList.toggle("sorted", active);
    button.classList.toggle("asc", active && dir === "asc");
    button.classList.toggle("desc", active && dir === "desc");
  }
}

/* ---------- Load ---------- */

async function loadRankings() {
  const wrap = document.getElementById("rankings-wrap");
  const status = document.getElementById("status");
  const toggle = document.getElementById("stats-toggle");

  toggle.addEventListener("click", () => {
    const showAll = wrap.classList.toggle("show-all");
    toggle.textContent = showAll ? "Show fewer stats" : "Show all stats";
  });

  try {
    // no-cache: always check for the newest rankings
    const response = await fetch(DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error("HTTP " + response.status);

    teams = await response.json();
    teams.sort((a, b) => a.rank - b.rank);

    const cutoffsByField = {};
    for (const col of STAT_COLUMNS) {
      if (col.highlight) cutoffsByField[col.field] = highlightCutoffs(col);
    }

    const table = document.createElement("table");
    table.className = "rankings";

    const thead = document.createElement("thead");
    thead.appendChild(buildHeaderRow());
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const team of teams) {
      const row = buildTeamRow(team, cutoffsByField);
      rowsByRank.set(team.rank, row);
      tbody.appendChild(row);
    }
    table.appendChild(tbody);

    wrap.appendChild(table);
    status.remove();
    applySort();
  } catch (error) {
    status.textContent = "Rankings could not be loaded. Please try again later.";
    console.error(error);
  }
}

loadRankings();