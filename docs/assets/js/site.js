/* =========================================================
   Power Digits - global header, shared by every page.
   To add or rename a menu link, edit NAV_LINKS below.
   ========================================================= */

const NAV_LINKS = [
  // path is relative to the docs/ folder
  { label: "Current Rankings", path: "currentrankings/" },
  // { label: "Math & FAQ", path: "math-faq/" },   <- turn on once that page exists
  { label: "X", url: "https://x.com/PowerDigits" },
  { label: "Instagram", url: "https://www.instagram.com/powerdigits" },
];

// Each page tells us how to get back to the docs/ folder, e.g. "../"
const ROOT = document.body.dataset.root || "";

function buildHeader() {
  const header = document.createElement("header");
  header.className = "site-header";

  const inner = document.createElement("div");
  inner.className = "site-header-inner";

  // Logo (falls back to text if the image file is missing)
  const logoLink = document.createElement("a");
  logoLink.className = "site-logo";
  logoLink.href = ROOT || "./";

  const logo = document.createElement("img");
  logo.src = ROOT + "assets/img/logo.png";
  logo.alt = "Power Digits";
  logo.onerror = () => {
    logoLink.textContent = "POWER DIGITS";
    logoLink.className = "site-logo-text";
  };
  logoLink.appendChild(logo);

  // Menu links
  const nav = document.createElement("nav");
  nav.className = "site-nav";

  for (const item of NAV_LINKS) {
    const a = document.createElement("a");
    a.textContent = item.label;

    if (item.url) {
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener";
    } else {
      a.href = ROOT + item.path;
      if (window.location.pathname.endsWith("/" + item.path)) {
        a.classList.add("active");
      }
    }

    nav.appendChild(a);
  }

  inner.appendChild(logoLink);
  inner.appendChild(nav);
  header.appendChild(inner);
  document.body.prepend(header);
}

buildHeader();