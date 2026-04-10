"""
╔══════════════════════════════════════════════════════════╗
║  TREND PULSE v2  —  Google Trends Comparison Dashboard   ║
║  Fix: patches pytrends for urllib3 v2 compatibility      ║
╚══════════════════════════════════════════════════════════╝
"""

# ── urllib3 v2 Compatibility Patch ────────────────────────────────────────────
# pytrends uses the deprecated `method_whitelist` kwarg removed in urllib3 v2.
# We monkey-patch Retry BEFORE pytrends is imported so the arg is silently
# mapped to the new `allowed_methods` parameter.
import urllib3.util.retry as _retry_mod

_OrigRetry = _retry_mod.Retry

class _PatchedRetry(_OrigRetry):
    def __init__(self, *args, **kwargs):
        if "method_whitelist" in kwargs:
            kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
        super().__init__(*args, **kwargs)

_retry_mod.Retry = _PatchedRetry

# Also patch the alias used by requests → urllib3
try:
    import requests.packages.urllib3.util.retry as _rq_retry
    _rq_retry.Retry = _PatchedRetry
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pytrends.request import TrendReq
from datetime import datetime

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trend Pulse",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

:root {
    --bg:    #07070e;
    --surf:  #0f0f1a;
    --surf2: #16162a;
    --bdr:   #252540;
    --p1:    #7c5cfc;
    --p2:    #00e5c3;
    --p3:    #ff6b6b;
    --p4:    #ffd93d;
    --p5:    #a8ff78;
    --txt:   #e8e8f8;
    --dim:   #7777aa;
    --mono:  'Space Mono', monospace;
    --sans:  'Syne', sans-serif;
}

html, body, [class*="css"] { background:var(--bg) !important; color:var(--txt) !important; font-family:var(--sans) !important; }
#MainMenu, footer, header { visibility:hidden; }
.block-container { padding:2rem 2.5rem !important; max-width:1700px !important; }

