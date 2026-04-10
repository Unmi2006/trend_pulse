"""
TREND PULSE v4  —  Google Trends Comparison Dashboard
======================================================
Fixes in this version:
  ✓ No matplotlib dependency (removed all .background_gradient calls)
  ✓ urllib3 v2 patch (method_whitelist → allowed_methods)
  ✓ 429 rate-limit handling with exponential backoff + jitter
  ✓ Demo / mock mode when Google blocks all requests
  ✓ Streamlit Cloud compatible (pure plotly + streamlit only)
"""

# ── 1. urllib3 v2 Patch (before ANY pytrends import) ─────────────────────────
import urllib3.util.retry as _r

class _SafeRetry(_r.Retry):
    def __init__(self, *a, **kw):
        kw.pop("method_whitelist", None)   # silently drop deprecated kwarg
        super().__init__(*a, **kw)

_r.Retry = _SafeRetry
try:
    import requests.packages.urllib3.util.retry as _rr
    _rr.Retry = _SafeRetry
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

import time, random, hashlib, json
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pytrends.request import TrendReq

# ── Page config ───────────────────────────────────────────────────────────────
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

:root{
  --bg:#07070e; --surf:#0f0f1a; --surf2:#16162a; --bdr:#252540;
  --p1:#7c5cfc; --p2:#00e5c3; --p3:#ff6b6b; --p4:#ffd93d; --p5:#a8ff78;
  --txt:#e8e8f8; --dim:#7777aa;
  --mono:'Space Mono',monospace; --sans:'Syne',sans-serif;
}
html,body,[class*="css"]{background:var(--bg)!important;color:var(--txt)!important;font-family:var(--sans)!important;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:1.8rem 2.4rem!important;max-width:1700px!important;}

