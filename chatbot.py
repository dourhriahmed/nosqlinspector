"""
chatbot.py - Floating AI assistant widget (Groq-powered) for Streamlit.
Uses st.components.v1.html to inject the widget into the parent page DOM,
because st.markdown silently strips <script> tags.
Call render_chatbot() once at the bottom of app.py.
"""

import os
import json
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()


CHATBOT_TEXTS = {
    "English": {
        "toggle_title": "NoSQL AI Assistant",
        "welcome": "Hello! I am your NoSQL assistant. Ask me questions about your schemas, security audits, or how to use the application.",
        "placeholder": "Ask your question...",
        "error_prefix": "Error: "
    },
    "Français": {
        "toggle_title": "Assistant IA NoSQL",
        "welcome": "Bonjour ! Je suis votre assistant NoSQL. Posez-moi des questions sur vos schémas, vos audits de sécurité, ou l'utilisation de l'application.",
        "placeholder": "Posez votre question...",
        "error_prefix": "Erreur: "
    }
}


def render_chatbot(lang="English", dbms=None, database=None, collections=None):
    """Inject the floating chatbot widget into the Streamlit parent page.

    dbms/database/collections describe the database currently inspected
    (from st.session_state), so the assistant can answer with awareness
    of what the user is actually looking at instead of just generic help.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    texts = CHATBOT_TEXTS.get(lang, CHATBOT_TEXTS["English"])

    if dbms:
        context_line = f"The user is currently connected to a {dbms} database"
        if database:
            context_line += f" named '{database}'"
        if collections:
            context_line += f", and is inspecting these collections: {', '.join(collections)}"
        context_line += ". Use this context to tailor your answers (e.g. refer to their actual collections) whenever it's relevant, instead of asking them to repeat it."
    else:
        context_line = "The user is not currently connected to any database yet."

    sys_prompt = (
        "You are 'NoSQL Inspector AI', a helpful assistant embedded in the 'NoSQL Schema Inspector' app. "
        "The app helps users analyze NoSQL databases (MongoDB, CouchDB, Firestore) and provides key features: "
        "1) Schema Inference & Visualization: Automatically discover document structures and view them as interactive treemaps. "
        "2) Security Auditing: Evaluate data against security rules (e.g., PII leakage, NoSQL injection) and get a security score (0-100). "
        "3) Schema Drift Detection: Save schema snapshots and compare them over time. "
        "4) Data Quality Profiling: Assess structural wellness and get a grade (A to F). "
        "5) Export & Monitoring: Export reports (JSON, CSV, PDF) and monitor real-time changes. "
        f"{context_line} "
        "If the user asks how to use the application or what inputs to provide for each database, guide them with these workflow steps: "
        "Step 1: Select the target database from the sidebar. "
        "Step 2: Provide the connection credentials based on the selected database: "
        "- For MongoDB: Enter the Connection URI (e.g., mongodb://localhost:27017) and the Database Name. "
        "- For CouchDB: Enter the Connection URL (e.g., http://localhost:5984), Username, and Password. "
        "- For Firestore: Provide the path to the serviceAccountKey.json file OR manually enter the Firebase Project ID, Client Email, and Private Key. "
        "Step 3: Connect to the instance. "
        "Step 4: Run schema analysis to extract the structure. Step 5: Explore visualizations, run security audits, or check schema drift. Step 6: Export results. "
        "Provide clear, step-by-step explanations tailored to the feature they are asking about. "
        "If they ask about something unrelated, politely clarify that this app focuses on NoSQL schema and security analysis. "
        "Write normally and conversationally. Be concise unless asked for details. "
        f"You MUST reply in the user's selected language: {lang}."
    )
    # json.dumps escapes quotes/backticks so a database or collection name
    # containing them can't break out of the JS string literal below.
    sys_prompt_json = json.dumps(sys_prompt)

    # Full self-contained HTML page rendered in a 0-height iframe.
    # JS reaches into window.parent.document to inject the widget into the
    # actual Streamlit page so position:fixed works correctly.
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<script>
(function() {{
  var doc = window.parent.document;

  // ── Remove any previous instance (Streamlit re-renders) ──────────────────
  var old = doc.getElementById('nsi-chatbot-root');
  if (old) {{ old.remove(); }}
  if (window.parent._chatbotListenersAttached) {{
    window.parent._chatbotListenersAttached = false;
  }}

  // ── Inject <style> into parent <head> ────────────────────────────────────
  var styleId = 'nsi-chatbot-style';
  if (!doc.getElementById(styleId)) {{
    var style = doc.createElement('style');
    style.id = styleId;
    style.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

      #nsi-chatbot-root * {{ box-sizing: border-box; font-family: 'Inter', sans-serif; }}

      /* Toggle button */
      #nsi-chatbot-toggle {{
        position: fixed;
        bottom: 28px; right: 28px;
        width: 58px; height: 58px;
        border-radius: 50%;
        background: linear-gradient(135deg,#6366f1,#a855f7);
        border: none; cursor: pointer;
        box-shadow: 0 6px 24px rgba(99,102,241,0.55);
        display: flex; align-items: center; justify-content: center;
        z-index: 999999;
        transition: transform .2s, box-shadow .2s;
        animation: nsiPulse 2.8s ease infinite;
      }}
      #nsi-chatbot-toggle:hover {{
        transform: scale(1.1);
        box-shadow: 0 10px 32px rgba(139,92,246,.7);
        animation: none;
      }}
      @keyframes nsiPulse {{
        0%,100% {{ box-shadow: 0 6px 24px rgba(99,102,241,.55); }}
        50%      {{ box-shadow: 0 6px 32px rgba(139,92,246,.85), 0 0 0 10px rgba(99,102,241,.1); }}
      }}

      /* Panel */
      #nsi-chatbot-panel {{
        position: fixed;
        bottom: 100px; right: 28px;
        width: 370px; height: 520px;
        background: rgba(255,255,255,0.96);
        backdrop-filter: blur(28px);
        border: 1px solid rgba(226, 232, 240, 1);
        border-radius: 18px;
        box-shadow: 0 24px 64px rgba(0,0,0,.15), inset 0 1px 0 rgba(255,255,255,.5);
        display: flex; flex-direction: column;
        z-index: 999998;
        overflow: hidden;
        transition: opacity .25s, transform .25s, width .3s ease, height .3s ease;
        transform-origin: bottom right;
      }}
      #nsi-chatbot-panel.nsi-expanded {{
        width: 800px;
        height: 85vh;
        max-width: 95vw;
      }}
      #nsi-chatbot-panel.nsi-hidden {{
        opacity: 0; transform: scale(.88); pointer-events: none;
      }}

      /* Header */
      #nsi-chatbot-header {{
        padding: 14px 16px;
        background: linear-gradient(135deg,#f8fafc,#f1f5f9);
        border-bottom: 1px solid #e2e8f0;
        display: flex; align-items: center; gap: 10px; flex-shrink: 0;
      }}
      .nsi-avatar {{
        width:36px; height:36px; border-radius:50%;
        background: linear-gradient(135deg,#6366f1,#a855f7);
        display:flex; align-items:center; justify-content:center;
        flex-shrink:0;
        box-shadow: 0 0 10px rgba(99,102,241,.2);
      }}
      .nsi-avatar svg {{ display:block; }}
      .nsi-hinfo {{ flex:1; }}
      .nsi-htitle {{ font-size:14px; font-weight:700; color:#0f172a; margin:0; }}
      .nsi-hsub   {{ font-size:11px; color:#64748b; margin:0; }}
      .nsi-dot {{
        width:7px; height:7px; border-radius:50%;
        background:#22c55e; box-shadow:0 0 6px #22c55e;
        animation: nsiBlink 2s ease infinite;
      }}
      @keyframes nsiBlink {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
      #nsi-chatbot-close, #nsi-chatbot-resize {{
        background:rgba(0,0,0,.04); border:none; border-radius:8px;
        color:#64748b; cursor:pointer;
        width:28px; height:28px; font-size:16px;
        display:flex; align-items:center; justify-content:center;
        transition: background .2s, color .2s;
      }}
      #nsi-chatbot-close:hover {{ background:rgba(239,68,68,.1); color:#ef4444; }}
      #nsi-chatbot-resize:hover {{ background:rgba(99,102,241,.1); color:#6366f1; }}

      /* Messages */
      #nsi-chatbot-msgs {{
        flex:1; overflow-y:auto; padding:14px;
        display:flex; flex-direction:column; gap:10px;
        scroll-behavior:smooth;
      }}
      #nsi-chatbot-msgs::-webkit-scrollbar {{ width:4px; }}
      #nsi-chatbot-msgs::-webkit-scrollbar-thumb {{ background:rgba(139,92,246,.4); border-radius:4px; }}

      .nsi-bubble {{
        max-width:85%; padding:10px 14px; border-radius:14px;
        font-size:13px; line-height:1.55;
        animation: nsiBubble .22s ease;
        word-wrap: break-word; white-space: pre-wrap;
      }}
      @keyframes nsiBubble {{ from{{opacity:0;transform:translateY(7px)}} to{{opacity:1;transform:translateY(0)}} }}
      .nsi-bubble.user {{
        background:linear-gradient(135deg,#6366f1,#8b5cf6);
        color:#fff; align-self:flex-end;
        border-bottom-right-radius:4px;
        box-shadow:0 4px 12px rgba(99,102,241,.2);
      }}
      .nsi-bubble.bot {{
        background:#ffffff;
        border:1px solid #e2e8f0;
        color:#0f172a; align-self:flex-start;
        border-bottom-left-radius:4px;
        box-shadow:0 2px 6px rgba(0,0,0,.05);
      }}
      .nsi-typing {{
        display:flex; gap:4px; align-items:center;
        padding:12px 14px;
        background:#ffffff;
        border:1px solid #e2e8f0;
        border-radius:14px; border-bottom-left-radius:4px;
        align-self:flex-start;
      }}
      .nsi-typing span {{
        width:6px; height:6px; background:#8b5cf6;
        border-radius:50%; animation:nsiDot 1.2s ease infinite;
      }}
      .nsi-typing span:nth-child(2){{animation-delay:.2s}}
      .nsi-typing span:nth-child(3){{animation-delay:.4s}}
      @keyframes nsiDot {{
        0%,60%,100%{{transform:translateY(0);opacity:.5}}
        30%{{transform:translateY(-5px);opacity:1}}
      }}

      /* Input area */
      #nsi-chatbot-footer {{
        padding:12px 14px;
        border-top:1px solid #e2e8f0;
        display:flex; gap:8px; flex-shrink:0;
        background:#f8fafc;
      }}
      #nsi-chatbot-input {{
        flex:1;
        background:#ffffff;
        border:1px solid #cbd5e1;
        border-radius:10px; padding:10px 12px;
        color:#0f172a; font-size:13px;
        outline:none; resize:none;
        transition: border-color .2s, box-shadow .2s;
        max-height:100px;
      }}
      #nsi-chatbot-input:focus {{
        border-color:#8b5cf6;
        box-shadow:0 0 0 3px rgba(139,92,246,.15);
      }}
      #nsi-chatbot-input::placeholder {{ color:#94a3b8; }}
      #nsi-chatbot-send {{
        width:40px; height:40px; flex-shrink:0; align-self:flex-end;
        background:linear-gradient(135deg,#6366f1,#a855f7);
        border:none; border-radius:10px; cursor:pointer; color:#fff;
        display:flex; align-items:center; justify-content:center;
        transition:transform .2s, box-shadow .2s;
      }}
      #nsi-chatbot-send:hover {{ transform:scale(1.08); box-shadow:0 4px 14px rgba(139,92,246,.5); }}
      #nsi-chatbot-send:disabled {{ opacity:.45; cursor:not-allowed; transform:none; }}
    `;
    doc.head.appendChild(style);
  }}

  // ── Build widget HTML and insert into parent body ─────────────────────────
  var root = doc.createElement('div');
  root.id = 'nsi-chatbot-root';
  root.innerHTML = `
    <button id="nsi-chatbot-toggle" title="{texts['toggle_title']}">
      <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="none"
           stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    </button>

    <div id="nsi-chatbot-panel" class="nsi-hidden">
      <div id="nsi-chatbot-header">
        <div class="nsi-avatar">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
               stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <!-- Head -->
            <rect x="4" y="7" width="16" height="12" rx="3" ry="3"/>
            <!-- Antenna -->
            <line x1="12" y1="7" x2="12" y2="3"/>
            <circle cx="12" cy="2.5" r="1" fill="white" stroke="none"/>
            <!-- Eyes -->
            <circle cx="9" cy="12" r="1.2" fill="white" stroke="none"/>
            <circle cx="15" cy="12" r="1.2" fill="white" stroke="none"/>
            <!-- Mouth -->
            <path d="M9 15.5 Q12 17.5 15 15.5" stroke-width="1.5" fill="none"/>
          </svg>
        </div>
        <div class="nsi-hinfo">
          <div class="nsi-htitle">NoSQL Inspector AI</div>
          <div class="nsi-hsub">Powered by Groq · LLaMA 3</div>
        </div>
        <div class="nsi-dot"></div>
        <button id="nsi-chatbot-resize" title="Expand/Collapse">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>
        </button>
        <button id="nsi-chatbot-close">✕</button>
      </div>

      <div id="nsi-chatbot-msgs">
        <div class="nsi-bubble bot">
          {texts['welcome']}
        </div>
      </div>

      <div id="nsi-chatbot-footer">
        <textarea id="nsi-chatbot-input" rows="1"
          placeholder="{texts['placeholder']}"></textarea>
        <button id="nsi-chatbot-send">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  `;
  doc.body.appendChild(root);

  // ── Wire up interactivity ─────────────────────────────────────────────────
  var toggle  = doc.getElementById('nsi-chatbot-toggle');
  var panel   = doc.getElementById('nsi-chatbot-panel');
  var closeBtn= doc.getElementById('nsi-chatbot-close');
  var resizeBtn = doc.getElementById('nsi-chatbot-resize');
  var input   = doc.getElementById('nsi-chatbot-input');
  var sendBtn = doc.getElementById('nsi-chatbot-send');
  var msgs    = doc.getElementById('nsi-chatbot-msgs');

  var history = [];
  var GROQ_KEY = "{api_key}";
  var GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";


  var SYS = {sys_prompt_json};

  function openChat() {{
    panel.classList.remove('nsi-hidden');
    toggle.style.display = 'none';
    input.focus();
  }}
  function closeChat() {{
    panel.classList.add('nsi-hidden');
    toggle.style.display = 'flex';
  }}

  var isExpanded = false;
  function toggleExpand() {{
    isExpanded = !isExpanded;
    if (isExpanded) {{
      panel.classList.add('nsi-expanded');
      resizeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>';
    }} else {{
      panel.classList.remove('nsi-expanded');
      resizeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>';
    }}
  }}

  toggle.addEventListener('click', openChat);
  closeBtn.addEventListener('click', closeChat);
  resizeBtn.addEventListener('click', toggleExpand);

  input.addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
  }});
  input.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); send(); }}
  }});
  sendBtn.addEventListener('click', send);

  function addBubble(role, text) {{
    var b = doc.createElement('div');
    b.className = 'nsi-bubble ' + role;
    b.textContent = text;
    msgs.appendChild(b);
    msgs.scrollTop = msgs.scrollHeight;
  }}

  function showTyping() {{
    var t = doc.createElement('div');
    t.className = 'nsi-typing'; t.id = 'nsi-typing';
    t.innerHTML = '<span></span><span></span><span></span>';
    msgs.appendChild(t); msgs.scrollTop = msgs.scrollHeight;
  }}
  function hideTyping() {{
    var t = doc.getElementById('nsi-typing');
    if (t) t.remove();
  }}

  async function send() {{
    var text = input.value.trim();
    if (!text || sendBtn.disabled) return;
    input.value = ''; input.style.height = 'auto';
    sendBtn.disabled = true;

    addBubble('user', text);
    history.push({{ role:'user', content:text }});
    showTyping();

    try {{
      var payload = {{
        model: "openai/gpt-oss-120b",
        messages: [{{ role:'system', content:SYS }}, ...history.slice(-12)],
        max_tokens: 1024,
        temperature: 0.7
      }};
      var res = await fetch(GROQ_URL, {{
        method: 'POST',
        headers: {{
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + GROQ_KEY
        }},
        body: JSON.stringify(payload)
      }});
      if (!res.ok) {{
        var e = await res.json();
        throw new Error(e.error?.message || 'HTTP ' + res.status);
      }}
      var data = await res.json();
      var reply = data.choices[0].message.content;
      history.push({{ role:'assistant', content:reply }});
      hideTyping();
      addBubble('bot', reply);
    }} catch(err) {{
      hideTyping();
      addBubble('bot', '{texts["error_prefix"]}' + err.message);
    }}

    sendBtn.disabled = false;
    input.focus();
  }}

}})();
</script>
</body>
</html>"""

    # height=0 → invisible iframe; scrolling="no" to avoid layout artifacts
    components.html(html, height=0, scrolling=False)

