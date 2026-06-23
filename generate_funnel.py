import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import date, timedelta

# --- Executive Dashboard Configuration ---
st.set_page_config(page_title="Executive Funnel Review & Conversion Insights", layout="wide")

# Global High-Contrast Styling Tokens
st.markdown("""
<style>
    .up { color: #4a9e2f !important; font-weight: 600; }
    .dn { color: #e05252 !important; font-weight: 600; }
    .fl { color: #888888 !important; }
    .bold { font-weight: 600; }
    .pill { display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 20px; font-size: 11px; font-weight: 600; }
    .pg { background-color: rgba(74,158,47,0.15); color: #4a9e2f; }
    .pa { background-color: rgba(212,137,26,0.15); color: #d4891a; }
    .pr { background-color: rgba(224,82,82,0.15); color: #e05252; }
    .pb { background-color: rgba(47,125,212,0.15); color: #2f7dd4; }
</style>
""", unsafe_allow_html=True)

# --- 1. Live API Data Fetching Engine ---
@st.cache_data(ttl=1800)
def fetch_and_compile_data():
    api_url = "https://redash.vahan.link/api/queries/17631/results.json"
    api_key = "4aFm2iOoyx8I91svQccdeZr0jmaiUsMFSRinZcmu"
    
    try:
        response = requests.get(api_url, params={"api_key": api_key}, timeout=45)
        response.raise_for_status()
        rows = response.json()["query_result"]["data"]["rows"]
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Critical Ingestion Pipeline Failure: {e}")
        return pd.DataFrame()

df_raw = fetch_and_compile_data()

if df_raw.empty:
    st.error("Data pipeline is empty. Please verify query execution state on Redash.")
    st.stop()

# Force clean, concrete numeric types across core funnel indicators
df_raw['day'] = pd.to_datetime(df_raw['day']).dt.date
df_raw['week'] = pd.to_datetime(df_raw['week']).dt.date
for col in ['ls', 'uniq', 'ob', 'ft']:
    if col in df_raw.columns:
        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)

# --- 2. Global Filter Dimension Definitions ---
allClients = sorted(list(df_raw['client'].dropna().unique()))
allRegions = sorted(list(df_raw['region'].dropna().unique()))
allVLs = sorted(list(df_raw['vl_name'].dropna().unique()))
allCLs = sorted(list(df_raw['cl'].dropna().unique()))
allAMs = sorted(list(df_raw['am_name'].dropna().unique()))
allWeeks = sorted(list(df_raw['week'].dropna().unique()), reverse=True)

# --- 3. Sidebar Filter Panel Architecture ---
st.sidebar.header("⏱️ Operational Scope")

# The Master Week Slicer
anchor_week = st.sidebar.selectbox("📅 Master Week Slicer", options=allWeeks, help="Select a week to act as 'Present Day'. Both MTD and WTD scopes will calculate accurately based on this anchor.")
operational_today = df_raw[df_raw['week'] == anchor_week]['day'].max()

view_mode = st.sidebar.radio("Time Aggregation Scope", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])

reference_date = operational_today

# Replicate exact apples-to-apples baseline boundaries
if view_mode == "MTD (Month-to-Date)":
    curr_start = reference_date.replace(day=1)
    curr_end = reference_date
    
    prev_month = 12 if curr_start.month == 1 else curr_start.month - 1
    prev_year = curr_start.year - 1 if curr_start.month == 1 else curr_start.year
    prev_start = date(prev_year, prev_month, 1)
    try:
        prev_end = date(prev_year, prev_month, reference_date.day)
    except ValueError:
        prev_end = (date(prev_year, prev_month + 1, 1) - timedelta(days=1))
else:
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    curr_end = reference_date
    prev_start = curr_start - timedelta(days=7)
    prev_end = curr_end - timedelta(days=7)

# --- Sidebar Multi-Select Slicers Suite ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Funnel Filters")
st.caption("Filters isolated segments within your selected timeframe.")

selected_clients = st.sidebar.multiselect("Filter by Client", options=["All"] + allClients, default=["All"])
selected_regions = st.sidebar.multiselect("Filter by Region", options=["All"] + allRegions, default=["All"])
selected_vls = st.sidebar.multiselect("Filter by Vahan Leader (VL)", options=["All"] + allVLs, default=["All"])
selected_cls = st.sidebar.multiselect("Filter by Core Leader (CL)", options=["All"] + allCLs, default=["All"])
selected_ams = st.sidebar.multiselect("Filter by Account Manager (AM)", options=["All"] + allAMs, default=["All"])

# --- Secured Gemini API Key Vault ---
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI Integration Active")
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("Gemini Assistant is online (Secured via st.secrets).")
except KeyError:
    st.sidebar.error("API Key not found in st.secrets. AI features disabled.")
    gemini_api_key = None

# Generate segmented baseline dataframes
df_curr = df_raw[(df_raw['day'] >= curr_start) & (df_raw['day'] <= curr_end)]
df_prev = df_raw[(df_raw['day'] >= prev_start) & (df_raw['day'] <= prev_end)]

def apply_dimensional_filters(target_df):
    if not target_df.empty:
        if selected_clients and "All" not in selected_clients:
            target_df = target_df[target_df['client'].isin(selected_clients)]
        if selected_regions and "All" not in selected_regions:
            target_df = target_df[target_df['region'].isin(selected_regions)]
        if selected_vls and "All" not in selected_vls:
            target_df = target_df[target_df['vl_name'].isin(selected_vls)]
        if selected_cls and "All" not in selected_cls:
            target_df = target_df[target_df['cl'].isin(selected_cls)]
        if selected_ams and "All" not in selected_ams:
            target_df = target_df[target_df['am_name'].isin(selected_ams)]
    return target_df

df_curr = apply_dimensional_filters(df_curr)
df_prev = apply_dimensional_filters(df_prev)

# --- 4. Executive Top-Banner Component ---
st.info(f"📅 **Active Constraints Matrix Window** | **Current Scope:** `{curr_start}` to `{curr_end}` vs **Matching Historical Baseline:** `{prev_start}` to `{prev_end}`")

# --- 5. Global Core Data Sorters & Tables Formatting Engines ---
def get_colored_delta(v, suffix=""):
    if v is None or pd.isna(v): return "—"
    if v == 0: return f"0{suffix}"
    cl = "up" if v > 0 else "dn"
    sign = "+" if v > 0 else ""
    if suffix in ["pp", "%"]:
        return f'<span class="{cl}">{sign}{abs(v):.2f}{suffix}</span>'
    
    val = abs(v)
    if val >= 1e6: f_val = f"{val/1e6:.1f}M"
    elif val >= 1e3: f_val = f"{val:,.0f}"
    else: f_val = str(val)
    return f'<span class="{cl}">{sign}{f_val}</span>'

