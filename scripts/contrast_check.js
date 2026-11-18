// Measured contrast of every visible text of the page, from the browser's computed styles
// (text colour against the first opaque background behind it). Returns the lowest ratios
// and every text under 4.5:1. Run in the browser on each page and theme.
(() => {
  const rgb = (css) => (css.match(/[\d.]+/g) || []).slice(0, 4).map(Number);
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const background = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length === 3 || (c.length === 4 && c[3] > 0.95)) return c.slice(0, 3);
    }
    return rgb(getComputedStyle(document.querySelector(".stApp")).backgroundColor).slice(0, 3);
  };
  const seen = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = node.textContent.trim();
    const el = node.parentElement;
    if (!text || !el || el.closest("script, style, svg, .js-plotly-plot, [data-testid=stDataFrame]")) continue;
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (!r.width || style.visibility === "hidden" || style.display === "none" || +style.opacity === 0) continue;
    const fg = rgb(style.color);
    if (fg.length === 4 && fg[3] < 0.5) continue;  // icon ligatures, invisible helpers
    seen.push({ text: text.slice(0, 40), ratio: Math.round(ratio(fg.slice(0, 3), background(el)) * 100) / 100,
                color: style.color });
  }
  seen.sort((a, b) => a.ratio - b.ratio);
  return { texts: seen.length, lowest: seen.slice(0, 6), under45: seen.filter((s) => s.ratio < 4.5) };
})();
