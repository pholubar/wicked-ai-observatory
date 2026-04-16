# ==================================================
# WAO MASTER-ZELLE — Alle Funktionen + Initialisierung
# Einmal ausführen, dann wao_weekly_update() starten
# ==================================================

# IMPORTS
import os
import feedparser
import sqlite3
import hashlib
import requests
import json
import subprocess
from datetime import datetime
from neo4j import GraphDatabase
import anthropic
from pyvis.network import Network

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a local .env file if present
except ImportError:
    pass  # python-dotenv is optional; env vars can also be set in the shell

# CONFIGURATION — loaded from environment variables
# Create a local .env file (excluded via .gitignore) with the following keys:
#
#   NEO4J_URI=bolt://localhost:7687
#   NEO4J_USER=neo4j
#   NEO4J_PASSWORD=your-password-here
#   NEO4J_DB=wao
#   ANTHROPIC_API_KEY=sk-ant-...
#   ZOTERO_GROUP_ID=your-group-id
#   ZOTERO_API_KEY=your-zotero-key
#
# See .env.example in the repository for a template.

NEO4J_URI        = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER       = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD   = os.environ.get("NEO4J_PASSWORD")
NEO4J_DB         = os.environ.get("NEO4J_DB", "wao")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ZOTERO_GROUP_ID  = os.environ.get("ZOTERO_GROUP_ID")
ZOTERO_API_KEY   = os.environ.get("ZOTERO_API_KEY")

# Sanity check — fail early with a clear message if credentials are missing
_missing = [k for k, v in {
    "NEO4J_PASSWORD":    NEO4J_PASSWORD,
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "ZOTERO_GROUP_ID":   ZOTERO_GROUP_ID,
    "ZOTERO_API_KEY":    ZOTERO_API_KEY,
}.items() if not v]
if _missing:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(_missing) +
        ". Create a .env file based on .env.example or export them in your shell."
    )

# CONNECTIONS
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# STAGING DATENBANK
conn = sqlite3.connect('wao_staging.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT,
        summary TEXT,
        source TEXT,
        url TEXT,
        published TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
''')
conn.commit()

# RSS FEEDS
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
    ("Green IT / Greenpeace Tech", "https://www.greenpeace.org/international/feed/"),
    ("IPCC News", "https://www.ipcc.ch/feed/"),
]

# FAKTORLISTE
FACTOR_LIST = [
    "Regulatory Capture", "AI-enabled Autocracy", "Election Integrity",
    "Compute Concentration", "Market Concentration", "Wealth Extraction",
    "Alignment Failures", "Liability Gaps",
    "Bias and Fairness", "Autonomy Erosion", "Accountability Gaps",
    "Algorithmic Discrimination",
    "Epistemic Breakdown", "Labour Displacement", "Inequality Amplification",
    "Skill Dependency", "Knowledge Quality",
    "Global Governance Gaps", "Access Asymmetry", "Geopolitical Rivalry",
    "Intergenerational Equity",
    "Compute Energy Use", "Resource Extraction", "Carbon Footprint AI",
    "Deterrence Instability", "Peacebuilding Potential",
    "Autonome Waffensysteme", "Hybrid Warfare", "Compressed Kill Chains"
]

# ==================================================
# MONITOR AGENT
# ==================================================

def fetch_zotero(group_id, api_key):
    url = f"https://api.zotero.org/groups/{group_id}/items"
    headers = {"Zotero-API-Key": api_key}
    params = {"format": "json", "limit": 25, "sort": "dateAdded", "direction": "desc"}
    response = requests.get(url, headers=headers, params=params)
    items = response.json()
    neue = 0
    for item in items:
        data = item.get("data", {})
        title = data.get("title", "")
        url_item = data.get("url", "")
        abstract = data.get("abstractNote", "")
        date_added = data.get("dateAdded", "")
        if not title:
            continue
        event_id = hashlib.md5((title + url_item).encode()).hexdigest()
        try:
            cursor.execute('''
                INSERT INTO events (id, title, summary, source, url, published, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event_id, title[:200], abstract[:500], "Zotero WAO",
                  url_item, date_added, datetime.now().isoformat()))
            conn.commit()
            neue += 1
        except sqlite3.IntegrityError:
            pass
    print(f"  Zotero: {neue} neue Einträge")
    return neue