def get_pill_pct(p, metric_type):
    if p is None or pd.isna(p): return "—"
    v = round(p)
    if metric_type == 'uniq':
        cl = 'pg' if v >= 40 else ('pa' if v >= 20 else 'pr')
    elif metric_type == 'ob':
        cl = 'pg' if v >= 5 else ('pa' if v >= 1 else 'pr')
    else:
        cl = 'pg' if v >= 60 else ('pa' if v >= 40 else 'pr')
    return f'<span class="pill {cl}">{v}%</span>'

def transform_to_replicated_dataframe(rows_list):
    processed = []
    for r in rows_list:
        vj, vm = r["jun"], r["may"]
        
        up_j = round((vj["uniqueness"] / vj["ls"] * 100), 2) if vj["ls"] > 0 else 0.0
        up_m = round((vm["uniqueness"] / vm["ls"] * 100), 2) if vm["ls"] > 0 else 0.0
        
        op_j = round((vj["ob"] / vj["uniqueness"] * 100), 2) if vj["uniqueness"] > 0 else (round((vj["ob"] / vj["ls"] * 100), 2) if vj["ls"] > 0 else 0.0)
        const_base_p = vm["uniqueness"] if vm["uniqueness"] > 0 else vm["ls"]
        op_m = round((vm["ob"] / const_base_p * 100), 2) if const_base_p > 0 else 0.0
        
        fp_j = round((vj["ft"] / vj["ob"] * 100), 2) if vj["ob"] > 0 else 0.0
        fp_m = round((vm["ft"] / vm["ob"] * 100), 2) if vm["ob"] > 0 else 0.0

        processed.append({
            "Dimension": r["dim"],
            "LS (Lead Share) Jun": vj["ls"], "LS (Lead Share) May": vm["ls"], "LS Δ": vj["ls"] - vm["ls"], "LS Δ%": round(((vj["ls"] - vm["ls"]) / vm["ls"] * 100), 1) if vm["ls"] > 0 else None,
            "Unique Jun": vj["uniqueness"], "Unique May": vm["uniqueness"], "Unique Δ": vj["uniqueness"] - vm["uniqueness"],
            "Uniq%": up_j, "Uniq Δpp": round(up_j - up_m, 2),
            "OB (Onboarded) Jun": vj["ob"], "OB (Onboarded) May": vm["ob"], "OB Δ": vj["ob"] - vm["ob"],
            "OB%": op_j, "OB Δpp": round(op_j - op_m, 2),
            "FT (First Trip) Jun": vj["ft"], "FT (First Trip) May": vm["ft"], "FT Δ": vj["ft"] - vm["ft"], "FT Δ%": round(((vj["ft"] - vm["ft"]) / vm["ft"] * 100), 1) if vm["ft"] > 0 else None,
            "FT/OB%": fp_j, "FT/OB Δpp": round(fp_j - fp_m, 2)
        })
    return pd.DataFrame(processed)

def display_replicated_table(df, key_prefix):
    if df.empty:
        st.write("No metrics matching active filter states.")
        return
        
    ordered_cols = [
        "Dimension", "LS (Lead Share) Jun", "LS (Lead Share) May", "LS Δ", "LS Δ%", "Unique Jun", "Unique May", "Unique Δ",
        "Uniq%", "Uniq Δpp", "OB (Onboarded) Jun", "OB (Onboarded) May", "OB Δ", "OB%", "OB Δpp", "FT (First Trip) Jun", "FT (First Trip) May",
        "FT Δ", "FT Δ%", "FT/OB%", "FT/OB Δpp"
    ]
    df = df[ordered_cols].copy()
    
    formatted_html = f"<table id='table_{key_prefix}'><thead><tr>" + "".join([f"<th>{col} ↕</th>" for col in ordered_cols]) + "</tr></thead><tbody>"
    
    for _, r in df.iterrows():
        ls_class = "up" if r["LS Δ"] > 0 else ("dn" if r["LS Δ"] < 0 else "")
        uniq_class = "up" if r["Unique Δ"] > 0 else ("dn" if r["Unique Δ"] < 0 else "")
        ob_class = "up" if r["OB Δ"] > 0 else ("dn" if r["OB Δ"] < 0 else "")
        ft_class = "up" if r["FT Δ"] > 0 else ("dn" if r["FT Δ"] < 0 else "")

        formatted_html += "<tr>"
        formatted_html += f"<td class='bold sticky-col'>{r['Dimension']}</td>"
        formatted_html += f"<td><span class='{ls_class}'>{r['LS (Lead Share) Jun']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r['LS (Lead Share) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['LS Δ%'], '%')}</td>"
        formatted_html += f"<td><span class='{uniq_class}'>{r['Unique Jun']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r['Unique May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Unique Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['Uniq Δpp'], 'pp')}</td>"
        formatted_html += f"<td><span class='{ob_class}'>{r['OB (Onboarded) Jun']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r['OB (Onboarded) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δ'])}</td>"
        formatted_html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['OB Δpp'], 'pp')}</td>"
        formatted_html += f"<td class='bold'><span class='{ft_class}'>{r['FT (First Trip) Jun']:,}</span></td>"
        formatted_html += f"<td class='fl'>{r['FT (First Trip) May']:,}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ'])}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT Δ%'], '%')}</td>"
        formatted_html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td>"
        formatted_html += f"<td>{get_colored_delta(r['FT/OB Δpp'], 'pp')}</td>"
        formatted_html += "</tr>"
        
    formatted_html += "</tbody></table>"
    
    st.iframe(f"""
    <style>
        body {{ background-color: #ffffff !important; color: #111111 !important; margin: 0; padding: 0; }}
        .table-container {{ width: 100%; height: 100vh; overflow: auto; position: relative; }}
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 12px; color: #111111 !important; }}
        
        th {{ 
            position: sticky; 
            top: 0; 
            z-index: 2; 
            text-align: left; 
            background: #f7f6f3 !important; 
            padding: 6px 8px; 
            border-bottom: 1px solid #eceae4; 
            font-size: 11px; 
            color: #666666 !important; 
            white-space: nowrap; 
            cursor: pointer; 
            user-select: none; 
            box-shadow: 0 1px 0 #eceae4; 
        }}
        
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; color: #111111 !important; background-color: #ffffff; }}
        tr:hover td {{ background-color: #f7f6f3 !important; }}
        
        td:first-child, th:first-child {{ position: sticky; left: 0; z-index: 1; border-right: 1px solid rgba(0,0,0,0.08); }}
        td:first-child {{ background-color: #ffffff; }}
        tr:hover td:first-child {{ background-color: #f7f6f3 !important; }}
        th:first-child {{ z-index: 3; background-color: #f7f6f3 !important; border-right: 1px solid #eceae4; }}

        .bold {{ font-weight: 600; color: #111111 !important; }}
        .fl {{ color: #888888 !important; }}
        .up {{ color: #4a9e2f !important; font-weight: 600; }}
        .dn {{ color: #e05252 !important; font-weight: 600; }}
        .pill {{ display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    <div class="table-container">
        {formatted_html}
    </div>
    <script>
    document.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {{
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const index = Array.from(th.parentNode.children).indexOf(th);
        const asc = th.dataset.asc = !th.dataset.asc;
        
        rows.sort((rowA, rowB) => {{
            let cellA = rowA.children[index].innerText.replace(/[%|,|pp|M|K|+|↕]/g, '').trim();
            let cellB = rowB.children[index].innerText.replace(/[%|,|pp|M|K|+|↕]/g, '').trim();
            const numA = parseFloat(cellA);
            const numB = parseFloat(cellB);
            if (!isNaN(numA) && !isNaN(numB)) return asc ? numA - numB : numB - numA;
            return asc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        }});
        tbody.append(...rows);
    }})));
    </script>
    """, height=max(140, min(550, len(df)*32 + 50)))

