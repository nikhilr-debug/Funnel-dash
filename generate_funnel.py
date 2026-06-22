import streamlit as st
import pandas as pd
from datetime import date, timedelta

# --- Page Config ---
st.set_page_config(page_title="Vahan Funnel & AI RCA Dashboard", layout="wide")

# --- 1. Mock Data Loading (Replace with your SQL/ClickHouse logic) ---
@st.cache_data
def load_data():
    # To make toggles work, your data should look like this in Pandas:
    # Columns: ['date', 'client', 'vl_name', 'region', 'ls', 'uniqueness', 'ob', 'ft']
    # Below is dummy data to make the app compile so you can see the layout.
    dates = pd.date_range(start="2026-05-01", end="2026-06-22")
    data = []
    for d in dates:
        data.append({"date": d, "client": "Blinkit", "vl_name": "VL1", "region": "NCR", "ls": 1000, "uniqueness": 500, "ob": 100, "ft": 50})
        data.append({"date": d, "client": "Instamart", "vl_name": "VL2", "region": "South", "ls": 800, "uniqueness": 400, "ob": 80, "ft": 30})
    return pd.DataFrame(data)

df = load_data()

# --- 2. Sidebar Controls & Date Math ---
st.sidebar.header("Dashboard Controls")

# Toggles
view_mode = st.sidebar.radio("View Mode", ["MTD (Month-to-Date)", "WTD (Week-to-Date)"])
exclude_incomplete = st.sidebar.checkbox("Exclude current incomplete week", value=False)

# Apples-to-Apples Date Calculation
today = date(2026, 6, 22) # Mocking 'today' based on the system prompt context

if exclude_incomplete:
    # Shift 'today' back to the end of the previous week (Sunday)
    days_to_subtract = today.weekday() + 1
    reference_date = today - timedelta(days=days_to_subtract)
else:
    reference_date = today

current_period_data = pd.DataFrame()
previous_period_data = pd.DataFrame()

if view_mode == "MTD (Month-to-Date)":
    # Current MTD: 1st of current month to reference_date
    curr_start = reference_date.replace(day=1)
    
    # Previous MTD: 1st of last month to the same day of last month
    # Handle January edge case
    prev_month = 12 if curr_start.month == 1 else curr_start.month - 1
    prev_year = curr_start.year - 1 if curr_start.month == 1 else curr_start.year
    prev_start = date(prev_year, prev_month, 1)
    
    # Apples-to-apples end date
    try:
        prev_end = date(prev_year, prev_month, reference_date.day)
    except ValueError:
        # Catch edge cases like comparing Feb 29 to Feb 28
        prev_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)

    st.sidebar.info(f"**Apples-to-Apples Comparison:**\nCurrent: {curr_start} to {reference_date}\nPrevious: {prev_start} to {prev_end}")

    current_period_data = df[(df['date'].dt.date >= curr_start) & (df['date'].dt.date <= reference_date)]
    previous_period_data = df[(df['date'].dt.date >= prev_start) & (df['date'].dt.date <= prev_end)]

else:
    # WTD Logic
    # Current WTD: Monday of current week to reference_date
    curr_start = reference_date - timedelta(days=reference_date.weekday())
    
    # Previous WTD: Monday of last week to same day of last week
    prev_start = curr_start - timedelta(days=7)
    prev_end = reference_date - timedelta(days=7)

    st.sidebar.info(f"**Apples-to-Apples Comparison:**\nCurrent: {curr_start} to {reference_date}\nPrevious: {prev_start} to {prev_end}")

    current_period_data = df[(df['date'].dt.date >= curr_start) & (df['date'].dt.date <= reference_date)]
    previous_period_data = df[(df['date'].dt.date >= prev_start) & (df['date'].dt.date <= prev_end)]


# --- 3. Helper Functions for Aggregation ---
def aggregate_funnel(data_frame):
    if data_frame.empty:
        return {"ls": 0, "uniqueness": 0, "ob": 0, "ft": 0}
    return {
        "ls": data_frame['ls'].sum(),
        "uniqueness": data_frame['uniqueness'].sum(),
        "ob": data_frame['ob'].sum(),
        "ft": data_frame['ft'].sum()
    }

# --- 4. Main Dashboard UI ---
tab1, tab2 = st.tabs(["Funnel View", "✨ AI RCA Summary"])

with tab1:
    st.title("Funnel View")
    
    # Overall KPIs
    st.subheader("Overall Funnel Performance")
    curr_totals = aggregate_funnel(current_period_data)
    prev_totals = aggregate_funnel(previous_period_data)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lead Submissions (LS)", f"{curr_totals['ls']:,}", f"{curr_totals['ls'] - prev_totals['ls']:,} vs prev")
    col2.metric("Unique Leads", f"{curr_totals['uniqueness']:,}", f"{curr_totals['uniqueness'] - prev_totals['uniqueness']:,} vs prev")
    col3.metric("Onboarded (OB)", f"{curr_totals['ob']:,}", f"{curr_totals['ob'] - prev_totals['ob']:,} vs prev")
    col4.metric("First Trip (FT)", f"{curr_totals['ft']:,}", f"{curr_totals['ft'] - prev_totals['ft']:,} vs prev")

    # Table View
    st.subheader("Client Cut")
    curr_client = current_period_data.groupby('client')[['ls', 'uniqueness', 'ob', 'ft']].sum().reset_index()
    st.dataframe(curr_client, use_container_width=True, hide_index=True)

