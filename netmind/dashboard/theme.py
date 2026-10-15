"""Page styling for the dashboard: IBM Plex type, teal for the brand and navigation, red only for
incidents. Works with both the light and the dark theme in .streamlit/config.toml. Selectors use Streamlit's data-testid
attributes; if a future Streamlit renames them, the page falls back to the default look."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
/* Colours are mixed from the theme's own text colour (currentColor), so every element works on
   both the light and the dark theme without the page having to know which one is active. */
:root {
  --nm-muted: color-mix(in srgb, currentColor 66%, transparent);
  --nm-card: color-mix(in srgb, currentColor 4%, transparent);
  --nm-line: color-mix(in srgb, currentColor 13%, transparent);
  --nm-teal: #17a2ac; --nm-red: #e04848; --nm-green: #2fa35c; --nm-amber: #d4951a;
  --nm-sans: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --nm-mono: 'IBM Plex Mono', Consolas, 'Courier New', monospace;
}
html, body, .stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, label, button, input, textarea {
  font-family: var(--nm-sans); }
/* Streamlit's top bar (with Deploy and the menu) is about 3.75rem tall and floats over the page,
   so the content has to start below it or the first heading is cut off. */
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 4.2rem; max-width: 1400px; }
h1, h2, h3 { font-family: var(--nm-sans); letter-spacing: -0.01em; }
h2 { font-size: 1.35rem; font-weight: 600; margin-top: 0.6rem; }
h3 { font-size: 1.08rem; font-weight: 600; }
code, .nm-mono { font-family: var(--nm-mono); }

/* charts sit on cards */
[data-testid="stPlotlyChart"] { background: var(--nm-card); border: 1px solid var(--nm-line);
  border-radius: 10px; padding: 6px 6px 2px; }

/* sidebar */
[data-testid="stSidebar"] { border-right: 1px solid var(--nm-line); }
.nm-brand { display: flex; align-items: center; gap: 0.6rem; margin: 0.2rem 0 0.2rem; }
.nm-brand-mark { width: 34px; height: 34px; }
.nm-brand-name { font-size: 1.45rem; font-weight: 700; letter-spacing: -0.02em; }
.nm-brand-sub { color: var(--nm-muted); font-size: 0.83rem; line-height: 1.35; margin-bottom: 0.9rem; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding: 0.28rem 0.5rem; border-radius: 6px;
  border-left: 3px solid transparent; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  background: color-mix(in srgb, var(--nm-teal) 10%, transparent); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: color-mix(in srgb, var(--nm-teal) 18%, transparent); border-left-color: var(--nm-teal); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { font-weight: 600; }
.nm-theme-hint { color: var(--nm-muted); font-size: 0.8rem; margin-top: 0.6rem; }

/* page header */
.nm-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;
  flex-wrap: wrap; margin-bottom: 0.2rem; }
.nm-title { font-size: 1.9rem; font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; margin: 0; }
.nm-meta { color: var(--nm-muted); font-size: 0.92rem; margin-top: 0.3rem; }
.nm-tag { display: inline-block; padding: 0.08rem 0.5rem; border-radius: 999px; font-size: 0.78rem;
  font-weight: 600; background: color-mix(in srgb, var(--nm-teal) 20%, transparent);
  margin-left: 0.5rem; vertical-align: middle; }
.nm-tag.synthetic { background: color-mix(in srgb, var(--nm-amber) 28%, transparent); }
.nm-verdict { font-size: 1.05rem; font-weight: 600; padding: 0.45rem 0.9rem; border-radius: 8px;
  border: 1px solid; }
.nm-verdict.bad { background: color-mix(in srgb, var(--nm-red) 13%, transparent); color: var(--nm-red);
  border-color: color-mix(in srgb, var(--nm-red) 35%, transparent); }
.nm-verdict.ok { background: color-mix(in srgb, var(--nm-green) 13%, transparent); color: var(--nm-green);
  border-color: color-mix(in srgb, var(--nm-green) 35%, transparent); }
.nm-verdict.info { background: color-mix(in srgb, var(--nm-amber) 15%, transparent);
  border-color: color-mix(in srgb, var(--nm-amber) 45%, transparent); }
.nm-trace-cap { color: var(--nm-muted); font-size: 0.85rem; margin: 0.1rem 0 0.8rem; }

/* KPI strip */
.nm-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 0.7rem;
  margin: 0.3rem 0 1.1rem; }
.nm-kpi { background: var(--nm-card); border: 1px solid var(--nm-line); border-radius: 10px;
  padding: 0.75rem 0.9rem 0.6rem; }
.nm-kpi-label { color: var(--nm-muted); font-size: 0.85rem; }
.nm-kpi-value { font-size: 1.55rem; font-weight: 600; margin-top: 0.1rem; font-variant-numeric: tabular-nums; }
.nm-kpi-note { font-size: 0.8rem; min-height: 1.1rem; }
.nm-kpi-note.nm-bad { color: var(--nm-red); font-weight: 600; }
.nm-kpi-note.nm-muted { color: var(--nm-muted); }
.nm-spark { display: block; margin-top: 0.25rem; width: 100%; height: 30px; }

/* incidents */
.nm-inc-head { display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; }
.nm-inc-title { font-size: 1.1rem; font-weight: 600; }
.nm-sev { font-size: 0.78rem; font-weight: 600; padding: 0.08rem 0.5rem; border-radius: 999px; color: #fff; }
.nm-inc-meta { color: var(--nm-muted); font-size: 0.9rem; margin: 0.15rem 0 0.4rem; }
.nm-inc-meta b { font-family: var(--nm-mono); font-weight: 500; }

/* copilot panel */
.nm-panel-title { font-size: 1.1rem; font-weight: 600; margin: 0 0 0.1rem; }
.nm-panel-sub { color: var(--nm-muted); font-size: 0.85rem; margin-bottom: 0.5rem; }
.nm-empty { color: var(--nm-muted); background: var(--nm-card); border: 1px dashed var(--nm-line);
  border-radius: 10px; padding: 1rem 1.1rem; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""

THEME_HINT = ('<div class="nm-theme-hint">Light or dark mode: open the ⋮ menu at the top right, '
              'then <b>Settings</b>.</div>')

BRAND = """
<div class="nm-brand">
  <svg class="nm-brand-mark" viewBox="0 0 34 34" aria-hidden="true">
    <circle cx="7" cy="9" r="4" fill="#2a78d6"/><circle cx="27" cy="9" r="4" fill="#2a78d6"/>
    <circle cx="17" cy="27" r="4" fill="#17a2ac"/>
    <path d="M7 9 L27 9 M7 9 L17 27 M27 9 L17 27" stroke="#17a2ac" stroke-width="2" fill="none"/>
  </svg>
  <div class="nm-brand-name">NetMind</div>
</div>
<div class="nm-brand-sub">Network measurements, anomaly detection and an AI Copilot that explains them.</div>
"""
