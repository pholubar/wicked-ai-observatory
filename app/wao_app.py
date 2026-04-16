import streamlit as st
import json
from datetime import datetime
from neo4j import GraphDatabase
import anthropic
import sqlite3
import feedparser
import hashlib
import requests
import subprocess
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a local .env file if present
except ImportError:
    pass  # python-dotenv is optional

# ─────────────────────────────────────────────
# CONFIGURATION — loaded from environment variables
# ─────────────────────────────────────────────
# Create a local .env file (excluded via .gitignore) with these keys.
# See .env.example in the repository for a template.

NEO4J_URI         = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER        = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD    = os.environ.get("NEO4J_PASSWORD")
NEO4J_DB          = os.environ.get("NEO4J_DB", "wao")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ZOTERO_GROUP_ID   = os.environ.get("ZOTERO_GROUP_ID")
ZOTERO_API_KEY    = os.environ.get("ZOTERO_API_KEY")

# Fail early with a clear message if credentials are missing
_missing = [k for k, v in {
    "NEO4J_PASSWORD":    NEO4J_PASSWORD,
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "ZOTERO_GROUP_ID":   ZOTERO_GROUP_ID,
    "ZOTERO_API_KEY":    ZOTERO_API_KEY,
}.items() if not v]
if _missing:
    st.error(
        "Missing required environment variables: " + ", ".join(_missing) +
        ". Create a .env file based on .env.example or export them in your shell."
    )
    st.stop()

FACTOR_LIST = [
    "Regulatory Capture","AI-enabled Autocracy","Election Integrity",
    "Alignment Failures","Compute Concentration","Market Concentration",
    "Wealth Extraction","Liability Gaps","Bias and Fairness",
    "Autonomy Erosion","Accountability Gaps","Algorithmic Discrimination",
    "Epistemic Breakdown","Labour Displacement","Inequality Amplification",
    "Skill Dependency","Knowledge Quality","Global Governance Gaps",
    "Access Asymmetry","Geopolitical Rivalry","Intergenerational Equity",
    "Compute Energy Use","Resource Extraction","Carbon Footprint AI",
    "Deterrence Instability","Peacebuilding Potential",
    "Autonomous Weapon Systems","Hybrid Warfare","Compressed Kill Chains"
]

DIMENSION_COLORS = {
    "Political":    "#BA7517",
    "Technical":    "#1D9E75",
    "Economic":     "#639922",
    "Legal":        "#378ADD",
    "Ethical":      "#7F77DD",
    "Societal":     "#D85A30",
    "Global":       "#D4537E",
    "War":          "#E24B4A",
    "Peace":        "#5DCAA5",
    "Environmental":"#97C459",
    "Pedagogical":  "#AFA9EC",
    "Epistemic":    "#B4B2A9",
}

