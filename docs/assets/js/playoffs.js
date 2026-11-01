/* =========================================================
   Power Digits - playoff brackets ("if the playoff started today")
   Loads playoffs.json (built by build_playoffs.py) and draws the
   selected format. Each format has its own small layout function.
   ========================================================= */

const DATA_URL = document.body.dataset.root + "data/playoffs.json";

const FORMAT_ORDER = ["4", "8", "12", "24", "24c", "32", "20conf", "24conf"]; // tab order
const DEFAULT_FORMAT = "12";

// Bracket geometry in "design pixels"; the whole bracket is then scaled to fit.
// "full" shows school names; "compact" (seed, logo, colors) is used when
// the full version would have to shrink below MIN_FULL_SCALE.
const SIZES = {
  full: { slotW: 252, colGap: 40, stub: 24, levelGap: 30, reach: 50 },
  compact: { slotW: 128, colGap: 28, stub: 18, levelGap: 20, reach: 34 },
};
const MIN_FULL_SCALE = 0.6;
const SLOT_H = 54;                           // height of one team slot
const LEAN = Math.tan((20 * Math.PI) / 180); // 20 degree slant, same as the rankings
const OVERHANG = SLOT_H * LEAN;              // how far a slant reaches sideways

// The empty "winner" boxes use Power Digits colors
const PD_PRIMARY = "#2f2f2f";
const PD_SECONDARY = "#bdad7c";

let playoffData = null;
let currentFormat = DEFAULT_FORMAT;

/* ---------- Small helpers ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgEl(tag, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

/* =========================================================
   LAYOUT BUILDER
   Every bracket is made of the same pieces:
     game(...)    two teams that meet in a point (first round, or 4/8-team games)
     byeGame(...) a first-round game whose winner plays a bye team
     merge(...)   bracket lines joining pairs of games, then running to the centre
   A layout lists its games for the left half (top to bottom) and the right
   half; the right half is drawn as a mirror image.
   ========================================================= */

// teamOf(key) returns the team for a key (a seed number, or [region, seed])
function makeBracket(teamOf, size, { gameCols, mergeLevels }) {
  const team = (key) => teamOf(key) || null;
  const W = size.slotW;

  // Column x positions on the left half
  const c0 = OVERHANG / 2 + 2;
  const c1 = c0 + W + size.colGap;
  const lastCol = gameCols === 2 ? c1 : c0;
  const pointX = lastCol + W + OVERHANG / 2;       // where the last games come to a point

  const mergeWidth = mergeLevels > 0 ? size.stub + (mergeLevels - 1) * size.levelGap : 0;
  const centerX = pointX + mergeWidth + size.reach;
  const width = centerX * 2;

  const slots = [];
  const lines = [];
  const flip = (x) => width - x;
  const slotX = (x, side) => (side === "left" ? x : width - x - W);
  const fx = (side) => (side === "left" ? (x) => x : flip);

  // Two teams that meet in a point: top team leans one way, bottom the other.
  // Returns the y of the point.
  function game(side, x, yTop, topTeam, bottomTeam) {
    slots.push({ x: slotX(x, side), y: yTop, team: topTeam, side, lean: "down" });
    slots.push({ x: slotX(x, side), y: yTop + SLOT_H, team: bottomTeam, side, lean: "up" });
    return yTop + SLOT_H;
  }

  // First-round game (better seed on the bottom) whose winner plays a bye team.
  // Returns the y where the second-round game comes to a point.
  function byeGame(side, yTop, topSeed, bottomSeed, byeSeed) {
    const r1Point = game(side, c0, yTop, team(topSeed), team(bottomSeed));
    // second round: empty winner box on top, bye team (home) on the bottom
    const r2Point = game(side, c1, r1Point - SLOT_H / 2, null, team(byeSeed));

    const f = fx(side);
    lines.push([[f(c0 + W + OVERHANG / 2), r1Point], [f(c1), r1Point]]);
    return r2Point;
  }

  // Join pairs of games level by level, then run a line to the centre.
  function merge(side, ys) {
    const f = fx(side);
    let x = pointX;
    let level = ys;
    let gap = size.stub;

    while (level.length > 1) {
      const nextX = x + gap;
      const next = [];
      for (let i = 0; i < level.length; i += 2) {
        const [a, b] = [level[i], level[i + 1]];
        lines.push([[f(x), a], [f(nextX), a], [f(nextX), b], [f(x), b]]);
        next.push((a + b) / 2);
      }
      x = nextX;
      level = next;
      gap = size.levelGap;
    }
    lines.push([[f(x), level[0]], [centerX, level[0]]]);
  }

  return { team, game, byeGame, merge, c0, c1, slots, lines, width, slotW: W };
}

