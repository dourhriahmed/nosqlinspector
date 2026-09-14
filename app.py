import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from connectors import CONNECTORS
from schema_inferrer import infer_schema
from visualizer import build_tree_figure, build_security_gauge
from security_auditor import run_audit
from exporter import (
    export_security_report_json,
    export_security_report_csv,
    export_security_report_pdf
)
from chatbot import render_chatbot
from i18n import get_text
from drift_detector import compare_snapshots, save_snapshot, load_snapshots
from semantic_profiler import (
    SemanticProfiler,
    export_report_json as export_quality_json,
    export_report_csv as export_quality_csv,
    generate_pdf_report as generate_quality_pdf
)
from streamlit.runtime.scriptrunner import get_script_run_ctx
from realtime_monitor import sync_listeners, cleanup_session, get_changed_collections


class SafeJSONEncoder(json.JSONEncoder):
    """Encoder JSON qui convertit les types non-sérialisables en string."""
    def default(self, obj):
        import datetime
        try:
            from bson import ObjectId
            if isinstance(obj, ObjectId):
                return str(obj)
        except ImportError:
            pass
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return str(obj)

from PIL import Image as _PILImage
_favicon = _PILImage.open("images/favicon.png")
st.set_page_config(
    page_title="NoSQL Schema Inspector",
    page_icon=_favicon,
    layout="wide"
)

# ── INITIALISATION ET SÉLECTION DE LA LANGUE ────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "English"

selected_lang_display = st.sidebar.selectbox(
    "Select Language / Choisir la langue",
    ["US", "FR"],
    index=0 if st.session_state.get("lang", "English") == "English" else 1,
    key="global_lang_selector",
    label_visibility="collapsed"
)
st.session_state["lang"] = "English" if selected_lang_display == "US" else "Français"

# ══════════════════════════════════════════════════════
#  PREMIUM CSS - animations + glassmorphism + SaaS style
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Load country flag polyfill font for Windows/Chromium users */
@font-face {
  font-family: 'Twemoji Country Flags';
  src: url('https://cdn.jsdelivr.net/npm/country-flag-emoji-polyfill@0.1/dist/TwemojiCountryFlags.woff2') format('woff2');
  unicode-range: U+1F1E6-1F1FF; /* Range for country flag symbols */
}