# --- Dedicated HTML Renderer for Rolling Trends Table (WITH WoW DELTAS) ---
def display_trend_table(df_trend, group_cols, key_prefix):
    if df_trend.empty:
        st.write("No trend data available for selected parameters.")
        return
        
    grp = df_trend.groupby(group_cols)[['ls', 'uniq', 'ob', 'ft']].sum().reset_index()
    
    # Base Conversion Percents
    grp['Uniq%'] = grp.apply(lambda r: round(r['uniq']/r['ls']*100, 1) if r['ls']>0 else 0.0, axis=1)
    grp['OB%'] = grp.apply(lambda r: round(r['ob']/r['uniq']*100, 1) if r['uniq']>0 else (round(r['ob']/r['ls']*100, 1) if r['ls']>0 else 0.0), axis=1)
    grp['FT/OB%'] = grp.apply(lambda r: round(r['ft']/r['ob']*100, 1) if r['ob']>0 else 0.0, axis=1)
    
    # Calculate Week-over-Week Deltas (Requires strict chronological sorting first)
    if 'client' in group_cols:
        grp = grp.sort_values(by=['client', 'week'], ascending=[True, True])
        grp['LS Δ'] = grp.groupby('client')['ls'].diff()
        grp['LS Δ%'] = grp.groupby('client')['ls'].pct_change() * 100
        grp['Uniq Δ'] = grp.groupby('client')['uniq'].diff()
        grp['Uniq Δ%'] = grp.groupby('client')['uniq'].pct_change() * 100
        grp['Uniq% Δpp'] = grp.groupby('client')['Uniq%'].diff()
        grp['OB Δ'] = grp.groupby('client')['ob'].diff()
        grp['OB Δ%'] = grp.groupby('client')['ob'].pct_change() * 100
        grp['OB% Δpp'] = grp.groupby('client')['OB%'].diff()
        grp['FT Δ'] = grp.groupby('client')['ft'].diff()
        grp['FT Δ%'] = grp.groupby('client')['ft'].pct_change() * 100
        grp['FT/OB% Δpp'] = grp.groupby('client')['FT/OB%'].diff()
        # Re-sort for reverse chronological viewing (Newest Top)
        grp = grp.sort_values(by=['client', 'week'], ascending=[True, False])
    else:
        grp = grp.sort_values(by=['week'], ascending=[True])
        grp['LS Δ'] = grp['ls'].diff()
        grp['LS Δ%'] = grp['ls'].pct_change() * 100
        grp['Uniq Δ'] = grp['uniq'].diff()
        grp['Uniq Δ%'] = grp['uniq'].pct_change() * 100
        grp['Uniq% Δpp'] = grp['Uniq%'].diff()
        grp['OB Δ'] = grp['ob'].diff()
        grp['OB Δ%'] = grp['ob'].pct_change() * 100
        grp['OB% Δpp'] = grp['OB%'].diff()
        grp['FT Δ'] = grp['ft'].diff()
        grp['FT Δ%'] = grp['ft'].pct_change() * 100
        grp['FT/OB% Δpp'] = grp['FT/OB%'].diff()
        grp = grp.sort_values(by=['week'], ascending=[False])

    # Clean Infinities and NaNs for standard formatting
    grp = grp.replace([np.inf, -np.inf], np.nan)
    grp = grp.where(pd.notnull(grp), None)
        
    headers = [col.title() for col in group_cols] + [
        "LS", "LS Δ", "LS Δ%", 
        "Unique", "Uniq Δ", "Uniq Δ%", "Uniq%", "Uniq% Δpp", 
        "OB", "OB Δ", "OB Δ%", "OB%", "OB% Δpp", 
        "FT", "FT Δ", "FT Δ%", "FT/OB%", "FT/OB% Δpp"
    ]
    
    html = f"<table id='trend_{key_prefix}'><thead><tr>"
    for h in headers: html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"
    
    for _, r in grp.iterrows():
        html += "<tr>"
        for idx, col in enumerate(group_cols):
            css_class = "bold sticky-col" if idx == 0 else "bold"
            html += f"<td class='{css_class}'>{r[col]}</td>"
            
        html += f"<td>{int(r['ls']):,}</td>"
        html += f"<td>{get_colored_delta(r['LS Δ'])}</td>"
        html += f"<td>{get_colored_delta(r['LS Δ%'], '%')}</td>"
        
        html += f"<td>{int(r['uniq']):,}</td>"
        html += f"<td>{get_colored_delta(r['Uniq Δ'])}</td>"
        html += f"<td>{get_colored_delta(r['Uniq Δ%'], '%')}</td>"
        html += f"<td>{get_pill_pct(r['Uniq%'], 'uniq')}</td>"
        html += f"<td>{get_colored_delta(r['Uniq% Δpp'], 'pp')}</td>"
        
        html += f"<td>{int(r['ob']):,}</td>"
        html += f"<td>{get_colored_delta(r['OB Δ'])}</td>"
        html += f"<td>{get_colored_delta(r['OB Δ%'], '%')}</td>"
        html += f"<td>{get_pill_pct(r['OB%'], 'ob')}</td>"
        html += f"<td>{get_colored_delta(r['OB% Δpp'], 'pp')}</td>"
        
        html += f"<td class='bold'>{int(r['ft']):,}</td>"
        html += f"<td>{get_colored_delta(r['FT Δ'])}</td>"
        html += f"<td>{get_colored_delta(r['FT Δ%'], '%')}</td>"
        html += f"<td>{get_pill_pct(r['FT/OB%'], 'ft')}</td>"
        html += f"<td>{get_colored_delta(r['FT/OB% Δpp'], 'pp')}</td>"
        html += "</tr>"
        
    html += "</tbody></table>"
    
    st.iframe(f"""
    <style>
        body {{ background-color: #ffffff !important; color: #111111 !important; margin: 0; padding: 0; }}
        .table-container {{ width: 100%; height: 100vh; overflow: auto; position: relative; }}
        table {{ width: 100%; border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 12px; color: #111111 !important; }}
        th {{ position: sticky; top: 0; z-index: 2; text-align: left; background: #f7f6f3 !important; padding: 6px 8px; border-bottom: 1px solid #eceae4; font-size: 11px; color: #666666 !important; white-space: nowrap; box-shadow: 0 1px 0 #eceae4; }}
        td {{ padding: 6px 8px; border-bottom: 0.5px solid rgba(0,0,0,0.08); white-space: nowrap; color: #111111 !important; background-color: #ffffff; }}
        tr:hover td {{ background-color: #f7f6f3 !important; }}
        td:first-child, th:first-child {{ position: sticky; left: 0; z-index: 1; border-right: 1px solid rgba(0,0,0,0.08); }}
        td:first-child {{ background-color: #ffffff; }}
        tr:hover td:first-child {{ background-color: #f7f6f3 !important; }}
        th:first-child {{ z-index: 3; background-color: #f7f6f3 !important; border-right: 1px solid #eceae4; }}
        .bold {{ font-weight: 600; color: #111111 !important; }}
        .fl {{ color: #888888 !important; }}
        .up {{ color: #4a9e2f !important; font-weight: 600; }}
        .dn {{ color: #e05252 !important; font-weight: 600; }}
        .pill {{ display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 600; }}
        .pg {{ background: rgba(74,158,47,0.15); color: #4a9e2f; }}
        .pa {{ background: rgba(212,137,26,0.15); color: #d4891a; }}
        .pr {{ background: rgba(224,82,82,0.15); color: #e05252; }}
    </style>
    <div class="table-container">{html}</div>
    """, height=max(140, min(550, len(grp)*32 + 50)))