.hero-title {
    font-family:var(--sans); font-weight:800; font-size:3rem; letter-spacing:-0.04em; line-height:1; margin:0; padding:0;
    background:linear-gradient(120deg,#7c5cfc 0%,#00e5c3 55%,#ff6b6b 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero-sub { font-family:var(--mono); font-size:0.63rem; color:var(--dim); letter-spacing:0.18em; text-transform:uppercase; margin-top:0.3rem; }

.mcard {
    background:var(--surf); border:1px solid var(--bdr); border-radius:14px;
    padding:1.1rem 1.3rem; position:relative; overflow:hidden;
    transition:transform .2s;
}
.mcard:hover { transform:translateY(-2px); }
.mlabel { font-family:var(--mono); font-size:0.6rem; color:var(--dim); text-transform:uppercase; letter-spacing:0.14em; margin-bottom:0.2rem; }
.mval   { font-family:var(--sans); font-weight:800; font-size:2.2rem; line-height:1; }
.msub   { font-family:var(--mono); font-size:0.6rem; color:var(--dim); margin-top:0.3rem; }
.bdg    { display:inline-block; font-family:var(--mono); font-size:0.6rem; padding:0.14rem 0.5rem; border-radius:4px; margin-top:0.35rem; }
.bup    { background:rgba(0,229,195,.15); color:#00e5c3; }
.bdn    { background:rgba(255,107,107,.15); color:#ff6b6b; }
.bfl    { background:rgba(124,92,252,.15); color:#7c5cfc; }

.sh { font-family:var(--mono); font-size:0.6rem; letter-spacing:0.18em; text-transform:uppercase; color:var(--dim); border-bottom:1px solid var(--bdr); padding-bottom:0.35rem; margin:1.2rem 0 0.7rem; }

.chip { display:inline-block; font-family:var(--mono); font-size:0.68rem; padding:0.2rem 0.7rem; border-radius:20px; margin:0.2rem; border:1px solid; font-weight:700; }

[data-testid="stSidebar"] { background:var(--surf) !important; border-right:1px solid var(--bdr) !important; }
[data-testid="stSidebar"] label { font-family:var(--mono) !important; font-size:0.68rem !important; letter-spacing:0.07em; color:var(--dim) !important; }

textarea, .stTextInput input { background:var(--surf2) !important; border:1px solid var(--bdr) !important; color:var(--txt) !important; border-radius:8px !important; font-family:var(--mono) !important; font-size:0.82rem !important; }
.stSelectbox > div > div { background:var(--surf2) !important; border-color:var(--bdr) !important; border-radius:8px !important; color:var(--txt) !important; font-family:var(--mono) !important; }

.stButton > button {
    background:linear-gradient(135deg,#7c5cfc,#5a3cd4) !important; color:#fff !important; border:none !important;
    border-radius:9px !important; font-family:var(--mono) !important; font-size:0.75rem !important;
    font-weight:700 !important; letter-spacing:0.12em !important; padding:0.65rem 1.5rem !important;
    text-transform:uppercase !important; transition:all .2s !important;
}
.stButton > button:hover { transform:translateY(-2px) !important; box-shadow:0 6px 24px rgba(124,92,252,.45) !important; }

.stTabs [data-baseweb="tab-list"] { background:var(--surf) !important; border-bottom:1px solid var(--bdr) !important; }
.stTabs [data-baseweb="tab"] { font-family:var(--mono) !important; font-size:0.68rem !important; text-transform:uppercase !important; letter-spacing:0.1em !important; color:var(--dim) !important; background:transparent !important; padding:0.7rem 1.2rem !important; }
.stTabs [aria-selected="true"] { color:var(--txt) !important; border-bottom:2px solid var(--p1) !important; }

.stInfo    { background:rgba(124,92,252,.1) !important; border:1px solid rgba(124,92,252,.3) !important; border-radius:8px !important; }
.stWarning { background:rgba(255,217,61,.08) !important; border:1px solid rgba(255,217,61,.3) !important; border-radius:8px !important; }
.stError   { background:rgba(255,107,107,.1) !important; border:1px solid rgba(255,107,107,.3) !important; border-radius:8px !important; }

hr { border-color:var(--bdr) !important; }
::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:var(--bg); }
::-webkit-scrollbar-thumb { background:var(--bdr); border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:var(--p1); }
</style>
""", unsafe_allow_html=True)

# ── Design Tokens ─────────────────────────────────────────────────────────────
PAL = ["#7c5cfc", "#00e5c3", "#ff6b6b", "#ffd93d", "#a8ff78"]

BL = dict(                          # base Plotly layout
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Space Mono, monospace", color="#e8e8f8", size=11),
    title_font=dict(family="Syne, sans-serif", size=14, color="#e8e8f8"),
    legend=dict(bgcolor="rgba(15,15,26,.95)", bordercolor="#252540",
                borderwidth=1, font=dict(size=10, family="Space Mono")),
    xaxis=dict(gridcolor="#14142a", linecolor="#252540", tickfont=dict(size=10), zeroline=False),
    yaxis=dict(gridcolor="#14142a", linecolor="#252540", tickfont=dict(size=10), zeroline=False),
    margin=dict(l=10, r=10, t=36, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#16162a", bordercolor="#252540",
                    font=dict(family="Space Mono", size=11)),
)

TIME_PERIODS = {
    "Past Hour": "now 1-H", "Past 4 Hours": "now 4-H",
    "Past Day": "now 1-d",  "Past 7 Days": "now 7-d",
    "Past 30 Days": "today 1-m", "Past 90 Days": "today 3-m",
    "Past 12 Months": "today 12-m", "Past 5 Years": "today 5-y",
}
CATEGORIES = {
    "All Categories": 0, "Arts & Entertainment": 3, "Autos & Vehicles": 47,
    "Business & Industry": 12, "Computers & Electronics": 5, "Finance": 7,
    "Food & Drink": 71, "Games": 8, "Health": 45,
    "Jobs & Education": 958, "News": 16, "People & Society": 14,
    "Science": 174, "Shopping": 18, "Sports": 20, "Technology": 13, "Travel": 67,
}
GEOS = {
    "Worldwide": "", "United States": "US", "United Kingdom": "GB",
    "India": "IN", "Germany": "DE", "France": "FR", "Brazil": "BR",
    "Japan": "JP", "Australia": "AU", "Canada": "CA",
    "Mexico": "MX", "South Korea": "KR",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def hex_rgba(h: str, a: float) -> str:
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"rgba({r},{g},{b},{a})"


def make_pt():
    """Instantiate TrendReq with no retries to avoid the method_whitelist path."""
    return TrendReq(hl="en-US", tz=330, timeout=(15, 35))


# ── Cached Fetchers ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_time(kws: tuple, tf: str, geo: str, cat: int) -> pd.DataFrame:
    pt = make_pt()
    pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
    df = pt.interest_over_time()
    if not df.empty and "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_region(kws: tuple, tf: str, geo: str, cat: int) -> pd.DataFrame:
    pt = make_pt()
    pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
    return pt.interest_by_region(resolution="COUNTRY", inc_low_vol=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_related(kws: tuple, tf: str, geo: str, cat: int) -> dict:
    pt = make_pt()
    pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
    return pt.related_queries()


@st.cache_data(ttl=120, show_spinner=False)
def fetch_trending(geo: str) -> pd.DataFrame:
    pn_map = {"US": "united_states", "GB": "united_kingdom", "IN": "india",
              "DE": "germany", "FR": "france", "BR": "brazil", "JP": "japan",
              "AU": "australia", "CA": "canada", "MX": "mexico", "KR": "south_korea"}
    pt = make_pt()
    try:
        return pt.trending_searches(pn=pn_map.get(geo, "united_states"))
    except Exception:
        return pd.DataFrame()


# ── Chart Builders ────────────────────────────────────────────────────────────
def ch_line(df, kws, stacked=False):
    fig = go.Figure()
    for i, kw in enumerate(kws):
        if kw not in df.columns:
            continue
        c = PAL[i % len(PAL)]
        kw_args = dict(x=df.index, y=df[kw], name=kw,
                       line=dict(color=c, width=2.5, shape="spline", smoothing=0.7),
                       hovertemplate=f"<b>{kw}</b>: %{{y}}<extra></extra>")
        if stacked:
            fig.add_trace(go.Scatter(**kw_args, mode="lines", stackgroup="one",
                                     fillcolor=hex_rgba(c, .35)))
        else:
            fig.add_trace(go.Scatter(**kw_args, mode="lines", fill="tozeroy",
                                     fillcolor=hex_rgba(c, .07)))
    fig.update_layout(**BL, height=390)
    return fig


def ch_corr(df, kws):
    valid = [k for k in kws if k in df.columns]
    if len(valid) < 2:
        return None
    corr = df[valid].corr().round(3)
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns, y=corr.index,
        colorscale=[[0, "#ff6b6b"], [0.5, "#16162a"], [1, "#00e5c3"]],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(family="Space Mono", size=12),
        hovertemplate="%{x} × %{y}<br>r = %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(**BL, height=290)
    return fig


def ch_geo_map(geo_df, kw):
    if kw not in geo_df.columns or geo_df.empty:
        return None
    d = geo_df[[kw]].reset_index()
    d.columns = ["location", "value"]
    d = d[d["value"] > 0]
    fig = px.choropleth(
        d, locations="location", locationmode="country names",
        color="value", hover_name="location", labels={"value": "Interest"},
        color_continuous_scale=[[0,"#07070e"],[.3,"#2e1a6e"],[.7,"#7c5cfc"],[1,"#00e5c3"]],
    )
    fig.update_layout(
        **BL, height=360,
        geo=dict(bgcolor="rgba(0,0,0,0)", landcolor="#1a1a30",
                 oceancolor="#07070e", showocean=True, lakecolor="#07070e",
                 framecolor="#252540", projection_type="natural earth"),
        coloraxis_colorbar=dict(bgcolor="rgba(0,0,0,0)",
                                tickfont=dict(family="Space Mono", size=9),
                                title_side="right"),
    )
    return fig


def ch_geo_bar(geo_df, kws, top=15):
    valid = [k for k in kws if k in geo_df.columns]
    if not valid:
        return None
    top_idx = geo_df[valid].sum(axis=1).nlargest(top).index
    sub = geo_df.loc[top_idx, valid]
    fig = go.Figure()
    for i, kw in enumerate(valid):
        c = PAL[i % len(PAL)]
        fig.add_trace(go.Bar(x=sub.index, y=sub[kw], name=kw, marker_color=c,
                             marker_line_width=0,
                             hovertemplate=f"<b>%{{x}}</b><br>{kw}: %{{y}}<extra></extra>"))
    fig.update_layout(**BL, height=310, barmode="group", bargap=0.18)
    return fig


def ch_bar_avg(df, kws):
    avgs = {k: round(df[k].mean(), 1) for k in kws if k in df.columns}
    kws_s = sorted(avgs, key=avgs.get, reverse=True)
    fig = go.Figure()
    for i, kw in enumerate(kws_s):
        fig.add_trace(go.Bar(
            x=[kw], y=[avgs[kw]], name=kw, marker_color=PAL[i % len(PAL)],
            marker_line_width=0,
            hovertemplate=f"<b>{kw}</b><br>Avg: %{{y:.1f}}<extra></extra>",
        ))
    fig.update_layout(**BL, height=290, showlegend=False, barmode="group", bargap=0.3)
    return fig


def ch_box(df, kws):
    fig = go.Figure()
    for i, kw in enumerate(kws):
        if kw not in df.columns:
            continue
        c = PAL[i % len(PAL)]
        fig.add_trace(go.Box(
            y=df[kw], name=kw, marker_color=c, line_color=c,
            fillcolor=hex_rgba(c, .15), boxmean="sd",
            hovertemplate=f"<b>{kw}</b><br>%{{y}}<extra></extra>",
        ))
    fig.update_layout(**BL, height=290, showlegend=False)
    return fig


def ch_radar(df, kws):
    avgs = {k: df[k].mean() for k in kws if k in df.columns}
    if len(avgs) < 2:
        return None
    ks, vs = list(avgs.keys()), list(avgs.values())
    fig = go.Figure(go.Scatterpolar(
        r=vs + [vs[0]], theta=ks + [ks[0]],
        fill="toself", fillcolor=hex_rgba("#7c5cfc", .2),
        line=dict(color="#7c5cfc", width=2),
        marker=dict(color="#00e5c3", size=8),
    ))
    fig.update_layout(
        **BL, height=310,
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(visible=True, gridcolor="#1e1e3a", tickfont=dict(size=9)),
                   angularaxis=dict(gridcolor="#1e1e3a", tickfont=dict(size=10))),
    )
    return fig


def ch_rolling(df, kws, w=7):
    fig = go.Figure()
    for i, kw in enumerate(kws):
        if kw not in df.columns:
            continue
        c = PAL[i % len(PAL)]
        roll = df[kw].rolling(w, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=roll, name=kw, mode="lines",
            line=dict(color=c, width=2.5),
            hovertemplate=f"<b>{kw}</b><br>%{{x}}<br>Roll avg: %{{y:.1f}}<extra></extra>",
        ))
    fig.update_layout(**BL, height=290)
    return fig


def ch_momentum(df, kws):
    n, q = len(df), max(1, len(df) // 4)
    rows = []
    for kw in kws:
        if kw not in df.columns:
            continue
        f = df[kw].iloc[:q].mean()
        l = df[kw].iloc[-q:].mean()
        rows.append({"kw": kw, "chg": round(((l - f) / (f + 1e-9)) * 100, 1)})
    if not rows:
        return None
    fig = go.Figure()
    for i, r in enumerate(rows):
        c = "#00e5c3" if r["chg"] >= 0 else "#ff6b6b"
        fig.add_trace(go.Bar(x=[r["kw"]], y=[r["chg"]], name=r["kw"],
                             marker_color=c, marker_line_width=0,
                             hovertemplate=f"<b>{r['kw']}</b><br>Δ %{{y:+.1f}}%<extra></extra>"))
    fig.add_hline(y=0, line_color="#252540", line_width=1)
    fig.update_layout(**BL, height=260, showlegend=False, yaxis_title="% Change")
    return fig


def ch_related_bar(df_q, color, title):
    if df_q is None or df_q.empty:
        return None
    d = df_q.head(10)
    fig = go.Figure(go.Bar(
        x=d["value"], y=d["query"], orientation="h",
        marker_color=color, marker_line_width=0,
        hovertemplate="%{y}<br>Value: %{x}<extra></extra>",
    ))
    fig.update_layout(**BL, height=290, showlegend=False,
                      yaxis=dict(autorange="reversed", **BL["yaxis"]),
                      title_text=title, title_font=dict(size=12))
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:1rem 0 1.2rem;'>
        <div style='font-family:Syne,sans-serif;font-weight:800;font-size:1.4rem;
                    background:linear-gradient(135deg,#7c5cfc,#00e5c3);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;'>
            TREND PULSE
        </div>
        <div style='font-family:Space Mono,monospace;font-size:0.56rem;color:#7777aa;
                    letter-spacing:0.16em;text-transform:uppercase;margin-top:0.15rem;'>
            Google Trends Explorer v2
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sh">Keywords (max 5)</div>', unsafe_allow_html=True)
    raw = st.text_area("kw", value="ChatGPT\nGemini\nClaude AI\nCopilot",
                       height=115, label_visibility="collapsed")
    keywords = [k.strip() for k in raw.strip().splitlines() if k.strip()][:5]

    st.markdown('<div class="sh">Settings</div>', unsafe_allow_html=True)
    tf_lbl  = st.selectbox("Time Period", list(TIME_PERIODS), index=6)
    geo_lbl = st.selectbox("Region", list(GEOS), index=2)
    cat_lbl = st.selectbox("Category", list(CATEGORIES), index=0)
    mode    = st.radio("Chart Style", ["Line", "Stacked Area"], horizontal=True)
    st.markdown("")
    run = st.button("⚡  ANALYZE TRENDS", use_container_width=True)

    st.markdown("""
    <div style='margin-top:1.4rem;padding:0.85rem;background:#0f0f1a;border:1px solid #252540;
                border-radius:10px;font-family:Space Mono,monospace;font-size:0.56rem;color:#7777aa;'>
        <div style='color:#7c5cfc;margin-bottom:0.35rem;font-weight:700;'>ℹ  INFO</div>
        • Values normalized 0–100<br>
        • 100 = peak of interest<br>
        • Cache: 5 min per query<br>
        • urllib3 v2 patched ✓<br>
        • pytrends retries=0 (safe)
    </div>""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([4, 1])
with hc1:
    st.markdown('<p class="hero-title">Trend Pulse</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Real-time search interest comparison · Powered by Google Trends</p>',
                unsafe_allow_html=True)
with hc2:
    st.markdown(f"""
    <div style='text-align:right;padding-top:.55rem;'>
        <div style='font-family:Space Mono;font-size:0.58rem;color:#7777aa;'>LIVE AS OF</div>
        <div style='font-family:Syne;font-weight:800;font-size:1rem;color:#00e5c3;'>
            {datetime.now().strftime('%H:%M · %d %b %Y')}
        </div>
        <div style='font-family:Space Mono;font-size:0.56rem;color:#7777aa;margin-top:0.2rem;'>
            {geo_lbl} &nbsp;·&nbsp; {tf_lbl}
        </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<hr style='margin:.7rem 0 .5rem;'>", unsafe_allow_html=True)

# Keyword chips
if keywords:
    chips = "".join(
        f"<span class='chip' style='color:{PAL[i%len(PAL)]};border-color:{PAL[i%len(PAL)]}44;"
        f"background:{PAL[i%len(PAL)]}12;'>{kw}</span>"
        for i, kw in enumerate(keywords)
    )
    st.markdown(f"<div style='margin-bottom:.9rem;'>{chips}</div>", unsafe_allow_html=True)

if not keywords:
    st.info("Enter keywords in the sidebar and click **ANALYZE TRENDS**.")
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────────────────
tf  = TIME_PERIODS[tf_lbl]
geo = GEOS[geo_lbl]
cat = CATEGORIES[cat_lbl]
kws = tuple(keywords)

with st.spinner("Fetching data from Google Trends..."):
    try:
        df = fetch_time(kws, tf, geo, cat)
    except Exception as e:
        st.error(
            f"**Google Trends error:** {e}\n\n"
            "**Tips:** reduce keywords · use a wider timeframe · try Worldwide region"
        )
        st.stop()

if df.empty:
    st.warning("No data returned. Try different keywords, a broader time range, or Worldwide region.")
    st.stop()

valid = [k for k in keywords if k in df.columns]

# ── Metric Cards ──────────────────────────────────────────────────────────────
st.markdown('<div class="sh">Summary Statistics</div>', unsafe_allow_html=True)
mc = st.columns(len(valid))
for i, kw in enumerate(valid):
    s  = df[kw]
    cur, peak, avg = int(s.iloc[-1]), int(s.max()), float(s.mean())
    d = int(s.iloc[-1]) - int(s.iloc[-2]) if len(s) > 1 else 0
    bc, bt = ("bup", f"↑ {abs(d)}") if d > 0 else ("bdn", f"↓ {abs(d)}") if d < 0 else ("bfl", "→ flat")
    c = PAL[i % len(PAL)]
    nc = PAL[(i + 1) % len(PAL)]
    with mc[i]:
        st.markdown(f"""
        <div class="mcard">
            <div style="position:absolute;top:0;left:0;right:0;height:3px;
                        background:linear-gradient(90deg,{c},{nc});
                        border-radius:14px 14px 0 0;"></div>
            <div class="mlabel">{kw}</div>
            <div class="mval" style="color:{c};">{cur}</div>
            <div class="msub">Peak <b style="color:{c};">{peak}</b>&nbsp;·&nbsp;Avg <b>{avg:.0f}</b></div>
            <span class="bdg {bc}">{bt}</span>
        </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1, t2, t3, t4, t5 = st.tabs([
    "📈  Interest Over Time",
    "🌍  Geographic Map",
    "🔍  Related Queries",
    "📊  Deep Analysis",
    "🔥  Trending Now",
])

# ── Tab 1 ─────────────────────────────────────────────────────────────────────
with t1:
    st.markdown('<div class="sh">Search Interest · 0–100 Normalized Scale</div>', unsafe_allow_html=True)
    st.plotly_chart(ch_line(df, valid, stacked=(mode == "Stacked Area")),
                    use_container_width=True, config={"displayModeBar": False})

    if len(valid) > 1:
        st.markdown('<div class="sh">Correlation Matrix</div>', unsafe_allow_html=True)
        f = ch_corr(df, valid)
        if f:
            st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

    with st.expander("📋  Raw Data — inspect & download"):
        st.dataframe(df.style.background_gradient(cmap="Purples", axis=None), use_container_width=True)
        st.download_button("⬇  Download CSV", df.to_csv().encode(),
                           "trends_data.csv", "text/csv", use_container_width=True)

# ── Tab 2 ─────────────────────────────────────────────────────────────────────
with t2:
    with st.spinner("Loading geographic data..."):
        try:
            gdf = fetch_region(kws, tf, geo, cat)
        except Exception:
            gdf = pd.DataFrame()

    if not gdf.empty:
        sel = st.selectbox("Keyword for choropleth", valid, key="g_sel")
        st.markdown(f'<div class="sh">World Map · {sel}</div>', unsafe_allow_html=True)
        fm = ch_geo_map(gdf, sel)
        if fm:
            st.plotly_chart(fm, use_container_width=True, config={"displayModeBar": False})
        st.markdown('<div class="sh">Top Regions — All Keywords</div>', unsafe_allow_html=True)
        fb = ch_geo_bar(gdf, valid)
        if fb:
            st.plotly_chart(fb, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No geographic data. Try a longer timeframe or Worldwide region.")

# ── Tab 3 ─────────────────────────────────────────────────────────────────────
with t3:
    with st.spinner("Loading related queries..."):
        try:
            rel = fetch_related(kws, tf, geo, cat)
        except Exception:
            rel = {}

    if rel:
        for i, kw in enumerate(valid):
            if kw not in rel or not rel[kw]:
                continue
            c = PAL[i % len(PAL)]
            with st.expander(f"🔑  {kw}", expanded=(i == 0)):
                lc, rc = st.columns(2)
                with lc:
                    f = ch_related_bar(rel[kw].get("top"), c, "🏆 Top Queries")
                    st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}) if f else st.caption("No top queries.")
                with rc:
                    f = ch_related_bar(rel[kw].get("rising"), "#00e5c3", "🚀 Rising Queries")
                    st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}) if f else st.caption("No rising queries.")
    else:
        st.info("No related queries data for this configuration.")

# ── Tab 4 ─────────────────────────────────────────────────────────────────────
with t4:
    ca, cb = st.columns(2)
    with ca:
        st.markdown('<div class="sh">Average Interest</div>', unsafe_allow_html=True)
        st.plotly_chart(ch_bar_avg(df, valid), use_container_width=True, config={"displayModeBar": False})
        st.markdown('<div class="sh">Distribution · Box + Std Dev</div>', unsafe_allow_html=True)
        st.plotly_chart(ch_box(df, valid), use_container_width=True, config={"displayModeBar": False})
    with cb:
        st.markdown('<div class="sh">Multi-Axis Radar</div>', unsafe_allow_html=True)
        fr = ch_radar(df, valid)
        st.plotly_chart(fr, use_container_width=True, config={"displayModeBar": False}) if fr else st.info("Radar needs ≥ 2 keywords.")
        st.markdown('<div class="sh">7-Day Rolling Average</div>', unsafe_allow_html=True)
        st.plotly_chart(ch_rolling(df, valid), use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="sh">Trend Momentum · First vs Last Quarter</div>', unsafe_allow_html=True)
    fm = ch_momentum(df, valid)
    if fm:
        st.plotly_chart(fm, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="sh">Descriptive Statistics</div>', unsafe_allow_html=True)
    stats = df[valid].describe().T.round(2)
    stats.index.name = "Keyword"
    st.dataframe(stats.style.background_gradient(cmap="Purples", axis=None), use_container_width=True)

# ── Tab 5 ─────────────────────────────────────────────────────────────────────
with t5:
    st.markdown('<div class="sh">Currently Trending Searches</div>', unsafe_allow_html=True)
    with st.spinner("Fetching trending..."):
        tdf = fetch_trending(geo)

    if not tdf.empty:
        tdf.columns = ["Trending Query"]
        tdf = tdf.head(25).reset_index(drop=True)
        tdf.index += 1
        html = ""
        for idx, row in tdf.iterrows():
            c = PAL[(idx - 1) % len(PAL)]
            html += (
                f"<div style='display:flex;align-items:center;gap:.8rem;padding:.45rem .8rem;"
                f"margin-bottom:.3rem;background:#0f0f1a;border:1px solid #252540;"
                f"border-radius:8px;border-left:3px solid {c};'>"
                f"<span style='font-family:Space Mono;font-size:.62rem;color:{c};font-weight:700;min-width:1.4rem;'>"
                f"{idx:02d}</span>"
                f"<span style='font-family:Syne;font-size:.9rem;color:#e8e8f8;'>{row['Trending Query']}</span>"
                f"</div>"
            )
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("Trending data unavailable for this region. Try United States.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr style='margin-top:2rem;'>", unsafe_allow_html=True)
st.markdown(f"""
<div style='font-family:Space Mono,monospace;font-size:0.56rem;color:#7777aa;
            display:flex;justify-content:space-between;padding:.4rem 0 1.2rem;flex-wrap:wrap;gap:.4rem;'>
    <span>TREND PULSE v2 &nbsp;·&nbsp; urllib3 v2 compatible</span>
    <span>{geo_lbl} &nbsp;·&nbsp; {tf_lbl} &nbsp;·&nbsp; {cat_lbl}</span>
    <span>Normalized 0–100 &nbsp;·&nbsp; pytrends</span>
</div>""", unsafe_allow_html=True)