"""All CSS for the demo - a light, modern SaaS dashboard.

Design rules
------------
* the canvas (app + sidebar) is pure white,
* every surface is separated by a 1px silver hairline plus a very soft shadow,
* the deep purple is an accent only - a rule, a key label, a focus ring,
* peach marks the soft surfaces (agent cards, Thought bubbles),
* soft red marks failures (bad hops, rejected verdicts, missing facts).
"""

from .palette import (
    APP_BG,
    INK,
    PEACH,
    PURPLE,
    PURPLE_DEEP,
    SILVER,
    SILVER_LIGHT,
    SOFT_RED,
    rgba,
)

INK_SOFT = "#5C5468"

CSS = f"""
<style>
  :root {{
    --app-bg: {APP_BG};
    --purple: {PURPLE};
    --purple-deep: {PURPLE_DEEP};
    --silver: {SILVER};
    --peach: {PEACH};
    --soft-red: {SOFT_RED};
    --ink: {INK};
    --ink-soft: {INK_SOFT};
    --peach-light: {SILVER_LIGHT};

    --line: 1px solid var(--silver);
    --hairline: 1px solid {rgba(SILVER, 0.55)};
    --radius: 12px;
    --radius-sm: 8px;
    --shadow-sm: 0 1px 2px rgba(16, 8, 32, 0.04);
    --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    --shadow-lg: 0 10px 24px -8px rgba(74, 30, 102, 0.22);
  }}

  /* ================= canvas ================= */
  .stApp {{
    background-color: var(--app-bg);
    color: var(--ink);
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 15px;
  }}
  .stApp [data-testid="stAppViewContainer"],
  .stApp [data-testid="stMain"],
  .stApp [data-testid="stMainBlockContainer"],
  .stApp [data-testid="stHeader"],
  .stApp [data-testid="stToolbar"] {{
    background-color: var(--app-bg);
  }}
  .stApp [data-testid="stMainBlockContainer"] {{ padding-top: 1.2rem; }}
  .stApp [data-testid="stVerticalBlock"] {{ gap: 0.55rem; }}
  h1, h2, h3, h4, h5, h6 {{ color: var(--purple); }}

  /* ================= header ================= */
  .mh-hero {{
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 4px 0 14px 0;
    margin: 0 0 18px 0;
    border-bottom: 1px solid var(--silver);
    box-shadow: none;
  }}
  .mh-hero h1 {{
    color: var(--purple);
    margin: 6px 0 6px 0;
    font-size: 2.05rem;
    font-weight: 650;
    letter-spacing: -0.5px;
    line-height: 1.2;
  }}
  .mh-hero p {{
    color: var(--silver);
    margin: 0;
    font-size: 0.95rem;
    line-height: 1.55;
    max-width: 68ch;
  }}
  .mh-hero .mh-kicker {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--purple);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin: 0;
  }}
  .mh-hero .mh-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--purple);
    display: inline-block;
    flex: 0 0 auto;
  }}

  /* ================= question banner ================= */
  .mh-question {{
    background: var(--app-bg);
    border: var(--line);
    border-left: 3px solid var(--purple);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 18px;
    box-shadow: var(--shadow);
  }}
  .mh-question .mh-label {{
    font-size: 0.68rem;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    color: var(--ink-soft);
    font-weight: 700;
  }}
  .mh-question .mh-q {{
    font-size: 1.18rem;
    font-weight: 600;
    color: var(--ink);
    margin-top: 6px;
    line-height: 1.35;
  }}
  .mh-question .mh-teach {{ color: var(--ink-soft); font-size: 0.86rem; margin-top: 6px; }}

  /* ================= idle / stale placeholders ================= */
  .mh-idle {{
    background: {rgba(PEACH, 0.20)};
    border: var(--line);
    border-left: 3px solid var(--purple);
    border-radius: var(--radius);
    padding: 26px 28px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
  }}
  .mh-idle .mh-label {{
    font-size: 0.68rem;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    color: var(--purple);
    font-weight: 700;
  }}
  .mh-idle h4 {{ margin: 6px 0 8px 0; font-size: 1.05rem; font-weight: 650; color: var(--ink); }}
  .mh-idle p {{ margin: 0 0 18px 0; font-size: 0.92rem; line-height: 1.6; color: var(--ink-soft); }}
  .mh-idle p b {{ color: var(--purple); font-weight: 650; }}
  .mh-idle-steps {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .mh-idle-step {{
    flex: 1;
    min-width: 190px;
    background: var(--app-bg);
    border: var(--line);
    border-radius: var(--radius-sm);
    padding: 12px 15px;
    box-shadow: var(--shadow-sm);
  }}
  .mh-idle-step b {{ display: block; color: var(--purple); font-size: 0.88rem; font-weight: 650; }}
  .mh-idle-step span {{ display: block; color: var(--ink-soft); font-size: 0.82rem; margin-top: 3px; line-height: 1.5; }}

  /* ================= agent cards ================= */
  .mh-agents {{ display: flex; gap: 16px; margin-bottom: 22px; }}
  .mh-agent {{
    flex: 1;
    background: {rgba(PEACH, 0.26)};
    border: var(--line);
    border-top: 3px solid var(--silver);
    border-radius: var(--radius);
    padding: 1.5rem;
    min-height: 132px;
    box-shadow: var(--shadow);
    transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
  }}
  .mh-agent:hover {{
    box-shadow: var(--shadow-lg);
    transform: translateY(-1px);
  }}
  .mh-agents > .mh-agent:nth-child(1) {{ border-top-color: var(--purple); }}
  .mh-agents > .mh-agent:nth-child(3) {{ border-top-color: var(--purple); }}
  .mh-agent.mh-agent-bad {{
    border-top-color: var(--soft-red);
    background: {rgba(SOFT_RED, 0.10)};
  }}
  .mh-agent h4 {{
    margin: 0 0 3px 0;
    font-size: 1rem;
    font-weight: 650;
    color: var(--purple);
    letter-spacing: -0.1px;
  }}
  .mh-agent .mh-role {{
    font-size: 0.67rem;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--ink-soft);
    font-weight: 600;
  }}
  .mh-agent .mh-body {{
    font-size: 0.88rem;
    margin-top: 12px;
    line-height: 1.55;
    color: var(--ink);
  }}
  .mh-agent .mh-body b {{ font-weight: 650; color: var(--purple); }}
  .mh-agent .mh-body code {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 0.8rem;
    background: {rgba(SILVER, 0.30)};
    border-radius: 5px;
    padding: 1px 5px;
    color: var(--ink);
  }}

  /* ================= pills / tags ================= */
  .mh-pill {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    line-height: 1.5;
    background: {rgba(SILVER, 0.34)};
    border: 1px solid {rgba(SILVER, 0.75)};
    color: var(--ink);
    white-space: nowrap;
    vertical-align: middle;
  }}
  .mh-pill.mh-pill-bad {{
    background: {rgba(SOFT_RED, 0.32)};
    border-color: {rgba(SOFT_RED, 0.85)};
    color: var(--ink);
  }}
  .mh-pill.mh-pill-grey {{
    background: {rgba(SILVER, 0.34)};
    border-color: {rgba(SILVER, 0.75)};
    color: var(--ink-soft);
  }}
  .mh-pill.mh-pill-accent {{
    background: {rgba(PURPLE, 0.10)};
    border-color: {rgba(PURPLE, 0.32)};
    color: var(--purple);
  }}

  /* ================= tabs ================= */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 1px solid var(--silver);
    background: transparent;
  }}
  .stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: var(--silver) !important;
    font-weight: 500;
    font-size: 0.92rem;
    padding: 10px 16px !important;
    transition: color 0.15s ease, border-color 0.15s ease;
  }}
  .stTabs [data-baseweb="tab"]:hover {{
    color: var(--purple) !important;
    background: transparent !important;
  }}
  .stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: transparent !important;
    color: var(--purple) !important;
    font-weight: 700;
    border-bottom: 2px solid var(--purple) !important;
  }}
  .stTabs [data-baseweb="tab-panel"] {{ background: transparent; padding-top: 1rem; }}
  .stTabs [data-baseweb="tab-highlight"],
  .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}

  /* ================= planner ================= */
  .mh-plan {{
    background: var(--app-bg);
    border: var(--line);
    border-left: 3px solid var(--purple);
    border-radius: var(--radius);
    padding: 18px 22px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
  }}
  .mh-plan h4 {{ margin: 0 0 10px 0; font-size: 0.98rem; font-weight: 650; }}
  .mh-plan ol {{ margin: 0; padding-left: 20px; }}
  .mh-plan li {{ margin-bottom: 7px; font-size: 0.93rem; line-height: 1.5; }}
  .mh-plan li::marker {{ color: var(--purple); font-weight: 700; }}
  .mh-plan .mh-meta {{
    font-size: 0.8rem;
    color: var(--ink-soft);
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed {rgba(SILVER, 0.6)};
  }}
  .mh-plan .mh-meta b {{ color: var(--purple); font-weight: 650; }}

  /* ================= trace ================= */
  .mh-trace {{ margin-bottom: 8px; }}
  .mh-trace h3 {{ font-size: 1.05rem; font-weight: 650; margin-bottom: 10px; }}
  .mh-step {{
    background: var(--app-bg);
    border: var(--line);
    border-radius: var(--radius);
    padding: 1.1rem 1.25rem 1.25rem 1.25rem;
    margin-bottom: 14px;
    box-shadow: var(--shadow);
    transition: box-shadow 0.18s ease;
  }}
  .mh-step:hover {{ box-shadow: var(--shadow-lg); }}
  .mh-step.mh-step-bad {{
    border-color: {rgba(SOFT_RED, 0.75)};
    background: {rgba(SOFT_RED, 0.06)};
    box-shadow: none;
  }}
  .mh-step.mh-step-repair {{ border-left: 3px solid var(--purple); }}
  .mh-step-top {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }}
  .mh-badge {{
    background: {rgba(PURPLE, 0.10)};
    color: var(--purple);
    border: 1px solid {rgba(PURPLE, 0.28)};
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
  }}
  .mh-tool {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 0.78rem;
    color: var(--ink-soft);
  }}
  .mh-state {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    padding: 2px 9px;
    border-radius: 999px;
    border: 1px solid transparent;
    line-height: 1.5;
  }}
  .mh-state-ok {{
    color: var(--purple);
    background: {rgba(PURPLE, 0.10)};
    border-color: {rgba(PURPLE, 0.28)};
  }}
  .mh-state-bad {{
    color: var(--ink);
    background: {rgba(SOFT_RED, 0.32)};
    border-color: {rgba(SOFT_RED, 0.85)};
  }}
  .mh-state-grey {{
    color: var(--ink-soft);
    background: {rgba(SILVER, 0.32)};
    border-color: {rgba(SILVER, 0.72)};
  }}

  .mh-block {{
    border-radius: var(--radius-sm);
    padding: 10px 13px;
    margin-bottom: 8px;
    border: 1px solid transparent;
    border-left-width: 3px;
  }}
  .mh-tag {{
    display: inline-block;
    min-width: 92px;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    vertical-align: top;
  }}
  .mh-thought {{
    background: var(--peach);
    border-color: {rgba(SILVER, 0.55)};
    border-left-color: var(--purple);
  }}
  .mh-thought .mh-tag {{ color: var(--purple); }}
  .mh-action {{
    background: {rgba(SOFT_RED, 0.16)};
    border-color: {rgba(SOFT_RED, 0.50)};
    border-left-color: var(--soft-red);
  }}
  .mh-action .mh-tag {{ color: var(--ink); }}
  .mh-action code {{
    font-family: "Consolas", "Courier New", monospace;
    color: var(--ink);
    font-size: 0.85rem;
  }}
  .mh-observation {{
    background: {rgba(SILVER, 0.26)};
    border-color: var(--silver);
    border-left-color: var(--silver);
  }}
  .mh-observation .mh-tag {{ color: var(--ink-soft); }}
  .mh-obs-text {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 0.84rem;
    color: var(--ink);
  }}

  .mh-evi {{
    margin-top: 12px;
    border-top: 1px dashed {rgba(SILVER, 0.7)};
    padding-top: 10px;
  }}
  .mh-evi-row {{
    display: flex;
    gap: 10px;
    align-items: baseline;
    font-size: 0.78rem;
    padding: 5px 8px;
    border-bottom: 1px dotted {rgba(SILVER, 0.45)};
  }}
  .mh-evi-row:last-child {{ border-bottom: none; }}
  .mh-evi-id {{
    font-family: "Consolas", monospace;
    color: var(--ink-soft);
    min-width: 150px;
  }}
  .mh-evi-txt {{ color: var(--ink-soft); flex: 1; }}
  .mh-evi-txt b {{ color: var(--ink); font-weight: 650; }}
  .mh-evi-num {{
    font-family: "Consolas", monospace;
    color: var(--ink-soft);
    font-size: 0.72rem;
    white-space: nowrap;
  }}
  .mh-evi-row.mh-evi-decoy {{
    background: {rgba(SOFT_RED, 0.14)};
    border-left: 3px solid var(--soft-red);
    border-radius: var(--radius-sm);
    padding: 5px 8px;
  }}
  .mh-evi-row.mh-evi-noise {{ opacity: 0.55; }}
  .mh-evi-cite {{
    background: {rgba(PEACH, 0.55)};
    border-left: 3px solid var(--silver);
    padding: 8px 12px;
    font-size: 0.83rem;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    color: var(--ink-soft);
  }}

  /* ================= terminal strip ================= */
  .mh-terminal {{
    background: var(--app-bg);
    border: var(--line);
    border-left: 3px solid var(--purple);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin: 10px 0 18px 0;
    box-shadow: var(--shadow);
    text-align: center;
  }}
  .mh-terminal.mh-terminal-bad {{
    border-left-color: var(--soft-red);
    background: {rgba(SOFT_RED, 0.08)};
    border-color: {rgba(SOFT_RED, 0.65)};
  }}
  .mh-terminal .mh-terminal-label {{
    color: var(--ink-soft);
    font-size: 0.68rem;
    letter-spacing: 2.4px;
    text-transform: uppercase;
    font-weight: 700;
  }}
  .mh-terminal .mh-terminal-value {{
    color: var(--purple);
    font-size: 1.85rem;
    font-weight: 700;
    margin: 6px 0 4px 0;
    letter-spacing: -0.4px;
  }}
  .mh-terminal.mh-terminal-bad .mh-terminal-value {{ color: var(--ink); }}
  .mh-terminal .mh-terminal-note {{ color: var(--ink-soft); font-size: 0.82rem; }}

  /* ================= final answer ================= */
  .mh-final {{
    background: var(--app-bg);
    border: var(--line);
    border-left: 4px solid var(--purple);
    border-radius: var(--radius);
    padding: 22px 26px;
    margin: 18px 0 20px 0;
    text-align: center;
    box-shadow: var(--shadow);
  }}
  .mh-final .mh-final-label {{
    color: var(--ink-soft);
    font-size: 0.68rem;
    letter-spacing: 2.8px;
    text-transform: uppercase;
    font-weight: 700;
  }}
  .mh-final .mh-final-value {{
    color: var(--purple);
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.8px;
    margin: 8px 0 8px 0;
  }}
  .mh-final .mh-final-note {{ color: var(--ink-soft); font-size: 0.84rem; }}
  .mh-final.mh-final-bad {{
    border-left-color: var(--soft-red);
    background: {rgba(SOFT_RED, 0.08)};
    border-color: {rgba(SOFT_RED, 0.65)};
  }}
  .mh-final.mh-final-bad .mh-final-label,
  .mh-final.mh-final-bad .mh-final-note {{ color: var(--ink-soft); }}
  .mh-final.mh-final-bad .mh-final-value {{ color: var(--ink); }}

  /* ================= verifier ================= */
  .mh-verdict {{
    border-radius: var(--radius);
    padding: 18px 22px;
    margin-bottom: 16px;
    border: var(--line);
    background: var(--app-bg);
    box-shadow: var(--shadow);
  }}
  .mh-verdict.mh-verdict-ok {{
    border-color: {rgba(PURPLE, 0.45)};
    border-left: 3px solid var(--purple);
  }}
  .mh-verdict.mh-verdict-bad {{
    background: {rgba(SOFT_RED, 0.08)};
    border-color: {rgba(SOFT_RED, 0.65)};
    border-left: 3px solid var(--soft-red);
  }}
  .mh-verdict h4 {{ margin: 0 0 8px 0; font-size: 0.98rem; font-weight: 650; }}
  .mh-verdict .mh-expl {{ font-size: 0.9rem; line-height: 1.6; color: var(--ink); }}
  .mh-check {{
    display: flex;
    gap: 12px;
    align-items: flex-start;
    font-size: 0.85rem;
    padding: 9px 0;
    border-bottom: 1px dotted {rgba(SILVER, 0.5)};
    line-height: 1.5;
  }}
  .mh-check:last-child {{ border-bottom: none; }}
  .mh-check .mh-check-name {{
    font-family: "Consolas", monospace;
    font-size: 0.75rem;
    min-width: 200px;
    color: var(--purple);
  }}
  .mh-status {{
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 2px 8px;
    min-width: 60px;
    text-align: center;
    border: 1px solid transparent;
  }}
  .mh-status-pass {{
    background: {rgba(SILVER, 0.34)};
    border-color: {rgba(SILVER, 0.75)};
    color: var(--ink);
  }}
  .mh-status-fail {{
    background: {rgba(SOFT_RED, 0.32)};
    border-color: {rgba(SOFT_RED, 0.85)};
    color: var(--ink);
  }}
  .mh-status-na {{
    background: {rgba(SILVER, 0.22)};
    border-color: {rgba(SILVER, 0.55)};
    color: var(--ink-soft);
  }}
  .mh-status-warn {{
    background: {rgba(SILVER, 0.34)};
    border-color: {rgba(SILVER, 0.75)};
    color: var(--ink);
  }}

  /* ================= misc blocks ================= */
  .mh-note {{
    background: {rgba(SILVER, 0.16)};
    border: 1px solid {rgba(SILVER, 0.45)};
    border-left: 3px solid var(--silver);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 9px 14px;
    font-size: 0.85rem;
    margin-bottom: 10px;
    color: var(--ink-soft);
    line-height: 1.55;
  }}
  .mh-fail {{
    background: {rgba(SOFT_RED, 0.10)};
    border: 1px solid {rgba(SOFT_RED, 0.65)};
    border-left: 3px solid var(--soft-red);
    border-radius: var(--radius);
    padding: 14px 18px;
    margin: 12px 0;
    box-shadow: var(--shadow-sm);
  }}
  .mh-fail h4 {{ margin: 0 0 6px 0; color: var(--ink); font-size: 0.95rem; font-weight: 650; }}
  .mh-fail div {{ font-size: 0.88rem; line-height: 1.55; color: var(--ink); }}
  .mh-kv {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 12px 0; }}
  .mh-kv-item {{
    background: var(--app-bg);
    border: var(--line);
    border-radius: var(--radius-sm);
    padding: 7px 12px;
    font-size: 0.8rem;
    box-shadow: var(--shadow-sm);
  }}
  .mh-kv-item span {{ color: var(--ink-soft); }}
  .mh-kv-item b {{ color: var(--purple); font-weight: 650; margin-left: 4px; }}

  /* ================= sidebar ================= */
  section[data-testid="stSidebar"] {{
    background-color: var(--app-bg);
    border-right: 1px solid var(--silver);
  }}
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {{
    color: var(--purple);
    font-size: 1.02rem;
    font-weight: 650;
    letter-spacing: -0.2px;
  }}
  section[data-testid="stSidebar"] h4 {{
    color: var(--ink-soft);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin: 1.4rem 0 0.35rem 0;
  }}
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] .stCaption {{
    color: var(--ink-soft);
    font-size: 0.8rem;
    line-height: 1.5;
  }}
  section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    color: var(--ink);
    font-size: 0.82rem;
  }}
  section[data-testid="stSidebar"] [data-baseweb="radio"] p,
  section[data-testid="stSidebar"] [data-baseweb="checkbox"] p {{
    color: var(--ink);
    font-size: 0.84rem;
  }}
  section[data-testid="stSidebar"] label {{ font-size: 0.82rem; color: var(--ink); }}
  section[data-testid="stSidebar"] hr {{ border-color: {rgba(SILVER, 0.5)}; }}

  /* ================= widgets ================= */
  .stButton > button {{
    background: var(--app-bg);
    color: var(--purple);
    border: 1px solid var(--silver);
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.86rem;
    padding: 0.42rem 0.9rem;
    box-shadow: var(--shadow-sm);
    transition: all 0.15s ease;
  }}
  .stButton > button:hover {{
    border-color: var(--purple);
    color: var(--purple);
    box-shadow: var(--shadow);
  }}
  .stButton > button[kind="primary"],
  .stButton > button[kind="primary"]:focus,
  .stButton > button[kind="primary"]:hover,
  .stButton > button[kind="primary"]:active {{
    background: var(--purple);
    color: #FFFFFF;
    border: 1px solid var(--purple);
    box-shadow: 0 1px 2px {rgba(PURPLE, 0.30)};
  }}
  .stButton > button[kind="primary"]:hover {{
    background: var(--purple-deep);
    border-color: var(--purple-deep);
  }}
  .stButton > button:focus-visible {{
    outline: none;
    box-shadow: 0 0 0 3px {rgba(PURPLE, 0.18)};
  }}
  /* the button label is markdown - let it inherit the button's own colour */
  .stButton > button p,
  .stButton > button span,
  .stButton > button div {{
    color: inherit !important;
    font-family: inherit;
  }}
  .stDownloadButton > button {{ border-radius: var(--radius-sm); }}

  .stTextInput input,
  .stNumberInput input,
  .stTextArea textarea {{
    border-radius: var(--radius-sm) !important;
    border-color: var(--silver) !important;
    box-shadow: var(--shadow-sm);
    font-size: 0.86rem;
  }}
  .stTextInput input:focus,
  .stNumberInput input:focus {{
    border-color: var(--purple) !important;
    box-shadow: 0 0 0 3px {rgba(PURPLE, 0.14)} !important;
  }}

  /* inputs, dropdowns and sliders - minimal and native */
  [data-testid="stTextInput"] input,
  [data-testid="stNumberInput"] input,
  [data-testid="stTextArea"] textarea {{
    border: 1px solid var(--silver) !important;
    border-radius: var(--radius-sm) !important;
    background: var(--app-bg) !important;
    color: var(--ink) !important;
    font-size: 0.86rem;
    box-shadow: var(--shadow-sm);
  }}
  [data-testid="stTextInput"] input:focus,
  [data-testid="stNumberInput"] input:focus,
  [data-testid="stTextArea"] textarea:focus {{
    border-color: var(--purple) !important;
    box-shadow: 0 0 0 3px {rgba(PURPLE, 0.14)} !important;
  }}
  [data-testid="stNumberInputContainer"] {{
    border: 1px solid var(--silver);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
  }}
  [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    border: 1px solid var(--silver) !important;
    border-radius: var(--radius-sm) !important;
    background: var(--app-bg) !important;
    box-shadow: var(--shadow-sm);
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {{
    border-color: var(--purple) !important;
  }}
  [data-testid="stSlider"] [role="slider"] {{
    background: var(--purple) !important;
    border-color: var(--purple) !important;
    box-shadow: 0 1px 3px {rgba(PURPLE, 0.35)};
  }}
  [data-testid="stSlider"] [data-testid="stSliderTickBar"] {{
    background: {rgba(SILVER, 0.45)};
  }}
  [data-testid="stCheckbox"] label p {{ color: var(--ink); font-size: 0.84rem; }}

  div[data-testid="stExpander"] details {{
    border: 1px solid var(--silver);
    border-radius: var(--radius);
    background: var(--app-bg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }}
  div[data-testid="stExpander"] summary {{
    color: var(--purple);
    font-weight: 650;
    font-size: 0.94rem;
    padding: 0.7rem 1rem;
    transition: background 0.15s ease;
  }}
  div[data-testid="stExpander"] summary:hover {{ background: {rgba(PURPLE, 0.04)}; }}
  div[data-testid="stExpander"] summary svg {{ fill: var(--purple); }}

  .stApp [data-testid="stDataFrame"] {{
    border: 1px solid var(--silver);
    border-radius: var(--radius);
    overflow: hidden;
  }}

  .stApp [data-testid="stCaptionContainer"] {{ color: var(--ink-soft); }}
  .stApp hr {{ border-color: {rgba(SILVER, 0.5)}; }}
  .stApp code {{
    background: {rgba(SILVER, 0.24)};
    border-radius: 5px;
    padding: 1px 5px;
  }}
</style>
"""
