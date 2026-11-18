// Theme consistency check, run in the browser on an AgriPrix page (step 2.3 of the
// dark-mode fixes). Returns, for each part of the page, the theme it is actually displayed
// in ("dark" or "light", from the computed colours), whether the theme button is visible,
// and the measured contrast of the button text. Used by hand in the browser pane; the
// expected theme is: ?theme= if present, else the system setting (fresh profile).
(() => {
  const rgb = (css) => (css.match(/[\d.]+/g) || []).slice(0, 4).map(Number);
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  // First non-transparent background up the tree.
  const bg = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length && (c.length < 4 || c[3] > 0.5)) return c.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const kind = (c) => (lum(c) < 0.2 ? "dark" : "light");
  const out = {};
  const app = document.querySelector(".stApp");
  out.page = kind(bg(app));
  const header = document.querySelector('header[data-testid="stHeader"]');
  out.header = header ? kind(bg(header)) : "missing";
  const filters = document.querySelector(".st-key-filters");
  out.filters = filters ? kind(bg(filters)) : "missing";
  const gd = [...document.querySelectorAll(".js-plotly-plot")].find((g) => g._fullLayout && g._fullLayout.map);
  out.map = gd ? (gd._fullLayout.map.style === "carto-darkmatter" ? "dark" : "light") : "missing";
  const chart = [...document.querySelectorAll(".js-plotly-plot")].find((g) => g._fullLayout && !g._fullLayout.map);
  out.chart = chart ? kind(rgb(chart._fullLayout.paper_bgcolor)) : "none";
  // Logo: colour of the "AgriPrix" letters (right part of the image): cream = dark theme.
  const logo = document.querySelector('[data-testid="stHeaderLogo"]');
  if (logo && logo.complete && logo.naturalWidth) {
    const canvas = document.createElement("canvas");
    canvas.width = logo.naturalWidth; canvas.height = logo.naturalHeight;
    const ctx = canvas.getContext("2d"); ctx.drawImage(logo, 0, 0);
    const x0 = Math.round(canvas.width * 0.45);
    const data = ctx.getImageData(x0, 0, canvas.width - x0, canvas.height).data;
    let sum = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) if (data[i + 3] > 200) { sum += lum([data[i], data[i + 1], data[i + 2]]); n++; }
    out.logo = n ? (sum / n > 0.5 ? "dark" : "light") : "unknown";
  } else out.logo = "missing";
  const button = document.querySelector('.st-key-theme_toggle button');
  if (button) {
    const r = button.getBoundingClientRect();
    const visible = r.width > 0 && r.height >= 44 && r.top >= 0 && r.top < window.innerHeight;
    const ratio = contrast(rgb(getComputedStyle(button).color).slice(0, 3), bg(button));
    out.button = { visible, height: Math.round(r.height), contrast: Math.round(ratio * 100) / 100, label: button.innerText.trim() };
  } else out.button = { visible: false };
  const parts = ["page", "header", "filters", "map", "logo"].map((k) => out[k]);
  if (out.chart !== "none") parts.push(out.chart);
  out.consistent = parts.every((p) => p === parts[0]);
  out.theme = parts[0];
  out.url = location.search;
  return out;
})();