def fetch_events():
    neue = 0
    fehler = 0
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                fehler += 1
                continue
            count = 0
            for entry in feed.entries[:10]:
                event_id = hashlib.md5(
                    entry.get('link', entry.get('title', '')).encode()
                ).hexdigest()
                try:
                    cursor.execute('''
                        INSERT INTO events
                        (id, title, summary, source, url, published, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event_id,
                        entry.get('title', '')[:200],
                        entry.get('summary', '')[:500],
                        source,
                        entry.get('link', ''),
                        entry.get('published', ''),
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    neue += 1
                    count += 1
                except sqlite3.IntegrityError:
                    pass
            print(f"  {source}: {count} neue Ereignisse")
        except Exception as e:
            print(f"  Fehler bei {source}: {e}")
            fehler += 1
    neue += fetch_zotero(ZOTERO_GROUP_ID, ZOTERO_API_KEY)
    print(f"\nGesamt: {neue} neu, {fehler} Fehler")
    return neue

# ==================================================
# CLASSIFY AGENT
# ==================================================

def classify_event(title, summary):
    prompt = f"""Du bist ein Analyst des Wicked AI Observatory.

Analysiere dieses Ereignis. Antworte NUR mit einem JSON-Objekt, kein anderer Text:

Titel: {title}
Zusammenfassung: {summary[:300]}

Verfügbare Faktoren: {', '.join(FACTOR_LIST)}

Besondere Hinweise:
- "Resource Extraction" betrifft Rohstoffabbau fuer KI-Hardware
- "Carbon Footprint AI" betrifft CO2-Emissionen durch KI
- "Intergenerational Equity" betrifft langfristige Verteilungsgerechtigkeit
- "Algorithmic Discrimination" betrifft direkte Benachteiligung durch KI

JSON-Format:
{{
  "ki_relevant": "ja|nein|indirekt",
  "ki_begruendung": "Ein Satz",
  "relevante_faktoren": ["max 2 Faktornamen"],
  "dimension": "Political|Technical|Economic|Legal|Ethical|Societal|Global|War|Peace|Environmental|Pedagogical|Epistemic",
  "signal_typ": "policy|research|incident|governance|technology",
  "wickedness_relevanz": "hoch|mittel|niedrig",
  "begruendung": "Ein Satz Analyse"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    start = raw.find('{')
    end = raw.rfind('}') + 1
    return json.loads(raw[start:end])

# ==================================================
# WRITE AGENT
# ==================================================

def write_event_to_graph(event_id, title, url, published, classification):
    with driver.session(database=NEO4J_DB) as session:
        session.run("""
            MERGE (e:Event {id: $id})
            SET e.title = $title,
                e.url = $url,
                e.published = $published,
                e.dimension = $dimension,
                e.signal_typ = $signal_typ,
                e.wickedness_relevanz = $wickedness_relevanz,
                e.begruendung = $begruendung,
                e.ki_relevant = $ki_relevant,
                e.written_by = 'classify_agent',
                e.review_status = 'pending',
                e.created_at = datetime()
        """, {
            "id": event_id, "title": title, "url": url,
            "published": published,
            "dimension": classification["dimension"],
            "signal_typ": classification["signal_typ"],
            "wickedness_relevanz": classification["wickedness_relevanz"],
            "begruendung": classification["begruendung"],
            "ki_relevant": classification["ki_relevant"]
        })
        for faktor in classification["relevante_faktoren"]:
            session.run("""
                MATCH (e:Event {id: $event_id})
                MATCH (f:Factor {name: $faktor})
                MERGE (e)-[:SIGNALS {
                    confidence: 0.70,
                    written_by: 'classify_agent',
                    review_status: 'pending'
                }]->(f)
            """, {"event_id": event_id, "faktor": faktor})

# ==================================================
# PROPOSAL AGENT
# ==================================================

def proposal_agent(faktor_name, aktuelle_events, aktueller_score):
    event_texte = "\n".join([
        f"- {e['titel']}: {e['begruendung']}"
        for e in aktuelle_events[:5]
    ])
    prompt = f"""Du bist der Proposal Agent des Wicked AI Observatory.

Faktor: {faktor_name}
Aktueller Wickedness-Score: {aktueller_score}

Aktuelle Ereignisse:
{event_texte}

Antworte NUR mit JSON:
{{
  "vorschlag": "erhoehen|beibehalten|senken",
  "neuer_score": {aktueller_score},
  "veraenderung": 0,
  "konfidenz": 0.0,
  "begruendung": "Ein klarer Satz warum",
  "schluessel_ereignis": "Das wichtigste Ereignis als Beleg"
}}

Regeln:
- Konfidenz zwischen 0.0 und 1.0
- Veraenderung maximal +/- 10 Punkte pro Zyklus
- Nur erhoehen wenn strukturelle Verschiebung, nicht nur Quantitaet
- Score niemals ueber 100 oder unter 0"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    start = raw.find('{')
    end = raw.rfind('}') + 1
    return json.loads(raw[start:end])

# ==================================================
# REVIEW DIGEST MIT VORSCHLAEGEN
# ==================================================

def review_digest_mit_vorschlaegen():
    print(f"\nREVIEW DIGEST MIT VORSCHLAEGEN — {datetime.now().strftime('%d.%m.%Y')}")
    print("=" * 60)
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            MATCH (e:Event)-[:SIGNALS]->(f:Factor)
            WHERE e.review_status = 'pending'
            WITH f, collect({
                titel: e.title,
                begruendung: e.begruendung,
                relevanz: e.wickedness_relevanz
            }) AS events, count(e) AS anzahl
            WHERE anzahl >= 2
            RETURN f.name AS faktor,
                   f.wickedness_score AS score,
                   f.dimension AS dimension,
                   events, anzahl
            ORDER BY anzahl DESC LIMIT 5
        """)
        vorschlaege = []
        for record in result:
            faktor = record["faktor"]
            score = record["score"]
            events = record["events"]
            anzahl = record["anzahl"]
            print(f"\n[{record['dimension']}] {faktor} (Score: {score})")
            print(f"  {anzahl} neue Ereignisse")
            try:
                vorschlag = proposal_agent(faktor, events, score)
                pfeil = "↑" if vorschlag["vorschlag"] == "erhoehen" else \
                        "↓" if vorschlag["vorschlag"] == "senken" else "→"
                print(f"\n  Vorschlag: {pfeil} Score: {score} → {vorschlag['neuer_score']} "
                      f"(Konfidenz: {int(vorschlag['konfidenz']*100)}%)")
                print(f"  Begründung: {vorschlag['begruendung']}")
                vorschlaege.append({"faktor": faktor, "alter_score": score, "vorschlag": vorschlag})
            except Exception as e:
                print(f"  Proposal-Fehler: {e}")

        print("\n" + "=" * 60)
        print("DEINE ENTSCHEIDUNGEN:")
        print("=" * 60)
        for v in vorschlaege:
            if v["vorschlag"]["vorschlag"] != "beibehalten":
                print(f"""
# {v['faktor']}: {v['alter_score']} → {v['vorschlag']['neuer_score']}
MATCH (f:Factor {{name: "{v['faktor']}"}})
SET f.wickedness_score = {v['vorschlag']['neuer_score']},
    f.score_begruendung = "{v['vorschlag']['begruendung']}",
    f.vorschlag_angenommen = true,
    f.last_reviewed = date()
RETURN f.name, f.wickedness_score;
""")
        session.run("""
            MATCH (e:Event)
            WHERE e.review_status = 'pending'
            SET e.review_status = 'reviewed'
        """)

# ==================================================
# WOCHENBERICHT
# ==================================================

def generate_weekly_report():
    report_date = datetime.now().strftime('%d.%m.%Y')
    with driver.session(database=NEO4J_DB) as session:
        top_faktoren = list(session.run("""
            MATCH (f:Factor)
            RETURN f.name AS name, f.dimension AS dimension,
                   f.wickedness_score AS score
            ORDER BY score DESC LIMIT 10
        """))
        neue_events = list(session.run("""
            MATCH (e:Event)-[:SIGNALS]->(f:Factor)
            WHERE e.created_at > datetime() - duration('P7D')
            RETURN e.title AS titel, e.url AS url,
                   f.name AS faktor, e.ki_relevant AS relevant,
                   e.begruendung AS begruendung
            ORDER BY e.created_at DESC LIMIT 15
        """))
        score_changes = list(session.run("""
            MATCH (f:Factor)
            WHERE f.last_reviewed = date()
            RETURN f.name AS name, f.wickedness_score AS score,
                   f.score_begruendung AS begruendung
            ORDER BY score DESC
        """))
        schweigen = list(session.run("""
            MATCH (f:Factor)
            WHERE NOT (f)<-[:SIGNALS]-(:Event)
            AND f.wickedness_score > 65
            RETURN f.name AS name, f.dimension AS dimension,
                   f.wickedness_score AS score
            ORDER BY score DESC
        """))

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8">
<title>WAO Wochenbericht {report_date}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;color:#333;line-height:1.6}}
h1{{color:#534AB7;border-bottom:3px solid #534AB7;padding-bottom:10px}}
h2{{color:#534AB7;margin-top:40px}}
table{{width:100%;border-collapse:collapse;margin:16px 0}}
th{{background:#534AB7;color:white;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #eee}}
tr:hover{{background:#f9f9f9}}
.score-high{{color:#E24B4A;font-weight:bold}}
.score-mid{{color:#BA7517;font-weight:bold}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px}}
.badge-ja{{background:#E1F5EE;color:#085041}}
.badge-indirekt{{background:#FAEEDA;color:#633806}}
.schweigen{{background:#FCEBEB;padding:10px 14px;border-radius:6px;margin:6px 0}}
.change{{background:#EEEDFE;padding:10px 14px;border-radius:6px;margin:6px 0}}
a{{color:#534AB7}}
.footer{{margin-top:60px;color:#999;font-size:12px;border-top:1px solid #eee;padding-top:16px}}
</style></head><body>
<h1>Wicked AI Observatory</h1>
<h3>Wochenbericht — {report_date}</h3>
<h2>Top 10 Faktoren nach Wickedness-Score</h2>
<table><tr><th>Faktor</th><th>Dimension</th><th>Score</th></tr>"""

    for r in top_faktoren:
        score = r["score"]
        css = "score-high" if score >= 80 else "score-mid" if score >= 65 else ""
        html += f"<tr><td>{r['name']}</td><td>{r['dimension']}</td><td class='{css}'>{score}</td></tr>"

    html += "</table><h2>Score-Änderungen diese Woche</h2>"
    if score_changes:
        for r in score_changes:
            html += f"<div class='change'><strong>{r['name']}</strong> → Score: {r['score']}<br><small>{r['begruendung']}</small></div>"
    else:
        html += "<p>Keine Score-Änderungen diese Woche.</p>"

    html += "<h2>Neue Ereignisse (letzte 7 Tage)</h2><table><tr><th>Titel</th><th>Faktor</th><th>Relevanz</th></tr>"
    for r in neue_events:
        badge = "badge-ja" if r["relevant"] == "ja" else "badge-indirekt"
        html += f"<tr><td><a href='{r['url']}' target='_blank'>{r['titel'][:80]}</a><br><small style='color:#666'>{(r['begruendung'] or '')[:120]}</small></td><td>{r['faktor']}</td><td><span class='badge {badge}'>{r['relevant']}</span></td></tr>"

    html += "</table><h2>Schweige-Signale</h2>"
    for r in schweigen:
        html += f"<div class='schweigen'><strong>{r['name']}</strong> [{r['dimension']}] — Score: {r['score']}<br><small>Kein Ereignis erfasst — Lücke im Monitoring.</small></div>"

    html += f"<div class='footer'>Wicked AI Observatory · {report_date}</div></body></html>"

    filename = f"wao_bericht_{datetime.now().strftime('%Y_%m_%d')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Bericht gespeichert: {filename}")
    return filename

# ==================================================
# GRAPH VISUALISIERUNG
# ==================================================

FARBEN = {
    "Political": "#BA7517", "Technical": "#1D9E75",
    "Economic": "#639922", "Legal": "#378ADD",
    "Ethical": "#7F77DD", "Societal": "#D85A30",
    "Global": "#D4537E", "War": "#E24B4A",
    "Peace": "#5DCAA5", "Environmental": "#97C459",
    "Pedagogical": "#AFA9EC", "Epistemic": "#B4B2A9"
}

KANTEN_FARBEN = {
    "AMPLIFIES": "#AAAAAA", "CONFLICTS_WITH": "#E24B4A",
    "POSITIONS_ON": "#FF8C00", "SIGNALS": "#B0C4DE"
}

LEGENDE = """<div style="position:absolute;top:16px;right:16px;background:white;
border:1px solid #ddd;border-radius:8px;padding:14px 18px;font-family:Arial,sans-serif;
font-size:12px;z-index:9999;box-shadow:0 2px 8px rgba(0,0,0,0.1);min-width:200px;">
<div style="font-weight:bold;margin-bottom:10px;font-size:13px;">Wicked AI Observatory</div>
<div style="font-weight:bold;color:#666;margin-bottom:6px;font-size:11px;">Dimensionen</div>
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
<div style="font-weight:bold;color:#666;margin-bottom:6px;font-size:11px;">Kanten</div>
<div style="display:grid;grid-template-columns:24px 1fr;gap:4px 8px;align-items:center;">
<div style="height:2px;background:#AAAAAA;"></div><span>AMPLIFIES</span>
<div style="height:2px;background:#E24B4A;"></div><span>CONFLICTS_WITH</span>
<div style="height:2px;background:#FF8C00;"></div><span>POSITIONS_ON</span>
{signals_zeile}
</div>
<div style="margin-top:12px;color:#999;font-size:10px;border-top:1px solid #eee;padding-top:8px;">
Stand: {datum} · WAO v1.0 · {titel}
</div></div>"""

PHYSICS_STRUKTUR = '{"physics":{"forceAtlas2Based":{"gravitationalConstant":-180,"springLength":220,"springConstant":0.04,"damping":0.9},"solver":"forceAtlas2Based","minVelocity":0.75,"stabilization":{"iterations":200}},"nodes":{"font":{"size":12},"borderWidth":1.5},"edges":{"smooth":{"type":"continuous"},"arrows":{"to":{"enabled":true,"scaleFactor":0.5}}},"interaction":{"hover":true,"tooltipDelay":100}}'
PHYSICS_VOLL = '{"physics":{"forceAtlas2Based":{"gravitationalConstant":-120,"springLength":160,"springConstant":0.03,"damping":0.9},"solver":"forceAtlas2Based","minVelocity":0.75,"stabilization":{"iterations":300}},"nodes":{"font":{"size":10},"borderWidth":1.5},"edges":{"smooth":{"type":"continuous"},"arrows":{"to":{"enabled":true,"scaleFactor":0.4}}},"interaction":{"hover":true,"tooltipDelay":100}}'

def add_faktoren(net, session):
    for r in session.run("MATCH (f:Factor) RETURN f.name AS name, f.dimension AS dimension, f.wickedness_score AS score"):
        farbe = FARBEN.get(r["dimension"], "#888780")
        net.add_node(r["name"], label=r["name"], color=farbe, size=r["score"]/4, title=f"{r['dimension']} | Score: {r['score']}")

def add_stakeholder(net, session):
    for r in session.run("MATCH (s:Stakeholder) RETURN s.name AS name, s.class AS klasse, s.influence AS influence"):
        net.add_node(r["name"], label=r["name"], color="#FF8C00", size=r["influence"]*25, shape="diamond", title=f"Stakeholder: {r['klasse']}")

def add_events(net, session):
    for r in session.run("MATCH (e:Event) RETURN e.title AS title, e.dimension AS dimension"):
        key = r["title"][:40]
        net.add_node(key, label=r["title"][:30]+"...", color="#B0C4DE", size=8, shape="dot", title=r["title"])

def add_kanten(net, session, mit_events=False, nur_faktoren=False):
    if nur_faktoren:
        query = "MATCH (a:Factor)-[r]->(b:Factor) RETURN a.name AS von, b.name AS zu, type(r) AS typ, r.strength AS staerke"
    elif mit_events:
        query = """MATCH (a)-[r]->(b) RETURN
            CASE WHEN a:Factor THEN a.name WHEN a:Stakeholder THEN a.name ELSE a.title END AS von,
            CASE WHEN b:Factor THEN b.name WHEN b:Stakeholder THEN b.name ELSE b.title END AS zu,
            type(r) AS typ, r.strength AS staerke"""
    else:
        query = """MATCH (a)-[r]->(b)
            WHERE (a:Factor OR a:Stakeholder) AND (b:Factor OR b:Stakeholder)
            RETURN a.name AS von, b.name AS zu, type(r) AS typ, r.strength AS staerke"""
    for r in session.run(query):
        farbe = KANTEN_FARBEN.get(r["typ"], "#AAAAAA")
        net.add_edge(str(r["von"])[:40], str(r["zu"])[:40], color=farbe, width=(r["staerke"] or 0.5)*2.5, title=r["typ"])

def speichere_mit_legende(net, filename, titel, mit_events=False):
    net.save_graph("_tmp.html")
    with open("_tmp.html", "r", encoding="utf-8") as f:
        html = f.read()
    datum = datetime.now().strftime('%Y_%m_%d')
    signals_zeile = '<div style="height:2px;background:#B0C4DE;"></div><span>SIGNALS</span>' if mit_events else ""
    legende = LEGENDE.format(signals_zeile=signals_zeile, datum=datum, titel=titel)
    html = html.replace("</body>", legende + "</body>")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Gespeichert: {filename}")

def generate_all_graphs():
    datum = datetime.now().strftime('%Y_%m_%d')
    with driver.session(database=NEO4J_DB) as session:
        net1 = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
        add_faktoren(net1, session)
        add_kanten(net1, session, nur_faktoren=True)
        net1.set_options(PHYSICS_STRUKTUR)
        speichere_mit_legende(net1, f"wao_faktoren_{datum}.html", "Nur Faktoren")
    with driver.session(database=NEO4J_DB) as session:
        net2 = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
        add_faktoren(net2, session)
        add_stakeholder(net2, session)
        add_kanten(net2, session, mit_events=False)
        net2.set_options(PHYSICS_STRUKTUR)
        speichere_mit_legende(net2, f"wao_struktur_{datum}.html", "Faktoren + Stakeholder")
    with driver.session(database=NEO4J_DB) as session:
        net3 = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
        add_faktoren(net3, session)
        add_stakeholder(net3, session)
        add_events(net3, session)
        add_kanten(net3, session, mit_events=True)
        net3.set_options(PHYSICS_VOLL)
        speichere_mit_legende(net3, f"wao_vollgraph_{datum}.html", "Vollgraph", mit_events=True)
    subprocess.run(["open", f"wao_faktoren_{datum}.html"])
    subprocess.run(["open", f"wao_struktur_{datum}.html"])
    subprocess.run(["open", f"wao_vollgraph_{datum}.html"])
    print("\nAlle drei Graphen geöffnet.")

# ==================================================
# WÖCHENTLICHER UPDATE
# ==================================================

def wao_weekly_update():
    print(f"WAO Update — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 50)

    print("\n1. Monitor Agent — lade neue Ereignisse...")
    neue_events = fetch_events()
    print(f"   {neue_events} neue Ereignisse gefunden")

    print("\n2. Classify + Write Agent — verarbeite Ereignisse...")
    cursor.execute("SELECT id, title, summary, url, published FROM events WHERE status = 'pending'")
    pending = cursor.fetchall()
    geschrieben = 0
    gefiltert = 0
    fehler = 0
    for event_id, title, summary, url, published in pending:
        try:
            classification = classify_event(title, summary)
            if classification["ki_relevant"] == "nein":
                cursor.execute("UPDATE events SET status = 'filtered' WHERE id = ?", (event_id,))
                conn.commit()
                gefiltert += 1
                continue
            write_event_to_graph(event_id, title, url, published, classification)
            cursor.execute("UPDATE events SET status = 'processed' WHERE id = ?", (event_id,))
            conn.commit()
            geschrieben += 1
            print(f"   [{classification['ki_relevant']}] {title[:50]}")
            print(f"   → {classification['relevante_faktoren']}")
        except Exception as e:
            fehler += 1
            print(f"   Fehler: {title[:40]} — {e}")

    print(f"\n   Geschrieben: {geschrieben} | Gefiltert: {gefiltert} | Fehler: {fehler}")

    print("\n3. Graph-Status:")
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("MATCH (n) RETURN labels(n)[0] AS typ, count(n) AS anzahl")
        for record in result:
            print(f"   {record['typ']}: {record['anzahl']}")

    print("\n4. Meistgenannte Faktoren:")
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            MATCH (e:Event)-[:SIGNALS]->(f:Factor)
            WHERE e.created_at > datetime() - duration('P7D')
            RETURN f.name AS faktor, count(e) AS signale
            ORDER BY signale DESC LIMIT 5
        """)
        for record in result:
            print(f"   {record['signale']}x {record['faktor']}")

    print("\n5. Wochenbericht generieren...")
    filename = generate_weekly_report()
    print(f"   Bericht: {filename}")

    review_digest_mit_vorschlaegen()

# ==================================================
# BEREIT
# ==================================================
print("WAO Funktionen geladen.")
print("Neo4j Verbindungstest...")
with driver.session(database=NEO4J_DB) as session:
    result = session.run("MATCH (n) RETURN count(n) AS anzahl")
    print(f"Graph: {result.single()['anzahl']} Knoten")
print("\nBereit. Starte mit: wao_weekly_update()")
