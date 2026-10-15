"""Page styling for the dashboard: IBM Plex type, a quiet light surface, a deep teal for the
brand and navigation, red only for incidents. Selectors use Streamlit's data-testid
attributes; if a future Streamlit renames them, the page falls back to the default look."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  --nm-ink: #14212b; --nm-ink2: #4a5863; --nm-muted: #6f7d87; --nm-line: #dfe5e9;
  --nm-surface: #ffffff; --nm-page: #f4f6f7; --nm-teal: #0b6e78; --nm-teal-soft: #e3f1f2;
  --nm-red: #c23434; --nm-red-soft: #fbecec; --nm-green: #1d7a3e; --nm-green-soft: #e7f4ec;
  --nm-amber: #8a5a00; --nm-amber-soft: #fbf1dc;
  --nm-sans: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --nm-mono: 'IBM Plex Mono', Consolas, 'Courier New', monospace;
}
html, body, .stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, label, button, input, textarea,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { font-family: var(--nm-sans); }
.stApp { background: var(--nm-page); color: var(--nm-ink); }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.6rem; max-width: 1400px; }
h1, h2, h3 { font-family: var(--nm-sans); color: var(--nm-ink); letter-spacing: -0.01em; }
h2 { font-size: 1.35rem; font-weight: 600; margin-top: 0.6rem; }
h3 { font-size: 1.08rem; font-weight: 600; }
code, .nm-mono { font-family: var(--nm-mono); }

/* sidebar */
[data-testid="stSidebar"] { background: #eaf0f2; border-right: 1px solid var(--nm-line); }
.nm-brand { display: flex; align-items: center; gap: 0.6rem; margin: 0.2rem 0 0.2rem; }
.nm-brand-mark { width: 34px; height: 34px; }
.nm-brand-name { font-size: 1.45rem; font-weight: 700; color: var(--nm-ink); letter-spacing: -0.02em; }
.nm-brand-sub { color: var(--nm-ink2); font-size: 0.83rem; line-height: 1.35; margin-bottom: 0.9rem; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding: 0.28rem 0.5rem; border-radius: 6px; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #dde7ea; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: var(--nm-teal-soft); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: var(--nm-teal); font-weight: 600; }

/* page header */
.nm-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;
  flex-wrap: wrap; margin-bottom: 0.2rem; }
.nm-title { font-size: 1.9rem; font-weight: 700; color: var(--nm-ink); line-height: 1.15;
  letter-spacing: -0.02em; margin: 0; }
.nm-meta { color: var(--nm-ink2); font-size: 0.92rem; margin-top: 0.3rem; }
.nm-tag { display: inline-block; padding: 0.08rem 0.5rem; border-radius: 999px; font-size: 0.78rem;
  font-weight: 600; background: var(--nm-teal-soft); color: var(--nm-teal); margin-left: 0.4rem;
  vertical-align: middle; }
.nm-tag.synthetic { background: var(--nm-amber-soft); color: var(--nm-amber); }
.nm-verdict { font-size: 1.05rem; font-weight: 600; padding: 0.45rem 0.9rem; border-radius: 8px; }
.nm-verdict.bad { background: var(--nm-red-soft); color: var(--nm-red); }
.nm-verdict.ok { background: var(--nm-green-soft); color: var(--nm-green); }
.nm-verdict.info { background: var(--nm-amber-soft); color: var(--nm-amber); }
.nm-trace-cap { color: var(--nm-muted); font-size: 0.85rem; margin: -0.4rem 0 0.8rem; }

/* KPI strip */
.nm-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 0.7rem;
  margin: 0.3rem 0 1.1rem; }
.nm-kpi { background: var(--nm-surface); border: 1px solid var(--nm-line); border-radius: 10px;
  padding: 0.75rem 0.9rem 0.6rem; }
.nm-kpi-label { color: var(--nm-ink2); font-size: 0.85rem; }
.nm-kpi-value { font-size: 1.55rem; font-weight: 600; color: var(--nm-ink); margin-top: 0.1rem;
  font-variant-numeric: tabular-nums; }
.nm-kpi-note { font-size: 0.8rem; min-height: 1.1rem; }
.nm-kpi-note.nm-bad { color: var(--nm-red); font-weight: 600; }
.nm-kpi-note.nm-muted { color: var(--nm-muted); }
.nm-spark { display: block; margin-top: 0.25rem; width: 100%; height: 30px; }

/* incidents */
.nm-inc-head { display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; }
.nm-inc-title { font-size: 1.1rem; font-weight: 600; color: var(--nm-ink); }
.nm-sev { font-size: 0.78rem; font-weight: 600; padding: 0.08rem 0.5rem; border-radius: 999px;
  color: #fff; }
.nm-inc-meta { color: var(--nm-ink2); font-size: 0.9rem; margin: 0.15rem 0 0.4rem; }
.nm-inc-meta b { font-family: var(--nm-mono); font-weight: 500; color: var(--nm-ink); }

/* copilot panel */
.nm-panel-title { font-size: 1.1rem; font-weight: 600; margin: 0 0 0.1rem; color: var(--nm-ink); }
.nm-panel-sub { color: var(--nm-muted); font-size: 0.85rem; margin-bottom: 0.5rem; }
.nm-empty { color: var(--nm-ink2); background: var(--nm-surface); border: 1px dashed var(--nm-line);
  border-radius: 10px; padding: 1rem 1.1rem; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""

BRAND = """
<div class="nm-brand">
  <svg class="nm-brand-mark" viewBox="0 0 34 34" aria-hidden="true">
    <circle cx="7" cy="9" r="4" fill="#2a78d6"/><circle cx="27" cy="9" r="4" fill="#2a78d6"/>
    <circle cx="17" cy="27" r="4" fill="#0b6e78"/>
    <path d="M7 9 L27 9 M7 9 L17 27 M27 9 L17 27" stroke="#0b6e78" stroke-width="2" fill="none"/>
  </svg>
  <div class="nm-brand-name">NetMind</div>
</div>
<div class="nm-brand-sub">Network measurements, anomaly detection and an AI Copilot that explains them.</div>
"""