with tab2:
    st.title("AI Root Cause Analysis (RCA)")
    
    # Calculate RCA metrics
    ft_delta = curr_totals['ft'] - prev_totals['ft']
    
    curr_conv = (curr_totals['ft'] / curr_totals['ob'] * 100) if curr_totals['ob'] else 0
    prev_conv = (prev_totals['ft'] / prev_totals['ob'] * 100) if prev_totals['ob'] else 0
    conv_drop = curr_conv - prev_conv
    
    curr_act = (curr_totals['ob'] / curr_totals['uniqueness'] * 100) if curr_totals['uniqueness'] else 0
    prev_act = (prev_totals['ob'] / prev_totals['uniqueness'] * 100) if prev_totals['uniqueness'] else 0
    act_drop = curr_act - prev_act

    # Overall View RCA
    st.subheader("A. Overall Funnel RCA")
    if ft_delta < 0:
        st.error(f"**FT Dropped by {abs(ft_delta):,}** overall compared to the previous period.")
        
        if conv_drop < 0:
            st.markdown(f"- **P0 Bottleneck (Conversion):** FT/OB conversion rate dropped by **{abs(conv_drop):.1f}pp**. Candidates are activating but failing to complete their first trip.")
        if act_drop < 0:
            st.markdown(f"- **P1 Bottleneck (Activation):** OB/Unique rate dropped by **{abs(act_drop):.1f}pp**.")
        if curr_totals['ls'] < prev_totals['ls']:
            st.markdown(f"- **P2 Bottleneck (Volume):** Top-of-funnel LS volume dropped by **{prev_totals['ls'] - curr_totals['ls']:,}**.")
    else:
        st.success(f"**FT is Up by {ft_delta:,}** compared to the previous period. Overall funnel health is stable.")

    # Client Level RCA
    st.subheader("B. Client-Level RCA (Prioritized by FT Drop)")
    
    clients = current_period_data['client'].unique()
    dropped_clients = []
    
    for client in clients:
        c_curr = aggregate_funnel(current_period_data[current_period_data['client'] == client])
        c_prev = aggregate_funnel(previous_period_data[previous_period_data['client'] == client])
        c_delta = c_curr['ft'] - c_prev['ft']
        if c_delta < 0:
            dropped_clients.append((client, c_curr, c_prev, c_delta))
            
    # Sort by worst FT drop
    dropped_clients.sort(key=lambda x: x[3])
    
    if not dropped_clients:
        st.info("No clients experienced an FT drop in this period.")
    else:
        for client, c_curr, c_prev, c_delta in dropped_clients:
            with st.expander(f"🚨 {client}: {abs(c_delta):,} FT Drop", expanded=True):
                # Basic bottleneck checks
                c_curr_conv = (c_curr['ft'] / c_curr['ob'] * 100) if c_curr['ob'] else 0
                c_prev_conv = (c_prev['ft'] / c_prev['ob'] * 100) if c_prev['ob'] else 0
                
                reasons = []
                if (c_curr_conv - c_prev_conv) < -5:
                    reasons.append(f"Severe FT/OB conversion drop ({(c_curr_conv - c_prev_conv):.1f}pp)")
                if c_curr['ls'] < c_prev['ls']:
                    reasons.append(f"LS Volume plummeted by {c_prev['ls'] - c_curr['ls']:,}")
                
                if reasons:
                    st.write("**Root Cause:** " + " and ".join(reasons))
                else:
                    st.write("**Root Cause:** General decay across funnel stages.")
                
                # VL Drilldown
                st.write("**Top Laggard VLs:**")
                vl_curr = current_period_data[current_period_data['client'] == client].groupby('vl_name')['ft'].sum()
                vl_prev = previous_period_data[previous_period_data['client'] == client].groupby('vl_name')['ft'].sum()
                
                # Combine and find drops
                vl_df = pd.DataFrame({'curr_ft': vl_curr, 'prev_ft': vl_prev}).fillna(0)
                vl_df['drop'] = vl_df['curr_ft'] - vl_df['prev_ft']
                vl_df = vl_df[vl_df['drop'] < 0].sort_values('drop').head(3)
                
                if not vl_df.empty:
                    for vl_name, row in vl_df.iterrows():
                        st.markdown(f"- **{vl_name}**: {int(abs(row['drop']))} fewer FTs")
                else:
                    st.markdown("- Drops were evenly distributed across VLs.")
