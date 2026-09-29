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


# --- Networking helpers ---

WAKE_MSG = "Couldn't reach the server — it may be waking up (free tier sleeps after inactivity). Wait ~30s and try again."


def api_request(method, path, **kwargs):
    """
    Make a request to the backend and return (resp, error_message).
    If the backend is unreachable or times out, resp is None and error_message is set.
    Never lets a network exception bubble up into a Streamlit traceback.
    """
    try:
        resp = requests.request(
            method, f"{BACKEND_URL}{path}", timeout=90, **kwargs)
        return resp, None
    except requests.exceptions.RequestException:
        return None, WAKE_MSG


def parse_json(resp):
    """Return parsed JSON, or None if the response body isn't valid JSON."""
    try:
        return resp.json()
    except ValueError:
        return None


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
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input(
                "Password", type="password", key="login_password")
            submitted = st.form_submit_button(
                "Login", use_container_width=True)
        if submitted:
            resp, err = api_request(
                "POST", "/auth/login",
                data={"username": email, "password": password},
            )
            if err:
                st.error(err)
            elif resp.status_code == 200:
                data = parse_json(resp)
                if data is None:
                    st.error(WAKE_MSG)
                else:
                    st.session_state.token = data["access_token"]
                    st.session_state.email = email
                    me_resp, me_err = api_request(
                        "GET", "/auth/me",
                        headers={
                            "Authorization": f"Bearer {st.session_state.token}"},
                    )
                    me_data = parse_json(
                        me_resp) if me_resp is not None else None
                    st.session_state.is_admin = (
                        me_data or {}).get("is_admin", False)
                    st.rerun()
            elif resp.status_code == 401:
                st.error("Invalid credentials")
            else:
                data = parse_json(resp)
                st.error((data or {}).get(
                    "detail", "Login failed. Please try again."))

    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", key="reg_email")
            password = st.text_input(
                "Password", type="password", key="reg_password")
            submitted = st.form_submit_button(
                "Register", use_container_width=True)
        if submitted:
            resp, err = api_request(
                "POST", "/auth/register",
                json={"email": email, "password": password},
            )
            if err:
                st.error(err)
            elif resp.status_code == 201:
                st.success("Account created — please log in")
            else:
                data = parse_json(resp)
                st.error((data or {}).get(
                    "detail", "Registration failed. Please try again."))


# --- Upload & Analyze Page ---

def page_upload():
    st.header("Upload Network Flow CSV")
    st.caption("Upload a CICIDS-format CSV. Each row is a network flow.")

    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded and st.button("Analyze"):
        with st.spinner("Running inference..."):
            resp, err = api_request(
                "POST", "/predictions/upload",
                headers=auth_headers(),
                files={
                    "file": (uploaded.name, uploaded.getvalue(), "text/csv")},
            )

        if err:
            st.error(err)
            return

        data = parse_json(resp)
        if resp.status_code != 200 or data is None:
            detail = (data or {}).get(
                "detail", "Unknown error") if data else "Server error — please try again."
            st.error(f"Error: {detail}")
            return

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Flows", data["total_flows"])
        col2.metric("Threats Detected", data["threat_count"])
        col3.metric("Benign Flows", data["benign_count"])

        st.caption(
            f"Model: `{data['model_version']}` | Inference time: {data['inference_time_ms']:.1f}ms")

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

    resp, err = api_request(
        "GET", "/predictions/history", headers=auth_headers())
    if err:
        st.error(err)
        return

    records = parse_json(resp)
    if resp.status_code != 200 or records is None:
        st.error("Could not fetch history — please try again.")
        return
    if not records:
        st.info("No predictions yet — upload a CSV to get started")
        return

    # Summary table
    df = pd.DataFrame(records)
    df["uploaded_at"] = pd.to_datetime(
        df["uploaded_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        df[["filename", "uploaded_at", "total_flows",
            "threat_count", "benign_count", "model_version"]],
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


# --- Main router ---

if not is_logged_in():
    page_auth()
else:
    st.sidebar.title(f"Logged in as\n{st.session_state.get('email', '')}")
    if st.sidebar.button("Logout"):
        del st.session_state.token
        st.rerun()

    pages = ["Upload & Analyze", "History"]
    page = st.sidebar.radio("Navigate", pages)

    if page == "Upload & Analyze":
        page_upload()
    elif page == "History":
        page_history()


# --- Admin Page ---
# Commented out — retraining UI is provisioned for future use.
# Backend routes (app/routes/retrain.py) and training logic (app/ml/trainer.py)
# are intact but not registered. Re-enable once the labeling workflow and
# persistent training data storage are in place.

# def page_admin():
#     st.header("Admin — Model Retraining")
#
#     resp = requests.get(f"{BACKEND_URL}/admin/retrain/status", headers=auth_headers())
#     if resp.status_code != 200:
#         st.error("Could not fetch retrain status")
#         return
#
#     state = resp.json()
#     status = state["status"]
#
#     status_color = {"idle": "🟡", "running": "🔵", "done": "🟢", "failed": "🔴"}
#     st.subheader(f"{status_color.get(status, '⚪')} Status: `{status}`")
#
#     if status == "running":
#         st.info("Retraining in progress — refresh to check for updates")
#         if st.button("Refresh Status"):
#             st.rerun()
#
#     if status == "done" and state.get("metrics"):
#         m = state["metrics"]
#         col1, col2, col3 = st.columns(3)
#         col1.metric("RF Weighted F1", f"{m['rf_f1']:.4f}")
#         col2.metric("LSTM Weighted F1", f"{m['lstm_f1']:.4f}")
#         col3.metric("Winner", m["winner"].upper())
#
#     if status == "failed" and state.get("error"):
#         st.error(f"Error: {state['error']}")
#
#     st.divider()
#
#     st.write("Trigger a new training run. Trains RF + LSTM on preprocessed data, promotes the winner to production, and hot-reloads the model.")
#     st.warning("Requires preprocessed data in `/app/processed/`. Training takes several minutes.")
#
#     if status == "running":
#         st.button("Trigger Retraining", disabled=True)
#     else:
#         if st.button("Trigger Retraining", type="primary"):
#             r = requests.post(f"{BACKEND_URL}/admin/retrain", headers=auth_headers())
#             if r.status_code == 202:
#                 st.success("Retraining started — refresh to monitor progress")
#                 st.rerun()
#             elif r.status_code == 409:
#                 st.warning("Already running")
#             else:
#                 st.error(f"Error: {r.json().get('detail', 'Unknown')}")