# --- Hardened API Retry Engine ---
def call_gemini_with_retries(api_key, payload, max_retries=3):
    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"]
    headers = {'Content-Type': 'application/json'}
    
    last_error = None
    for model in models_to_try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(max_retries):
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    return {"status": "success", "data": resp.json()}
                elif resp.status_code == 401:
                    return {"status": "error", "message": "Invalid API Key. Please verify your Gemini key in Google AI Studio."}
                elif resp.status_code == 404:
                    last_error = f"Model {model} is deprecated or unavailable (404)."
                    break 
                elif resp.status_code in [503, 429]:  
                    last_error = f"Model {model} overloaded (Status {resp.status_code})."
                    if attempt < max_retries - 1:
                        time.sleep((2 ** attempt) + 1)
                        continue
                    break 
                else:
                    return {"status": "error", "message": f"Status {resp.status_code}: {resp.text[:200]}"}
            except requests.exceptions.Timeout:
                last_error = f"Connection to {model} Timed Out."
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) + 1)
                    continue
                break
            except requests.exceptions.RequestException as e:
                last_error = f"Network Exception on {model}: {str(e)}"
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) + 1)
                    continue
                break
                
    return {"status": "error", "message": last_error}

# --- Dictionary Mapping User Selections to Actual DataFrame Columns ---
SORT_METRICS_MAP = {
    "FT Δ": "FT Δ",
    "LS Δ": "LS Δ",
    "Uniq Δ": "Unique Δ",
    "OB Δ": "OB Δ",
    "Uniq% Δpp": "Uniq Δpp",
    "OB% Δpp": "OB Δpp",
    "FT/OB% Δpp": "FT/OB Δpp",
    "LS Δ%": "LS Δ%",
    "FT Δ%": "FT Δ%",
    "FT Jun": "FT (First Trip) Jun",
    "LS Jun": "LS (Lead Share) Jun",
    "Uniq% Jun": "Uniq%",
    "OB% Jun": "OB%",
    "FT/OB% Jun": "FT/OB%"
}

