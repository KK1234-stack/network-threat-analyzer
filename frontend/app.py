"""
Network Threat Analyzer — Streamlit Frontend
Three pages: Login/Register | Upload & Analyze | History Dashboard
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Network Threat Analyzer", layout="wide")


# --- Session state helpers ---

def is_logged_in():
    return "token" in st.session_state and st.session_state.token


def is_admin():
    return st.session_state.get("is_admin", False)


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# --- Auth Page ---

def page_auth():
    st.title("Network Threat Analyzer")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            resp = requests.post(
                f"{BACKEND_URL}/auth/login",
                data={"username": email, "password": password},
            )
            if resp.status_code == 200:
                st.session_state.token = resp.json()["access_token"]
                st.session_state.email = email
                me = requests.get(f"{BACKEND_URL}/auth/me", headers={"Authorization": f"Bearer {st.session_state.token}"})
                st.session_state.is_admin = me.json().get("is_admin", False)
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab_register:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register"):
            resp = requests.post(
                f"{BACKEND_URL}/auth/register",
                json={"email": email, "password": password},
            )
            if resp.status_code == 201:
                st.success("Account created — please log in")
            else:
                st.error(resp.json().get("detail", "Error"))


# --- Upload & Analyze Page ---

def page_upload():
    st.header("Upload Network Flow CSV")
    st.caption("Upload a CICIDS-format CSV. Each row is a network flow.")

    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded and st.button("Analyze"):
        with st.spinner("Running inference..."):
            resp = requests.post(
                f"{BACKEND_URL}/predictions/upload",
                headers=auth_headers(),
                files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
            )

        if resp.status_code != 200:
            st.error(f"Error: {resp.json().get('detail', 'Unknown error')}")
            return

        data = resp.json()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Flows", data["total_flows"])
        col2.metric("Threats Detected", data["threat_count"])
        col3.metric("Benign Flows", data["benign_count"])

        st.caption(f"Model: `{data['model_version']}` | Inference time: {data['inference_time_ms']:.1f}ms")

        # Label distribution pie chart
        dist = data["label_distribution"]
        fig = px.pie(
            values=list(dist.values()),
            names=list(dist.keys()),
            title="Threat Distribution",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Per-row results table
        st.subheader("Per-Flow Results")
        rows_df = pd.DataFrame(data["per_row"])
        rows_df["confidence"] = rows_df["confidence"].map(lambda x: f"{x:.2%}")
        st.dataframe(rows_df, use_container_width=True)


# --- History Dashboard Page ---

def page_history():
    st.header("Prediction History")

    resp = requests.get(f"{BACKEND_URL}/predictions/history", headers=auth_headers())
    if resp.status_code != 200:
        st.error("Could not fetch history")
        return

    records = resp.json()
    if not records:
        st.info("No predictions yet — upload a CSV to get started")
        return

    # Summary table
    df = pd.DataFrame(records)
    df["uploaded_at"] = pd.to_datetime(df["uploaded_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        df[["filename", "uploaded_at", "total_flows", "threat_count", "benign_count", "model_version"]],
        use_container_width=True,
    )

    # Aggregate threat distribution across all predictions
    all_labels = {}
    for r in records:
        for label, count in r["label_distribution"].items():
            all_labels[label] = all_labels.get(label, 0) + count

    fig = px.bar(
        x=list(all_labels.keys()),
        y=list(all_labels.values()),
        labels={"x": "Label", "y": "Count"},
        title="Cumulative Threat Distribution (All Predictions)",
    )
    st.plotly_chart(fig, use_container_width=True)


# --- Admin Page ---

def page_admin():
    st.header("Admin — Model Retraining")

    # Current status
    resp = requests.get(f"{BACKEND_URL}/admin/retrain/status", headers=auth_headers())
    if resp.status_code != 200:
        st.error("Could not fetch retrain status")
        return

    state = resp.json()
    status = state["status"]

    status_color = {"idle": "🟡", "running": "🔵", "done": "🟢", "failed": "🔴"}
    st.subheader(f"{status_color.get(status, '⚪')} Status: `{status}`")

    if status == "running":
        st.info("Retraining in progress — refresh to check for updates")
        if st.button("Refresh Status"):
            st.rerun()

    if status == "done" and state.get("metrics"):
        m = state["metrics"]
        col1, col2, col3 = st.columns(3)
        col1.metric("RF Weighted F1", f"{m['rf_f1']:.4f}")
        col2.metric("LSTM Weighted F1", f"{m['lstm_f1']:.4f}")
        col3.metric("Winner", m["winner"].upper())

    if status == "failed" and state.get("error"):
        st.error(f"Error: {state['error']}")

    st.divider()

    # Trigger retraining
    st.write("Trigger a new training run. Trains RF + LSTM on preprocessed data, promotes the winner to production, and hot-reloads the model.")
    st.warning("Requires preprocessed data in `/app/processed/`. Training takes several minutes.")

    if status == "running":
        st.button("Trigger Retraining", disabled=True)
    else:
        if st.button("Trigger Retraining", type="primary"):
            r = requests.post(f"{BACKEND_URL}/admin/retrain", headers=auth_headers())
            if r.status_code == 202:
                st.success("Retraining started — refresh to monitor progress")
                st.rerun()
            elif r.status_code == 409:
                st.warning("Already running")
            else:
                st.error(f"Error: {r.json().get('detail', 'Unknown')}")


# --- Main router ---

if not is_logged_in():
    page_auth()
else:
    st.sidebar.title(f"Logged in as\n{st.session_state.get('email', '')}")
    if st.sidebar.button("Logout"):
        del st.session_state.token
        st.rerun()

    pages = ["Upload & Analyze", "History"]
    if is_admin():
        pages.append("Admin")

    page = st.sidebar.radio("Navigate", pages)

    if page == "Upload & Analyze":
        page_upload()
    elif page == "History":
        page_history()
    elif page == "Admin":
        page_admin()