function finish(b, height) {
  return { width: b.width, height, slotW: b.slotW, slots: b.slots, lines: b.lines };
}

// Look-ups for the two kinds of data in playoffs.json
const bySeed = (entry) => (seed) => entry.seeds.find((t) => t.seed === seed);
const byRegion = (entry) => ([region, seed]) =>
  (entry.regions[region] || []).find((t) => t.seed === seed);

// 24 teams, seeds 1-8 get byes (used by "24" and "24c")
function layout24(entry, size) {
  const b = makeBracket(bySeed(entry), size, { gameCols: 2, mergeLevels: 2 });
  const y0 = 4;
  const gap = SLOT_H * 3.25;
  const halves = {
    left: [[17, 16, 1], [24, 9, 8], [20, 13, 4], [21, 12, 5]],
    right: [[18, 15, 2], [23, 10, 7], [19, 14, 3], [22, 11, 6]],
  };
  for (const [side, games] of Object.entries(halves)) {
    const points = games.map(([top, bottom, bye], i) =>
      b.byeGame(side, y0 + i * gap, top, bottom, bye)
    );
    b.merge(side, points);
  }
  return finish(b, y0 + gap * 3 + SLOT_H * 2.5 + 4);
}

// Conference regions ("20conf" and "24conf").
// A 4-team region plays 1v4 and 2v3; a 6-team region has a play-in round
// (4v5 for #1, 3v6 for #2). Left: Big Ten over ACC. Right: SEC over Big 12.
function layoutRegions(entry, size) {
  const b = makeBracket(byRegion(entry), size, { gameCols: 2, mergeLevels: 2 });
  const y0 = 4;
  const podGap = SLOT_H * 3.25;      // between the two games of a region
  const regionGap = SLOT_H * 1.25;   // extra space between regions

  // draws one region starting at yTop; returns [points, height]
  function region(side, name, yTop) {
    const count = (entry.regions[name] || []).length;
    if (count >= 6) {
      return [[
        b.byeGame(side, yTop, [name, 5], [name, 4], [name, 1]),
        b.byeGame(side, yTop + podGap, [name, 6], [name, 3], [name, 2]),
      ], podGap + SLOT_H * 2.5];
    }
    // 4 teams: both games in the same column as the 6-team regions' second round
    const top = yTop + SLOT_H / 2;
    return [[
      b.game(side, b.c1, top, b.team([name, 4]), b.team([name, 1])),
      b.game(side, b.c1, top + podGap, b.team([name, 3]), b.team([name, 2])),
    ], podGap + SLOT_H * 2.5];
  }

  let height = 0;
  for (const [side, upper, lower] of [["left", "Big Ten", "ACC"], ["right", "SEC", "Big 12"]]) {
    const [upperPoints, upperH] = region(side, upper, y0);
    const [lowerPoints] = region(side, lower, y0 + upperH + regionGap);
    b.merge(side, [...upperPoints, ...lowerPoints]);
    height = y0 + (upperH + regionGap) * 2;
  }
  return finish(b, height - regionGap + 4);
}