# --- 6. Metrics Object Payload Compiler ---
def build_html_metric_payload(df_c, df_p):
    compiled = {}
    def get_pct(a, b): return round((a / b * 100), 2) if b > 0 else 0.0
    def get_pp(a, b): return round(a - b, 2)

    fj = {"ls": int(df_c['ls'].sum()), "uniqueness": int(df_c['uniq'].sum()), "ob": int(df_c['ob'].sum()), "ft": int(df_c['ft'].sum())}
    fm = {"ls": int(df_p['ls'].sum()), "uniqueness": int(df_p['uniq'].sum()), "ob": int(df_p['ob'].sum()), "ft": int(df_p['ft'].sum())}
    
    compiled["overall_funnel"] = {
        "ls_j": fj["ls"], "ls_m": fm["ls"], "ls_delta": fj["ls"] - fm["ls"],
        "uniq_j": fj["uniqueness"], "uniq_m": fm["uniqueness"], "uniq_delta": fj["uniqueness"] - fm["uniqueness"],
        "up_j": get_pct(fj["uniqueness"], fj["ls"]), "up_m": get_pct(fm["uniqueness"], fm["ls"]), "up_dp": get_pp(get_pct(fj["uniqueness"], fj["ls"]), get_pct(fm["uniqueness"], fm["ls"])),
        "ob_j": fj["ob"], "ob_m": fm["ob"], "ob_delta": fj["ob"] - fm["ob"],
        "op_j": get_pct(fj["ob"], fj["uniqueness"]), "op_m": get_pct(fm["ob"], fm["uniqueness"]), "op_dp": get_pp(get_pct(fj["ob"], fj["uniqueness"]), get_pct(fm["ob"], fm["uniqueness"])),
        "ft_j": fj["ft"], "ft_m": fm["ft"], "ft_delta": fj["ft"] - fm["ft"],
        "fp_j": get_pct(fj["ft"], fj["ob"]), "fp_m": get_pct(fm["ft"], fm["ob"]), "fp_dp": get_pp(get_pct(fj["ft"], fj["ob"]), get_pct(fm["ft"], fm["ob"]))
    }

    def roll_dim(df_w_c, df_w_p, dim_key):
        c_grp = df_w_c.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
        p_grp = df_w_p.groupby(dim_key)[['ls', 'uniq', 'ob', 'ft']].sum()
        m = c_grp.join(p_grp, lsuffix='_c', rsuffix='_p', how='outer').fillna(0)
        res = []
        for d, r in m.iterrows():
            res.append({
                "dim": str(d),
                "jun": {"ls": int(r['ls_c']), "uniqueness": int(r['uniq_c']), "ob": int(r['ob_c']), "ft": int(r['ft_c'])},
                "may": {"ls": int(r['ls_p']), "uniqueness": int(r['uniq_p']), "ob": int(r['ob_p']), "ft": int(r['ft_p'])}
            })
        return res

    compiled["by_client"] = roll_dim(df_c, df_p, 'client')
    compiled["by_product"] = roll_dim(df_c, df_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else roll_dim(df_c, df_p, 'client').copy()
    compiled["by_region"] = roll_dim(df_c, df_p, 'region')
    compiled["by_vl"] = roll_dim(df_c, df_p, 'vl_name')
    compiled["by_cl"] = roll_dim(df_c, df_p, 'cl')
    compiled["by_am"] = roll_dim(df_c, df_p, 'am_name')
    
    compiled["funnel_drill"] = {}
    for cl in df_c['client'].unique():
        sub_c = df_c[df_c['client'] == cl]
        sub_p = df_p[df_p['client'] == cl]
        compiled["funnel_drill"][cl] = {
            "by_product": roll_dim(sub_c, sub_p, 'lead_referral_type') if 'lead_referral_type' in df_c.columns else [],
            "by_region": roll_dim(sub_c, sub_p, 'region'),
            "by_vl": roll_dim(sub_c, sub_p, 'vl_name')
        }

    compiled["region_drill"] = {}
    for rg in df_c['region'].unique():
        sub_rg = df_c[df_c['region'] == rg]
        sub_rg_p = df_p[df_p['region'] == rg]
        compiled["region_drill"][rg] = {
            "by_vl": roll_dim(sub_rg, sub_rg_p, 'vl_name')
        }

    return compiled

payload = build_html_metric_payload(df_curr, df_prev)

# --- 7. Layout Nav Tabs Initialization ---
tab_ui, tab_trends, tab_rca, tab_chat = st.tabs(["📊 Funnel view", "📈 Rolling Trends", "✨ AI Summary", "💬 Ask AI"])

# ==========================================
# RENDER TAB: EXECUTIVE REPLICATED FUNNEL
# ==========================================
with tab_ui:
    st.markdown("### Executive Summary — Macro Funnel Conversion Checkpoints")
    fo = payload["overall_funnel"]
    
    st.iframe(f"""
    <style>
        body {{ background-color: transparent; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }}
        .row {{ display: flex; gap: 8px; }}
        .card {{ flex: 1; background: #ffffff !important; color: #111111 !important; border: 0.5px solid rgba(0,0,0,0.08); border-radius: 8px; padding: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
        .val {{ font-size: 22px; font-weight: 600; color: #111111 !important; }}
        .lbl {{ font-size: 10px; color: #666666 !important; text-transform: uppercase; margin: 3px 0; letter-spacing: 0.05em; }}
        .sub {{ font-size: 11px; color: #888888 !important; }}
        .up {{ color: #4a9e2f; font-weight: 600; }} .dn {{ color: #e05252; font-weight: 600; }}
    </style>
    <div class="row">
        <div class="card"><div class="val">{fo['ls_j']:,}</div><div class="lbl">Lead Share (LS)</div><div class="sub">Prior: {fo['ls_m']:,}</div><div><span class="{ 'up' if fo['ls_delta']>=0 else 'dn' }">{fo['ls_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['uniq_j']:,}</div><div class="lbl">Unique to Client</div><div class="sub">Prior: {fo['uniq_m']:,}</div><div><span class="{ 'up' if fo['uniq_delta']>=0 else 'dn' }">{fo['uniq_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ob_j']:,}</div><div class="lbl">Onboarded (OB)</div><div class="sub">Prior: {fo['ob_m']:,}</div><div><span class="{ 'up' if fo['ob_delta']>=0 else 'dn' }">{fo['ob_delta']:+,}</span></div></div>
        <div class="card"><div class="val">{fo['ft_j']:,}</div><div class="lbl">First Trips (FT)</div><div class="sub">Prior: {fo['ft_m']:,}</div><div><span class="{ 'up' if fo['ft_delta']>=0 else 'dn' }">{fo['ft_delta']:+,}</span></div></div>
    </div>
    """, height=115)

    st.markdown("#### Client Cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_client"]), "s1")

    st.markdown("#### Product Type Cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_product"]), "s2")

    st.markdown("#### Region Cut")
    display_replicated_table(transform_to_replicated_dataframe(payload["by_region"]), "s4")

    st.markdown("#### VL Cut — Configurable Volume Scan")
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_vl = col1.slider("Select Display Window Scale (S5 Cut)", min_value=5, max_value=100, value=20, key="s5_slider")
    sort_vl = col2.selectbox("Sort Priority By:", list(SORT_METRICS_MAP.keys()), index=0, key="s5_sort")
    order_vl = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s5_order")
    
    df_s5 = transform_to_replicated_dataframe(payload["by_vl"])
    if not df_s5.empty:
        df_s5 = df_s5.sort_values(by=SORT_METRICS_MAP[sort_vl], ascending=(order_vl == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s5.head(top_n_vl), "s5")

    st.markdown("#### Client × VL Matrix Drilldown")
    active_drill_list = sorted(list(df_curr['client'].dropna().unique()))
    selected_client_drill = st.multiselect("Isolate Specific Corporate Partner Focus (Client × VL)", options=["All"] + active_drill_list, default=["All"], key="s9_drill_select")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s9 = col1.slider("Select Display Window Scale (S9 Drilldown)", min_value=5, max_value=100, value=20, key="s9_slider")
    sort_s9 = col2.selectbox("Sort Priority By:", list(SORT_METRICS_MAP.keys()), index=0, key="s9_sort")
    order_s9 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s9_order")
    
    drilled_rows_vl = []
    if "All" in selected_client_drill or not selected_client_drill:
        for c, data in payload["funnel_drill"].items():
            for row in data["by_vl"]:
                drilled_rows_vl.append({**row, "dim": f"{c} · {row['dim']}"})
    else:
        for cl_isolate in selected_client_drill:
            if cl_isolate in payload["funnel_drill"]:
                for row in payload["funnel_drill"][cl_isolate].get("by_vl", []):
                    drilled_rows_vl.append({**row, "dim": f"{cl_isolate} · {row['dim']}"})
    
    df_s9 = transform_to_replicated_dataframe(drilled_rows_vl)
    if not df_s9.empty:
        df_s9 = df_s9.sort_values(by=SORT_METRICS_MAP[sort_s9], ascending=(order_s9 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s9.head(top_n_drill_s9), "s9")

    st.markdown("#### Client × Region Drilldown")
    selected_client_region = st.multiselect("Isolate Specific Corporate Partner Focus (Client × Region)", options=["All"] + active_drill_list, default=["All"], key="s8_drill_select")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s8 = col1.slider("Select Display Window Scale (Client × Region)", min_value=5, max_value=100, value=20, key="s8_slider")
    sort_s8 = col2.selectbox("Sort Priority By:", list(SORT_METRICS_MAP.keys()), index=0, key="s8_sort")
    order_s8 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s8_order")
    
    drilled_rows_region = []
    if "All" in selected_client_region or not selected_client_region:
        for c, data in payload["funnel_drill"].items():
            for row in data["by_region"]:
                drilled_rows_region.append({**row, "dim": f"{c} · {row['dim']}"})
    else:
        for cl_isolate in selected_client_region:
            if cl_isolate in payload["funnel_drill"]:
                for row in payload["funnel_drill"][cl_isolate].get("by_region", []):
                    drilled_rows_region.append({**row, "dim": f"{cl_isolate} · {row['dim']}"})
                    
    df_s8 = transform_to_replicated_dataframe(drilled_rows_region)
    if not df_s8.empty:
        df_s8 = df_s8.sort_values(by=SORT_METRICS_MAP[sort_s8], ascending=(order_s8 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s8.head(top_n_drill_s8), "s8")

    st.markdown("#### Client × Product Type Drilldown")
    selected_client_product = st.multiselect("Isolate Specific Corporate Partner Focus (Client × Product Type)", options=["All"] + active_drill_list, default=["All"], key="s6_drill_select")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s6 = col1.slider("Select Display Window Scale (Client × Product)", min_value=5, max_value=100, value=20, key="s6_slider")
    sort_s6 = col2.selectbox("Sort Priority By:", list(SORT_METRICS_MAP.keys()), index=0, key="s6_sort")
    order_s6 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s6_order")
    
    drilled_rows_product = []
    if "All" in selected_client_product or not selected_client_product:
        for c, data in payload["funnel_drill"].items():
            for row in data["by_product"]:
                drilled_rows_product.append({**row, "dim": f"{c} · {row['dim']}"})
    else:
        for cl_isolate in selected_client_product:
            if cl_isolate in payload["funnel_drill"]:
                for row in payload["funnel_drill"][cl_isolate].get("by_product", []):
                    drilled_rows_product.append({**row, "dim": f"{cl_isolate} · {row['dim']}"})
                    
    df_s6 = transform_to_replicated_dataframe(drilled_rows_product)
    if not df_s6.empty:
        df_s6 = df_s6.sort_values(by=SORT_METRICS_MAP[sort_s6], ascending=(order_s6 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s6.head(top_n_drill_s6), "s6")

    st.markdown("#### Region × VL Drilldown")
    active_region_list = sorted(list(df_curr['region'].dropna().unique()))
    selected_region_vl = st.multiselect("Isolate Specific Region Focus (Region × VL)", options=["All"] + active_region_list, default=["All"], key="s11_drill_select")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    top_n_drill_s11 = col1.slider("Select Display Window Scale (Region × VL)", min_value=5, max_value=100, value=20, key="s11_slider")
    sort_s11 = col2.selectbox("Sort Priority By:", list(SORT_METRICS_MAP.keys()), index=0, key="s11_sort")
    order_s11 = col3.selectbox("Trend View:", ["Top Performers (Growing)", "Bottom Performers (Degrowing)"], key="s11_order")
    
    drilled_rows_region_vl = []
    if "All" in selected_region_vl or not selected_region_vl:
        for r, data in payload["region_drill"].items():
            for row in data["by_vl"]:
                drilled_rows_region_vl.append({**row, "dim": f"{r} · {row['dim']}"})
    else:
        for rg_isolate in selected_region_vl:
            if rg_isolate in payload["region_drill"]:
                for row in payload["region_drill"][rg_isolate].get("by_vl", []):
                    drilled_rows_region_vl.append({**row, "dim": f"{rg_isolate} · {row['dim']}"})
                    
    df_s11 = transform_to_replicated_dataframe(drilled_rows_region_vl)
    if not df_s11.empty:
        df_s11 = df_s11.sort_values(by=SORT_METRICS_MAP[sort_s11], ascending=(order_s11 == "Bottom Performers (Degrowing)"))
    display_replicated_table(df_s11.head(top_n_drill_s11), "s11")

# ==========================================
# RENDER TAB: ROLLING TRENDS (NEW TAB)
# ==========================================
with tab_trends:
    st.markdown("## 📈 Rolling Week-on-Week Performance")
    st.caption("Review historical funnel metrics leading up to the selected Master Week Slicer anchor.")
    
    rolling_n = st.slider("Select Configurable N Weeks", min_value=2, max_value=12, value=5, help="Number of historical weeks to look backwards from the Master Week.")
    
    trend_target_weeks = [w for w in allWeeks if w <= anchor_week][:rolling_n]
    df_trend_raw = apply_dimensional_filters(df_raw[df_raw['week'].isin(trend_target_weeks)])
    
    st.markdown("#### 1. Overall Pipeline Trend")
    display_trend_table(df_trend_raw, ['week'], "overall_trend")
    
    st.markdown("#### 2. Client × Week Breakdown")
    display_trend_table(df_trend_raw, ['client', 'week'], "client_trend")

# ==========================================
# RENDER SCOPE: CONTEXTUAL RCA GENERATOR
# ==========================================
with tab_rca:
    st.markdown("## ⚙️ Funnel Conversion Insights Briefing")
    st.caption("Reviewing conversion paths across Lead Share (LS), Uniqueness, Onboarding (OB), and First Trips (FT).")
    
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        rca_client_filter = st.multiselect("Isolate Executive Client Segments", options=["All"] + allClients, default=["All"], key="rca_c")
    with filter_col2:
        rca_region_filter = st.multiselect("Isolate Geo-Spatial Territory Boundaries", options=["All"] + allRegions, default=["All"], key="rca_r")
        
    df_rca_curr = df_curr.copy()
    df_rca_prev = df_prev.copy()
    
    if rca_client_filter and "All" not in rca_client_filter:
        df_rca_curr = df_rca_curr[df_rca_curr['client'].isin(rca_client_filter)]
        df_rca_prev = df_rca_prev[df_rca_prev['client'].isin(rca_client_filter)]
    if rca_region_filter and "All" not in rca_region_filter:
        df_rca_curr = df_rca_curr[df_rca_curr['region'].isin(rca_region_filter)]
        df_rca_prev = df_rca_prev[df_rca_prev['region'].isin(rca_region_filter)]
        
    payload_rca = build_html_metric_payload(df_rca_curr, df_rca_prev)
    fo_rca = payload_rca["overall_funnel"]
    
    client_funnels_compiled = []
    for c_obj in payload_rca["by_client"]:
        c_name = c_obj["dim"]
        vj, vm = c_obj["jun"], c_obj["may"]
        ft_delta = vj["ft"] - vm["ft"]
        
        up_j = (vj["uniqueness"] / vj["ls"] * 100) if vj["ls"] > 0 else 0.0
        up_m = (vm["uniqueness"] / vm["ls"] * 100) if vm["ls"] > 0 else 0.0
        op_j = (vj["ob"] / vj["uniqueness"] * 100) if vj["uniqueness"] > 0 else 0.0
        op_m = (vm["ob"] / vm["uniqueness"] * 100) if vm["uniqueness"] > 0 else 0.0
        fp_j = (vj["ft"] / vj["ob"] * 100) if vj["ob"] > 0 else 0.0
        fp_m = (vm["ft"] / vm["ob"] * 100) if vm["ob"] > 0 else 0.0
        
        up_dp = round(up_j - up_m, 2)
        op_dp = round(op_j - op_m, 2)
        fp_dp = round(fp_j - fp_m, 2)
        
        client_funnels_compiled.append({
            "name": c_name, "ft_abs": ft_delta, "ls_j": vj["ls"], "ls_delta": vj["ls"] - vm["ls"], "ls_m": vm["ls"],
            "up_j": up_j, "up_m": up_m, "up_dp": up_dp, 
            "op_j": op_j, "op_m": op_m, "op_dp": op_dp, 
            "fp_j": fp_j, "fp_m": fp_m, "fp_dp": fp_dp
        })

    laggard_clients = [a for a in client_funnels_compiled if a["ft_abs"] < 0]
    laggard_clients.sort(key=lambda x: x["ft_abs"])

    vl_rca_c = df_rca_curr.groupby('vl_name')['ft'].sum()
    vl_rca_p = df_rca_prev.groupby('vl_name')['ft'].sum()
    vl_rca_m = pd.DataFrame({'curr': vl_rca_c, 'prev': vl_rca_p}).fillna(0)
    vl_rca_m['delta'] = vl_rca_m['curr'] - vl_rca_m['prev']
    
    top_growing_vls = vl_rca_m.sort_values(by='delta', ascending=False).head(5)
    top_degrowing_vls = vl_rca_m.sort_values(by='delta', ascending=True).head(5)

    def generate_ceo_download_report():
        ls_drop_pct = abs(round((fo_rca["ls_delta"] / fo_rca["ls_m"] * 100), 1)) if fo_rca["ls_m"] > 0 else 0
        client_ls_drops = []
        for c in client_funnels_compiled:
            if c["ls_delta"] < 0:
                client_ls_drops.append((c["name"], abs(c["ls_delta"])))
        client_ls_drops.sort(key=lambda x: x[1], reverse=True)
        top_offenders = [f"{name} - {val/100000:.1f}L" for name, val in client_ls_drops[:3]]
        
        report_lines = [
            f"=== VAHAN EXECUTIVE FUNNEL PERFORMANCE MATRIX ===",
            f"Reporting Range: {curr_start} to {curr_end} vs Baseline: {prev_start} to {prev_end}",
            f"",
            f"1. OVERALL FUNNEL SUMMARY",
            f"• {fo_rca['ls_j']/100000:.1f}L leads uploaded (Lead Share) this month down from {fo_rca['ls_m']/100000:.1f}L; {ls_drop_pct}% ▼",
            f"• Largest drop comes from ({', '.join(top_offenders)})",
            f"• Uniqueness has dropped by {abs(fo_rca['up_dp'])}pp from {fo_rca['up_m']:.1f}% down to {fo_rca['up_j']:.1f}% (meaning fewer fresh leads new to client databases).",
            f"",
            f"2. ATTRIBUTION DRILL-DOWN SUMMARY",
            f"• Swiggy is the highest impacted client where the VLs are moving leads from Instamart to Swiggy Food.",
            f"  (Key Vahan Leaders tracking migration: My Smart Buy, Runner Jobs, Delhive, Fastseek and Speed Rider).",
            f"• Qualitative Friction Vector: RojiRoty is re-utilising his leads on various clients but not pushing numbers on Swiggy or Instamart.",
            f"  He has significantly reduced overall Lead Share volume on Swiggy and is flagged at high risk of churn."
        ]
        return "\n".join(report_lines)

    st.markdown("### A. Overall Funnel Summary")
    
    if gemini_api_key:
        with st.spinner("🧠 Querying free Gemini AI cascade layer to generate corporate analysis briefing..."):
            gemini_api_key_clean = gemini_api_key.strip()
            
            context_payload = {
                "overall": fo_rca,
                "top_growing_vls": {str(k): int(v) for k, v in top_growing_vls['delta'].items()},
                "top_degrowing_vls": {str(k): int(v) for k, v in top_degrowing_vls['delta'].items()},
                "laggard_clients_volume": [(str(c["name"]), int(c["ft_abs"])) for c in laggard_clients]
            }
            
            prompt_payload = {
                "contents": [{
                    "parts": [{
                        "text": f"You are a Senior Data Analyst reporting directly to the CEO. Write a clean, professional, concise metric conversion narrative briefing based on this comprehensive snapshot: {json.dumps(context_payload)}. "
                                f"Terminology rules: LS is Lead Share (referred leads pool). Uniqueness means new to the client's database. OB means Onboarding/Activation. FT means completed First Trip. "
                                f"Work backward down the funnel steps from FT to explain why changes happened and pinpoint whether specific Clients, VLs, Regions, CLs, or AMs originated the shift. "
                                f"Do not use complex technical terms or harsh keywords. Keep it clear, supportive, and completely direct to the point."
                    }]
                }]
            }
            
            llm_response = call_gemini_with_retries(gemini_api_key_clean, prompt_payload)
            if llm_response["status"] == "success":
                ai_text = llm_response["data"]["candidates"][0]["content"]["parts"][0]["text"]
                st.markdown(ai_text)
            else:
                st.warning(f"AI API System Alert: {llm_response['message']}. Defaulting to strict analytical engine.")
                gemini_api_key = None

    if not gemini_api_key:
        if fo_rca["ft_delta"] < 0:
            st.markdown(f"### :red[Conversion Deficit:] Total First Trips (FT) dropped by **{abs(fo_rca['ft_delta']):,}** compared to the baseline period.")
            rca_bullets = []
            if fo_rca["fp_dp"] < 0:
                rca_bullets.append(f"<li><strong>First Trip Drop Layer (OB ➔ FT):</strong> Conversion dropped by <span class='dn'>{abs(fo_rca['fp_dp'])}pp</span>.</li>")
            if fo_rca["op_dp"] < 0:
                rca_bullets.append(f"<li><strong>Onboarding Drop Layer (Unique ➔ OB):</strong> Conversion dropped by <span class='dn'>{abs(fo_rca['op_dp'])}pp</span>.</li>")
            if fo_rca["up_dp"] < 0:
                rca_bullets.append(f"<li><strong>Lead Penetration Loss Layer (LS ➔ Unique):</strong> Unique lead penetration dropped by <span class='dn'>{abs(fo_rca['up_dp'])}pp</span>.</li>")
            if fo_rca["ls_delta"] < 0:
                rca_bullets.append(f"<li><strong>Volume Contraction Layer (Lead Share Ingress):</strong> Total raw leads shared decreased by <span class='dn'>{abs(fo_rca['ls_delta']):,} leads</span>.</li>")
            st.markdown(f"<ul>{''.join(rca_bullets)}</ul>", unsafe_allow_html=True)
        else:
            st.markdown(f"### :green[Conversion Pipeline Stable:] Target funnel configuration shows expansion of **+{fo_rca['ft_delta']:,} Completed First Trips** vs. prior period baseline parameters.")

    st.download_button(label="📥", data=generate_ceo_download_report(), file_name=f"Vahan_CEO_Funnel_Review_{curr_end}.txt", mime="text/plain")

    st.markdown("---")
    st.markdown("### Vahan Leader (VL Grain) Performance Standouts")
    growth_col1, growth_col2 = st.columns(2)
    with growth_col1:
        st.markdown("#### Top 5 Growing VLs (Absolute Increase)")
        for vl_name, row in top_growing_vls.iterrows():
            if row['delta'] > 0:
                st.markdown(f"- 🟢 **{vl_name}**: Added :green[+{int(row['delta'])}] First Trips (Jun: {int(row['curr'])} vs May: {int(row['prev'])})")
    with growth_col2:
        st.markdown("#### Top 5 Degrowing VLs (Absolute Decrease)")
        for vl_name, row in top_degrowing_vls.iterrows():
            if row['delta'] < 0:
                st.markdown(f"- 🔴 **{vl_name}**: Dropped :red[{int(row['delta'])}] First Trips (Jun: {int(row['curr'])} vs May: {int(row['prev'])})")

    st.markdown("---")
    st.markdown("### B. Drill-down Summary")
    if not laggard_clients:
        st.info("No deficit vectors logged across business channels matching current tracking parameters.")
    else:
        for client in laggard_clients:
            st.markdown(f"""
            <div style='background: #ffffff !important; border: 0.5px solid rgba(0,0,0,0.08); border-left: 4px solid #e05252; border-radius: 8px; padding: 12px; margin-bottom: 12px;'>
                <div style='display:flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size:13px; font-weight:600; color: #111111 !important;'>{client['name'].upper()}</span>
                    <span style='color: #e05252 !important; font-weight: 600;'>{client['ft_abs']:,} First Trips (FT) Variance Loss</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            client_bullets = []
            if client["fp_dp"] < 0:
                client_bullets.append(f"<li><strong>First Trip Drop Layer (OB ➔ FT):</strong> Conversion dropped by <span class='dn'>{abs(client['fp_dp'])}pp</span> (from {client['fp_m']:.1f}% to {client['fp_j']:.1f}%).</li>")
            if client["op_dp"] < 0:
                client_bullets.append(f"<li><strong>Onboarding Drop Layer (Unique ➔ OB):</strong> Conversion dropped by <span class='dn'>{abs(client['op_dp'])}pp</span> (from {client['op_m']:.1f}% to {client['op_j']:.1f}%).</li>")
            if client["up_dp"] < 0:
                client_bullets.append(f"<li><strong>Lead Penetration Loss Layer (LS ➔ Unique):</strong> Uniqueness penetration dropped by <span class='dn'>{abs(client['up_dp'])}pp</span> (from {client['up_m']:.1f}% to {client['up_j']:.1f}%).</li>")
            if client["ls_delta"] < 0:
                client_bullets.append(f"<li><strong>Volume Contraction Layer (Lead Share Ingress):</strong> Total raw leads shared decreased by <span class='dn'>{abs(client['ls_delta']):,} leads</span>.</li>")
            
            if client_bullets:
                st.markdown(f"<ul>{''.join(client_bullets)}</ul>", unsafe_allow_html=True)
            
            vl_drill_source = payload_rca["funnel_drill"].get(client["name"], {}).get("by_vl", [])
            vl_analysis_frame = transform_to_replicated_dataframe(vl_drill_source)
            if not vl_analysis_frame.empty and "FT Δ" in vl_analysis_frame.columns:
                worst_performing_vls = vl_analysis_frame[vl_analysis_frame["FT Δ"] < 0].sort_values(by="FT Δ").head(3)
                if not worst_performing_vls.empty:
                    st.markdown("**Top-3 Contributing Laggard VLs:**")
                    for _, v_row in worst_performing_vls.iterrows():
                        st.markdown(f"- 📉 Laggard **{v_row['Dimension']}**: Net Deficit of :red[{abs(v_row['FT Δ'])}] Completed First Trips (Jun: {v_row['FT (First Trip) Jun']} vs May: {v_row['FT (First Trip) May']})")
            st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# RENDER SCOPE: AI CHATBOT INTERFACE
# ==========================================
with tab_chat:
    st.markdown("## 💬 Executive AI Assistant")
    st.caption("Ask questions about funnel drops, top performing VLs, or client-specific drill-down attribution metrics.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about the funnel performance..."):
        if not gemini_api_key:
            st.warning("Please configure your st.secrets file to activate the AI Chatbot.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("Analyzing rolling 5-week deep data structures..."):
                    
                    chat_target_weeks = [w for w in allWeeks if w <= anchor_week][:5]
                    df_chat_raw = apply_dimensional_filters(df_raw[df_raw['week'].isin(chat_target_weeks)])
                    
                    df_chat_weeks = df_chat_raw.groupby(['client', 'vl_name', 'week'])[['ls', 'uniq', 'ob', 'ft']].sum().reset_index()
                    
                    weekly_chronology_tree = {}
                    for _, row in df_chat_weeks.iterrows():
                        c = str(row['client'])
                        vl = str(row['vl_name'])
                        wk = str(row['week'])
                        
                        if c not in weekly_chronology_tree: 
                            weekly_chronology_tree[c] = {}
                        if vl not in weekly_chronology_tree[c]: 
                            weekly_chronology_tree[c][vl] = {}
                            
                        weekly_chronology_tree[c][vl][wk] = {
                            "Lead_Share_LS": int(row['ls']),
                            "Uniqueness": int(row['uniq']),
                            "Onboarded_OB": int(row['ob']),
                            "First_Trips_FT": int(row['ft'])
                        }
                    
                    context_data = {
                        "macro_summary_aggregates": fo_rca,
                        "chronological_rolling_5_week_client_x_vl_funnel_tree": weekly_chronology_tree
                    }
                    
                    system_guideline = (
                        "You are an expert Executive Operations Data Analyst reporting directly to the CEO.\n"
                        "CRITICAL STRUCTURAL RULES FOR THE BUSINESS TAXONOMY:\n"
                        "1. CLIENTS are purchasing enterprises (e.g., Swiggy, Blinkit, Zomato). Never call them vendors.\n"
                        "2. VAHAN LEADERS (VLs) are third-party manpower sourcing vendors who recruit and supply workers TO clients.\n"
                        "3. NEVER confuse a Client with a VL.\n\n"
                        "ROOT CAUSE ANALYSIS (RCA) EXECUTION MATRIX:\n"
                        "You have been provided with a deep chronology tree representing EXACTLY the last 5 rolling weeks of data for every Client and VL combination. "
                        "When analyzing fluctuations, execute a BACKWARD funnel evaluation: First Trips (FT) ➔ Onboarding (OB) ➔ Uniqueness ➔ Lead Share (LS). "
                        "Identify the exact week and exact VL driving the client's drop."
                    )
                    
                    gemini_history = [{"role": "user", "parts": [{"text": system_guideline}]}]
                    for m in st.session_state.chat_history[:-1]:
                        gemini_role = "user" if m["role"] == "user" else "model"
                        gemini_history.append({"role": gemini_role, "parts": [{"text": m["content"]}]})
                    
                    current_prompt_with_context = f"Granular Database Matrix: {json.dumps(context_data)}\n\nUser Operational Question: {prompt}"
                    gemini_history.append({"role": "user", "parts": [{"text": current_prompt_with_context}]})
                    
                    gemini_api_key_clean = gemini_api_key.strip()
                    payload_chat = {"contents": gemini_history}
                    
                    llm_chat_resp = call_gemini_with_retries(gemini_api_key_clean, payload_chat)
                    
                    if llm_chat_resp["status"] == "success":
                        ai_response = llm_chat_resp["data"]["candidates"][0]["content"]["parts"][0]["text"]
                        message_placeholder.markdown(ai_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    else:
                        message_placeholder.error(f"Chatbot Layer Connection Alert: {llm_chat_resp['message']}")
