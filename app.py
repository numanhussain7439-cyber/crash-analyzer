import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd
import streamlit as st
import altair as alt
from streamlit_autorefresh import st_autorefresh

APP_TITLE = "CRASH Analyzer"
DEFAULT_BALANCE = 500
DEFAULT_TARGET = 770899
DATA_FILE = Path("crash_history.csv")

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1100px;}
.metric-card {padding: 14px; border: 1px solid rgba(128,128,128,.25);
              border-radius: 12px; min-height: 88px;}
.small-note {font-size: .85rem; opacity: .8;}
</style>
""", unsafe_allow_html=True)

st.title("📈 CRASH Analyzer")
st.caption("History analysis and bankroll tracking — not a future-outcome predictor.")

def load_history():
    if DATA_FILE.exists():
        try:
            df = pd.read_csv(DATA_FILE)
            if {"timestamp", "multiplier"}.issubset(df.columns):
                df["multiplier"] = pd.to_numeric(df["multiplier"], errors="coerce")
                df = df.dropna(subset=["multiplier"])
                return df
        except Exception:
            pass
    return pd.DataFrame(columns=["timestamp", "multiplier", "round_id"])

def save_history(df):
    df.to_csv(DATA_FILE, index=False)

def normalize_records(payload):
    # Accepted JSON formats:
    # [{"multiplier": 1.7, "timestamp": "...", "round_id": "123"}, ...]
    # {"rounds": [...]} or {"history": [...]}
    if isinstance(payload, dict):
        payload = payload.get("rounds", payload.get("history", []))
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON list or an object containing 'rounds'/'history'.")
    rows = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict) or "multiplier" not in item:
            continue
        try:
            mult = float(str(item["multiplier"]).lower().replace("x", "").strip())
        except (TypeError, ValueError):
            continue
        if mult < 1 or mult > 1_000_000:
            continue
        ts = item.get("timestamp") or datetime.now(timezone.utc).isoformat()
        rows.append({
            "timestamp": str(ts),
            "multiplier": mult,
            "round_id": str(item.get("round_id", item.get("id", "")))
        })
    return pd.DataFrame(rows, columns=["timestamp", "multiplier", "round_id"])

def fetch_feed(url, token=""):
    if not url.startswith("https://"):
        raise ValueError("For safety, the feed URL must use HTTPS.")
    headers = {"Accept": "application/json", "User-Agent": "CrashAnalyzer/1.0"}
    if token.strip():
        headers["Authorization"] = "Bearer " + token.strip()
    req = Request(url, headers=headers)
    with urlopen(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError(f"Feed returned HTTP {response.status}")
        return normalize_records(json.loads(response.read().decode("utf-8")))

if "history" not in st.session_state:
    st.session_state.history = load_history()
if "balance" not in st.session_state:
    st.session_state.balance = DEFAULT_BALANCE
if "target_balance" not in st.session_state:
    st.session_state.target_balance = DEFAULT_TARGET
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = "Not refreshed yet"

with st.sidebar:
    st.header("Settings")
    st.number_input("Current coin balance", min_value=0, step=10,
                    key="balance", value=DEFAULT_BALANCE)
    st.number_input("Target coin balance", min_value=1, step=100,
                    key="target_balance", value=DEFAULT_TARGET)
    st.markdown("---")
    st.subheader("Live history feed")
    feed_url = st.text_input("HTTPS JSON feed URL", placeholder="https://provider.example/api/history")
    token = st.text_input("Optional API token", type="password",
                          help="Stored only in this running browser session; do not paste your website password.")
    refresh_seconds = st.selectbox("Auto-refresh interval", [0, 15, 30, 60, 120],
                                   format_func=lambda x: "Off" if x == 0 else f"{x} seconds")
    if st.button("Refresh history now", use_container_width=True):
        if not feed_url:
            st.warning("Add an official history-feed URL first.")
        else:
            try:
                incoming = fetch_feed(feed_url, token)
                combined = pd.concat([st.session_state.history, incoming], ignore_index=True)
                if not combined.empty:
                    combined = combined.drop_duplicates(
                        subset=["round_id", "timestamp", "multiplier"], keep="last"
                    ).tail(5000)
                st.session_state.history = combined
                save_history(combined)
                st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"Loaded {len(incoming)} history records.")
            except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
                st.error(f"Could not load feed: {e}")
    st.caption("A provider-supported public/API feed is required. This app does not scrape protected pages or log in.")

# Poll the configured authorized feed while this dashboard remains open.
if refresh_seconds and feed_url:
    st_autorefresh(interval=refresh_seconds * 1000, key="crash_feed_autorefresh")
    try:
        incoming = fetch_feed(feed_url, token)
        combined = pd.concat([st.session_state.history, incoming], ignore_index=True)
        if not combined.empty:
            combined = combined.drop_duplicates(
                subset=["round_id", "timestamp", "multiplier"], keep="last"
            ).tail(5000)
        st.session_state.history = combined
        save_history(combined)
        st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        st.warning(f"Automatic feed refresh failed: {e}")

st.write(f"**Last refresh:** {st.session_state.last_refresh}")

st.subheader("Add history manually")
with st.form("add_round", clear_on_submit=True):
    c1, c2 = st.columns(2)
    mult_text = c1.text_input("Multiplier (e.g. 2.45 or 2.45x)")
    round_id = c2.text_input("Round ID (optional)")
    submitted = st.form_submit_button("Add round")
    if submitted:
        try:
            mult = float(mult_text.lower().replace("x", "").strip())
            if mult < 1:
                st.error("Multiplier must be at least 1.00x.")
            else:
                row = pd.DataFrame([{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "multiplier": mult,
                    "round_id": round_id.strip()
                }])
                st.session_state.history = pd.concat(
                    [st.session_state.history, row], ignore_index=True
                ).tail(5000)
                save_history(st.session_state.history)
                st.success(f"Added {mult:.2f}x.")
        except ValueError:
            st.error("Enter a valid number, such as 1.72.")

st.subheader("Import history CSV")
uploaded = st.file_uploader("CSV must contain a 'multiplier' column; timestamp and round_id are optional.",
                            type=["csv"])
if uploaded is not None:
    try:
        imported = pd.read_csv(uploaded)
        if "multiplier" not in imported.columns:
            st.error("CSV needs a multiplier column.")
        else:
            imported["multiplier"] = pd.to_numeric(imported["multiplier"], errors="coerce")
            imported = imported.dropna(subset=["multiplier"])
            if "timestamp" not in imported: imported["timestamp"] = datetime.now(timezone.utc).isoformat()
            if "round_id" not in imported: imported["round_id"] = ""
            imported = imported[["timestamp", "multiplier", "round_id"]]
            st.session_state.history = pd.concat(
                [st.session_state.history, imported], ignore_index=True
            ).tail(5000)
            save_history(st.session_state.history)
            st.success(f"Imported {len(imported)} rows.")
    except Exception as e:
        st.error(f"CSV import failed: {e}")

df = st.session_state.history.copy()
if not df.empty:
    df["multiplier"] = pd.to_numeric(df["multiplier"], errors="coerce")
    df = df.dropna(subset=["multiplier"])
    df = df[df["multiplier"] >= 1].tail(5000)

st.markdown("---")
current_balance = int(st.session_state.balance)
target_balance = int(st.session_state.target_balance)
remaining = max(target_balance - current_balance, 0)
progress = min(current_balance / target_balance, 1.0) if target_balance > 0 else 0.0

st.subheader("🎯 Coin recovery progress")
p1, p2, p3 = st.columns(3)
p1.metric("Current balance", f"{current_balance:,} coins")
p2.metric("Target balance", f"{target_balance:,} coins")
p3.metric("Coins remaining", f"{remaining:,} coins")
st.progress(progress, text=f"{progress * 100:.3f}% of target")
if current_balance >= target_balance:
    st.success("Target balance reached.")
else:
    st.caption("Progress tracker only — it does not place bets or promise recovery.")

if df.empty:
    st.info("No game history loaded yet. Add a few rounds or connect an official JSON history feed.")
else:
    n = len(df)
    avg = df["multiplier"].mean()
    med = df["multiplier"].median()
    latest = df.iloc[-1]["multiplier"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rounds analyzed", f"{n:,}")
    c2.metric("Average multiplier", f"{avg:.2f}x")
    c3.metric("Median multiplier", f"{med:.2f}x")
    c4.metric("Latest recorded", f"{latest:.2f}x")

    st.subheader("Recent multiplier history")
    chart_df = df.tail(150).reset_index(drop=True)
    chart_df["round_number"] = range(1, len(chart_df) + 1)
    line = alt.Chart(chart_df).mark_line(point=True).encode(
        x=alt.X("round_number:Q", title="Recent round (oldest → newest)"),
        y=alt.Y("multiplier:Q", title="Recorded multiplier", scale=alt.Scale(zero=False)),
        tooltip=["round_number", "multiplier", "timestamp"]
    ).properties(height=280)
    st.altair_chart(line, use_container_width=True)

    st.subheader("Historical threshold frequencies")
    thresholds = [1.5, 2, 3, 5, 10]
    freq_rows = []
    for t in thresholds:
        count = int((df["multiplier"] >= t).sum())
        freq_rows.append({"Threshold": f"{t:g}x", "Rounds at/above": count,
                          "Observed frequency": count / n,
                          "Observed %": f"{count/n*100:.1f}%"})
    freq = pd.DataFrame(freq_rows)
    st.dataframe(freq, hide_index=True, use_container_width=True,
                 column_config={"Observed frequency": st.column_config.ProgressColumn(
                     "Observed frequency", min_value=0, max_value=1, format="%.1%%"
                 )})

    st.subheader("Recent streaks (descriptive only)")
    low_cut = st.number_input("Define a low crash as below", min_value=1.01,
                              max_value=100.0, value=2.0, step=0.1)
    recent = df["multiplier"].tail(100).tolist()
    streak = 0
    for value in reversed(recent):
        if value < low_cut: streak += 1
        else: break
    st.metric(f"Current consecutive rounds below {low_cut:.2f}x", streak)
    st.caption("A streak does not make a high multiplier 'due'. Independent random rounds do not become predictable from prior results.")

    st.subheader("Coin balance tracker")
    stake = st.number_input("Hypothetical stake per round", min_value=0, value=100, step=10)
    target = st.number_input("Hypothetical cash-out target", min_value=1.01, value=2.0, step=0.1)
    if stake > 0:
        wins = int((df["multiplier"] >= target).sum())
        losses = n - wins
        # Hypothetical net for fixed stake and target, ignoring fees and provider-specific rules.
        net = wins * stake * (target - 1) - losses * stake
        st.metric("Hypothetical net if this exact rule had been used",
                  f"{net:+,.0f} coins",
                  help="A historical simulation, not a forecast. Assumes stake is lost below target and target cash-out pays stake × target.")
        st.caption(f"Observed hit rate: {wins/n*100:.1f}% ({wins} of {n} recorded rounds). Past frequency is not a reliable prediction of the next round.")

    with st.expander("View latest 100 records"):
        st.dataframe(df.tail(100).iloc[::-1], use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download analyzed history CSV", csv, "crash_history_export.csv",
                       "text/csv", use_container_width=True)

st.markdown("---")
st.warning("""
**Safety & accuracy:** This tool only summarizes recorded outcomes. It cannot know the next crash point,
guarantee profit, or recover lost coins. Do not stake money you cannot afford to lose. Never enter your
casino password, wallet seed phrase, OTP, or private key here. Only connect a documented feed you are
authorized to use.
""")