const LAYOUTS = {
  // 4 teams: 1 v 4 on the left, 2 v 3 on the right
  "4": (entry, size) => {
    const b = makeBracket(bySeed(entry), size, { gameCols: 1, mergeLevels: 0 });
    const y0 = 4;
    b.merge("left", [b.game("left", b.c0, y0, b.team(4), b.team(1))]);
    b.merge("right", [b.game("right", b.c0, y0, b.team(3), b.team(2))]);
    return finish(b, y0 + SLOT_H * 2 + 4);
  },

  // 8 teams: 1 v 8 and 4 v 5 on the left; 2 v 7 and 3 v 6 on the right
  "8": (entry, size) => {
    const b = makeBracket(bySeed(entry), size, { gameCols: 1, mergeLevels: 1 });
    const y0 = 4;
    const gap = SLOT_H * 3;
    for (const [side, games] of [["left", [[8, 1], [5, 4]]], ["right", [[7, 2], [6, 3]]]]) {
      const points = games.map(([top, bottom], i) =>
        b.game(side, b.c0, y0 + i * gap, b.team(top), b.team(bottom))
      );
      b.merge(side, points);
    }
    return finish(b, y0 + gap + SLOT_H * 2 + 4);
  },

  // 12 teams: seeds 1-4 get byes
  "12": (entry, size) => {
    const b = makeBracket(bySeed(entry), size, { gameCols: 2, mergeLevels: 1 });
    const y0 = 4;
    const gap = SLOT_H * 4.25;
    const halves = {
      left: [[9, 8, 1], [12, 5, 4]],
      right: [[10, 7, 2], [11, 6, 3]],
    };
    for (const [side, games] of Object.entries(halves)) {
      const points = games.map(([top, bottom, bye], i) =>
        b.byeGame(side, y0 + i * gap, top, bottom, bye)
      );
      b.merge(side, points);
    }
    return finish(b, y0 + gap + SLOT_H * 2.5 + 4);
  },

  "24": layout24,
  "24c": layout24,

  // 32 teams, no byes. Each pair of games feeds the same second-round game.
  "32": (entry, size) => {
    const b = makeBracket(bySeed(entry), size, { gameCols: 1, mergeLevels: 4 });
    const y0 = 4;
    const gap = SLOT_H * 2.5;          // one game (2 slots) + half a slot of space
    const halves = {
      left: [[17, 16], [32, 1], [24, 9], [25, 8], [20, 13], [29, 4], [21, 12], [28, 5]],
      right: [[18, 15], [31, 2], [23, 10], [26, 7], [19, 14], [30, 3], [22, 11], [27, 6]],
    };
    for (const [side, games] of Object.entries(halves)) {
      const points = games.map(([top, bottom], i) =>
        b.game(side, b.c0, y0 + i * gap, b.team(top), b.team(bottom))
      );
      b.merge(side, points);
    }
    return finish(b, y0 + gap * 7 + SLOT_H * 2 + 4);
  },

  "20conf": layoutRegions,
  "24conf": layoutRegions,
};

/* =========================================================
   DRAWING
   ========================================================= */

function buildSlot(slot, slotW, label) {
  const node = el("div", `slot slot-${slot.side} lean-${slot.lean}`);

  node.style.left = slot.x + "px";
  node.style.top = slot.y + "px";
  node.style.width = slotW + "px";
  node.style.height = SLOT_H + "px";

  const t = slot.team;
  node.style.setProperty("--primary", t ? t.primary_color || "#555555" : PD_PRIMARY);
  node.style.setProperty("--secondary", t ? t.secondary_color || "#ffffff" : PD_SECONDARY);

  const plate = el("div", "slot-plate");
  const inner = el("div", "slot-inner");

  if (t) {
    inner.appendChild(el("span", "slot-seed", String(label === "rank" ? t.rank : t.seed)));

    const img = document.createElement("img");
    img.alt = "";
    img.onerror = () => (img.style.visibility = "hidden");
    const logo = t.logo_dark_url || t.logo_url;
    if (logo) img.src = logo;
    else img.style.visibility = "hidden";
    inner.appendChild(img);

    inner.appendChild(el("span", "slot-name", t.school_short || t.school_name));
  } else {
    node.classList.add("slot-empty");
  }

  plate.appendChild(inner);
  node.appendChild(plate);

  for (const stripe of ["stripe thick secondary", "stripe thin-primary primary", "stripe thin secondary"]) {
    node.appendChild(el("span", stripe));
  }
  return node;
}