/* ─── Keyframes ─────────────────────────────────── */
@keyframes fadeInUp   { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn     { from { opacity:0; } to { opacity:1; } }
@keyframes slideInLeft{ from { opacity:0; transform:translateX(-30px); } to { opacity:1; transform:translateX(0); } }
@keyframes gradientBG { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
@keyframes pulse      { 0%,100%{ box-shadow:0 0 0 0 rgba(99,102,241,.4); } 50%{ box-shadow:0 0 0 8px rgba(99,102,241,0); } }
@keyframes shimmer    { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
@keyframes glow       { 0%,100%{ text-shadow:0 0 8px rgba(139,92,246,.6); } 50%{ text-shadow:0 0 20px rgba(139,92,246,1),0 0 40px rgba(99,102,241,.5); } }

/* ─── Global ─────────────────────────────────────── */
html, body, select, option, [data-baseweb="select"] * {
  font-family: 'Twemoji Country Flags', 'Inter', sans-serif !important;
}

/* Hide Deploy button, main menu icon, and footer, but keep transparent header so sidebar collapse/expand works */
.stDeployButton { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }
[data-testid="stHeader"] {
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: none !important;
    box-shadow: none !important;
}

[data-testid="stSidebarUserContent"] { padding-top: 0px !important; margin-top: -10px !important; }

.stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 30%, #e2e8f0 60%, #cbd5e1 100%) !important;
    background-size: 400% 400% !important;
    animation: gradientBG 18s ease infinite !important;
    color: #0f172a !important;
}

/* ─── Main content animation ─────────────────────── */
.main .block-container, [data-testid="stAppViewBlockContainer"] {
    animation: fadeInUp 0.6s ease both;
    padding-top: 0px !important;
    margin-top: -30px !important;
}

/* ─── Sidebar glassmorphism ───────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(20px) !important;
    border-right: 1px solid rgba(139,92,246,0.15) !important;
    box-shadow: 4px 0 30px rgba(0,0,0,0.05) !important;
    animation: slideInLeft 0.5s ease both !important;
}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: #475569 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #0f172a !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* ─── Sidebar inputs ─────────────────────────────── */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: #ffffff !important;
    border: 1px solid rgba(139,92,246,0.3) !important;
    color: #0f172a !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
[data-testid="stSidebar"] input:focus,
[data-testid="stSidebar"] textarea:focus {
    border-color: #8b5cf6 !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.2), 0 0 12px rgba(139,92,246,0.15) !important;
    background: #ffffff !important;
}
[data-testid="stSidebar"] [data-baseweb="multi-select"] input {
    width: 0px !important;
    min-width: 0px !important;
    max-width: 0px !important;
    padding: 0 !important;
    margin: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
            
/* ─── Primary Button ─────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%) !important;
    background-size: 200% 200% !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.02em !important;
    padding: 12px 22px !important;
    width: 100% !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(99,102,241,0.35) !important;
    animation: pulse 2.5s infinite !important;
}
.stButton > button p, .stButton > button div, .stButton > button span {
    color: #ffffff !important;
}
.stButton > button:hover {
    background-position: right center !important;
    transform: translateY(-2px) scale(1.02) !important;
    box-shadow: 0 8px 25px rgba(139,92,246,0.55) !important;
    animation: none !important;
}
.stButton > button:active {
    transform: translateY(0) scale(0.99) !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.3) !important;
}

/* ─── Download Button ────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: #ffffff !important;
    color: #4f46e5 !important;
    border: 1px solid rgba(139,92,246,0.35) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.25s ease !important;
    animation: none !important;
    box-shadow: none !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: rgba(139,92,246,0.05) !important;
    border-color: #8b5cf6 !important;
    color: #4338ca !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 6px -1px rgba(139,92,246,0.1) !important;
}

/* ─── Metric cards ───────────────────────────────── */
[data-testid="metric-container"] {
    background: #ffffff !important;
    border: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    backdrop-filter: blur(10px) !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.8) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    animation: fadeInUp 0.7s ease both !important;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 15px rgba(139,92,246,0.1), inset 0 1px 0 rgba(255,255,255,1) !important;
}
[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #0f172a !important;
    font-size: 32px !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
}

/* ─── Tabs ───────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.5) !important;
    border-bottom: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 4px 8px 0 !important;
    gap: 4px !important;
    backdrop-filter: blur(10px) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    border-radius: 8px 8px 0 0 !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 10px 20px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.25s ease !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #4f46e5 !important;
    border-bottom: 2px solid #8b5cf6 !important;
    background: rgba(139,92,246,0.05) !important;
    text-shadow: none !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #6366f1 !important;
    background: rgba(139,92,246,0.07) !important;
}
[data-testid="stTabPanel"] {
    background: transparent !important;
    animation: fadeIn 0.4s ease both !important;
    padding-top: 20px !important;
}

/* ─── Divider ─────────────────────────────────────── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(139,92,246,0.4), transparent) !important;
    margin: 24px 0 !important;
}

/* ─── Headers ─────────────────────────────────────── */
h1,h2,h3 { color: #0f172a !important; letter-spacing: -0.02em !important; font-weight: 700 !important; }
h2 { font-size: 20px !important; }
h3 { font-size: 16px !important; }

/* ─── Alerts ─────────────────────────────────────── */
[data-testid="stAlert"] {
    background: #ffffff !important;
    border-radius: 10px !important;
    border-left-width: 3px !important;
    backdrop-filter: blur(8px) !important;
    font-size: 13px !important;
    color: #334155 !important;
    box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1) !important;
    animation: fadeIn 0.4s ease !important;
}

/* ─── Dataframe ───────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
}

/* ─── Expander ────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 10px !important;
    backdrop-filter: blur(10px) !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(139,92,246,0.4) !important;
}
[data-testid="stExpander"] summary { color: #64748b !important; font-size: 13px !important; }

/* ─── Selectbox / Inputs ──────────────────────────── */
[data-baseweb="select"] > div {
    background: #ffffff !important;
    border-color: rgba(139,92,246,0.3) !important;
    border-radius: 8px !important;
    color: #0f172a !important;
}
[data-testid="stNumberInput"] input {
    background: #ffffff !important;
    border-color: rgba(139,92,246,0.3) !important;
    color: #0f172a !important;
    border-radius: 8px !important;
}

/* ─── Multiselect tags ────────────────────────────── */
[data-baseweb="tag"] {
    background: linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    border-radius: 6px !important;
    font-size: 12px !important;
}
[data-baseweb="multi-select"] {
    background: #ffffff !important;
    border-color: rgba(139,92,246,0.3) !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    flex-wrap: wrap !important;
    row-gap: 6px !important;
    padding-top: 6px !important;
    padding-bottom: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div {
    flex-wrap: wrap !important;
    row-gap: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    min-width: 0 !important;
    width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* ─── Spinner ─────────────────────────────────────── */
[data-testid="stSpinner"] > div { border-top-color: #8b5cf6 !important; }

/* ─── Scrollbar ───────────────────────────────────── */
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(139,92,246,0.4); border-radius:10px; }
::-webkit-scrollbar-thumb:hover { background:rgba(139,92,246,0.7); }
</style>
""", unsafe_allow_html=True)

# ── INITIALISATION LANGUE (I18N) ────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "English"

# ── HEADER ANIMÉ ────────────────────────────────────
st.markdown(f"""
<div style="
    padding: 0px 0 15px 0;
    margin-top: 0px;
    margin-bottom: 20px;
    border-bottom: 1px solid rgba(139,92,246,0.25);
    animation: fadeInUp 0.5s ease both;
">
    <div style="display:flex; align-items:center; gap:16px;">
        <div style="
            background: linear-gradient(135deg,#6366f1,#a855f7);
            border-radius: 14px;
            width: 52px; height: 52px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 6px 20px rgba(99,102,241,0.45), 0 0 40px rgba(139,92,246,0.2);
        "><svg xmlns='http://www.w3.org/2000/svg' width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><ellipse cx='12' cy='5' rx='9' ry='3'/><path d='M21 12c0 1.66-4 3-9 3s-9-1.34-9-3'/><path d='M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5'/></svg></div>
        <div>
            <h1 style="
                margin:0;
                font-size:28px;
                font-weight:800;
                letter-spacing:-0.03em;
                background: linear-gradient(135deg,#e0e7ff,#c4b5fd,#a5b4fc);
                -webkit-background-clip:text;
                -webkit-text-fill-color:transparent;
            ">{get_text('app_title')}</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#64748b;font-weight:400;">
                {get_text('app_subtitle')}
            </p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────

st.sidebar.header(get_text("config_header"))


db_type = st.sidebar.selectbox(
    get_text("db_type"),
    list(CONNECTORS.keys())
)

st.sidebar.subheader(get_text("conn_params"))

conn_params = {}

if db_type == "MongoDB":
    conn_params["uri"] = st.sidebar.text_input("URI", value="mongodb://localhost:27017")
    db_name = st.sidebar.text_input(get_text("mongo_db_name"), value="nosql_test")

elif db_type == "CouchDB":
    conn_params["url"] = st.sidebar.text_input("URL", value="http://localhost:5984")
    conn_params["username"] = st.sidebar.text_input(get_text("couch_user"), value="admin")
    conn_params["password"] = st.sidebar.text_input(get_text("couch_pass"), type="password")
    db_name = ""  # CouchDB : pas de db_name, les bases sont les collections

elif db_type == "Firebase Firestore":
    st.sidebar.info(
        get_text("fb_info")
    )
    conn_params["credentials_path"] = st.sidebar.text_input(
        get_text("fb_cred_path"),
        value="",
        placeholder="/chemin/vers/serviceAccountKey.json"
    )
    st.sidebar.markdown(get_text("fb_manual_label"))
    fb_project_id   = st.sidebar.text_input(get_text("fb_project_id"), placeholder="mon-projet-firebase")
    fb_client_email = st.sidebar.text_input(
        get_text("fb_client_email"),
        placeholder="firebase-adminsdk-xxx@mon-projet.iam.gserviceaccount.com"
    )
    fb_private_key  = st.sidebar.text_area(
        get_text("fb_private_key"),
        placeholder="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
        height=120
    )
    if fb_project_id and fb_client_email and fb_private_key:
        conn_params["credentials_dict"] = {
            "type": "service_account",
            "project_id": fb_project_id,
            "private_key": fb_private_key.replace("\\n", "\n"),
            "client_email": fb_client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    else:
        conn_params["credentials_dict"] = None
    db_name = ""

limit = st.sidebar.number_input(get_text("doc_limit"), min_value=0, value=0)

# ── CONNEXION + ANALYSE EN UN SEUL BOUTON ─────────────
if st.sidebar.button(get_text("btn_connect")):
    # Vider tout l'état de la connexion précédente et nettoyer les anciens écouteurs
    ctx = get_script_run_ctx()
    session_id = ctx.session_id if ctx else None
    if session_id:
        cleanup_session(session_id)

    for _key in ["connector", "collections", "db_name", "db_type",
                 "limit", "selected_collections", "analyser_clicked"]:
        st.session_state.pop(_key, None)
    # Vider les caches de documents (clés "docs_*")
    for _key in [k for k in st.session_state if k.startswith("docs_")]:
        del st.session_state[_key]

    connector = CONNECTORS[db_type]()
    try:
        success = connector.connect(**conn_params)
        err_msg = ""
    except Exception as e:
        success = False
        err_msg = str(e)

    if not success:
        base_msg = get_text("err_connect").format(db_type=db_type)
        final_msg = f"<b>{base_msg}</b><br/><span style='font-size: 0.9em; opacity: 0.9;'>{err_msg}</span>" if err_msg else base_msg
        st.sidebar.markdown(
            f"<div style='background-color: rgba(239, 68, 68, 0.1); color: #f87171; padding: 12px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3); margin-bottom: 1rem;'>{final_msg}</div>",
            unsafe_allow_html=True
        )
    else:
        st.sidebar.success(get_text("success_connect").format(db_type=db_type))
        collections = connector.get_collections(db_name)

        if not collections:
            st.sidebar.warning(get_text("warn_no_collections"))
        else:
            selected = collections
            st.session_state["connector"] = connector
            st.session_state["collections"] = collections
            st.session_state["db_name"] = db_name
            st.session_state["db_type"] = db_type
            st.session_state["limit"] = limit
            st.session_state["selected_collections"] = selected
            st.session_state["analyser_clicked"] = True

# ── SÉLECTION MANUELLE DES COLLECTIONS (après connexion) ──
# N'afficher le filtre QUE si la base sélectionnée correspond à la connexion active
if (
    "collections" in st.session_state
    and st.session_state["collections"]
    and st.session_state.get("db_type") == db_type
):
    collections = st.session_state["collections"]
    current_db_type = st.session_state["db_type"]

    if current_db_type == "CouchDB":
        label_choisir = get_text("filter_bases")
    else:
        label_choisir = get_text("filter_colls")

    selected_filtered = st.sidebar.multiselect(
        label_choisir,
        collections,
        default=st.session_state.get("selected_collections", collections[:3])
    )

    if st.sidebar.button(get_text("btn_apply")):
        st.session_state["selected_collections"] = selected_filtered
        st.session_state["analyser_clicked"] = True
        for _c in selected_filtered:
            st.session_state.pop(f"docs_{_c}", None)

# ── ANALYSE ET AFFICHAGE ──────────────────────────────
if st.session_state.get("analyser_clicked") and "selected_collections" in st.session_state:
    connector = st.session_state["connector"]
    db_name = st.session_state["db_name"]
    limit = st.session_state["limit"]
    selected = st.session_state["selected_collections"]

    # Synchroniser les écouteurs en arrière-plan
    ctx = get_script_run_ctx()
    session_id = ctx.session_id if ctx else None
    if session_id:
        sync_listeners(session_id, connector, db_name, selected)

        # Watcher léger exécuté toutes les 2 secondes
        @st.fragment(run_every=2)
        def change_watcher(sid):
            changed_cols = get_changed_collections(sid)
            if changed_cols:
                has_changes = False
                for c in changed_cols:
                    cache_key = f"docs_{c}"
                    if cache_key in st.session_state:
                        st.session_state.pop(cache_key, None)
                        has_changes = True
                if has_changes:
                    st.toast("Modification détectée ! Rafraîchissement automatique du schéma...", icon=":material/sync:")
                    import time
                    time.sleep(0.5)
                    st.rerun()

        change_watcher(session_id)

    if not selected:
        st.warning(get_text("warn_select_coll"))
    else:
        tabs = st.tabs(selected)

        for tab, coll_name in zip(tabs, selected):
            with tab:
                # ── FETCH DOCS (avec cache par collection) ──────────────
                _cache_key = f"docs_{coll_name}"
                if _cache_key not in st.session_state:
                    with st.spinner(get_text("loading_data").format(coll_name=coll_name)):
                        _fresh = connector.get_documents(
                            db_name, coll_name,
                            limit=limit if limit > 0 else None
                        )
                    st.session_state[_cache_key] = _fresh

                docs = st.session_state[_cache_key]

                if not docs:
                    st.warning(get_text("warn_no_docs").format(coll_name=coll_name))
                    continue

                schema = infer_schema(docs)

                if not schema:
                    st.warning(get_text("warn_empty_schema").format(coll_name=coll_name))
                    continue

                # ── EN-TÊTE : titre + bouton Actualiser (top-right) ───────
                col_title, col_btn = st.columns([8, 2])
                with col_title:
                    st.markdown(
                        f"<span style='font-size:13px;color:#6b7280'>"
                        f"{get_text('label_collection')}<b style='color:#1e3a5f'>{coll_name}</b></span>",
                        unsafe_allow_html=True
                    )
                with col_btn:
                    if st.button(
                        get_text("btn_refresh"),
                        key=f"reload_{coll_name}",
                        help=get_text("help_refresh"),
                        use_container_width=True
                    ):
                        # Supprimer le cache de CETTE collection uniquement
                        st.session_state.pop(f"docs_{coll_name}", None)

                st.divider()

                # ── MÉTRIQUES GLOBALES ────────────────────────
                col1, col2, col3 = st.columns(3)
                col1.metric(get_text("metric_analyzed_docs"), len(docs))
                col2.metric(get_text("metric_detected_fields"), len(schema))
                col3.metric(get_text("metric_perfect_fields"), sum(
                    1 for f in schema.values() if f["presence"] == 100.0
                ))

                st.divider()

                # ── SOUS-ONGLETS ──────────────────────────────
                schema_tab, security_tab, drift_tab, quality_tab = st.tabs(
                    [get_text("tab_schema_vis"), get_text("tab_sec_audit"), get_text("tab_schema_drift"), get_text("tab_data_quality")]
                )

                # ═══════════════════════════════════════════════
                # TAB 1 - SCHÉMA
                # ═══════════════════════════════════════════════
                with schema_tab:
                    st.subheader(get_text("schema_discovered"))
                    rows = [
                        {
                            get_text("col_field"): field,
                            get_text("col_types"): ", ".join(
                                f"{t}({n}x)" for t, n in info["types"].items()
                            ),
                            get_text("col_presence"): info["presence"],
                            get_text("col_occurrences"): info["count"]
                        }
                        for field, info in sorted(schema.items())
                    ]
                    df = pd.DataFrame(rows)

                    def color_presence(val):
                        if val == 100.0:
                            return "background-color: #166534; color: white"
                        elif val >= 50:
                            return "background-color: #854d0e; color: white"
                        else:
                            return "background-color: #7f1d1d; color: white"

                    dynamic_height = min(400, max(100, len(df) * 35 + 40))
                    styled_df = df.style.map(color_presence, subset=[get_text("col_presence")])
                    st.dataframe(
                        styled_df, use_container_width=True, height=dynamic_height
                    )

                    st.divider()
                    st.subheader(get_text("schema_visual"))
                    st.markdown(get_text("color_guide"))
                    fig = build_tree_figure(schema, collection_name=coll_name)
                    st.plotly_chart(
                        fig, use_container_width=True, key=f"chart_{coll_name}"
                    )

                    st.divider()
                    st.subheader(get_text("export_schema"))
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            get_text("download_json_schema"),
                            json.dumps(schema, indent=2, ensure_ascii=False, cls=SafeJSONEncoder),
                            file_name=f"schema_{coll_name}.json",
                            mime="application/json",
                            key=f"json_{coll_name}"
                        )
                    with col_b:
                        st.download_button(
                            get_text("download_csv_schema"),
                            df.to_csv(index=False).encode("utf-8"),
                            file_name=f"schema_{coll_name}.csv",
                            mime="text/csv",
                            key=f"csv_{coll_name}"
                        )

                    with st.expander(get_text("view_raw_docs")):
                        st.json(docs[:5])

                # ═══════════════════════════════════════════════
                # TAB 2 - AUDIT SÉCURITÉ
                # ═══════════════════════════════════════════════
                with security_tab:
                    with st.spinner(get_text("analyzing_vulns")):
                        audit = run_audit(docs, schema, lang=st.session_state["lang"])

                    score   = audit["score"]
                    summary = audit["summary"]
                    findings = audit["findings"]

                    # ── Jauge + résumé ───────────────────────
                    col_gauge, col_cards = st.columns([4, 3])

                    with col_gauge:
                        fig_gauge = build_security_gauge(score)
                        st.plotly_chart(
                            fig_gauge, use_container_width=True,
                            key=f"gauge_{coll_name}"
                        )

                    with col_cards:
                        st.markdown(f"#### {get_text('summary_findings')}")
                        sev_cfg = [
                            ("CRITICAL", "", "#dc2626", "#450a0a"),
                            ("HIGH",     "", "#ea580c", "#431407"),
                            ("MEDIUM",   "", "#ca8a04", "#422006"),
                            ("INFO",     "", "#2563eb", "#1e3a5f"),
                        ]
                        for sev, icon, fg, bg in sev_cfg:
                            count = summary.get(sev, 0)
                            st.markdown(
                                f"""
                                <div style="
                                    background:{bg};
                                    border-left: 4px solid {fg};
                                    padding: 10px 16px;
                                    border-radius: 6px;
                                    margin-bottom: 8px;
                                    color:white;
                                    font-size: 15px;
                                ">
                                {icon} <b>{sev}</b> - {get_text('finding_count').format(count=count)}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                    st.divider()

                    # ── Détail des findings ──────────────────
                    if not findings:
                        st.success(
                            get_text("no_vuln_detected")
                        )
                    else:
                        st.subheader(get_text("vuln_details"))

                        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
                        sorted_findings = sorted(
                            findings,
                            key=lambda x: sev_order.get(x["severity"], 99)
                        )

                        sev_colors = {
                            "CRITICAL": ("#dc2626", "#450a0a", ""),
                            "HIGH":     ("#ea580c", "#431407", ""),
                            "MEDIUM":   ("#ca8a04", "#422006", ""),
                            "INFO":     ("#2563eb", "#1e3a5f", ""),
                        }

                        for f in sorted_findings:
                            fg, bg, icon = sev_colors.get(
                                f["severity"], ("#6b7280", "#1f2937", "•")
                            )
                            st.markdown(
                                f"""
                                <div style="
                                    background:{bg};
                                    border-left:5px solid {fg};
                                    padding:12px 18px;
                                    border-radius:8px;
                                    margin-bottom:10px;
                                    color:white;
                                ">
                                <div style="font-size:14px;font-weight:bold;margin-bottom:4px">
                                    {icon} [{f['severity']}] &nbsp;
                                    <code style="color:{fg}">{f['rule']}</code>
                                    &nbsp;-&nbsp; {get_text('label_field')} : <b>{f['field']}</b>
                                </div>
                                <div style="font-size:13px;margin-bottom:4px">{f['message']}</div>
                                <div style="font-size:12px;opacity:0.8">
                                    {get_text('affected_docs_label')} <b>{f['affected_docs']}</b>
                                    &nbsp;|&nbsp; {get_text('example_masked_label')}
                                    <code>{f['sample']}</code>
                                </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                    st.divider()

                    # ── Export du rapport ────────────────────────
                    st.subheader(get_text("export_sec_report"))
                    col_rj, col_rc, col_rp = st.columns(3)

                    with col_rj:
                        st.download_button(
                            get_text("download_json_report"),
                            export_security_report_json(audit, coll_name),
                            file_name=f"security_{coll_name}.json",
                            mime="application/json",
                            key=f"sec_json_{coll_name}"
                        )
                    with col_rc:
                        st.download_button(
                            get_text("download_csv_report"),
                            export_security_report_csv(audit),
                            file_name=f"security_{coll_name}.csv",
                            mime="text/csv",
                            key=f"sec_csv_{coll_name}"
                        )
                    with col_rp:
                        try:
                            pdf_bytes = export_security_report_pdf(audit, coll_name, lang=st.session_state["lang"])
                            st.download_button(
                                get_text("download_pdf_report"),
                                pdf_bytes,
                                file_name=f"security_{coll_name}.pdf",
                                mime="application/pdf",
                                key=f"sec_pdf_{coll_name}"
                            )
                        except ImportError:
                            st.warning(
                                get_text("err_pdf_unavailable")
                            )

                # ═══════════════════════════════════════════════
                # TAB 3 - SCHEMA DRIFT
                # ═══════════════════════════════════════════════
                with drift_tab:
                    st.subheader(get_text("drift_detector_title"))
                    
                    @st.dialog(get_text("drift_save_popover"))
                    def save_snapshot_dialog(coll_name_arg, db_name_arg, schema_arg):
                        st.caption(get_text("drift_refresh_tip"))
                        snap_label = st.text_input(get_text("drift_label_input"), placeholder=get_text("drift_label_placeholder"), key=f"dlg_snap_label_{coll_name_arg}")
                        if st.button(get_text("drift_btn_save"), key=f"dlg_save_snap_{coll_name_arg}"):
                            if snap_label:
                                save_snapshot(snap_label, st.session_state["db_type"], db_name_arg, coll_name_arg, schema_arg)
                                st.session_state['success_msg'] = get_text("drift_success_save")
                                st.rerun()
                            else:
                                st.error(get_text("drift_err_label"))

                    if 'success_msg' in st.session_state:
                        st.toast(st.session_state['success_msg'], icon=":material/check_circle:")
                        del st.session_state['success_msg']

                    col_save, col_spacer = st.columns([3, 7])
                    with col_save:
                        if st.button(get_text("drift_save_popover"), key=f"btn_open_dlg_{coll_name}"):
                            save_snapshot_dialog(coll_name, db_name, schema)
                    
                    st.divider()
                    
                    snapshots = load_snapshots()
                    # Filter strictly by db type, db name AND collection name
                    _cur_db_type = st.session_state.get("db_type", "")
                    coll_snapshots = [
                        s for s in snapshots
                        if s["collection_name"] == coll_name
                        and s.get("database_type", "") == _cur_db_type
                        and s.get("database_name", "") == db_name
                    ]
                    
                    if len(coll_snapshots) < 2:
                        st.info(get_text("drift_info_need_snapshots"))
                    else:
                        col_a, col_b, col_btn = st.columns([4, 4, 2])
                        opts = { s["snapshot_id"]: f"{s['label']} ({s['timestamp'][:10]})" for s in coll_snapshots }
                        sorted_opts = sorted(coll_snapshots, key=lambda x: x["timestamp"], reverse=True)
                        
                        snap_a_id = col_a.selectbox(get_text("drift_select_older"), options=[s["snapshot_id"] for s in sorted_opts], format_func=lambda x: opts[x], index=1, key=f"snap_a_{coll_name}")
                        snap_b_id = col_b.selectbox(get_text("drift_select_newer"), options=[s["snapshot_id"] for s in sorted_opts], format_func=lambda x: opts[x], index=0, key=f"snap_b_{coll_name}")
                        
                        if col_btn.button(get_text("drift_btn_compare"), key=f"btn_compare_{coll_name}", use_container_width=True):
                            snap_a = next(s for s in coll_snapshots if s["snapshot_id"] == snap_a_id)
                            snap_b = next(s for s in coll_snapshots if s["snapshot_id"] == snap_b_id)
                            
                            report = compare_snapshots(snap_a, snap_b)
                            
                            st.markdown(f"### {get_text('drift_stability_score')}: {report['stability_score']}/100")
                            
                            if len(report['results']) == 0:
                                st.success(get_text("drift_no_drift"))
                            else:
                                date_a = snap_a['timestamp'][:19].replace('T', ' ')
                                date_b = snap_b['timestamp'][:19].replace('T', ' ')
                                st.markdown(f"**{get_text('drift_changes_detected').format(num=len(report['results']), date_a=date_a, date_b=date_b)}**")
                                df_drift = pd.DataFrame(report['results'])
                                if not df_drift.empty:
                                    df_drift = df_drift.drop(columns=[
                                        "type_of_old_value",
                                        "type_of_new_value",
                                        "information_useful_in_inspector"
                                    ], errors="ignore")
                                    df_drift = df_drift.rename(columns={
                                        "field_path": get_text("col_field"),
                                        "drift_type": get_text("drift_col_change_type")
                                    })
                                
                                st.dataframe(df_drift, use_container_width=True)
                                
                                st.download_button(
                                    get_text("drift_btn_download_json"),
                                    json.dumps(report, indent=2),
                                    file_name=f"drift_report_{coll_name}.json",
                                    mime="application/json",
                                    key=f"drift_dl_{coll_name}"
                                )

                # ═══════════════════════════════════════════════
                # TAB 4 - DATA QUALITY
                # ═══════════════════════════════════════════════
                with quality_tab:

                    # ──────────────────────────────────────────────
                    # SECTION 0: Top action bar
                    # ──────────────────────────────────────────────
                    st.markdown(
                        f"""
                        <div style="
                            background:#ffffff;
                            border:1px solid rgba(124,58,237,0.25);
                            border-radius:14px;
                            padding:18px 24px 14px;
                            margin-bottom:20px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        ">
                            <h3 style="margin:0 0 4px;font-size:18px;color:#0f172a;
                                       font-weight:700;letter-spacing:-0.02em">
                                {get_text("quality_title")}
                            </h3>
                            <p style="margin:0;font-size:12px;color:#64748b">
                                {get_text("quality_subtitle")}
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    _qbar_col, _qts_col = st.columns([3, 5])
                    with _qbar_col:
                        if st.button(
                            get_text("quality_btn_run"),
                            key=f"btn_run_quality_{coll_name}",
                            use_container_width=True
                        ):
                            with st.spinner(get_text("quality_running_spinner").format(count=len(docs))):
                                _profiler = SemanticProfiler(docs, collection_name=coll_name)
                                st.session_state[f"quality_report_{coll_name}"] = _profiler.profile()
                                import datetime as _dt
                                st.session_state[f"quality_ts_{coll_name}"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    _qts = st.session_state.get(f"quality_ts_{coll_name}")
                    if _qts:
                        _ts_formatted = f"<b style='color:#94a3b8'>{_qts}</b>"
                        _qts_col.markdown(
                            f"<p style='color:#64748b;font-size:12px;margin-top:14px'>"
                            f"{get_text('quality_last_analysis').format(ts=_ts_formatted)}</p>",
                            unsafe_allow_html=True
                        )

                    _report_key = f"quality_report_{coll_name}"

                    if _report_key not in st.session_state:
                        _btn_style = f"<b style='color:#c4b5fd'>{get_text('quality_btn_run')}</b>"
                        _prompt_html = get_text("quality_prompt_run").replace("Run Quality Analysis", _btn_style).replace("Lancer l'analyse de qualité", _btn_style)
                        st.markdown(
                            f"""
                            <div style="
                                text-align:center;
                                padding:60px 20px;
                                background:#ffffff;
                                border:1px dashed rgba(139,92,246,0.35);
                                border-radius:14px;
                                margin-top:16px;
                                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                            ">
                                <div style="margin-bottom:12px;">
                                    <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="#8b5cf6">
                                      <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z"/>
                                    </svg>
                                </div>
                                <div style="color:#64748b;font-size:15px">
                                    {_prompt_html}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        _qr = st.session_state[_report_key]
                        # SemanticReport is a dataclass - access attrs directly
                        _score    = _qr.quality_score
                        _grade    = _qr.grade
                        _findings = _qr.findings          # List[SemanticFinding]
                        _profiles = _qr.field_profiles    # Dict[str, FieldProfile]
                        _total_docs = _qr.total_documents

                        st.divider()

                        # ──────────────────────────────────────────────
                        # SECTION 1: Quality Score Header
                        # ──────────────────────────────────────────────
                        _crit_n = sum(1 for f in _findings if f.severity == "CRITICAL")
                        _high_n = sum(1 for f in _findings if f.severity == "HIGH")
                        _med_n  = sum(1 for f in _findings if f.severity == "MEDIUM")
                        _info_n = sum(1 for f in _findings if f.severity == "INFO")

                        if _score >= 80:
                            _bar_color  = "#10b981"
                            _grade_bg   = "#f0fdf4"
                            _score_lbl  = get_text("quality_lbl_excellent")
                            _step_color = [
                                {"range": [0,  50], "color": "#fef2f2"},
                                {"range": [50, 80], "color": "#fff7ed"},
                                {"range": [80, 100], "color": "#ecfdf5"},
                            ]
                        elif _score >= 50:
                            _bar_color  = "#f59e0b"
                            _grade_bg   = "#fff7ed"
                            _score_lbl  = get_text("quality_lbl_needs_attention")
                            _step_color = [
                                {"range": [0,  50], "color": "#fef2f2"},
                                {"range": [50, 80], "color": "#fff7ed"},
                                {"range": [80, 100], "color": "#ecfdf5"},
                            ]
                        else:
                            _bar_color  = "#ef4444"
                            _grade_bg   = "#fef2f2"
                            _score_lbl  = get_text("quality_lbl_poor")
                            _step_color = [
                                {"range": [0,  50], "color": "#fef2f2"},
                                {"range": [50, 80], "color": "#fff7ed"},
                                {"range": [80, 100], "color": "#ecfdf5"},
                            ]

                        _gauge_col, _metrics_col = st.columns([4, 3])

                        with _gauge_col:
                            _fig_q = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=_score,
                                align="center",
                                domain={"x": [0, 1], "y": [0, 1]},
                                title={
                                    "text": (
                                        f"{get_text('quality_score_title')}<br>"
                                        f"<span style='font-size:0.85em;color:{_bar_color}'>{_score_lbl}</span>"
                                    ),
                                    "font": {"size": 16, "color": "#0f172a"}
                                },
                                number={
                                    "suffix": " / 100",
                                    "font": {"size": 20, "color": _bar_color}
                                },
                                gauge={
                                    "axis": {
                                        "range": [0, 100],
                                        "tickwidth": 1,
                                        "tickcolor": "#64748b",
                                        "tickfont": {"color": "#64748b"}
                                    },
                                    "bar": {"color": _bar_color, "thickness": 0.25},
                                    "bgcolor": "#f1f5f9",
                                    "borderwidth": 2,
                                    "bordercolor": "#cbd5e1",
                                    "steps": _step_color
                                }
                            ))
                            _fig_q.update_layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                height=280,
                                margin=dict(t=60, b=20, l=20, r=20)
                            )
                            st.plotly_chart(
                                _fig_q, use_container_width=True,
                                key=f"quality_gauge_{coll_name}"
                            )

                        with _metrics_col:
                            # Grade badge
                            _grade_colors = {
                                "A": ("#16a34a", "#f0fdf4"),
                                "B": ("#059669", "#ecfdf5"),
                                "C": ("#d97706", "#fef3c7"),
                                "D": ("#dc2626", "#fef2f2"),
                                "F": ("#b91c1c", "#fef2f2"),
                            }
                            _gc, _gb = _grade_colors.get(_grade, ("#475569", "#f8fafc"))
                            
                            _affected_fields = len({f.field_path for f in _findings})
                            _summary_html = get_text("quality_summary_findings").format(
                                total=f"<b style='color:#e2e8f0'>{len(_findings)}</b>",
                                fields=f"<b style='color:#e2e8f0'>{_affected_fields}</b>",
                                docs=f"<b style='color:#e2e8f0'>{_total_docs}</b>"
                            )
                            _card_html = f"""<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 20px; backdrop-filter: blur(10px); box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="display: flex; align-items: center; gap: 16px; background: {_gb}; border: 1px solid {_gc}44; border-radius: 12px; padding: 12px 20px; margin-bottom: 20px;">
        <span style="font-size: 44px; font-weight: 900; color: {_gc}; line-height: 1;">{_grade}</span>
        <div style="font-size: 13px; color: #0f172a; line-height: 1.4;">
            <b style="color: {_gc}; font-size: 15px;">{get_text('quality_grade_lbl').format(grade=_grade)}</b><br>
            <span style="color: #64748b;">{get_text('quality_score_sub').format(score=_score)}</span>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #ef4444; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">{get_text('quality_metric_critical')}</div>
            <div style="font-size: 26px; font-weight: 800; color: #b91c1c; margin-top: 4px;">{_crit_n}</div>
        </div>
        <div style="background: #fff7ed; border: 1px solid #fdba74; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #ea580c; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">{get_text('quality_metric_high')}</div>
            <div style="font-size: 26px; font-weight: 800; color: #c2410c; margin-top: 4px;">{_high_n}</div>
        </div>
        <div style="background: #fefce8; border: 1px solid #fde047; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #ca8a04; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">{get_text('quality_metric_medium')}</div>
            <div style="font-size: 26px; font-weight: 800; color: #a16207; margin-top: 4px;">{_med_n}</div>
        </div>
        <div style="background: #eff6ff; border: 1px solid #93c5fd; border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #2563eb; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">{get_text('quality_metric_info')}</div>
            <div style="font-size: 26px; font-weight: 800; color: #1d4ed8; margin-top: 4px;">{_info_n}</div>
        </div>
    </div>
    <div style="font-size: 12.5px; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 14px; margin-top: 14px; line-height: 1.4;">
        {_summary_html}
    </div>
</div>"""
                            _card_html_clean = " ".join([line.strip() for line in _card_html.split("\n") if line.strip()])
                            st.markdown(_card_html_clean, unsafe_allow_html=True)

                        st.divider()

                        # ──────────────────────────────────────────────
                        # SECTION 2: Findings Table
                        # ──────────────────────────────────────────────
                        st.subheader(get_text("quality_findings_header"))

                        if not _findings:
                            st.success(get_text("quality_no_issues"))
                        else:
                            _sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}

                            # Filter controls
                            _fc1, _fc2 = st.columns([3, 5])
                            with _fc1:
                                _sev_filter = st.multiselect(
                                    get_text("quality_filter_severity"),
                                    ["CRITICAL", "HIGH", "MEDIUM", "INFO"],
                                    default=["CRITICAL", "HIGH", "MEDIUM", "INFO"],
                                    key=f"quality_severity_filter_{coll_name}"
                                )
                            with _fc2:
                                _field_search = st.text_input(
                                    get_text("quality_search_field"),
                                    placeholder=get_text("quality_search_placeholder"),
                                    key=f"quality_field_search_{coll_name}"
                                ).strip().lower()

                            _ff = [
                                f for f in _findings
                                if f.severity in _sev_filter
                                and (_field_search == "" or _field_search in f.field_path.lower())
                            ]
                            _ff.sort(key=lambda x: (
                                _sev_order.get(x.severity, 99),
                                -x.affected_rate
                            ))

                            # Summary table (styled dataframe)
                            if _ff:
                                _rows = [{
                                    get_text("quality_col_severity"):   f.severity,
                                    get_text("quality_col_rule"):       f.rule_name,
                                    get_text("quality_col_field"):      f.field_path,
                                    get_text("quality_col_affected"):   f.affected_count,
                                    get_text("quality_col_rate"):       round(f.affected_rate, 1),
                                    get_text("quality_col_suggestion"): f.suggestion
                                } for f in _ff]
                                _df_findings = pd.DataFrame(_rows)

                                _SEV_BG = {
                                    "CRITICAL": "background-color:#fef2f2;color:#dc2626",
                                    "HIGH":     "background-color:#fff7ed;color:#ea580c",
                                    "MEDIUM":   "background-color:#fefce8;color:#ca8a04",
                                    "INFO":     "background-color:#eff6ff;color:#2563eb",
                                }

                                def _color_sev_row(row):
                                    style = _SEV_BG.get(row[get_text("quality_col_severity")], "")
                                    return [style] * len(row)

                                _styled = _df_findings.style.apply(
                                    _color_sev_row, axis=1
                                )
                                _dyn_h = min(500, max(120, len(_df_findings) * 38 + 42))
                                st.dataframe(
                                    _styled,
                                    use_container_width=True,
                                    height=_dyn_h
                                )

                                st.markdown(
                                    f"<p style='font-size:12px;color:#64748b;margin-top:4px'>"
                                    f"{get_text('quality_findings_tip')}</p>",
                                    unsafe_allow_html=True
                                )

                            # Expandable detail cards per finding
                            _sev_colors_q = {
                                "CRITICAL": ("#dc2626", "#fef2f2"),
                                "HIGH":     ("#ea580c", "#fff7ed"),
                                "MEDIUM":   ("#ca8a04", "#fefce8"),
                                "INFO":     ("#2563eb", "#eff6ff"),
                            }

                            for _idx_f, _finding in enumerate(_ff):
                                _sev  = _finding.severity
                                _fg_c, _bg_c = _sev_colors_q.get(_sev, ("#6b7280", "#1f2937"))
                                _rule  = _finding.rule_name
                                _fpath = _finding.field_path
                                _aff   = _finding.affected_count
                                _tot   = _finding.total_count
                                _rate  = _finding.affected_rate
                                _sugg  = _finding.suggestion
                                _exs   = _finding.examples

                                with st.expander(
                                    f"{_rule}  ·  {_fpath}  ({_aff}/{_tot} docs, {_rate:.1f}%)",
                                    expanded=False
                                ):
                                    st.markdown(
                                        f"""
                                        <div style="
                                            background:{_bg_c};
                                            border-left:4px solid {_fg_c};
                                            padding:10px 16px;
                                            border-radius:8px;
                                            margin-bottom:12px;
                                            color:#0f172a;
                                        ">
                                            <b style="color:{_fg_c}">{_sev}</b>
                                            &nbsp;|&nbsp; {get_text('quality_detail_rule')}: <code style="color:{_fg_c}">{_rule}</code>
                                            &nbsp;|&nbsp; {get_text('quality_detail_field')}: <code>{_fpath}</code>
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )
                                    _det1, _det2 = st.columns(2)
                                    with _det1:
                                        st.metric(get_text("quality_detail_affected"), f"{_aff} / {_tot}")
                                        st.metric(get_text("quality_detail_rate"), f"{_rate:.1f}%")
                                        if _sugg:
                                            st.info(_sugg)
                                    with _det2:
                                        if _exs:
                                            st.markdown(
                                                f"<p style='font-size:12px;color:#94a3b8;"
                                                f"margin-bottom:4px'><b>{get_text('quality_detail_bad_values')}</b></p>",
                                                unsafe_allow_html=True
                                            )
                                            for _ex in _exs[:3]:
                                                st.code(str(_ex), language=None)

                                    # MongoDB shell fix command
                                    _mongo_cmd = ""
                                    _safe_fp = _fpath.replace(",", "__")
                                    if _rule == "NegativeValue":
                                        _mongo_cmd = (
                                            f"// Fix: set negative {_fpath} to 0\n"
                                            f"db.{coll_name}.updateMany(\n"
                                            f"  {{ {_fpath}: {{ $lt: 0 }} }},\n"
                                            f"  [{{ $set: {{ {_fpath}: {{ $abs: '${_fpath}' }} }} }}]\n"
                                            f")"
                                        )
                                    elif _rule == "ZeroValue":
                                        _mongo_cmd = (
                                            f"// Fix: remove documents where {_fpath} == 0\n"
                                            f"db.{coll_name}.updateMany(\n"
                                            f"  {{ {_fpath}: 0 }},\n"
                                            f"  {{ $unset: {{ {_fpath}: '' }} }}\n"
                                            f")"
                                        )
                                    elif _rule == "OutlierValue":
                                        _mongo_cmd = (
                                            f"// Investigate outliers in {_fpath}\n"
                                            f"db.{coll_name}.find(\n"
                                            f"  {{ {_fpath}: {{ $exists: true }} }}\n"
                                            f").sort({{ {_fpath}: -1 }}).limit(10)"
                                        )
                                    elif _rule == "MalformedEmail":
                                        _mongo_cmd = (
                                            f"// Find malformed emails\n"
                                            f"db.{coll_name}.find({{\n"
                                            f"  {_fpath}: {{\n"
                                            f"    $not: /^[\\w.+-]+@[\\w-]+\\.[a-zA-Z]{{2,}}$/\n"
                                            f"  }}\n"
                                            f"}})"
                                        )
                                    elif _rule == "MalformedPhone":
                                        _mongo_cmd = (
                                            f"// Find malformed phone numbers in {_fpath}\n"
                                            f"db.{coll_name}.find({{\n"
                                            f"  {_fpath}: {{ $not: /^[0-9\\s+\\-\\(\\){{8,}}$/ }}\n"
                                            f"}})"
                                        )
                                    elif _rule == "FutureDate":
                                        _mongo_cmd = (
                                            f"// Fix: set future dates in {_fpath} to current date\n"
                                            f"db.{coll_name}.updateMany(\n"
                                            f"  {{ {_fpath}: {{ $gt: new Date() }} }},\n"
                                            f"  {{ $set: {{ {_fpath}: new Date() }} }}\n"
                                            f")"
                                        )
                                    elif _rule == "DuplicateID":
                                        _mongo_cmd = (
                                            f"// Find duplicate IDs in {_fpath}\n"
                                            f"db.{coll_name}.aggregate([\n"
                                            f"  {{ $group: {{ _id: '${_fpath}', count: {{ $sum: 1 }} }} }},\n"
                                            f"  {{ $match: {{ count: {{ $gt: 1 }} }} }},\n"
                                            f"  {{ $sort: {{ count: -1 }} }}\n"
                                            f"])"
                                        )
                                    elif _rule == "NullID":
                                        _mongo_cmd = (
                                            f"// Find documents missing {_fpath}\n"
                                            f"db.{coll_name}.find({{\n"
                                            f"  $or: [\n"
                                            f"    {{ {_fpath}: null }},\n"
                                            f"    {{ {_fpath}: {{ $exists: false }} }},\n"
                                            f"    {{ {_fpath}: '' }}\n"
                                            f"  ]\n"
                                            f"}})"
                                        )
                                    elif _rule == "EmptyString":
                                        _mongo_cmd = (
                                            f"// Fix: set empty strings to null in {_fpath}\n"
                                            f"db.{coll_name}.updateMany(\n"
                                            f"  {{ {_fpath}: '' }},\n"
                                            f"  {{ $set: {{ {_fpath}: null }} }}\n"
                                            f")"
                                        )
                                    elif _rule == "SuspiciousDefault":
                                        _mongo_cmd = (
                                            f"// Find test/placeholder values in {_fpath}\n"
                                            f"db.{coll_name}.find({{\n"
                                            f"  {_fpath}: {{ $in: ['test','admin','n/a','null',"
                                            f"'undefined','todo','fixme','xxx'] }}\n"
                                            f"}})"
                                        )
                                    elif _rule == "FakeBoolean":
                                        _mongo_cmd = (
                                            f"// Fix: cast string/int booleans in {_fpath} to true bool\n"
                                            f"db.{coll_name}.find({{ {_fpath}: {{ $in: [0, 1, 'true', 'false'] }} }}).forEach(\n"
                                            f"  doc => db.{coll_name}.updateOne(\n"
                                            f"    {{ _id: doc._id }},\n"
                                            f"    {{ $set: {{ {_fpath}: Boolean(doc.{_fpath}) }} }}\n"
                                            f"  )\n"
                                            f")"
                                        )
                                    elif _rule == "InconsistentTotal":
                                        _mongo_cmd = (
                                            f"// Inspect documents with mismatched totals\n"
                                            f"db.{coll_name}.aggregate([\n"
                                            f"  {{ $addFields: {{\n"
                                            f"    computed_total: {{ $sum: '$$items.price' }}\n"
                                            f"  }} }},\n"
                                            f"  {{ $match: {{\n"
                                            f"    $expr: {{ $gt: [{{ $abs: {{ $subtract: ['$total','$computed_total'] }} }}, 0.01] }}\n"
                                            f"  }} }}\n"
                                            f"])"
                                        )
                                    else:
                                        _mongo_cmd = (
                                            f"// Inspect affected documents for rule {_rule}\n"
                                            f"db.{coll_name}.find({{ {_fpath}: {{ $exists: true }} }}).limit(20)"
                                        )

                                    st.markdown(
                                        f"<p style='font-size:12px;color:#94a3b8;margin:12px 0 4px'>"
                                        f"<b>{get_text('quality_detail_mongo_cmd')}</b></p>",
                                        unsafe_allow_html=True
                                    )
                                    st.code(_mongo_cmd, language="javascript")

                        st.divider()

                        # ──────────────────────────────────────────────
                        # SECTION 3: Field Semantic Profiles
                        # ──────────────────────────────────────────────
                        if _profiles:
                            st.subheader(get_text("quality_profiles_header"))

                            _field_select = st.selectbox(
                                get_text("quality_field_select_lbl"),
                                options=sorted(_profiles.keys()),
                                key=f"quality_field_select_{coll_name}"
                            )

                            if _field_select and _field_select in _profiles:
                                _fp = _profiles[_field_select]
                                _null_pct    = _fp.null_rate * 100
                                _unique_pct  = _fp.unique_rate * 100
                                _dom_type    = _fp.dominant_type
                                _sem_type    = _fp.semantic_type
                                _top_vals    = _fp.top_values
                                _min_v       = _fp.min_val
                                _max_v       = _fp.max_val
                                _avg_v       = _fp.avg_val

                                _prof_left, _prof_right = st.columns([2, 3])

                                with _prof_left:
                                    st.markdown(
                                        f"""
                                        <div style="
                                            background:#ffffff;
                                            border:1px solid #e2e8f0;
                                            border-radius:12px;
                                            padding:16px 20px;
                                            margin-bottom:16px;
                                            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                                        ">
                                            <div style="font-size:11px;color:#64748b;
                                                        text-transform:uppercase;
                                                        letter-spacing:.06em;
                                                        margin-bottom:6px">{get_text("quality_fp_field")}</div>
                                            <div style="font-size:15px;font-weight:700;
                                                        color:#c4b5fd;word-break:break-all">{_field_select}</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )
                                    
                                    _pm3, _pm4 = st.columns(2)
                                    _pm3.metric(get_text("quality_fp_python_type"),
                                                _dom_type)
                                    _pm4.metric(get_text("quality_fp_semantic_type"),
                                                _sem_type)

                                    # Numeric stats
                                    if _min_v is not None and _avg_v is not None:
                                        st.markdown(
                                            f"<p style='font-size:11px;color:#64748b;"
                                            f"margin-top:12px;margin-bottom:4px'>"
                                            f"<b>{get_text('quality_fp_numeric_stats')}</b></p>",
                                            unsafe_allow_html=True
                                        )
                                        _ns1, _ns2, _ns3 = st.columns(3)
                                        _ns1.metric(get_text("quality_fp_min"),
                                                    f"{_min_v:.2f}" if isinstance(_min_v, float) else str(_min_v))
                                        _ns2.metric(get_text("quality_fp_max"),
                                                    f"{_max_v:.2f}" if isinstance(_max_v, float) else str(_max_v))
                                        _ns3.metric(get_text("quality_fp_avg"),
                                                    f"{_avg_v:.2f}" if _avg_v is not None else "N/A")

                                    # Email validity %
                                    if _sem_type == "EMAIL":
                                        import re as _re
                                        _email_re = _re.compile(r'^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$')
                                        _raw_vals = [
                                            doc.get(_field_select)
                                            for doc in docs
                                            if isinstance(doc.get(_field_select), str)
                                        ]
                                        if _raw_vals:
                                            _valid_e   = sum(1 for v in _raw_vals if _email_re.match(v))
                                            _invalid_e = len(_raw_vals) - _valid_e
                                            st.markdown(
                                                f"<p style='font-size:11px;color:#64748b;"
                                                f"margin-top:12px;margin-bottom:4px'>"
                                                f"<b>{get_text('quality_fp_email_validity')}</b></p>",
                                                unsafe_allow_html=True
                                            )
                                            _ev1, _ev2 = st.columns(2)
                                            _ev1.metric(get_text("quality_fp_valid"),
                                                        f"{_valid_e} ({_valid_e/len(_raw_vals)*100:.0f}%)")
                                            _ev2.metric(get_text("quality_fp_invalid"),
                                                        f"{_invalid_e} ({_invalid_e/len(_raw_vals)*100:.0f}%)")

                                with _prof_right:

                                    # ── Null / Unique rate donut ───────────────
                                    _donut_labels = ["Null", "Unique", "Other"]
                                    _non_null = 1.0 - (_null_pct / 100)
                                    _unique_abs = _unique_pct / 100
                                    _other_abs = max(0.0, _non_null - _unique_abs)
                                    _donut_vals = [_null_pct / 100, _unique_abs, _other_abs]
                                    _fig_donut = go.Figure(go.Pie(
                                        labels=_donut_labels,
                                        values=_donut_vals,
                                        hole=0.6,
                                        marker=dict(colors=["#ef4444", "#10b981", "#6366f1"]),
                                        textinfo="label+percent",
                                        hovertemplate="%{label}: %{percent}<extra></extra>",
                                        sort=False,
                                    ))
                                    _fig_donut.update_layout(
                                        title_text="Null / Unique / Other",
                                        title_font_color="#94a3b8",
                                        paper_bgcolor="rgba(0,0,0,0)",
                                        plot_bgcolor="rgba(0,0,0,0)",
                                        font_color="#94a3b8",
                                        height=220,
                                        margin=dict(t=40, b=10, l=10, r=10),
                                        showlegend=False,
                                    )
                                    st.plotly_chart(
                                        _fig_donut, use_container_width=True,
                                        key=f"qp_donut_{coll_name}_{_field_select}"
                                    )

                                    # ── Numeric histogram ─────────────────────
                                    if _dom_type in ("int", "float") and _avg_v is not None:
                                        _num_data = [
                                            doc.get(_field_select)
                                            for doc in docs
                                            if isinstance(doc.get(_field_select), (int, float))
                                        ]
                                        if _num_data:
                                            _fig_hist = go.Figure(go.Histogram(
                                                x=_num_data,
                                                nbinsx=20,
                                                marker_color="#6366f1",
                                                marker_line_color="rgba(99,102,241,0.4)",
                                                marker_line_width=1,
                                                hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>"
                                            ))
                                            _fig_hist.update_layout(
                                                title_text=get_text("quality_fp_distribution").format(field=_field_select),
                                                title_font_color="#94a3b8",
                                                paper_bgcolor="rgba(0,0,0,0)",
                                                plot_bgcolor="rgba(0,0,0,0)",
                                                font_color="#94a3b8",
                                                height=240,
                                                margin=dict(t=40, b=40, l=20, r=20),
                                                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                                                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                                            )
                                            st.plotly_chart(
                                                _fig_hist, use_container_width=True,
                                                key=f"qp_hist_{coll_name}_{_field_select}"
                                            )

                                    # ── Top values bar chart (text/bool/other) ─
                                    # _top_vals is a List[value] from value_counts().index
                                    # We count occurrences from raw docs then plot
                                    if _top_vals and _dom_type not in ("int", "float"):
                                        _tv_counter: dict = {}
                                        for _tdoc in docs:
                                            _tv_raw = _tdoc.get(_field_select)
                                            if _tv_raw is not None:
                                                _tv_key = str(_tv_raw)
                                                _tv_counter[_tv_key] = _tv_counter.get(_tv_key, 0) + 1
                                        _tv_allowed = {str(v) for v in _top_vals}
                                        _tv_filtered = {k: v for k, v in _tv_counter.items() if k in _tv_allowed}
                                        _tv_sorted = sorted(_tv_filtered.items(), key=lambda x: x[1], reverse=True)[:10]
                                        if _tv_sorted:
                                            _tv_labels = [k for k, _ in _tv_sorted]
                                            _tv_counts = [v for _, v in _tv_sorted]
                                            _fig_tv = go.Figure(go.Bar(
                                                x=_tv_counts,
                                                y=_tv_labels,
                                                orientation="h",
                                                marker=dict(
                                                    color=_tv_counts,
                                                    colorscale=[[0, "#312e81"], [1, "#a855f7"]],
                                                    showscale=False,
                                                ),
                                                hovertemplate="%{y}: %{x} docs<extra></extra>",
                                            ))
                                            _fig_tv.update_layout(
                                                title_text=get_text("quality_fp_top_values"),
                                                title_font_color="#94a3b8",
                                                paper_bgcolor="rgba(0,0,0,0)",
                                                plot_bgcolor="rgba(0,0,0,0)",
                                                font_color="#94a3b8",
                                                height=max(200, len(_tv_sorted) * 30 + 60),
                                                margin=dict(t=40, b=20, l=10, r=20),
                                                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                                                yaxis=dict(
                                                    gridcolor="rgba(255,255,255,0.05)",
                                                    autorange="reversed",
                                                ),
                                            )
                                            st.plotly_chart(
                                                _fig_tv, use_container_width=True,
                                                key=f"qp_tv_{coll_name}_{_field_select}"
                                            )

                                    # ── DATE timeline by month ────────────────
                                    if _sem_type == "DATE":
                                        import datetime as _dt2
                                        from semantic_profiler import parse_date_safely as _pds
                                        _date_raw = [doc.get(_field_select) for doc in docs]
                                        _parsed_dates = [_pds(v) for v in _date_raw if v is not None]
                                        _parsed_dates = [d for d in _parsed_dates if d]
                                        if _parsed_dates:
                                            _month_counts: dict = {}
                                            for _pd_d in _parsed_dates:
                                                _mk = _pd_d.strftime("%Y-%m")
                                                _month_counts[_mk] = _month_counts.get(_mk, 0) + 1
                                            _months = sorted(_month_counts.keys())
                                            _mcounts = [_month_counts[m] for m in _months]
                                            _fig_tl = go.Figure(go.Bar(
                                                x=_months,
                                                y=_mcounts,
                                                marker_color="#06b6d4",
                                                hovertemplate="%{x}: %{y} docs<extra></extra>"
                                            ))
                                            _fig_tl.update_layout(
                                                title_text=get_text("quality_fp_timeline").format(field=_field_select),
                                                title_font_color="#94a3b8",
                                                paper_bgcolor="rgba(0,0,0,0)",
                                                plot_bgcolor="rgba(0,0,0,0)",
                                                font_color="#94a3b8",
                                                height=240,
                                                margin=dict(t=40, b=40, l=20, r=20),
                                                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                                                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                                            )
                                            st.plotly_chart(
                                                _fig_tl, use_container_width=True,
                                                key=f"qp_tl_{coll_name}_{_field_select}"
                                            )

                        st.divider()

                        # ──────────────────────────────────────────────
                        # SECTION 4: Smart Suggestions Panel
                        # ──────────────────────────────────────────────
                        _crit_high = [f for f in _findings if f.severity in ("CRITICAL", "HIGH")]
                        if _crit_high:
                            st.subheader(get_text("quality_autofix_header"))
                            st.markdown(
                                f"<p style='font-size:12px;color:#64748b;margin-top:-8px'>"
                                f"{get_text('quality_autofix_subtitle')}</p>",
                                unsafe_allow_html=True
                            )
                            for _fx in _crit_high:
                                _fx_sev   = _fx.severity
                                _fx_rule  = _fx.rule_name
                                _fx_field = _fx.field_path
                                _fx_fg    = "#dc2626" if _fx_sev == "CRITICAL" else "#ea580c"

                                _fix_body = (
                                    f"// Rule: {_fx_rule} | Field: {_fx_field}\n"
                                    f"// Affected: {_fx.affected_count}/{_fx.total_count} "
                                    f"docs ({_fx.affected_rate:.1f}%)\n"
                                )
                                if _fx_rule == "NegativeValue":
                                    _fix_body += (
                                        f"db.{coll_name}.updateMany(\n"
                                        f"  {{ {_fx_field}: {{ $lt: 0 }} }},\n"
                                        f"  [{{ $set: {{ {_fx_field}: {{ $abs: '${_fx_field}' }} }} }}]\n"
                                        f")"
                                    )
                                elif _fx_rule == "MalformedEmail":
                                    _fix_body += (
                                        f"db.{coll_name}.find({{\n"
                                        f"  {_fx_field}: {{ $not: /^[\\w.+-]+@[\\w-]+\\.[a-zA-Z]{{2,}}$/ }}\n"
                                        f"}})"
                                    )
                                elif _fx_rule == "FutureDate":
                                    _fix_body += (
                                        f"db.{coll_name}.updateMany(\n"
                                        f"  {{ {_fx_field}: {{ $gt: new Date() }} }},\n"
                                        f"  {{ $set: {{ {_fx_field}: new Date() }} }}\n"
                                        f")"
                                    )
                                elif _fx_rule == "DuplicateID":
                                    _fix_body += (
                                        f"db.{coll_name}.aggregate([\n"
                                        f"  {{ $group: {{ _id: '${_fx_field}', count: {{ $sum: 1 }} }} }},\n"
                                        f"  {{ $match: {{ count: {{ $gt: 1 }} }} }}\n"
                                        f"])"
                                    )
                                elif _fx_rule == "NullID":
                                    _fix_body += (
                                        f"db.{coll_name}.find({{\n"
                                        f"  $or: [\n"
                                        f"    {{ {_fx_field}: null }},\n"
                                        f"    {{ {_fx_field}: {{ $exists: false }} }},\n"
                                        f"    {{ {_fx_field}: '' }}\n"
                                        f"  ]\n"
                                        f"}})"
                                    )
                                elif _fx_rule == "PaidVsAmount":
                                    _fix_body += (
                                        f"db.{coll_name}.find({{\n"
                                        f"  paid: true, total: {{ $in: [0, null] }}\n"
                                        f"}})"
                                    )
                                elif _fx_rule == "InconsistentTotal":
                                    _fix_body += (
                                        f"db.{coll_name}.aggregate([\n"
                                        f"  {{ $addFields: {{\n"
                                        f"    _computed: {{ $sum: '$$items.price' }}\n"
                                        f"  }} }},\n"
                                        f"  {{ $match: {{\n"
                                        f"    $expr: {{ $gt: [{{ $abs: {{ $subtract: ['$total','$_computed'] }} }}, 0.01] }}\n"
                                        f"  }} }}\n"
                                        f"])"
                                    )
                                elif _fx_rule == "InvalidDateString":
                                    _fix_body += (
                                        f"// Find unparseable date strings in {_fx_field}\n"
                                        f"db.{coll_name}.find({{\n"
                                        f"  {_fx_field}: {{ $type: 'string' }}\n"
                                        f"}})"
                                    )
                                elif _fx_rule == "MalformedPhone":
                                    _fix_body += (
                                        f"db.{coll_name}.find({{\n"
                                        f"  {_fx_field}: {{ $not: /^[\\+0-9\\s\\-\\(\\){{8,}}$/ }}\n"
                                        f"}})"
                                    )
                                else:
                                    _fix_body += (
                                        f"db.{coll_name}.find({{\n"
                                        f"  {_fx_field}: {{ $exists: true }}\n"
                                        f"}}).limit(20)"
                                    )

                                with st.expander(
                                    f"[{_fx_sev}]  {_fx_rule}  on  {_fx_field}",
                                    expanded=False
                                ):
                                    st.markdown(
                                        f"<p style='font-size:12px;color:#94a3b8'>"
                                        f"{_fx.suggestion}</p>",
                                        unsafe_allow_html=True
                                    )
                                    st.code(_fix_body, language="javascript")
                        else:
                            st.success(
                                get_text("quality_autofix_success")
                            )

                        st.divider()

                        # ──────────────────────────────────────────────
                        # SECTION 5: Export Panel
                        # ──────────────────────────────────────────────
                        st.subheader(get_text("quality_export_header"))
                        _eq2, _eq3 = st.columns(2)

                       
                        with _eq2:
                            try:
                                _csv_df = export_quality_csv(_qr)
                                _csv_bytes = _csv_df.to_csv(index=False).encode("utf-8")
                                st.download_button(
                                    get_text("quality_btn_dl_csv"),
                                    _csv_bytes,
                                    file_name=f"quality_{coll_name}.csv",
                                    mime="text/csv",
                                    key=f"q_csv_{coll_name}"
                                )
                            except Exception as _e:
                                st.warning(get_text("quality_err_csv").format(err=_e))

                        with _eq3:
                            try:
                                _pdf_bytes = generate_quality_pdf(_qr)
                                st.download_button(
                                    get_text("quality_btn_dl_pdf"),
                                    _pdf_bytes,
                                    file_name=f"quality_{coll_name}.pdf",
                                    mime="application/pdf",
                                    key=f"q_pdf_{coll_name}"
                                )
                            except Exception as _e:
                                st.warning(get_text("quality_err_pdf").format(err=_e))

# ── FLOATING CHATBOT (always rendered last) ───────────────────────────────────
render_chatbot(
    lang=st.session_state["lang"],
    dbms=st.session_state.get("db_type"),
    database=st.session_state.get("db_name"),
    collections=st.session_state.get("selected_collections"),
)