# ─────────────────────────────────────────────
# VERBINDUNGEN (gecacht)
# ─────────────────────────────────────────────
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@st.cache_resource
def get_client():
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@st.cache_resource
def get_db():
    conn = sqlite3.connect("wao_staging.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY, title TEXT, summary TEXT,
        source TEXT, url TEXT, published TEXT,
        status TEXT DEFAULT 'pending', created_at TEXT)""")
    conn.commit()
    return conn

# ─────────────────────────────────────────────
# SEITE KONFIGURIEREN
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Wicked AI Observatory",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
h1, h2, h3 {
    font-family: 'DM Serif Display', serif !important;
}
.wao-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem 2.5rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    color: white;
}
.wao-header h1 {
    color: white !important;
    font-size: 2rem;
    margin: 0;
    letter-spacing: -0.5px;
}
.wao-header p {
    color: rgba(255,255,255,0.6);
    margin: 0.25rem 0 0;
    font-size: 0.9rem;
}
.metric-card {
    background: white;
    border: 1px solid #eee;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    text-align: center;
}
.metric-card .number {
    font-size: 2.5rem;
    font-weight: 300;
    color: #534AB7;
    line-height: 1;
}
.metric-card .label {
    font-size: 0.8rem;
    color: #888;
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.factor-card {
    background: white;
    border: 1px solid #eee;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.score-badge {
    font-size: 1.4rem;
    font-weight: 300;
    min-width: 3rem;
    text-align: right;
}
.event-item {
    padding: 0.75rem 1rem;
    border-left: 3px solid #534AB7;
    background: #f8f8ff;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.5rem;
}
.event-item.indirect {
    border-left-color: #BA7517;
    background: #fffbf0;
}
.tag {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.tag-ja { background: #E1F5EE; color: #085041; }
.tag-indirekt { background: #FEF5E5; color: #633806; }
.tag-nein { background: #fef0f0; color: #c0392b; }
.silence-card {
    background: #fff5f5;
    border: 1px solid #ffd5d5;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.4rem;
}
.proposal-card {
    background: #f0f0ff;
    border: 1px solid #d0d0ff;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}
.source-flag-warn { color: #E24B4A; font-weight: 500; }
.source-flag-low  { color: #BA7517; font-weight: 500; }
.source-flag-ok   { color: #1D9E75; font-weight: 500; }
.stButton > button {
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown(f"""
<div class="wao-header">
    <h1>🔭 Wicked AI Observatory</h1>
    <p>Dynamisches Monitoring von KI-Governance-Herausforderungen · Stand: {datetime.now().strftime('%d.%m.%Y')}</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Navigation")
    seite = st.radio("", [
        "📊 Dashboard",
        "🔄 Wöchentlicher Update",
        "📋 Review Digest",
        "⚖️ Quellen-Gewichtung",
        "📤 Export",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### Graph-Status")

    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DB) as session:
            r = session.run("MATCH (n) RETURN labels(n)[0] AS typ, count(n) AS n")
            stats = {rec["typ"]: rec["n"] for rec in r}
        st.metric("Faktoren", stats.get("Factor", 0))
        st.metric("Stakeholder", stats.get("Stakeholder", 0))
        st.metric("Events", stats.get("Event", 0))
        st.success("Neo4j verbunden")
    except Exception as e:
        st.error("Neo4j nicht verbunden")
        st.caption("Starte Neo4j Desktop → wao-v2")

# ─────────────────────────────────────────────
# SEITE: DASHBOARD
# ─────────────────────────────────────────────
if seite == "📊 Dashboard":

    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DB) as session:

            # Top Faktoren
            top = list(session.run("""
                MATCH (f:Factor)
                RETURN f.name AS name, f.dimension AS dim,
                       f.wickedness_score AS score
                ORDER BY score DESC LIMIT 10
            """))

            # Meistgenannte Faktoren
            signale = list(session.run("""
                MATCH (e:Event)-[:SIGNALS]->(f:Factor)
                RETURN f.name AS name, count(e) AS n
                ORDER BY n DESC LIMIT 5
            """))

            # Score-Änderungen
            changes = list(session.run("""
                MATCH (f:Factor)
                WHERE f.last_reviewed = date()
                RETURN f.name AS name, f.wickedness_score AS score,
                       f.score_begruendung AS begruendung
                ORDER BY score DESC
            """))

            # Schweige-Signale
            schweigen = list(session.run("""
                MATCH (f:Factor)
                WHERE NOT (f)<-[:SIGNALS]-(:Event)
                AND f.wickedness_score > 65
                RETURN f.name AS name, f.dimension AS dim,
                       f.wickedness_score AS score
                ORDER BY score DESC
            """))

            # Neueste Events
            events = list(session.run("""
                MATCH (e:Event)-[:SIGNALS]->(f:Factor)
                RETURN e.title AS titel, e.url AS url,
                       e.ki_relevant AS relevant, f.name AS faktor,
                       e.source AS quelle, e.begruendung AS begruendung
                ORDER BY e.created_at DESC LIMIT 10
            """))

        # Metriken
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            top1 = top[0] if top else None
            st.markdown(f"""<div class="metric-card">
                <div class="number">{top1['score'] if top1 else '–'}</div>
                <div class="label">Höchster Score</div>
                <div style="font-size:0.75rem;color:#666;margin-top:0.25rem">{top1['name'] if top1 else ''}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            sig1 = signale[0] if signale else None
            st.markdown(f"""<div class="metric-card">
                <div class="number">{sig1['n'] if sig1 else '–'}</div>
                <div class="label">Meiste Events</div>
                <div style="font-size:0.75rem;color:#666;margin-top:0.25rem">{sig1['name'] if sig1 else ''}</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="metric-card">
                <div class="number">{len(schweigen)}</div>
                <div class="label">Schweige-Signale</div>
                <div style="font-size:0.75rem;color:#666;margin-top:0.25rem">Faktoren ohne Events</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""<div class="metric-card">
                <div class="number">{len(changes)}</div>
                <div class="label">Score-Änderungen</div>
                <div style="font-size:0.75rem;color:#666;margin-top:0.25rem">Heute</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")

        # Zwei Spalten
        col_left, col_right = st.columns([1.2, 1])

        with col_left:
            st.markdown("#### Top 10 Faktoren nach Wickedness-Score")
            for r in top:
                farbe = DIMENSION_COLORS.get(r["dim"], "#888")
                breite = int(r["score"] or 0)
                st.markdown(f"""
                <div style="margin-bottom:0.4rem">
                    <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                        <span style="font-size:0.85rem;font-weight:500">{r['name']}</span>
                        <span style="font-size:0.85rem;color:{farbe};font-weight:600">{r['score']}</span>
                    </div>
                    <div style="background:#eee;border-radius:4px;height:6px">
                        <div style="background:{farbe};width:{breite}%;height:6px;border-radius:4px"></div>
                    </div>
                    <div style="font-size:0.7rem;color:#999;margin-top:1px">{r['dim']}</div>
                </div>
                """, unsafe_allow_html=True)

        with col_right:
            st.markdown("#### Neueste Events")
            for e in events[:6]:
                cls = "event-item" if e["relevant"] == "ja" else "event-item indirect"
                tag_cls = "tag-ja" if e["relevant"] == "ja" else "tag-indirekt"
                url = e["url"] or "#"
                st.markdown(f"""
                <div class="{cls}">
                    <div style="font-size:0.82rem;font-weight:500">
                        <a href="{url}" target="_blank" style="color:inherit;text-decoration:none">{(e['titel'] or '')[:65]}{'...' if len(e['titel'] or '')>65 else ''}</a>
                    </div>
                    <div style="margin-top:0.25rem;display:flex;gap:0.4rem;align-items:center">
                        <span class="tag {tag_cls}">{e['relevant']}</span>
                        <span style="font-size:0.72rem;color:#888">{e['faktor']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Schweige-Signale
        if schweigen:
            st.markdown("#### ⚠️ Schweige-Signale")
            cols = st.columns(3)
            for i, s in enumerate(schweigen):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="silence-card">
                        <div style="font-weight:500;font-size:0.85rem">{s['name']}</div>
                        <div style="font-size:0.75rem;color:#888">{s['dim']} · Score: {s['score']}</div>
                        <div style="font-size:0.72rem;color:#c0392b;margin-top:0.2rem">Kein Event erfasst</div>
                    </div>
                    """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
        st.info("Stelle sicher dass Neo4j Desktop läuft und wao-v2 gestartet ist.")

# ─────────────────────────────────────────────
# SEITE: WÖCHENTLICHER UPDATE
# ─────────────────────────────────────────────
elif seite == "🔄 Wöchentlicher Update":

    st.markdown("#### Wöchentlicher Update")
    st.caption("Startet Monitor Agent, Classify Agent und Write Agent in einem Schritt.")

    if st.button("▶️ Update jetzt starten", type="primary"):
        try:
            driver = get_driver()
            client = get_client()
            conn   = get_db()
            cursor = conn.cursor()

            progress = st.progress(0)
            status   = st.empty()
            log      = st.empty()
            logs     = []

            def add_log(msg):
                logs.append(msg)
                log.markdown("\n".join(f"- {l}" for l in logs[-15:]))

            # FEEDS
            FEEDS = [
                ("EU AI Office", "https://digital-strategy.ec.europa.eu/en/rss.xml"),
                ("EU Parlament", "https://www.europarl.europa.eu/rss/doc/news/en.xml"),
                ("ArXiv AI", "https://rss.arxiv.org/rss/cs.AI"),
                ("ArXiv Cybersecurity", "https://rss.arxiv.org/rss/cs.CR"),
                ("ArXiv Society", "https://rss.arxiv.org/rss/cs.CY"),
                ("ArXiv Robotics", "https://rss.arxiv.org/rss/cs.RO"),
                ("AI Now Institute", "https://ainowinstitute.org/feed"),
                ("Future of Life", "https://futureoflife.org/feed/"),
                ("MIT Tech Review AI", "https://www.technologyreview.com/feed/"),
                ("UN News Tech", "https://news.un.org/feed/subscribe/en/news/topic/science-and-technology/feed/rss.xml"),
                ("Carbon Brief", "https://www.carbonbrief.org/feed/"),
                ("Greenpeace", "https://www.greenpeace.org/international/feed/"),
                ("IPCC", "https://www.ipcc.ch/feed/"),
            ]

            status.info("1/4 Monitor Agent läuft...")
            progress.progress(10)
            neue = 0

            for source, url in FEEDS:
                try:
                    feed = feedparser.parse(url)
                    count = 0
                    for entry in feed.entries[:10]:
                        eid = hashlib.md5(entry.get("link", entry.get("title","")).encode()).hexdigest()
                        try:
                            cursor.execute("""INSERT INTO events
                                (id,title,summary,source,url,published,created_at)
                                VALUES (?,?,?,?,?,?,?)""",
                                (eid, entry.get("title","")[:200],
                                 entry.get("summary","")[:500], source,
                                 entry.get("link",""), entry.get("published",""),
                                 datetime.now().isoformat()))
                            conn.commit()
                            neue += 1
                            count += 1
                        except sqlite3.IntegrityError:
                            pass
                    add_log(f"{source}: {count} neue Events")
                except Exception as ex:
                    add_log(f"⚠️ {source}: {ex}")

            # Zotero
            try:
                zr = requests.get(
                    f"https://api.zotero.org/groups/{ZOTERO_GROUP_ID}/items",
                    headers={"Zotero-API-Key": ZOTERO_API_KEY},
                    params={"format":"json","limit":25,"sort":"dateAdded","direction":"desc"},
                    timeout=10
                )
                if zr.status_code == 200:
                    for item in zr.json():
                        d = item.get("data",{})
                        title = d.get("title","")
                        if not title:
                            continue
                        eid = hashlib.md5((title+d.get("url","")).encode()).hexdigest()
                        try:
                            cursor.execute("""INSERT INTO events
                                (id,title,summary,source,url,published,created_at)
                                VALUES (?,?,?,?,?,?,?)""",
                                (eid, title[:200], d.get("abstractNote","")[:500],
                                 "Zotero WAO", d.get("url",""),
                                 d.get("dateAdded",""), datetime.now().isoformat()))
                            conn.commit()
                            neue += 1
                        except sqlite3.IntegrityError:
                            pass
                    add_log(f"Zotero: OK")
            except Exception as ex:
                add_log(f"⚠️ Zotero: {ex}")

            progress.progress(35)
            status.info("2/4 Classify Agent läuft...")

            cursor.execute("SELECT id,title,summary,url,published,source FROM events WHERE status='pending'")
            pending = cursor.fetchall()
            geschrieben = gefiltert = fehler = 0

            for i, (eid, title, summary, url, published, source) in enumerate(pending):
                try:
                    prompt = f"""Analysiere dieses Ereignis. Antworte NUR mit JSON:
Titel: {title}
Zusammenfassung: {(summary or '')[:300]}
Faktoren: {', '.join(FACTOR_LIST)}

{{"ki_relevant":"ja|nein|indirekt","relevante_faktoren":["max 2 Faktornamen"],"dimension":"Political|Technical|Economic|Legal|Ethical|Societal|Global|War|Peace|Environmental|Pedagogical|Epistemic","signal_typ":"policy|research|incident|governance|technology","wickedness_relevanz":"hoch|mittel|niedrig","begruendung":"Ein Satz"}}"""

                    msg = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=300,
                        messages=[{"role":"user","content":prompt}]
                    )
                    raw = msg.content[0].text.strip()
                    cls = json.loads(raw[raw.find("{"):raw.rfind("}")+1])

                    if cls["ki_relevant"] == "nein":
                        cursor.execute("UPDATE events SET status='filtered' WHERE id=?", (eid,))
                        conn.commit()
                        gefiltert += 1
                        continue

                    with driver.session(database=NEO4J_DB) as session:
                        session.run("""
                            MERGE (e:Event {id:$id})
                            SET e.title=$title, e.url=$url, e.published=$published,
                                e.source=$source, e.dimension=$dim,
                                e.signal_typ=$st, e.wickedness_relevanz=$wr,
                                e.begruendung=$bg, e.ki_relevant=$kr,
                                e.written_by='classify_agent',
                                e.review_status='pending', e.created_at=datetime()
                        """, {"id":eid,"title":title,"url":url,"published":published,
                              "source":source or "","dim":cls["dimension"],
                              "st":cls["signal_typ"],"wr":cls["wickedness_relevanz"],
                              "bg":cls["begruendung"],"kr":cls["ki_relevant"]})
                        for faktor in cls["relevante_faktoren"]:
                            session.run("""
                                MATCH (e:Event{id:$eid}) MATCH (f:Factor{name:$f})
                                MERGE (e)-[:SIGNALS{confidence:0.70,written_by:'classify_agent',review_status:'pending'}]->(f)
                            """, {"eid":eid,"f":faktor})

                    cursor.execute("UPDATE events SET status='processed' WHERE id=?", (eid,))
                    conn.commit()
                    geschrieben += 1
                    add_log(f"[{cls['ki_relevant']}] {title[:50]}")

                except Exception as ex:
                    fehler += 1
                    cursor.execute("UPDATE events SET status='error' WHERE id=?", (eid,))
                    conn.commit()

                progress.progress(35 + int(55 * (i+1) / max(len(pending),1)))

            progress.progress(100)
            status.success(f"✅ Update abgeschlossen — {geschrieben} geschrieben · {gefiltert} gefiltert · {fehler} Fehler")
            st.balloons()

        except Exception as e:
            st.error(f"Fehler: {e}")

# ─────────────────────────────────────────────
# SEITE: REVIEW DIGEST
# ─────────────────────────────────────────────
elif seite == "📋 Review Digest":

    st.markdown("#### Review Digest")
    st.caption("Faktoren mit neuen Events — Score-Vorschläge bestätigen oder anpassen.")

    try:
        driver  = get_driver()
        client  = get_client()

        with driver.session(database=NEO4J_DB) as session:
            result = list(session.run("""
                MATCH (e:Event)-[:SIGNALS]->(f:Factor)
                WHERE e.review_status = 'pending'
                WITH f, collect({titel:e.title, bg:e.begruendung, rel:e.wickedness_relevanz}) AS evts, count(e) AS n
                WHERE n >= 2
                RETURN f.name AS faktor, f.wickedness_score AS score,
                       f.dimension AS dim, evts, n
                ORDER BY n DESC LIMIT 8
            """))

        if not result:
            st.info("Keine pending Events — führe zuerst den wöchentlichen Update aus.")
        else:
            for rec in result:
                faktor = rec["faktor"]
                score  = rec["score"]
                dim    = rec["dim"]
                evts   = rec["evts"]
                n      = rec["n"]
                farbe  = DIMENSION_COLORS.get(dim, "#888")

                with st.expander(f"**{faktor}** — Score: {score} · {n} neue Events · {dim}", expanded=True):

                    # Events anzeigen
                    for ev in evts[:3]:
                        st.markdown(f"- {(ev['titel'] or '')[:80]}")

                    # Proposal Agent
                    if st.button(f"KI-Vorschlag generieren", key=f"prop_{faktor}"):
                        with st.spinner("Proposal Agent läuft..."):
                            prompt = f"""Du bist der Proposal Agent des WAO.
Faktor: {faktor} · Score: {score}
Events: {chr(10).join(f"- {e['titel'][:60]}: {e['bg']}" for e in evts[:5])}
Antworte NUR mit JSON:
{{"vorschlag":"erhoehen|beibehalten|senken","neuer_score":{score},"veraenderung":0,"konfidenz":0.0,"begruendung":"Ein Satz"}}"""
                            msg = client.messages.create(
                                model="claude-sonnet-4-6", max_tokens=200,
                                messages=[{"role":"user","content":prompt}])
                            raw = msg.content[0].text.strip()
                            v = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
                            st.session_state[f"vorschlag_{faktor}"] = v

                    if f"vorschlag_{faktor}" in st.session_state:
                        v = st.session_state[f"vorschlag_{faktor}"]
                        pfeil = "↑" if v["vorschlag"]=="erhoehen" else "↓" if v["vorschlag"]=="senken" else "→"
                        st.markdown(f"""
                        <div class="proposal-card">
                            <strong>Vorschlag: {pfeil} {score} → {v['neuer_score']}</strong>
                            (Konfidenz: {int(v['konfidenz']*100)}%)<br>
                            <span style="font-size:0.85rem;color:#555">{v['begruendung']}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    # Score-Eingabe
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        default = st.session_state.get(f"vorschlag_{faktor}", {}).get("neuer_score", score)
                        neuer_score = st.number_input(
                            "Neuer Score", min_value=0, max_value=100,
                            value=int(default), key=f"score_{faktor}")
                        begruendung = st.text_input(
                            "Begründung", key=f"bg_{faktor}",
                            placeholder="Warum wird der Score angepasst?")
                    with col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("✓ Bestätigen", key=f"confirm_{faktor}", type="primary"):
                            with driver.session(database=NEO4J_DB) as session:
                                session.run("""
                                    MATCH (f:Factor {name:$name})
                                    SET f.wickedness_score=$score,
                                        f.score_begruendung=$bg,
                                        f.vorschlag_angenommen=true,
                                        f.last_reviewed=date()
                                """, {"name":faktor,"score":neuer_score,"bg":begruendung or "Manuell bestätigt"})
                                session.run("""
                                    MATCH (e:Event)-[:SIGNALS]->(f:Factor{name:$name})
                                    WHERE e.review_status='pending'
                                    SET e.review_status='reviewed'
                                """, {"name":faktor})
                            st.success(f"✓ {faktor}: {score} → {neuer_score}")
                    with col3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Überspringen", key=f"skip_{faktor}"):
                            st.info("Übersprungen")

    except Exception as e:
        st.error(f"Fehler: {e}")

# ─────────────────────────────────────────────
# SEITE: QUELLEN-GEWICHTUNG
# ─────────────────────────────────────────────
elif seite == "⚖️ Quellen-Gewichtung":

    st.markdown("#### Quellen-Gewichtung")
    st.caption("Faktoren mit geringer Quellen-Diversität — Gewicht direkt anpassen.")

    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DB) as session:
            result = list(session.run("""
                MATCH (e:Event)-[:SIGNALS]->(f:Factor)
                WITH f.name AS faktor,
                     collect(DISTINCT e.source) AS quellen,
                     count(e) AS n
                WHERE n >= 2
                RETURN faktor, quellen, n
                ORDER BY size(quellen) ASC, n DESC
                LIMIT 15
            """))

        for rec in result:
            faktor  = rec["faktor"]
            quellen = [q for q in rec["quellen"] if q]
            n       = rec["n"]
            div     = len(quellen)

            if div == 1:
                flag = "⚠️ SINGLE SOURCE"
                cls  = "source-flag-warn"
                default_w = 0.5
            elif div == 2:
                flag = "△ LOW DIVERSITY"
                cls  = "source-flag-low"
                default_w = 0.75
            elif div <= 4:
                flag = "○ MODERAT"
                cls  = "source-flag-ok"
                default_w = 0.9
            else:
                flag = "✓ GUT"
                cls  = "source-flag-ok"
                default_w = 1.0

            with st.expander(f"**{faktor}** · {n} Events · {div} {'Quelle' if div==1 else 'Quellen'}"):
                st.markdown(f'<span class="{cls}">{flag}</span>', unsafe_allow_html=True)

                if quellen:
                    for q in quellen:
                        st.caption(f"· {q}")
                else:
                    st.caption("(Keine Quellen-Information)")

                col1, col2 = st.columns([2, 1])
                with col1:
                    gewicht = st.slider(
                        "Quellen-Gewicht",
                        min_value=0.0, max_value=1.0,
                        value=float(st.session_state.get(f"w_{faktor}", default_w)),
                        step=0.05, key=f"slider_{faktor}",
                        help="1.0 = volle Gewichtung · 0.5 = halbiert · 0.0 = ignoriert"
                    )
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Speichern", key=f"save_w_{faktor}"):
                        with driver.session(database=NEO4J_DB) as session:
                            session.run("""
                                MATCH (e:Event)-[:SIGNALS]->(f:Factor{name:$faktor})
                                SET e.source_weight=$w,
                                    e.source_reviewed=true,
                                    e.source_reviewed_date=date()
                            """, {"faktor":faktor,"w":gewicht})
                        st.success(f"✓ Gespeichert: {gewicht}")

    except Exception as e:
        st.error(f"Fehler: {e}")

# ─────────────────────────────────────────────
# SEITE: EXPORT
# ─────────────────────────────────────────────
elif seite == "📤 Export":

    st.markdown("#### Export")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Cypher-Export**")
        st.caption("Exportiert alle Faktoren, Stakeholder und Beziehungen als .cypher Datei.")
        if st.button("📥 Cypher exportieren", type="primary"):
            try:
                driver = get_driver()
                lines  = [f"// Wicked AI Observatory — Export {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
                with driver.session(database=NEO4J_DB) as session:
                    lines.append("// FAKTOREN")
                    for r in session.run("MATCH (f:Factor) RETURN f ORDER BY f.dimension, f.name"):
                        f = r["f"]
                        lines.append(f'MERGE (f:Factor {{name:"{f["name"]}"}}) SET f.dimension="{f.get("dimension","")}", f.wickedness_score={f.get("wickedness_score",0)}, f.last_updated=date();')
                    lines.append("\n// STAKEHOLDER")
                    for r in session.run("MATCH (s:Stakeholder) RETURN s ORDER BY s.name"):
                        s = r["s"]
                        lines.append(f'MERGE (s:Stakeholder {{name:"{s["name"]}"}}) SET s.class="{s.get("class","")}", s.influence={s.get("influence",0.5)}, s.last_updated=date();')
                    lines.append("\n// AMPLIFIES")
                    for r in session.run("MATCH (a:Factor)-[r:AMPLIFIES]->(b:Factor) RETURN a.name AS v, b.name AS z, r.strength AS st"):
                        lines.append(f'MATCH (a:Factor{{name:"{r["v"]}"}}),(b:Factor{{name:"{r["z"]}"}}) MERGE (a)-[:AMPLIFIES{{strength:{r["st"] or 0.7}}}]->(b);')
                    lines.append("\n// CONFLICTS_WITH")
                    for r in session.run("MATCH (a:Factor)-[r:CONFLICTS_WITH]->(b:Factor) RETURN a.name AS v, b.name AS z, r.strength AS st"):
                        lines.append(f'MATCH (a:Factor{{name:"{r["v"]}"}}),(b:Factor{{name:"{r["z"]}"}}) MERGE (a)-[:CONFLICTS_WITH{{strength:{r["st"] or 0.7}}}]->(b);')

                content = "\n".join(lines)
                filename = f"wicked_ai_observatory_{datetime.now().strftime('%Y_%m_%d')}.cypher"
                st.download_button("⬇️ Download", content, filename, "text/plain")
                st.success("Bereit zum Download")
            except Exception as e:
                st.error(f"Fehler: {e}")

    with col2:
        st.markdown("**Graph-Status**")
        st.caption("Aktueller Stand aller Faktoren.")
        if st.button("📊 Faktoren anzeigen"):
            try:
                driver = get_driver()
                with driver.session(database=NEO4J_DB) as session:
                    faktoren = list(session.run("""
                        MATCH (f:Factor)
                        OPTIONAL MATCH (e:Event)-[:SIGNALS]->(f)
                        RETURN f.name AS name, f.dimension AS dim,
                               f.wickedness_score AS score,
                               count(e) AS events,
                               f.last_reviewed AS reviewed
                        ORDER BY score DESC
                    """))
                import pandas as pd
                df = pd.DataFrame([{
                    "Faktor": r["name"],
                    "Dimension": r["dim"],
                    "Score": r["score"],
                    "Events": r["events"],
                    "Reviewed": r["reviewed"] or "–"
                } for r in faktoren])
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Fehler: {e}")


    # --- HTML-Graphen generieren ---
    st.divider()
    st.markdown("**HTML-Graphen generieren**")
    st.caption("Drei interaktive Graphen: Faktoren, Struktur, Vollgraph.")
    if st.button("Graphen generieren"):
        try:
            from pyvis.network import Network
            import os as _os
            FARBEN = {"Political":"#BA7517","Technical":"#1D9E75","Economic":"#639922","Legal":"#378ADD","Ethical":"#7F77DD","Societal":"#D85A30","Global":"#D4537E","War":"#E24B4A","Peace":"#5DCAA5","Environmental":"#97C459","Pedagogical":"#AFA9EC","Epistemic":"#B4B2A9"}
            driver = get_driver()
            with driver.session(database=NEO4J_DB) as session:
                fk = list(session.run("MATCH (f:Factor) RETURN f.name AS name, f.dimension AS dim, f.wickedness_score AS score"))
                sk = list(session.run("MATCH (s:Stakeholder) RETURN s.name AS name, s.class AS klasse, s.influence AS inf"))
                ek = list(session.run("MATCH (e:Event) RETURN e.title AS title"))
                ka = list(session.run("MATCH (a)-[r]->(b) RETURN CASE WHEN a:Factor THEN a.name WHEN a:Stakeholder THEN a.name ELSE a.title END AS von, CASE WHEN b:Factor THEN b.name WHEN b:Stakeholder THEN b.name ELSE b.title END AS nach, type(r) AS typ"))
            fn = [f["name"] for f in fk]
            sn = [s["name"] for s in sk]
            generated = []
            for gname, inc_s, inc_e in [("faktoren", False, False), ("struktur", True, False), ("vollgraph", True, True)]:
                net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
                for f in fk:
                    net.add_node(f["name"], label=f["name"], color=FARBEN.get(f["dim"],"#888"), size=f["score"]/5, title=str(f["dim"])+" | Score: "+str(f["score"]))
                if inc_s:
                    for s in sk:
                        net.add_node(s["name"], label=s["name"], color="#FF8C00", size=(s["inf"] or 0.5)*30, shape="diamond")
                if inc_e:
                    for e in ek:
                        lbl = (e["title"] or "")[:30]+"..."
                        net.add_node(e["title"], label=lbl, color="#B0C4DE", size=8, shape="dot", title=e["title"])
                valid = fn + (sn if inc_s else [])
                for k in ka:
                    try:
                        v = k["von"] or ""
                        n = k["nach"] or ""
                        if inc_e or (v in valid and n in valid):
                            net.add_edge(v, n, title=k["typ"])
                    except:
                        pass
                path = _os.path.expanduser("~/wao_graph_"+gname+".html")
                net.save_graph("_tmp_graph.html")
                with open("_tmp_graph.html", "r", encoding="utf-8") as _f:
                    _html = _f.read()
                from datetime import datetime as _dt
                _datum = _dt.now().strftime("%Y-%m-%d")
                _sig = '<div style="height:2px;background:#B0C4DE;"></div><span>SIGNALS</span>' if inc_e else ""
                _legende = f"""<div style="position:absolute;top:16px;right:16px;background:white;border:1px solid #ddd;border-radius:8px;padding:14px 18px;font-family:Arial,sans-serif;font-size:12px;z-index:9999;box-shadow:0 2px 8px rgba(0,0,0,0.1);min-width:200px;">
<div style="font-weight:bold;margin-bottom:10px;font-size:13px;">Wicked AI Observatory</div>
<div style="font-weight:bold;color:#666;margin-bottom:6px;font-size:11px;">Dimensions</div>
<div style="display:grid;grid-template-columns:14px 1fr;gap:4px 8px;align-items:center;margin-bottom:12px;">
<div style="width:12px;height:12px;border-radius:50%;background:#BA7517;"></div><span>Political</span>
<div style="width:12px;height:12px;border-radius:50%;background:#1D9E75;"></div><span>Technical</span>
<div style="width:12px;height:12px;border-radius:50%;background:#639922;"></div><span>Economic</span>
<div style="width:12px;height:12px;border-radius:50%;background:#378ADD;"></div><span>Legal</span>
<div style="width:12px;height:12px;border-radius:50%;background:#7F77DD;"></div><span>Ethical</span>
<div style="width:12px;height:12px;border-radius:50%;background:#D85A30;"></div><span>Societal</span>
<div style="width:12px;height:12px;border-radius:50%;background:#D4537E;"></div><span>Global</span>
<div style="width:12px;height:12px;border-radius:50%;background:#E24B4A;"></div><span>War</span>
<div style="width:12px;height:12px;border-radius:50%;background:#5DCAA5;"></div><span>Peace</span>
<div style="width:12px;height:12px;border-radius:50%;background:#97C459;"></div><span>Environmental</span>
<div style="width:12px;height:12px;border-radius:50%;background:#AFA9EC;"></div><span>Pedagogical</span>
<div style="width:12px;height:12px;border-radius:50%;background:#B4B2A9;"></div><span>Epistemic</span>
</div>
<div style="font-weight:bold;color:#666;margin-bottom:6px;font-size:11px;">Edges</div>
<div style="display:grid;grid-template-columns:24px 1fr;gap:4px 8px;align-items:center;">
<div style="height:2px;background:#AAAAAA;"></div><span>AMPLIFIES</span>
<div style="height:2px;background:#E24B4A;"></div><span>CONFLICTS_WITH</span>
<div style="height:2px;background:#FF8C00;"></div><span>POSITIONS_ON</span>
{_sig}
</div>
<div style="margin-top:12px;color:#999;font-size:10px;border-top:1px solid #eee;padding-top:8px;">
Date: {_datum} · WAO v1.0 · {gname}
</div></div>"""
                _html = _html.replace("</body>", _legende + "</body>")
                with open(path, "w", encoding="utf-8") as _f:
                    _f.write(_html)
                _os.remove("_tmp_graph.html")
                generated.append((gname, path))
            st.success("Graphen generiert: " + ", ".join(g[0] for g in generated))
            for gn, gp in generated:
                with open(gp, "r") as gf:
                    st.download_button("Download "+gn, gf.read(), _os.path.basename(gp), "text/html")
        except ImportError:
            st.error("pyvis nicht installiert: pip install pyvis")
        except Exception as e:
            st.error("Fehler: " + str(e))