/* Hero */
.hero-title{
  font-family:var(--sans);font-weight:800;font-size:2.9rem;
  letter-spacing:-.04em;line-height:1;margin:0;padding:0;
  background:linear-gradient(120deg,#7c5cfc 0%,#00e5c3 55%,#ff6b6b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.hero-sub{font-family:var(--mono);font-size:.62rem;color:var(--dim);letter-spacing:.18em;text-transform:uppercase;margin-top:.3rem;}

/* Metric cards */
.mcard{background:var(--surf);border:1px solid var(--bdr);border-radius:14px;
  padding:1.1rem 1.3rem;position:relative;overflow:hidden;transition:transform .2s;}
.mcard:hover{transform:translateY(-2px);}
.mlabel{font-family:var(--mono);font-size:.59rem;color:var(--dim);text-transform:uppercase;letter-spacing:.13em;margin-bottom:.2rem;}
.mval{font-family:var(--sans);font-weight:800;font-size:2.1rem;line-height:1;}
.msub{font-family:var(--mono);font-size:.59rem;color:var(--dim);margin-top:.3rem;}
.bdg{display:inline-block;font-family:var(--mono);font-size:.59rem;padding:.13rem .5rem;border-radius:4px;margin-top:.32rem;}
.bup{background:rgba(0,229,195,.15);color:#00e5c3;}
.bdn{background:rgba(255,107,107,.15);color:#ff6b6b;}
.bfl{background:rgba(124,92,252,.15);color:#7c5cfc;}

/* Section header */
.sh{font-family:var(--mono);font-size:.59rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--dim);border-bottom:1px solid var(--bdr);padding-bottom:.32rem;margin:1.1rem 0 .65rem;}

/* Chips */
.chip{display:inline-block;font-family:var(--mono);font-size:.67rem;
  padding:.18rem .65rem;border-radius:20px;margin:.18rem;border:1px solid;font-weight:700;}

/* Demo banner */
.demo-banner{background:rgba(255,217,61,.08);border:1px solid rgba(255,217,61,.35);
  border-radius:10px;padding:.7rem 1rem;margin-bottom:1rem;
  font-family:var(--mono);font-size:.65rem;color:#ffd93d;letter-spacing:.04em;}

/* Sidebar */
[data-testid="stSidebar"]{background:var(--surf)!important;border-right:1px solid var(--bdr)!important;}
[data-testid="stSidebar"] label{font-family:var(--mono)!important;font-size:.67rem!important;letter-spacing:.07em;color:var(--dim)!important;}

/* Inputs */
textarea,.stTextInput input{background:var(--surf2)!important;border:1px solid var(--bdr)!important;
  color:var(--txt)!important;border-radius:8px!important;font-family:var(--mono)!important;font-size:.81rem!important;}
.stSelectbox>div>div{background:var(--surf2)!important;border-color:var(--bdr)!important;
  border-radius:8px!important;color:var(--txt)!important;font-family:var(--mono)!important;}

/* Button */
.stButton>button{
  background:linear-gradient(135deg,#7c5cfc,#5a3cd4)!important;color:#fff!important;
  border:none!important;border-radius:9px!important;font-family:var(--mono)!important;
  font-size:.74rem!important;font-weight:700!important;letter-spacing:.12em!important;
  padding:.63rem 1.4rem!important;text-transform:uppercase!important;transition:all .2s!important;
}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 6px 22px rgba(124,92,252,.45)!important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{background:var(--surf)!important;border-bottom:1px solid var(--bdr)!important;}
.stTabs [data-baseweb="tab"]{font-family:var(--mono)!important;font-size:.67rem!important;
  text-transform:uppercase!important;letter-spacing:.1em!important;color:var(--dim)!important;
  background:transparent!important;padding:.68rem 1.2rem!important;}
.stTabs [aria-selected="true"]{color:var(--txt)!important;border-bottom:2px solid var(--p1)!important;}

/* Alerts */
.stInfo{background:rgba(124,92,252,.1)!important;border:1px solid rgba(124,92,252,.3)!important;border-radius:8px!important;}
.stWarning{background:rgba(255,217,61,.08)!important;border:1px solid rgba(255,217,61,.3)!important;border-radius:8px!important;}
.stError{background:rgba(255,107,107,.1)!important;border:1px solid rgba(255,107,107,.3)!important;border-radius:8px!important;}
.stSuccess{background:rgba(0,229,195,.1)!important;border:1px solid rgba(0,229,195,.3)!important;border-radius:8px!important;}

/* Table — no matplotlib needed */
.stDataFrame{border:1px solid var(--bdr)!important;border-radius:8px!important;}
.stDataFrame th{background:var(--surf2)!important;color:var(--dim)!important;font-family:var(--mono)!important;font-size:.65rem!important;}
.stDataFrame td{font-family:var(--mono)!important;font-size:.72rem!important;}

hr{border-color:var(--bdr)!important;}
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:4px;}
::-webkit-scrollbar-thumb:hover{background:var(--p1);}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
PAL = ["#7c5cfc", "#00e5c3", "#ff6b6b", "#ffd93d", "#a8ff78"]

BL = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Space Mono,monospace", color="#e8e8f8", size=11),
    title_font=dict(family="Syne,sans-serif", size=13, color="#e8e8f8"),
    legend=dict(bgcolor="rgba(15,15,26,.95)", bordercolor="#252540",
                borderwidth=1, font=dict(size=10, family="Space Mono")),
    xaxis=dict(gridcolor="#14142a", linecolor="#252540", tickfont=dict(size=10), zeroline=False),
    yaxis=dict(gridcolor="#14142a", linecolor="#252540", tickfont=dict(size=10), zeroline=False),
    margin=dict(l=10, r=10, t=36, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#16162a", bordercolor="#252540",
                    font=dict(family="Space Mono", size=11)),
)

TIME_OPTS = {
    "Past Hour": "now 1-H", "Past 4 Hours": "now 4-H",
    "Past Day": "now 1-d", "Past 7 Days": "now 7-d",
    "Past 30 Days": "today 1-m", "Past 90 Days": "today 3-m",
    "Past 12 Months": "today 12-m", "Past 5 Years": "today 5-y",
}
CAT_OPTS = {
    "All Categories": 0, "Arts & Entertainment": 3, "Autos & Vehicles": 47,
    "Business & Industry": 12, "Computers & Electronics": 5, "Finance": 7,
    "Food & Drink": 71, "Games": 8, "Health": 45, "Jobs & Education": 958,
    "News": 16, "People & Society": 14, "Science": 174,
    "Shopping": 18, "Sports": 20, "Technology": 13, "Travel": 67,
}
GEO_OPTS = {
    "Worldwide": "", "United States": "US", "United Kingdom": "GB",
    "India": "IN", "Germany": "DE", "France": "FR", "Brazil": "BR",
    "Japan": "JP", "Australia": "AU", "Canada": "CA",
    "Mexico": "MX", "South Korea": "KR",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def rgba(h: str, a: float) -> str:
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"rgba({r},{g},{b},{a})"


def cache_key(*args) -> str:
    return hashlib.md5(json.dumps(args, default=str).encode()).hexdigest()[:16]


# ── In-memory request cache (survives re-runs within session) ─────────────────
if "req_cache" not in st.session_state:
    st.session_state.req_cache = {}
if "last_call_ts" not in st.session_state:
    st.session_state.last_call_ts = 0.0
if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = False


def polite_sleep():
    """Enforce ≥ 2 s between Google calls to avoid 429."""
    elapsed = time.time() - st.session_state.last_call_ts
    gap = random.uniform(2.2, 4.0)
    if elapsed < gap:
        time.sleep(gap - elapsed)
    st.session_state.last_call_ts = time.time()


def make_pt() -> TrendReq:
    ua = random.choice(USER_AGENTS)
    return TrendReq(
        hl="en-US", tz=330,
        timeout=(20, 40),
        requests_args={"headers": {"User-Agent": ua}},
    )


def call_with_backoff(fn, max_retries=4):
    """
    Call fn() with exponential back-off on 429 / ResponseError.
    Returns (result, error_str).
    """
    for attempt in range(max_retries):
        try:
            polite_sleep()
            return fn(), None
        except Exception as e:
            msg = str(e)
            is_429 = "429" in msg or "quota" in msg.lower() or "too many" in msg.lower()
            if is_429 and attempt < max_retries - 1:
                wait = (2 ** attempt) * random.uniform(3, 6)   # 3-6s, 6-12s, 12-24s …
                st.toast(f"⏳ Rate limited — waiting {wait:.0f}s before retry {attempt+2}/{max_retries}…",
                         icon="⚠️")
                time.sleep(wait)
            else:
                return None, msg
    return None, "Max retries exceeded"


# ── Demo data generator (no Google needed) ────────────────────────────────────
def demo_over_time(keywords, timeframe):
    np.random.seed(42)
    if "H" in timeframe:
        periods, freq = 60, "min"
    elif "7-d" in timeframe or "1-d" in timeframe:
        periods, freq = 168, "h"
    elif "1-m" in timeframe:
        periods, freq = 30, "D"
    elif "3-m" in timeframe:
        periods, freq = 90, "D"
    elif "5-y" in timeframe:
        periods, freq = 260, "W"
    else:
        periods, freq = 52, "W"

    dates = pd.date_range(end=datetime.today(), periods=periods, freq=freq)
    n = len(dates)          # use actual length (date_range can differ by ±1)
    bases = [random.randint(25, 85) for _ in keywords]
    data = {}
    for i, kw in enumerate(keywords):
        trend = np.linspace(0, random.choice([-1, 1]) * random.randint(5, 20), n)
        noise = np.random.randn(n) * random.uniform(3, 9)
        spike_idx = random.randint(n // 4, 3 * n // 4)
        spike = np.zeros(n)
        spike[spike_idx:min(spike_idx + 3, n)] = random.randint(10, 35)
        vals = np.clip(bases[i] + trend + noise + spike, 0, 100).astype(int)
        data[kw] = vals
    return pd.DataFrame(data, index=dates)


def demo_by_region(keywords):
    countries = [
        "United States", "India", "United Kingdom", "Germany", "Brazil",
        "Canada", "Australia", "France", "Japan", "Mexico",
        "Indonesia", "South Korea", "Italy", "Spain", "Netherlands",
    ]
    data = {kw: np.random.randint(10, 100, len(countries)) for kw in keywords}
    return pd.DataFrame(data, index=countries)


def demo_related(keywords):
    templates = {
        "top": ["how to use {kw}", "{kw} tutorial", "{kw} vs gpt4", "{kw} api", "{kw} login",
                "best {kw} prompts", "{kw} pricing", "{kw} free", "{kw} download", "{kw} review"],
        "rising": ["{kw} 2024", "{kw} news", "new {kw} features", "{kw} update", "{kw} alternative",
                   "{kw} benchmark", "{kw} comparison", "{kw} jailbreak", "{kw} image", "{kw} code"],
    }
    result = {}
    for kw in keywords:
        top_q = [q.replace("{kw}", kw) for q in templates["top"]]
        ris_q = [q.replace("{kw}", kw) for q in templates["rising"]]
        result[kw] = {
            "top": pd.DataFrame({"query": top_q, "value": sorted(np.random.randint(40, 100, 10), reverse=True)}),
            "rising": pd.DataFrame({"query": ris_q, "value": sorted(np.random.randint(200, 5000, 10), reverse=True)}),
        }
    return result


def demo_trending():
    items = [
        "OpenAI GPT-5", "Apple Intelligence", "Formula 1", "Python 3.13",
        "World Cup 2026", "Claude 4", "Llama 3", "Tesla Cybertruck",
        "Nintendo Switch 2", "Solar Eclipse", "SpaceX Starship", "Taylor Swift",
        "Bitcoin ETF", "Gemini Ultra", "Vision Pro 2",
    ]
    return pd.DataFrame(items, columns=["Trending Query"])


# ── Cached fetchers (session cache, no @st.cache_data to avoid hash issues) ───
def get_over_time(kws, tf, geo, cat):
    key = cache_key("ot", kws, tf, geo, cat)
    if key in st.session_state.req_cache:
        return st.session_state.req_cache[key], None, False   # data, err, is_demo

    if st.session_state.demo_mode:
        data = demo_over_time(list(kws), tf)
        st.session_state.req_cache[key] = data
        return data, None, True

    def _fetch():
        pt = make_pt()
        pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
        df = pt.interest_over_time()
        if not df.empty and "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        return df

    data, err = call_with_backoff(_fetch)
    if err or (data is not None and data.empty):
        # Fall back to demo
        data = demo_over_time(list(kws), tf)
        st.session_state.req_cache[key] = data
        return data, err, True

    st.session_state.req_cache[key] = data
    return data, None, False


def get_by_region(kws, tf, geo, cat):
    key = cache_key("br", kws, tf, geo, cat)
    if key in st.session_state.req_cache:
        return st.session_state.req_cache[key], False

    if st.session_state.demo_mode:
        data = demo_by_region(list(kws))
        st.session_state.req_cache[key] = data
        return data, True

    def _fetch():
        pt = make_pt()
        pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
        return pt.interest_by_region(resolution="COUNTRY", inc_low_vol=True)

    data, err = call_with_backoff(_fetch)
    if err or data is None or data.empty:
        data = demo_by_region(list(kws))
        st.session_state.req_cache[key] = data
        return data, True

    st.session_state.req_cache[key] = data
    return data, False


def get_related(kws, tf, geo, cat):
    key = cache_key("rq", kws, tf, geo, cat)
    if key in st.session_state.req_cache:
        return st.session_state.req_cache[key], False

    if st.session_state.demo_mode:
        data = demo_related(list(kws))
        st.session_state.req_cache[key] = data
        return data, True

    def _fetch():
        pt = make_pt()
        pt.build_payload(list(kws), cat=cat, timeframe=tf, geo=geo)
        return pt.related_queries()

    data, err = call_with_backoff(_fetch)
    if err or not data:
        data = demo_related(list(kws))
        st.session_state.req_cache[key] = data
        return data, True

    st.session_state.req_cache[key] = data
    return data, False


def get_trending(geo):
    key = cache_key("tr", geo)
    if key in st.session_state.req_cache:
        return st.session_state.req_cache[key], False

    if st.session_state.demo_mode:
        data = demo_trending()
        st.session_state.req_cache[key] = data
        return data, True

    pn_map = {
        "US": "united_states", "GB": "united_kingdom", "IN": "india",
        "DE": "germany", "FR": "france", "BR": "brazil", "JP": "japan",
        "AU": "australia", "CA": "canada", "MX": "mexico", "KR": "south_korea",
    }

    def _fetch():
        pt = make_pt()
        return pt.trending_searches(pn=pn_map.get(geo, "united_states"))

    data, err = call_with_backoff(_fetch)
    if err or data is None or data.empty:
        data = demo_trending()
        st.session_state.req_cache[key] = data
        return data, True

    st.session_state.req_cache[key] = data
    return data, False


# ── Chart builders ────────────────────────────────────────────────────────────
def ch_line(df, kws, stacked=False):
    fig = go.Figure()
    for i, kw in enumerate(kws):
        if kw not in df.columns:
            continue
        c = PAL[i % len(PAL)]
        kw_args = dict(
            x=df.index, y=df[kw], name=kw,
            line=dict(color=c, width=2.4, shape="spline", smoothing=0.7),
            hovertemplate=f"<b>{kw}</b>: %{{y}}<extra></extra>",
        )
        if stacked:
            fig.add_trace(go.Scatter(**kw_args, mode="lines", stackgroup="one",
                                     fillcolor=rgba(c, .32)))
        else:
            fig.add_trace(go.Scatter(**kw_args, mode="lines", fill="tozeroy",
                                     fillcolor=rgba(c, .07)))
    fig.update_layout(**BL, height=380)
    return fig


def ch_corr(df, kws):
    valid = [k for k in kws if k in df.columns]
    if len(valid) < 2:
        return None
    corr = df[valid].corr().round(3)
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns, y=corr.index,
        colorscale=[[0, "#ff6b6b"], [.5, "#16162a"], [1, "#00e5c3"]],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(family="Space Mono", size=12),
        hovertemplate="%{x} × %{y}<br>r = %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(**BL, height=280)
    return fig


def ch_geo_map(geo_df, kw):
    if kw not in geo_df.columns or geo_df.empty:
        return None
    d = geo_df[[kw]].reset_index()
    d.columns = ["location", "value"]
    d = d[d["value"] > 0]
    fig = px.choropleth(
        d, locations="location", locationmode="country names", color="value",
        hover_name="location", labels={"value": "Interest"},
        color_continuous_scale=[[0, "#07070e"], [.3, "#2e1a6e"], [.7, "#7c5cfc"], [1, "#00e5c3"]],
    )
    fig.update_layout(
        **BL, height=350,
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
    idx = geo_df[valid].sum(axis=1).nlargest(top).index
    sub = geo_df.loc[idx, valid]
    fig = go.Figure()
    for i, kw in enumerate(valid):
        c = PAL[i % len(PAL)]
        fig.add_trace(go.Bar(x=sub.index, y=sub[kw], name=kw,
                             marker_color=c, marker_line_width=0,
                             hovertemplate=f"<b>%{{x}}</b><br>{kw}: %{{y}}<extra></extra>"))
    fig.update_layout(**BL, height=300, barmode="group", bargap=0.18)
    return fig


def ch_bar_avg(df, kws):
    avgs = {k: round(df[k].mean(), 1) for k in kws if k in df.columns}
    ks = sorted(avgs, key=avgs.get, reverse=True)
    fig = go.Figure()
    for i, kw in enumerate(ks):
        fig.add_trace(go.Bar(x=[kw], y=[avgs[kw]], name=kw,
                             marker_color=PAL[i % len(PAL)], marker_line_width=0,
                             hovertemplate=f"<b>{kw}</b><br>Avg: %{{y:.1f}}<extra></extra>"))
    fig.update_layout(**BL, height=280, showlegend=False, barmode="group", bargap=0.3)
    return fig


def ch_box(df, kws):
    fig = go.Figure()
    for i, kw in enumerate(kws):
        if kw not in df.columns:
            continue
        c = PAL[i % len(PAL)]
        fig.add_trace(go.Box(y=df[kw], name=kw, marker_color=c, line_color=c,
                             fillcolor=rgba(c, .15), boxmean="sd",
                             hovertemplate=f"<b>{kw}</b><br>%{{y}}<extra></extra>"))
    fig.update_layout(**BL, height=280, showlegend=False)
    return fig


def ch_radar(df, kws):
    avgs = {k: df[k].mean() for k in kws if k in df.columns}
    if len(avgs) < 2:
        return None
    ks, vs = list(avgs.keys()), list(avgs.values())
    fig = go.Figure(go.Scatterpolar(
        r=vs + [vs[0]], theta=ks + [ks[0]],
        fill="toself", fillcolor=rgba("#7c5cfc", .2),
        line=dict(color="#7c5cfc", width=2),
        marker=dict(color="#00e5c3", size=8),
    ))
    fig.update_layout(
        **BL, height=300,
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
            line=dict(color=c, width=2.4),
            hovertemplate=f"<b>{kw}</b><br>%{{x}}<br>Rolling avg: %{{y:.1f}}<extra></extra>",
        ))
    fig.update_layout(**BL, height=280)
    return fig


def ch_momentum(df, kws):
    q = max(1, len(df) // 4)
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
    fig.update_layout(**BL, height=255, showlegend=False, yaxis_title="% Change")
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
    fig.update_layout(**BL, height=280, showlegend=False,
                      yaxis=dict(autorange="reversed", **BL["yaxis"]),
                      title_text=title, title_font=dict(size=12))
    return fig


def styled_table(df: pd.DataFrame):
    """
    Render a dataframe with custom inline HTML styling —
    zero matplotlib dependency.
    """
    cols = list(df.columns)
    rows_html = ""
    for _, row in df.iterrows():
        row_html = f"<tr><td style='color:#7777aa;font-weight:700;padding:5px 10px;white-space:nowrap;'>{row.name}</td>"
        for col in cols:
            val = row[col]
            # Colour numeric cells by magnitude
            if isinstance(val, (int, float)) and not pd.isna(val):
                intensity = min(int(val / 100 * 180), 180)
                bg = f"rgba(124,92,252,{intensity/255:.2f})"
                row_html += f"<td style='padding:5px 10px;background:{bg};text-align:right;'>{val}</td>"
            else:
                row_html += f"<td style='padding:5px 10px;text-align:right;'>{val}</td>"
        rows_html += row_html + "</tr>"

    header_html = "<tr><th style='padding:5px 10px;'></th>" + "".join(
        f"<th style='padding:5px 10px;color:#7777aa;font-family:Space Mono,monospace;"
        f"font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;text-align:right;'>{c}</th>"
        for c in cols
    ) + "</tr>"

    return f"""
    <div style='overflow-x:auto;'>
    <table style='width:100%;border-collapse:collapse;font-family:Space Mono,monospace;
                  font-size:.72rem;color:#e8e8f8;background:#0f0f1a;
                  border:1px solid #252540;border-radius:8px;overflow:hidden;'>
      <thead style='border-bottom:1px solid #252540;'>{header_html}</thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown("""
    <div style='padding:.9rem 0 1rem;'>
      <div style='font-family:Syne,sans-serif;font-weight:800;font-size:1.4rem;
                  background:linear-gradient(135deg,#7c5cfc,#00e5c3);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;'>
        TREND PULSE
      </div>
      <div style='font-family:Space Mono,monospace;font-size:.55rem;color:#7777aa;
                  letter-spacing:.16em;text-transform:uppercase;margin-top:.12rem;'>
        Google Trends Explorer v4
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sh">Keywords (max 5)</div>', unsafe_allow_html=True)
    raw = st.text_area("kw", value="ChatGPT\nGemini\nClaude AI\nCopilot",
                       height=110, label_visibility="collapsed")
    keywords = [k.strip() for k in raw.strip().splitlines() if k.strip()][:5]

    st.markdown('<div class="sh">Settings</div>', unsafe_allow_html=True)
    tf_lbl  = st.selectbox("Time Period", list(TIME_OPTS), index=6)
    geo_lbl = st.selectbox("Region", list(GEO_OPTS), index=2)
    cat_lbl = st.selectbox("Category", list(CAT_OPTS), index=0)
    mode    = st.radio("Chart Style", ["Line", "Stacked Area"], horizontal=True)

    st.markdown('<div class="sh">Mode</div>', unsafe_allow_html=True)
    demo_toggle = st.toggle(
        "Demo Mode (no Google calls)",
        value=st.session_state.demo_mode,
        help="Enables instant mock data — useful when Google rate-limits you (429).",
    )
    st.session_state.demo_mode = demo_toggle

    if st.button("🗑  Clear Cache", use_container_width=True):
        st.session_state.req_cache = {}
        st.session_state.last_call_ts = 0.0
        st.toast("Cache cleared!", icon="✅")

    st.markdown("")
    run = st.button("⚡  ANALYZE TRENDS", use_container_width=True)

    st.markdown("""
    <div style='margin-top:1.2rem;padding:.8rem;background:#0f0f1a;border:1px solid #252540;
                border-radius:10px;font-family:Space Mono,monospace;font-size:.55rem;color:#7777aa;'>
      <div style='color:#7c5cfc;margin-bottom:.3rem;font-weight:700;'>ℹ  HOW IT WORKS</div>
      • Values normalized 0–100<br>
      • 100 = peak of interest<br>
      • Auto-retry on 429 (×4)<br>
      • Falls back to demo data<br>
      • Session cache avoids re-calls<br>
      • urllib3 v2 compatible ✓
    </div>""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HEADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
hc1, hc2 = st.columns([4, 1])
with hc1:
    st.markdown('<p class="hero-title">Trend Pulse</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Real-time search interest comparison · Google Trends</p>',
                unsafe_allow_html=True)
with hc2:
    st.markdown(f"""
    <div style='text-align:right;padding-top:.5rem;'>
      <div style='font-family:Space Mono;font-size:.56rem;color:#7777aa;'>LIVE AS OF</div>
      <div style='font-family:Syne;font-weight:800;font-size:.95rem;color:#00e5c3;'>
        {datetime.now().strftime('%H:%M · %d %b %Y')}
      </div>
      <div style='font-family:Space Mono;font-size:.54rem;color:#7777aa;margin-top:.18rem;'>
        {geo_lbl} &nbsp;·&nbsp; {tf_lbl}
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<hr style='margin:.6rem 0 .45rem;'>", unsafe_allow_html=True)

# Chips
if keywords:
    chips = "".join(
        f"<span class='chip' style='color:{PAL[i%len(PAL)]};border-color:{PAL[i%len(PAL)]}44;"
        f"background:{PAL[i%len(PAL)]}12;'>{kw}</span>"
        for i, kw in enumerate(keywords)
    )
    st.markdown(f"<div style='margin-bottom:.8rem;'>{chips}</div>", unsafe_allow_html=True)

if not keywords:
    st.info("Enter keywords in the sidebar, then click **ANALYZE TRENDS**.")
    st.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FETCH MAIN DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
tf  = TIME_OPTS[tf_lbl]
geo = GEO_OPTS[geo_lbl]
cat = CAT_OPTS[cat_lbl]
kws = tuple(keywords)

with st.spinner("Fetching trend data…"):
    df, fetch_err, is_demo = get_over_time(kws, tf, geo, cat)

if is_demo:
    banner_msg = (
        "📊 **Demo Mode active** — showing simulated data."
        if st.session_state.demo_mode
        else f"⚠️ **Google returned a 429 / error** — showing demo data instead. "
             f"Enable *Demo Mode* in the sidebar to skip Google calls entirely, "
             f"or wait a few minutes and try again."
    )
    st.markdown(f'<div class="demo-banner">{banner_msg}</div>', unsafe_allow_html=True)

if df is None or df.empty:
    st.error("No data available. Try changing keywords or switching to Demo Mode.")
    st.stop()

valid = [k for k in keywords if k in df.columns]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# METRIC CARDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown('<div class="sh">Summary Statistics</div>', unsafe_allow_html=True)
mc = st.columns(len(valid))
for i, kw in enumerate(valid):
    s = df[kw]
    cur   = int(s.iloc[-1])
    peak  = int(s.max())
    avg   = float(s.mean())
    delta = int(s.iloc[-1]) - int(s.iloc[-2]) if len(s) > 1 else 0
    bc, bt = (("bup", f"↑ {abs(delta)}") if delta > 0
              else ("bdn", f"↓ {abs(delta)}") if delta < 0
              else ("bfl", "→ flat"))
    c  = PAL[i % len(PAL)]
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        fc = ch_corr(df, valid)
        if fc:
            st.plotly_chart(fc, use_container_width=True, config={"displayModeBar": False})

    with st.expander("📋  Raw Data — inspect & download"):
        # Plain dataframe — NO .style.background_gradient (no matplotlib needed)
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇  Download CSV", df.to_csv().encode(),
                           "trends_data.csv", "text/csv", use_container_width=True)

# ── Tab 2 ─────────────────────────────────────────────────────────────────────
with t2:
    with st.spinner("Loading geographic data…"):
        gdf, g_demo = get_by_region(kws, tf, geo, cat)

    if g_demo and not st.session_state.demo_mode:
        st.warning("Geographic data fell back to demo due to rate limiting.")

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
        st.info("No geographic data available.")

# ── Tab 3 ─────────────────────────────────────────────────────────────────────
with t3:
    with st.spinner("Loading related queries…"):
        rel, rq_demo = get_related(kws, tf, geo, cat)

    if rq_demo and not st.session_state.demo_mode:
        st.warning("Related queries fell back to demo due to rate limiting.")

    if rel:
        for i, kw in enumerate(valid):
            if kw not in rel or not rel[kw]:
                continue
            c = PAL[i % len(PAL)]
            with st.expander(f"🔑  {kw}", expanded=(i == 0)):
                lc, rc = st.columns(2)
                with lc:
                    f = ch_related_bar(rel[kw].get("top"), c, "🏆 Top Queries")
                    if f:
                        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})
                    else:
                        st.caption("No top queries.")
                with rc:
                    f = ch_related_bar(rel[kw].get("rising"), "#00e5c3", "🚀 Rising Queries")
                    if f:
                        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})
                    else:
                        st.caption("No rising queries.")
    else:
        st.info("No related queries data.")

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
        if fr:
            st.plotly_chart(fr, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Radar chart needs ≥ 2 keywords.")

        st.markdown('<div class="sh">7-Day Rolling Average</div>', unsafe_allow_html=True)
        st.plotly_chart(ch_rolling(df, valid), use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="sh">Trend Momentum · First vs Last Quarter</div>', unsafe_allow_html=True)
    fm = ch_momentum(df, valid)
    if fm:
        st.plotly_chart(fm, use_container_width=True, config={"displayModeBar": False})

    # Descriptive stats — custom HTML table (no matplotlib)
    st.markdown('<div class="sh">Descriptive Statistics</div>', unsafe_allow_html=True)
    stats = df[valid].describe().T.round(2)
    st.markdown(styled_table(stats), unsafe_allow_html=True)

# ── Tab 5 ─────────────────────────────────────────────────────────────────────
with t5:
    st.markdown('<div class="sh">Currently Trending Searches</div>', unsafe_allow_html=True)
    with st.spinner("Fetching trending…"):
        tdf, t_demo = get_trending(geo)

    if t_demo and not st.session_state.demo_mode:
        st.warning("Trending data fell back to demo due to rate limiting.")

    if not tdf.empty:
        tdf.columns = ["Trending Query"]
        tdf = tdf.head(25).reset_index(drop=True)
        tdf.index += 1
        rows_html = ""
        for idx, row in tdf.iterrows():
            c = PAL[(idx - 1) % len(PAL)]
            rows_html += (
                f"<div style='display:flex;align-items:center;gap:.75rem;padding:.42rem .8rem;"
                f"margin-bottom:.28rem;background:#0f0f1a;border:1px solid #252540;"
                f"border-radius:8px;border-left:3px solid {c};'>"
                f"<span style='font-family:Space Mono;font-size:.6rem;color:{c};font-weight:700;min-width:1.3rem;'>{idx:02d}</span>"
                f"<span style='font-family:Syne;font-size:.88rem;color:#e8e8f8;'>{row['Trending Query']}</span>"
                f"</div>"
            )
        st.markdown(rows_html, unsafe_allow_html=True)
    else:
        st.info("Trending data unavailable. Try United States or enable Demo Mode.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr style='margin-top:1.8rem;'>", unsafe_allow_html=True)
st.markdown(f"""
<div style='font-family:Space Mono,monospace;font-size:.54rem;color:#7777aa;
            display:flex;justify-content:space-between;padding:.35rem 0 1rem;flex-wrap:wrap;gap:.35rem;'>
  <span>TREND PULSE v4 &nbsp;·&nbsp; urllib3 v2 ✓ &nbsp;·&nbsp; no matplotlib ✓</span>
  <span>{geo_lbl} &nbsp;·&nbsp; {tf_lbl} &nbsp;·&nbsp; {cat_lbl}</span>
  <span>{'⚡ DEMO DATA' if (is_demo or st.session_state.demo_mode) else '🌐 LIVE DATA'} &nbsp;·&nbsp; pytrends</span>
</div>""", unsafe_allow_html=True)