// Space available for the bracket: the page width, and the screen height
// below the bracket's top edge (so the whole bracket stays in view).
function availableSpace() {
  const area = document.getElementById("bracket-area");
  const note = document.getElementById("bracket-note");
  const top = area.getBoundingClientRect().top + window.scrollY;
  const noteH = note.offsetHeight + 16; // description sits below the bracket
  return {
    width: area.clientWidth,
    // leave room for the description and the page's bottom padding
    height: Math.max(260, window.innerHeight - top - noteH - 48),
  };
}

function scaleFor(layout, space) {
  return Math.min(1, space.width / layout.width, space.height / layout.height);
}

function drawBracket(format) {
  currentFormat = format;
  const entry = playoffData.formats[format];
  document.getElementById("bracket-title").textContent = entry.name;
  document.getElementById("bracket-note").textContent = entry.description || "";

  const area = document.getElementById("bracket-area");
  area.replaceChildren();

  const layoutFn = LAYOUTS[format];
  if (!layoutFn || !(entry.seeds || entry.regions)) {
    area.appendChild(el("p", "status", `The ${entry.name} bracket is coming soon.`));
    return;
  }

  // Use the full design unless it would have to shrink too far
  const space = availableSpace();
  let sizeName = "full";
  let layout = layoutFn(entry, SIZES.full);
  if (scaleFor(layout, space) < MIN_FULL_SCALE) {
    sizeName = "compact";
    layout = layoutFn(entry, SIZES.compact);
  }
  const scale = scaleFor(layout, space);

  // stage = the scaled box that takes up space on the page
  const stage = el("div", "bracket-stage");
  stage.style.width = layout.width * scale + "px";
  stage.style.height = layout.height * scale + "px";

  const bracket = el("div", `bracket bracket-${sizeName}`);
  bracket.style.width = layout.width + "px";
  bracket.style.height = layout.height + "px";
  bracket.style.transform = `scale(${scale})`;

  // connector lines
  const svg = svgEl("svg", {
    class: "bracket-lines",
    width: layout.width,
    height: layout.height,
    viewBox: `0 0 ${layout.width} ${layout.height}`,
  });
  for (const points of layout.lines) {
    svg.appendChild(svgEl("polyline", { points: points.map((p) => p.join(",")).join(" ") }));
  }
  bracket.appendChild(svg);

  for (const slot of layout.slots) {
    bracket.appendChild(buildSlot(slot, layout.slotW, entry.label));
  }

  stage.appendChild(bracket);
  area.appendChild(stage);
}

// Redraw on resize (after the resizing stops) so the bracket always fits
let resizeTimer = null;
function onResize() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => drawBracket(currentFormat), 120);
}

/* ---------- Format tabs ---------- */

function buildTabs(active) {
  const tabs = document.getElementById("format-tabs");
  tabs.replaceChildren();

  for (const key of FORMAT_ORDER) {
    const entry = playoffData.formats[key];
    if (!entry) continue;

    const button = el("button", "format-tab", entry.tab || entry.name);
    button.type = "button";
    if (key === active) button.classList.add("active");
    button.addEventListener("click", () => {
      buildTabs(key);
      drawBracket(key);
    });
    tabs.appendChild(button);
  }
}

/* ---------- Load ---------- */

async function loadPlayoffs() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    playoffData = await response.json();

    buildTabs(DEFAULT_FORMAT);
    drawBracket(DEFAULT_FORMAT);
    window.addEventListener("resize", onResize);
  } catch (error) {
    document.getElementById("status").textContent =
      "Brackets could not be loaded. Please try again later.";
    console.error(error);
  }
}

loadPlayoffs();