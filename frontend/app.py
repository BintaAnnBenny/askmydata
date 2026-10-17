import os
import sys
import html
import re
import time

import pandas as pd
import streamlit as st

# ==================================================
# CONFIGURATION
# ==================================================
st.set_page_config(
    page_title="AskMyData | Data Workspace",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_URL = os.getenv("API_URL", "http://localhost:8010").rstrip("/")
ASK_ENDPOINT = "/ask"
TIMEOUT_SECONDS = 90
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

HERE = os.path.dirname(os.path.abspath(__file__))
for path in (HERE, os.path.dirname(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from dataset_tool import (
        UploadError, load_file, make_connection, describe, is_safe_sql, run_query, TABLE,
    )
except ModuleNotFoundError as exc:
    st.error(f"Missing module: {exc.name}. Run: python -m pip install -r requirements.txt")
    st.stop()

# ==================================================
# COMPACT DASHBOARD CSS
# ==================================================
st.markdown(
    """
    <style>
    /* PAGE SIZE AND SPACING */
    .stApp {
        background: #F5F7FC;
        color: #172033;
    }
    header[data-testid="stHeader"] {
    background: transparent !important;
}

.stAppViewContainer {
    background: #F5F7FC;
}

div[data-testid="stToolbar"] {
    background: transparent !important;
}
div[data-testid="stToolbar"] *,
header[data-testid="stHeader"] * {
    color: #172033 !important;
}
    


    .block-container {
        max-width: 1600px;
        padding: 0.3rem 1.35rem 2rem;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 1rem;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.65rem;
        align-items: stretch;
    }

    div[data-testid="stVerticalBlock"] > div {
        min-width: 0;
    }

    div[data-testid="stMarkdown"] p {
        margin-top: 0;
        margin-bottom: 0.35rem !important;
        line-height: 1.4;
    }

    /* HEADINGS */
    h1, h2, h3 {
        color: #172033;
        letter-spacing: -0.03em;
        margin: 0 0 0.3rem !important;
    }

    h1 {
        font-size: 1.55rem !important;
        font-weight: 800 !important;
    }

    h2 {
        font-size: 1.08rem !important;
        font-weight: 800 !important;
    }

    h3 {
        font-size: 0.92rem !important;
        font-weight: 750 !important;
    }

    p {
        margin-bottom: 0.3rem !important;
    }

    /* BRAND HEADER */
    .brandbar {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0 0 6px;
    }

    .brandicon {
        font-size: 28px;
        color: #4F6BFF;
        line-height: 1;
    }

    .brandname {
        font-size: 22px;
        font-weight: 850;
        color: #182344;
        line-height: 1.1;
    }

    .brandtag {
        font-size: 10px;
        color: #778198;
        margin-top: 2px;
    }

    /* HERO PANEL */
    .hero {
        background: linear-gradient(110deg, #E4F4FF 0%, #ECEBFF 55%, #F6E9FF 100%);
        border: 1px solid #E0E8FF;
        border-radius: 16px;
        overflow: hidden;
        min-height: 240px;
        box-sizing: border-box;
        padding: 24px 22px;
        width: 100%;
    }

    .hero-title {
        font-size: 1.7rem;
        line-height: 1.35;
        font-weight: 850;
        color: #172344;
        margin: 0 0 14px;
    }

    .hero-title span {
        color: #4F5FFF;
    }

    .hero-copy {
        font-size: 0.9rem;
        color: #5F6D8B;
        line-height: 1.6;
        max-width: 480px;
        margin-bottom: 22px;
    }

    .feature-row {
        display: flex;
        gap: 22px;
        flex-wrap: wrap;
        font-size: 10px;
        color: #34415F;
        margin-top: 16px;
    }

    .feature {
        display: flex;
        gap: 6px;
        align-items: center;
        min-width: 0;
    }

    .feature-icon {
        display: inline-flex;
        width: 27px;
        height: 27px;
        flex-shrink: 0;
        border-radius: 8px;
        align-items: center;
        justify-content: center;
        background: #4F7DFF;
        color: white;
        font-size: 14px;
    }

    .upload-panel {
        background: rgba(255, 255, 255, 0.8);
        border: 1px solid #DCE4FF;
        padding: 9px 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }

    .panel-title {
        font-size: 12px;
        font-weight: 800;
        color: #263455;
        margin-bottom: 2px;
    }

    .panel-sub {
        font-size: 10px;
        color: #7A86A3;
        margin-bottom: 3px;
    }

    /* DATASET METRIC CARDS */
    .metric-card {
        height: 65px;
        box-sizing: border-box;
        background: white;
        border: 1px solid #E3E8F4;
        border-radius: 11px;
        padding: 9px 11px;
    }

    .metric-label {
        color: #6F7A93;
        font-size: 10px;
        margin-bottom: 4px;
    }

    .metric-value {
        color: #1B2440;
        font-size: 1.25rem;
        font-weight: 850;
        line-height: 1.1;
    }

    /* SECTION CARDS */
    .section-card {
        box-sizing: border-box;
        min-width: 0;
        background: white;
        border: 1px solid #E3E8F4;
        border-radius: 13px;
        padding: 10px 12px;
    }

    .section-head {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
    }

    .section-icon {
        color: #4F6BFF;
        font-size: 19px;
        flex-shrink: 0;
    }

    .section-title {
        color: #1C2949;
        font-size: 14px;
        font-weight: 850;
    }

    .section-sub {
        color: #7A86A3;
        font-size: 10px;
        line-height: 1.4;
        margin-top: 2px;
        margin-bottom: 5px;
    }

    /* FILE UPLOADER */
    div[data-testid="stFileUploader"] {
        width: 100%;
        min-width: 0;
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stFileUploader"] section {
        box-sizing: border-box;
        padding: 5px;
        background: white;
        border: 1px dashed #B8C6FF;
        border-radius: 9px;
    }

    div[data-testid="stFileUploader"] button {
        background: #246BFF !important;
        color: white !important;
        border: 1px solid #246BFF !important;
        opacity: 1 !important;
    }

    div[data-testid="stFileUploader"] button:hover {
        background: #1858E8 !important;
        border-color: #1858E8 !important;
        color: white !important;
    }

    div[data-testid="stFileUploader"] button p {
        color: white !important;
    }

    div[data-testid="stFileUploader"] small {
        font-size: 9px !important;
    }

    /* GENERAL BUTTONS */
    div[data-testid="stButton"] > button {
        min-height: 35px;
        padding: 0.3rem 0.65rem;
        border-radius: 8px;
        font-size: 0.78rem;
        font-weight: 750;
    }

    div[data-testid="stButton"] > button[kind="primary"] {
        color: white !important;
        background: #246BFF !important;
        border-color: #246BFF !important;
    }

    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #1858E8 !important;
        border-color: #1858E8 !important;
    }

    /* TABLES */
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        border: 1px solid #E3E8F4;
        border-radius: 8px;
        overflow: hidden;
    }

    /* CONTAINERS AND DIVIDERS */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0.45rem 0.6rem;
        border-radius: 10px;
    }

    hr {
        margin: 0.35rem 0 !important;
        border-color: #E5EAF5;
    }

    footer {
        visibility: hidden;
    }

    /* DESKTOP: KEEP SPACING CONTROLLED */
    @media (min-width: 901px) {
        .block-container {
            padding-top: 0.3rem;
            padding-bottom: 0.35rem;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.45rem;
        }
    }

    /* RESPONSIVE LAYOUT */
    @media (max-width: 900px) {
        .block-container {
            padding: 0.5rem 0.65rem;
        }

        .hero,
        .upload-panel {
            height: auto;
            min-height: 155px;
        }

        .feature-row {
            gap: 7px;
        }

        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
    }

/* Spacing between dashboard sections */
div[data-testid="stVerticalBlock"] { gap: 1rem !important; }
div[data-testid="stHorizontalBlock"] { gap: 1rem !important; }
.block-container { padding-bottom: 4rem !important; }

/* Fix dark button text on dark backgrounds */
.stApp button:disabled {
    color: #FFFFFF !important;
    opacity: 1 !important;
    background-color: #E5E7EB !important;
    border: 1px solid #D1D5DB !important;
}

/* Keep enabled buttons readable */
.stApp button:enabled {
    color: #FFFFFF !important;
}

/* Download button: consistent appearance on hover */
.stDownloadButton button,
.stDownloadButton button:hover,
.stDownloadButton button:focus,
.stDownloadButton button:active {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #2563EB !important;
    opacity: 1 !important;
}

.stDownloadButton button p,
.stDownloadButton button span {
    color: #FFFFFF !important;
}

/* Clear results button */
.stApp button[kind="secondary"],
.stApp button[kind="secondary"]:hover,
.stApp button[kind="secondary"]:focus,
.stApp button[kind="secondary"]:active {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #2563EB !important;
    opacity: 1 !important;
}

/* Dataset expander and tabs */
div[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DCE3F0 !important;
    border-radius: 10px !important;
}
div[data-testid="stTabs"] button,
div[data-testid="stTabs"] button p { color: #334155 !important; }
div[data-testid="stTabs"] button[aria-selected="true"],
div[data-testid="stTabs"] button[aria-selected="true"] p { color: #2563EB !important; }

/* Fix full dataset expander heading */
div[data-testid="stExpander"] summary {
    background-color: #FFFFFF !important;
    color: #172554 !important;
}

div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary span {
    color: #172554 !important;
}

/* Upload card: keep all wording, with the light-blue upload box underneath */
    .stApp .st-key-upload_card {
        height: auto !important;
        min-height: 0 !important;
        padding: 16px 16px 12px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        justify-content: flex-start !important;
        gap: 10px !important;
        background: #FFFFFF !important;
        border: 1px solid #DCE4FF !important;
        border-radius: 16px !important;
        box-sizing: border-box !important;
    }
    .stApp .st-key-upload_card .upload-heading {
        text-align: center !important;
        padding: 4px 0 2px !important;
    }
    .stApp .st-key-upload_card .upload-arrow {
        color: #4568D8 !important;
        font-size: 26px !important;
        line-height: 1.2 !important;
        margin-bottom: 6px !important;
    }
    .stApp .st-key-upload_card .panel-title {
        color: #263455 !important;
        text-align: center !important;
        font-weight: 800 !important;
        margin-bottom: 4px !important;
    }
    .stApp .st-key-upload_card .panel-sub {
        color: #64748B !important;
        text-align: center !important;
    }
    .stApp .st-key-upload_card div[data-testid="stFileUploader"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .stApp .st-key-upload_card div[data-testid="stFileUploader"] section,
    .stApp .st-key-upload_card div[data-testid="stFileUploaderDropzone"] {
        min-height: 110px !important;
        padding: 14px !important;
        background: #EEF5FF !important;
        border: 1px dashed #7AA7FF !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        box-sizing: border-box !important;
        /* center the Upload button and the hint text */
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        text-align: center !important;
    }
    /* hint text: centered, readable, and placed under the button */
    .stApp .st-key-upload_card div[data-testid="stFileUploaderDropzoneInstructions"] {
        display: none !important;  /* built-in hint says 200MB; real limit is shown below the box */
    }
    .stApp .st-key-upload_card div[data-testid="stFileUploaderDropzoneInstructions"] span,
    .stApp .st-key-upload_card div[data-testid="stFileUploaderDropzoneInstructions"] small {
        color: #64748B !important;
        font-size: 11px !important;
    }
    .stApp .st-key-upload_card div[data-testid="stFileUploaderDropzone"] button {
        order: 1;
        margin: 0 auto !important;
    }
    .stApp .st-key-upload_card .upload-file-note {
        padding-top: 2px !important;
        font-size: 11px !important;
    }

    /* Uploaded file chip: light instead of black */
    .stApp .st-key-upload_card div[data-testid="stFileChip"] {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
    }
    .stApp .st-key-upload_card div[data-testid="stFileChip"] * {
        color: #172033 !important;
    }
    .stApp .st-key-upload_card div[data-testid="stFileChip"] div { background: transparent !important; }
    .stApp .st-key-upload_card div[data-testid="stFileChip"] svg { color: #2563EB !important; }
    .stApp .st-key-upload_card button[data-testid="stFileChipDeleteBtn"] *,
    .stApp .st-key-upload_card button[data-testid="stFileChipDeleteBtn"] svg { color: #FFFFFF !important; }

    /* Question field: neutral border and white background, also when focused */
    .stApp div[data-testid="stTextInputRootElement"],
    .stApp div[data-testid="stTextInputRootElement"]:hover,
    .stApp div[data-testid="stTextInputRootElement"]:focus-within,
    .stApp div[data-testid="stTextInput"] div[data-baseweb="input"],
    .stApp div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stApp div[data-testid="stTextInput"] input:disabled {
        -webkit-text-fill-color: #64748B !important;
        opacity: 1 !important;
    }
    .stApp div[data-testid="stTextInput"] input,
    .stApp div[data-testid="stTextInput"] input:focus,
    .stApp div[data-testid="stTextInput"] input:active {
        background: transparent !important;
        color: #172033 !important;
        -webkit-text-fill-color: #172033 !important;
        caret-color: #2563EB !important;
        border: 0 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stApp div[data-testid="stTextInput"] input::placeholder {
        color: #64748B !important;
        -webkit-text-fill-color: #64748B !important;
        opacity: 1 !important;
    }

    /* Alerts: no background, plain black text */
    .stApp div[data-testid="stAlertContainer"],
    .stApp div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]),
    .stApp div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]),
    .stApp div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]),
    .stApp div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        padding-left: 0 !important;
        color: #000000 !important;
    }
    .stApp div[data-testid="stAlertContainer"] * { color: #000000 !important; }

    /* Code blocks (SQL, column list): light instead of black */
    .stApp div[data-testid="stCode"],
    .stApp div[data-testid="stCode"] pre {
        background: #F1F5F9 !important;
        border: 1px solid #DCE3F0 !important;
        border-radius: 10px !important;
    }
    .stApp div[data-testid="stCode"] code,
    .stApp div[data-testid="stCode"] code span {
        color: #172033 !important;
        background: transparent !important;
    }

    /* Chart / table hover toolbar: visible icons and readable tooltip */
    div[data-testid="stElementToolbarButtonContainer"] {
        background: #FFFFFF !important;
        border: 1px solid #DCE3F0 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(23, 32, 51, 0.12) !important;
    }
    div[data-testid="stElementToolbarButton"] button,
    div[data-testid="stElementToolbarButton"] svg {
        color: #334155 !important;
        opacity: 1 !important;
    }
    div[data-testid="stElementToolbarButton"] button:hover { background: #EEF2FF !important; }
    div[data-testid="stTooltipContent"],
    div[data-testid="stTooltipContent"] * {
        background: #172033 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)



# ==================================================
# SESSION STATE
# ==================================================
defaults = {
    "dataset_df": None,
    "dataset_con": None,
    "dataset_name": None,
    "dataset_notes": [],
    "dataset_signature": None,
    "question_result": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================================================
# HEADER + UPLOAD: SAME ROW AS REFERENCE
# ==================================================
st.markdown(
    """
    <div class="brandbar">
      <div class="brandicon">▥</div>
      <div>
        <div class="brandname">AskMyData</div>
        <div class="brandtag">Upload. Ask. Visualize. Get insights.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_col, upload_col = st.columns([1.65, 1], gap="small")
with hero_col:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-title">Turn Your Data Into <span>Answers</span></div>
          <div class="hero-copy">Upload your dataset, ask questions in plain English, and get instant
          charts, comparisons, and AI-powered insights.</div>
          <div class="feature-row">
            <div class="feature"><span class="feature-icon" style="background:#20B889">↥</span><span><b>Upload</b><br>CSV or Excel</span></div>
            <div class="feature"><span class="feature-icon" style="background:#8155F5">☏</span><span><b>Ask questions</b><br>in natural language</span></div>
            <div class="feature"><span class="feature-icon" style="background:#3689FF">▥</span><span><b>Visualizations</b><br>and comparisons</span></div>
            <div class="feature"><span class="feature-icon" style="background:#F4A623">✦</span><span><b>AI-powered</b><br>insights</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with upload_col:
    with st.container(key="upload_card"):
        st.markdown(
            """
            <div class="upload-heading">
              <div class="upload-arrow">⇧</div>
              <div class="panel-title">Upload your dataset</div>
              <div class="panel-sub">Choose a CSV or Excel file to begin</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=["csv", "xlsx", "xlsm"],
            help="Supported formats: CSV, XLSX, XLSM. Maximum size: 10 MB.",
            key="dataset_uploader",
            label_visibility="collapsed",
        )
        st.markdown(
            '<div class="panel-sub upload-file-note">CSV, XLSX, XLSM · Max file size: 10 MB</div>',
            unsafe_allow_html=True,
        )

# Process upload without changing the existing dataset logic.
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        st.error("The uploaded file exceeds the 10 MB limit.")
    else:
        signature = (uploaded_file.name, len(file_bytes), hash(file_bytes))
        if signature != st.session_state.dataset_signature:
            try:
                with st.spinner("Preparing your dataset..."):
                    new_df, notes = load_file(uploaded_file.name, file_bytes)
                    new_con = make_connection(new_df)
                old_con = st.session_state.dataset_con
                st.session_state.dataset_df = new_df
                st.session_state.dataset_con = new_con
                st.session_state.dataset_name = uploaded_file.name
                st.session_state.dataset_notes = notes
                st.session_state.dataset_signature = signature
                st.session_state.question_result = None
                if old_con is not None:
                    try:
                        old_con.close()
                    except Exception:
                        pass
            except UploadError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not load the dataset: {exc}")

df = st.session_state.dataset_df
con = st.session_state.dataset_con

# ==================================================
# DATASET OVERVIEW
# ==================================================
st.markdown(
    '<div class="section-head"><span class="section-icon">▤</span><div><div class="section-title">Dataset Overview</div><div class="section-sub">Key information about your uploaded data.</div></div></div>',
    unsafe_allow_html=True,
)
if df is None:
    metrics = [("Total Rows", "—"), ("Total Columns", "—"), ("Numeric Columns", "—"), ("Categorical Columns", "—"), ("Missing Values", "—")]
else:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    metrics = [
        ("Total Rows", f"{len(df):,}"),
        ("Total Columns", f"{len(df.columns):,}"),
        ("Numeric Columns", f"{len(numeric_cols):,}"),
        ("Categorical Columns", f"{len(df.columns) - len(numeric_cols):,}"),
        ("Missing Values", f"{int(df.isna().sum().sum()):,}"),
    ]
metric_cols = st.columns(5, gap="small")
for col, (label, value) in zip(metric_cols, metrics):
    with col:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div><div class="metric-value">{html.escape(value)}</div></div>',
            unsafe_allow_html=True,
        )


# ==================================================
# GEMINI HELPERS (retry + friendly errors)
# ==================================================
def gemini_text(prompt):
    """Call Gemini and return its text. Retries temporary errors; raises RuntimeError with a clear message."""
    from dotenv import find_dotenv, load_dotenv
    from google import genai

    load_dotenv(find_dotenv(usecwd=True), override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from your .env file.")
    client = genai.Client(api_key=api_key)

    retries = 4
    for attempt in range(retries):
        try:
            return (client.models.generate_content(model=model_name, contents=prompt).text or "").strip()
        except Exception as exc:
            msg = str(exc).lower()
            if "perday" in msg or "per day" in msg:
                raise RuntimeError("The daily Gemini quota is used up. Try again after it resets.") from exc
            if any(k in msg for k in ("api key", "api_key_invalid", "401", "403", "permission")):
                raise RuntimeError("Gemini rejected the API key. Check GEMINI_API_KEY in your .env file.") from exc
            if "404" in msg or "not found" in msg:
                raise RuntimeError(f"Gemini model '{model_name}' was not found. Set GEMINI_MODEL in your .env file to a model your key can use.") from exc
            temporary = any(k in msg for k in ("503", "429", "overloaded", "high demand", "unavailable", "resource_exhausted"))
            if temporary and attempt < retries - 1:
                found = re.search(r"retry in ([\d.]+)s", msg)
                time.sleep(min(float(found.group(1)) + 1, 30) if found else 2 * (attempt + 1))
                continue
            if temporary:
                raise RuntimeError("Gemini is busy right now. Please try again in a minute.") from exc
            raise RuntimeError(f"Gemini request failed: {exc}") from exc


def clean_sql(text):
    return text.replace("```sql", "").replace("```", "").strip().rstrip(";").strip()

# ==================================================
# ASK A QUESTION
# ==================================================
st.markdown(
    '<div class="section-head" style="margin-top:5px;"><span class="section-icon">▰</span><div><div class="section-title">Ask a Question</div><div class="section-sub">Use natural language to analyze your dataset and get visualizations, comparisons, and insights.</div></div></div>',
    unsafe_allow_html=True,
)
question_col, button_col = st.columns([5, 1], gap="small")
with question_col:
    question = st.text_input(
        "Ask anything about your data",
        key="upload_question",
        placeholder="Ask anything about your data...",
        label_visibility="collapsed",
        disabled=df is None or con is None,
    )
with button_col:
    analyze_clicked = st.button(
        "✦ Analyze question",
        type="primary",
        width="stretch",
        key="analyze_question",
        disabled=df is None or con is None,
    )

st.markdown(
    '<div style="font-size:10px;color:#74809B;padding:1px 0 4px;">💡 Example questions: Average value by category　·　Top 5 products　·　Monthly trend　·　Compare categories　·　Show distribution</div>',
    unsafe_allow_html=True,
)

if analyze_clicked:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        try:
            columns_text, sample_text = describe(con, df)
            prompt = f"""
You are a careful data analyst.
Convert the user's question into exactly ONE DuckDB SELECT query.
The uploaded table is named: {TABLE}
Available columns and types:
{columns_text}
Sample rows:
{sample_text}
Rules:
- Return only SQL, without Markdown or backticks.
- Use only the table named {TABLE} and listed columns.
- Use DuckDB SQL syntax and one read-only SELECT statement only.
- Never use INSERT, UPDATE, DELETE, DROP, COPY, file-reading functions, or external data sources.
- For grouped results, return meaningful column aliases.
- Use LIMIT 100 for non-aggregate results.
- If a column describes units, levels or categories that make adding values together misleading (for example units, aggregation level, variable name), filter or group by it so unlike values are never summed together.
- If the question cannot be answered from these columns, return exactly CANNOT_ANSWER.
Question: {question}
"""
            with st.spinner("Analyzing your data..."):
                sql = clean_sql(gemini_text(prompt))
                if sql == "CANNOT_ANSWER":
                    sql, result_df = None, None
                elif not is_safe_sql(sql):
                    sql, result_df = "BLOCKED", None
                else:
                    try:
                        result_df = run_query(con, sql, timeout=20, max_rows=1000)
                    except Exception as first_error:
                        # Give the model one chance to fix its own SQL.
                        fixed = clean_sql(gemini_text(
                            prompt + f"\nYour previous query failed.\nQuery: {sql}\nError: {first_error}\nReturn a corrected query only."
                        ))
                        if fixed == "CANNOT_ANSWER" or not is_safe_sql(fixed):
                            raise RuntimeError("The generated query could not be run. Try rephrasing your question.") from first_error
                        try:
                            sql, result_df = fixed, run_query(con, fixed, timeout=20, max_rows=1000)
                        except Exception as second_error:
                            raise RuntimeError("The generated query could not be run. Try rephrasing your question.") from second_error

            if sql is None:
                st.warning("This question cannot be answered using the uploaded dataset.")
                st.info("Available columns:")
                st.code(columns_text)
            elif sql == "BLOCKED":
                st.error("The generated query failed the SQL safety check. Try rephrasing your question.")
            else:
                st.session_state.question_result = {"question": question, "sql": sql, "data": result_df.round(2)}
                st.session_state.pop("explanation_key", None)
                st.rerun()
        except Exception as exc:
            st.error(f"Could not answer the question: {exc}")

# ==================================================
# RESULTS: TABLE + CHART + INSIGHTS IN ONE ROW
# ==================================================
st.markdown(
    '<div class="section-head" style="margin-top:4px;"><span class="section-icon">▥</span><div><div class="section-title">Results</div><div class="section-sub">Query results, table, visualization and AI insights.</div></div></div>',
    unsafe_allow_html=True,
)
result = st.session_state.question_result
if result is None:
    left, middle, right = st.columns([1, 1.15, 1], gap="small")
    with left:
        st.markdown('<div class="section-card"><b style="font-size:12px;">▦ Result Table</b><div style="font-size:10px;color:#8290AA;margin-top:8px;">Your query results will appear here.</div></div>', unsafe_allow_html=True)
    with middle:
        st.markdown('<div class="section-card"><b style="font-size:12px;">▥ Visualization</b><div style="font-size:10px;color:#8290AA;margin-top:8px;">Your chart will appear here after analysis.</div></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-card"><b style="font-size:12px;">✦ AI Insights</b><div style="font-size:10px;color:#8290AA;margin-top:8px;">Insights based on your data will appear here.</div></div>', unsafe_allow_html=True)
else:
    result_df = result["data"]
    table_col, chart_col, insight_col = st.columns([1, 1.15, 1], gap="small")
    with table_col:
        st.markdown("**▦ Result Table**")
        if result_df.empty:
            st.info("No matching rows.")
        else:
            st.dataframe(result_df, width="stretch", hide_index=True, height=220)
        st.download_button(
            "↓ Download results",
            data=result_df.to_csv(index=False).encode("utf-8"),
            file_name="askmydata_results.csv",
            mime="text/csv",
            width="stretch",
        )
    with chart_col:
        st.markdown("**▥ Visualization**")
        result_numeric = [
            col for col in result_df.select_dtypes(include="number").columns
            if col.lower() not in ["year", "id"]
        ]
        result_labels = [col for col in result_df.columns if col not in result_numeric]
        if result_numeric and len(result_df) > 1:
            chart_df = result_df.copy()
            if result_labels:
                chart_df = chart_df.set_index(result_labels[0])
                if pd.api.types.is_numeric_dtype(chart_df.index):
                    chart_df.index = chart_df.index.astype(str)  # show 2013, not 2,013
            chart_df = chart_df[result_numeric]
            if result_labels and chart_df.index.astype(str).str.fullmatch(r"\d{4}").all():
                st.line_chart(chart_df, height=220)
            else:
                st.bar_chart(chart_df, height=220, sort=False)
        else:
            st.info("A chart needs numeric results and more than one row.")
    with insight_col:
        st.markdown("**✦ AI Insights**")
        try:
            from dotenv import find_dotenv, load_dotenv
            load_dotenv(find_dotenv(usecwd=True), override=True)
            if not os.getenv("GEMINI_API_KEY"):
                st.info("Add GEMINI_API_KEY to enable AI explanations.")
            elif result_df.empty:
                st.info("No rows were returned to explain.")
            else:
                # Cache the explanation so reruns do not call Gemini again.
                explanation_key = (result["question"], result["sql"], result_df.to_json())
                if st.session_state.get("explanation_key") != explanation_key:
                    explanation_prompt = f"""
You are a business data analyst. Answer the user's question based only on these query results.
Question: {result["question"]}
SQL used: {result["sql"]}
Results:
{result_df.head(30).to_string(index=False)}
Give a concise direct answer (2-3 sentences) with key values and comparisons. Do not invent facts. Do not use Markdown headings. Mention units (for example "millions", "%") only if they appear in the question, the SQL or the results; never assume a currency. Write numbers with thousands separators.
"""
                    with st.spinner("Preparing AI insights..."):
                        st.session_state.explanation_text = gemini_text(explanation_prompt) or "No explanation generated."
                    st.session_state.explanation_key = explanation_key
                st.markdown(st.session_state.get("explanation_text", "").replace("$", "\\$"))
        except Exception as exc:
            st.warning(f"Could not generate AI insights: {exc}")
        with st.expander("View SQL query"):
            st.code(result["sql"], language="sql")
        if st.button("Clear results", key="clear_question_result"):
            st.session_state.question_result = None
            st.session_state.pop("explanation_key", None)
            st.session_state.pop("explanation_text", None)
            st.rerun()

# Detailed data inspection is available without forcing it into the main dashboard.
if df is not None:
    with st.expander("View full dataset, column information and data quality"):
        preview_tab, columns_tab, quality_tab = st.tabs(["Data preview", "Column information", "Data quality"])
        with preview_tab:
            st.dataframe(df.head(500), width="stretch", hide_index=True, height=300)
        with columns_tab:
            info_df = pd.DataFrame({
                "Column": df.columns,
                "Data type": [str(dtype) for dtype in df.dtypes],
                "Missing values": [int(df[col].isna().sum()) for col in df.columns],
                "Unique values": [int(df[col].nunique(dropna=True)) for col in df.columns],
            })
            st.dataframe(info_df, width="stretch", hide_index=True)
        with quality_tab:
            st.write(f"**Duplicate rows:** {int(df.duplicated().sum()):,}")
            total_cells = len(df) * len(df.columns)
            missing_percent = int(df.isna().sum().sum()) / total_cells * 100 if total_cells else 0
            st.write(f"**Missing cells:** {int(df.isna().sum().sum()):,} ({missing_percent:.2f}%)")
            for note in st.session_state.dataset_notes:
                st.write(f"- {note}")

