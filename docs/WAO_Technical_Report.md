# Wicked AI Observatory (WAO)

**A Multi-Agent System for Dynamic Mapping of Wicked Problems in Artificial Intelligence — Architecture and Setup**

*Technical Report · Version 0.7 · April 2026*

**Peter Holubar**
BOKU University Vienna
`peter.holubar@boku.ac.at`
ORCID: https://orcid.org/0000-0003-1613-6466

**Keywords:** wicked problems, AI governance, multi-agent systems, knowledge graphs, Neo4j, human-in-the-loop, LLM classification, reproducibility, research software

---

## Abstract

This technical report documents the architecture and setup of the **Wicked AI Observatory (WAO)**, a research prototype that continuously monitors AI governance developments, classifies them against a twenty-nine-factor taxonomy spanning thirteen dimensions using large language models, and maintains a Neo4j knowledge graph with explicit provenance and uncertainty metadata. The system is motivated by the observation — grounded in Rittel and Webber's (1973) wicked-problem theory — that AI governance is a domain in which every intervention reshapes the problem itself, and that the existing instruments available to policymakers, journalists, researchers, and informed citizens are not designed for such problems.

The report is narrowly scoped to what is needed for independent inspection and replication: a brief background on the wicked-problem framing, an overview of the seven-agent architecture, and a complete setup procedure covering prerequisites, installation, configuration of the agents and monitoring sources, and verification. A working prototype was tested across five monitoring cycles with 172 events from the EU AI regulation domain; the empirical findings and validation framework from those cycles are treated in a separate publication currently in preparation. The source code, initial factor registry, and configuration templates referenced here are available in the companion GitHub repository, for which this report serves as the primary documentation.

---

## 1. Background: Why a "Wicked AI" Observatory?

AI governance is not a collection of separate problems waiting for separate technical fixes. It is an interlocking set of challenges in which every intervention reshapes the problem itself. When the European Union enacted the AI Act, it simultaneously concentrated the market around large firms able to absorb compliance costs, created geopolitical asymmetries with non-EU systems, and opened new avenues for industry lobbying over implementation. Regulating one dimension generated new problems in at least three others. This is not a failure of regulation; it is the defining feature of the domain.

In planning theory, this structure has a precise name. Rittel and Webber (1973) introduced the concept of *wicked problems* to describe challenges that resist definitive formulation, have no clear stopping rule, and admit no solutions that are unambiguously right or wrong. Every criterion applies to AI governance: stakeholders disagree on what the problem even is, there is no threshold at which AI is "safe enough," and every intervention — from the AI Act to voluntary industry commitments — generates new, unforeseen challenges.

The instruments available to those who must navigate this landscape — policymakers, journalists, researchers, informed citizens — are not designed for such problems. Policy briefs treat one dimension at a time. Academic reviews cover specific domains. Regulatory impact assessments operate within fixed institutional mandates. None continuously track how AI challenges interact across dimensions, and none make uncertainty explicit instead of hiding it behind confident recommendations.

The **Wicked AI Observatory (WAO)** is an attempt to build such an instrument. It does not claim to solve wicked problems — by definition, they cannot be solved. It aims instead to make their structure visible: which dimensions of AI governance are most entangled, where structural shifts are occurring, which factors are becoming more wicked over time, and where monitoring gaps leave critical developments unseen.

Concretely, WAO:

- continuously monitors developments from thirteen curated sources (RSS feeds and an analyst-curated Zotero literature library);
- classifies events using large language models against a twenty-nine-factor taxonomy spanning thirteen dimensions (algorithmic fairness, autonomous weapons, labor displacement, regulatory capture, and others);
- maps classified events into a Neo4j knowledge graph that preserves provenance and uncertainty metadata;
- generates structured score-adjustment proposals that a human analyst accepts, modifies, or rejects with documented reasoning;
- produces outputs in which an honest "we don't know" is treated as more valuable than a false appearance of certainty.

A working prototype tested across five monitoring cycles with 172 events from the EU AI regulation domain produced a striking result: the highest-scoring wicked factor was not an ethical concern or technical risk, but *Compressed Kill Chains* (96/100) — the acceleration of military decision cycles through AI integration to intervals that preclude meaningful human review. *Regulatory Capture* (91/100) and *Accountability Gaps* (90/100) followed. *Accountability Gaps*, initially ranked ninth, emerged as the most frequently signaled factor across all sources — a structural pattern that no single-domain analysis would have revealed.

### 1.1 Scope of this report

This report is a **setup and architecture document**, not a theoretical or empirical treatment. Its purpose is to give other researchers enough to inspect, install, and run WAO independently, and to understand the design decisions at the level needed for meaningful critique. The wicked-problem theoretical foundations, the validation framework, the detailed empirical findings from the five monitoring cycles, and the full discussion of limitations are the subject of a separate, longer manuscript currently in preparation; that manuscript will be published as a distinct Zenodo record and linked to this one via "related identifiers" (`isSupplementedBy` / `isDocumentedBy`).

The scoping choice is itself an epistemic one. The author considers it inappropriate to publish the longer theoretical argument until it has been worked through carefully enough to hold up to critique. Making the system itself — the code, the factor registry, the configuration, and this documentation — available now allows the technical and empirical substrate to be inspected and challenged while the theoretical treatment matures.

---

## 2. System Overview

The WAO consists of seven specialized agents coordinated through a Neo4j knowledge graph, a SQLite staging database, and a Streamlit-based web interface. The weekly monitoring cycle runs the agents in sequence: the Monitor Agent ingests events, the Taxonomy Agent classifies them, the Wickedness Analysis Agent scores them, the Evaluation Agent gates knowledge graph writes, the Proposal Agent generates score-adjustment recommendations, the human analyst reviews them, and the Explanation Agent makes outputs accessible to non-specialist stakeholders.

### 2.1 Architecture at a glance

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Web Interface                      │
│         (dashboard · weekly update · review digest · export)     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │                Agent Orchestration           │
        │     (Jupyter notebook → standalone script)   │
        └──┬────────┬────────┬────────┬────────┬──────┘
           │        │        │        │        │
     ┌─────▼──┐ ┌───▼────┐ ┌─▼─────┐ ┌▼─────┐ ┌▼──────────┐
     │Monitor │ │Classify│ │Wicked-│ │Eval- │ │ Proposal  │
     │ Agent  │ │ Agent  │ │ness   │ │uation│ │  Agent    │
     │        │ │        │ │Agent  │ │Agent │ │           │
     └────┬───┘ └───┬────┘ └──┬────┘ └──┬───┘ └─────┬─────┘
          │         │         │         │           │
          ▼         ▼         ▼         ▼           ▼
     ┌─────────────────┐          ┌──────────────────────┐
     │ SQLite staging  │ ───────► │  Neo4j knowledge     │
     │ (events buffer) │          │  graph (provenance,  │
     └─────────────────┘          │  uncertainty, edges) │
                                  └──────────┬───────────┘
                                             │
                                       ┌─────▼─────┐
                                       │Explanation│
                                       │  Agent    │
                                       └───────────┘
```

### 2.2 The seven agents

| Agent | Purpose |
|---|---|
| **Monitor Agent** | Ingests events from 13 RSS feeds and the Zotero literature library; deduplicates; writes to SQLite staging. |
| **Taxonomy / Classify Agent** | Classifies each event against the 29-factor registry. Assigns dimension, signal type, AI-relevance (`ja`/`indirekt`/`nein`), and up to two factors. Confidence < 0.65 triggers human review. |
| **Wickedness Analysis Agent** | Produces a 14-parameter wickedness vector for each classified event (stakeholder plurality, normative conflict, causal complexity, uncertainty, governance ambiguity, temporal instability, feedback intensity, and others). |
| **Evaluation Agent** | Quality gate for graph writes. Weighs source credibility, flags contested claims, routes events to `auto-accepted`, `pending review`, or `human-confirmed`. |
| **Proposal Agent** | Generates structured score-adjustment proposals (direction, proposed score, confidence, one-sentence justification, key supporting event) for analyst review. |
| **Human Analyst (HITL)** | Accepts, modifies, or rejects proposals with documented reasoning. Not an agent but a first-class role in the system. |
| **Explanation Agent** | Translates graph structure and wickedness scores into stakeholder-specific, uncertainty-foregrounding narratives. Answers natural-language queries. |

### 2.3 Taxonomy at a glance

The factor registry spans thirteen dimensions grouped into three clusters:

- **Institutional:** Political, Technical, Economic, Legal
- **Societal:** Ethical, Societal, Pedagogical, Epistemic
- **Planetary:** Global, Environmental, Peace, War

Each of the 29 factors carries an initial wickedness score (42–96), a primary literature source, and relationships (`AMPLIFIES`, `CONFLICTS_WITH`) to other factors. The full table is provided in `data/factor_registry.csv` in the companion repository.

---

## 3. Prerequisites

Before installation, ensure the following are available on the target machine.

### 3.1 Hardware

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB (Neo4j + LLM API latency buffers) |
| Disk | 20 GB free | 50 GB free (graph growth + logs) |
| Network | Stable internet | Stable internet; outbound access to `api.anthropic.com`, RSS hosts, Zotero API |

### 3.2 Software

- **Operating system:** Linux (Ubuntu 22.04+ recommended), macOS 13+, or Windows 11 with WSL2.
- **Python:** 3.11 or 3.12 (via Anaconda/Miniconda).
- **Neo4j:** Community Edition 2026.02 or later.
- **Git:** 2.30+.
- **Web browser:** Chrome, Firefox, or Edge for the Streamlit interface.

### 3.3 Accounts and credentials

- **Anthropic API key** (for Claude Sonnet, used by the Classify, Wickedness Analysis, Proposal, and Explanation agents).
- **Zotero account** with a group library and an API key (for analyst-curated literature ingestion).
- Optional: institutional email for RSS feeds that require registration.

> **Security note.** API keys are read from a local `.env` file and must never be committed to the repository. The `.gitignore` in the companion repository already excludes `.env`, `*.key`, and the `data/` directory.

---

## 4. Installation

The installation is described as six stages: environment, database, environment variables, sources, agents, and verification. Each stage is independent enough that a failure in one does not require repeating the others.

### 4.1 Stage 1 — Clone the repository and create the Python environment

```bash
# Clone
git clone https://github.com/<your-org>/wicked-ai-observatory.git
cd wicked-ai-observatory

# Create a conda environment
conda create -n wao python=3.12 -y
conda activate wao

# Install dependencies
pip install -r requirements.txt
```

The `requirements.txt` pins the following core packages:

```
anthropic>=0.40.0
neo4j>=5.26.0
streamlit>=1.40.0
feedparser>=6.0.11
pyzotero>=1.5.20
python-dotenv>=1.0.1
pandas>=2.2.0
networkx>=3.3
pydantic>=2.9.0
jupyterlab>=4.2.0
```

### 4.2 Stage 2 — Install and configure Neo4j

Install Neo4j Community Edition 2026.02 following the official instructions for your operating system. After installation:

```bash
# Set an admin password during first launch; record it for the .env file.
neo4j start

# Verify the server is running
curl -u neo4j:<password> http://localhost:7474/db/data/
```

Once the server is up, load the graph schema:

```bash
# From the repo root
python scripts/init_graph.py
```

This script creates the following constraints and indexes:

- Uniqueness constraint on `Factor.id`
- Uniqueness constraint on `Event.id`
- Uniqueness constraint on `Source.id`
- Full-text index on `Event.title` and `Event.summary`
- Range index on `Event.ingested_at`

It then loads the initial factor registry (`data/factor_registry.csv`) as `Factor` nodes with their initial wickedness scores, dimensions, clusters, and primary sources, and creates the initial `AMPLIFIES` and `CONFLICTS_WITH` edges from `data/initial_relationships.csv`.

### 4.3 Stage 3 — Configure environment variables

Copy the template and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your preferred editor
```

The `.env` file contains:

```ini
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=neo4j

# Anthropic API
ANTHROPIC_API_KEY=<your-key>
ANTHROPIC_MODEL=claude-sonnet-4-5

# Zotero
ZOTERO_API_KEY=<your-key>
ZOTERO_LIBRARY_ID=<your-group-id>
ZOTERO_LIBRARY_TYPE=group

# WAO runtime
WAO_DATA_DIR=./data
WAO_LOG_LEVEL=INFO
WAO_CONFIDENCE_THRESHOLD=0.65
WAO_REVIEW_BATCH_SIZE=20
```

### 4.4 Stage 4 — Configure RSS feeds and the Zotero library

The monitoring infrastructure is defined in `config/sources.yaml`. The default configuration mirrors the prototype used in the preprint:

```yaml
feeds:
  - id: ai_now
    name: AI Now Institute
    url: https://ainowinstitute.org/feed
    weight: 0.9
    dimensions: [ethical, political, war]
  - id: corp_europe
    name: Corporate Europe Observatory
    url: https://corporateeurope.org/en/rss.xml
    weight: 0.85
    dimensions: [political, economic]
  - id: sipri
    name: SIPRI
    url: https://www.sipri.org/rss.xml
    weight: 0.9
    dimensions: [war, peace]
  # ... additional feeds, see config/sources.yaml for the full list

zotero:
  collection_key: <your-collection-key>
  sync_interval_hours: 168    # weekly
```

To add or remove a feed, edit `sources.yaml` and restart the Streamlit app; no schema changes are required.

### 4.5 Stage 5 — Agent configuration

Agent-specific behavior is governed by `config/agents.yaml`. The defaults reproduce the prototype configuration used for the five monitoring cycles reported in the forthcoming empirical paper.

```yaml
monitor_agent:
  dedup_window_days: 30
  max_events_per_cycle: 200

classify_agent:
  model: claude-sonnet-4-5
  temperature: 0.2
  max_tokens: 1024
  confidence_threshold: 0.65
  ai_relevance_labels: [ja, indirekt, nein]
  max_factors_per_event: 2

wickedness_agent:
  model: claude-sonnet-4-5
  temperature: 0.1
  vector_parameters:
    - stakeholder_plurality
    - normative_conflict
    - causal_complexity
    - uncertainty
    - governance_ambiguity
    - temporal_instability
    - feedback_intensity
    - political_contestation
    - economic_concentration
    - irreversibility
    - distributional_asymmetry
    - peace_impact_potential
    - conflict_escalation_potential
    - documentability

evaluation_agent:
  auto_accept_confidence: 0.85
  pending_review_confidence: 0.65
  source_weight_floor: 0.3

proposal_agent:
  model: claude-sonnet-4-5
  temperature: 0.3
  min_events_for_proposal: 5
  score_change_cap: 10

explanation_agent:
  model: claude-sonnet-4-5
  temperature: 0.4
  stakeholder_modes: [journalist, researcher, policymaker, citizen]
```

Each agent's prompt templates live in `prompts/`, one Jinja2 template per agent. Modifying a prompt does not require code changes; the prompts are reloaded at the start of each weekly cycle.

### 4.6 Stage 6 — Verify the installation

Run the verification suite:

```bash
python scripts/verify_install.py
```

The script performs the following checks in order and prints a pass/fail summary:

1. Python version and required packages.
2. Neo4j connection and schema presence.
3. Anthropic API reachability and model availability.
4. Zotero API reachability and library access.
5. RSS feed reachability for each configured feed.
6. Initial factor registry loaded (expects 29 factors).
7. Streamlit app imports cleanly.

Any failure is reported with the offending configuration key and suggested remediation.

---

## 5. Running the System

### 5.1 Launching the Streamlit interface

```bash
streamlit run app/main.py
```

The interface opens at `http://localhost:8501` and provides:

- a dashboard with real-time graph statistics (factor count, event count, last cycle timestamp);
- a one-click **Run Weekly Update** button, which triggers the Monitor, Classify, and Write agents sequentially;
- a **Review Digest** pane where the analyst processes Proposal Agent recommendations (accept / modify / reject, each with a mandatory rationale field);
- a source weight management panel;
- export functions for Cypher dumps, CSV snapshots of the factor registry, and JSON exports of individual events with full provenance.

### 5.2 Running a cycle from the command line

For headless or scheduled operation:

```bash
python scripts/run_cycle.py --cycle-name "2026-W16" --mode full
```

Modes are `full` (all agents), `ingest-only` (Monitor + Classify + staging), and `review-only` (Proposal Agent on already-ingested events). Scheduled runs should normally use `ingest-only`, leaving the review step for an interactive session.

### 5.3 Exporting and sharing graph snapshots

```bash
# Cypher dump (re-importable into another Neo4j instance)
python scripts/export_graph.py --format cypher --out exports/wao_$(date +%Y%m%d).cypher

# Tabular snapshot of factors and scores
python scripts/export_graph.py --format csv --out exports/factors_$(date +%Y%m%d).csv
```

Snapshots include provenance fields (source, ingested_at, confidence, reviewer, rationale) so that downstream analysis can reconstruct how a given score was reached.

---

## 6. Repository Layout

```
wicked-ai-observatory/
├── README.md                  # pointer to this report
├── LICENSE
├── requirements.txt
├── .env.example
├── .gitignore
├── app/
│   └── main.py                # Streamlit entry point
├── agents/
│   ├── monitor.py
│   ├── classify.py
│   ├── wickedness.py
│   ├── evaluation.py
│   ├── proposal.py
│   └── explanation.py
├── config/
│   ├── sources.yaml           # RSS feeds and Zotero
│   └── agents.yaml            # agent parameters
├── prompts/
│   ├── classify.j2
│   ├── wickedness.j2
│   ├── proposal.j2
│   └── explanation.j2
├── data/
│   ├── factor_registry.csv    # 29 factors with initial scores
│   └── initial_relationships.csv
├── scripts/
│   ├── init_graph.py
│   ├── verify_install.py
│   ├── run_cycle.py
│   └── export_graph.py
├── notebooks/
│   └── weekly_update.ipynb    # legacy workflow, kept for reference
└── docs/
    ├── taxonomy.md
    ├── validation.md
    └── governance.md
```

---

## 7. Known Limitations of This Release

In the spirit of the system's own epistemological commitments, the following limitations of Version 0.7 are explicitly flagged. A fuller treatment will appear in the accompanying empirical manuscript.

- **Single-analyst bottleneck.** All factor-selection, initial-scoring, and review decisions in this release were made by one analyst. A diverse curatorial core group is a planned governance addition, not a current feature.
- **Domain asymmetry.** The factor registry was calibrated on EU AI regulation. US executive governance, China's algorithmic regulation, and Global South concerns are underrepresented.
- **Source geography.** Most RSS feeds are European or English-language. Global South civil society, non-English regulatory discourse, and military doctrine literature are underrepresented.
- **Initial score fragility.** Initial wickedness scores were assigned by expert judgment and are marked with lower confidence (0.60–0.75) than human-confirmed adjustments (0.85–0.95). They are informed estimates, not measurements.
- **AI-relevance filter calibration.** A systematic comparison of Classify Agent judgments against human expert judgments has not yet been performed. Roughly 60% of ingested events were classified as directly or indirectly AI-relevant in the prototype; the precision of this filter remains to be measured.
- **Scenario linearity.** The scenario sandbox projects score changes linearly; this contradicts the wicked-problem structure the system is designed to illuminate. An agent-based replacement is on the roadmap.
- **Measurement tension.** Assigning numeric scores to wicked problems is in tension with the theoretical claim that wicked problems resist measurement. The system treats scores as structured, revisable estimates with explicit uncertainty, but this tension is not resolved; it is made visible.

---

## 8. Related Work

A longer manuscript treating the theoretical foundations of the wicked-problem framing applied to AI governance, the four-level validation framework for domains without a gold standard, and the detailed empirical results from five monitoring cycles is in preparation. When published, it will be deposited as a separate Zenodo record and linked to this one via the relation `isSupplementedBy`; this report will then carry a reciprocal `isDocumentedBy` reference.

Technically, WAO builds on recent work combining LLMs with temporal knowledge graphs — notably Sampath et al. (2025) on agentic reasoning for social-event extrapolation and Rawal et al. (2026) on LLM-assisted causal knowledge-graph generation for policy analysis. WAO shares this architecture but diverges epistemologically: rather than optimizing for predictive accuracy, it treats uncertainty as a first-class output.

---

## 9. References

### 9.1 Scientific literature

European Parliament. (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act). *Official Journal of the European Union*, L 2024/1689.

Rawal, A., Johnson, K., Martinez, R., & Mitchell, C. (2026). Large language model (LLM) assisted causal knowledge graph generation framework for survey data. *Journal of Engineering Design*.

Rittel, H. W. J., & Webber, M. M. (1973). Dilemmas in a general theory of planning. *Policy Sciences*, *4*(2), 155–169.

Sampath, A. N., Thakur, A., & Krishnan, S. (2025). Agentic reasoning for social event extrapolation: Integrating knowledge graphs and language models. *IEEE Access*.

### 9.2 Software and platforms

Anthropic. (2026). *Claude (Sonnet 4.5) [Large language model]*. https://www.anthropic.com/claude

Neo4j, Inc. (2026). *Neo4j Community Edition (Version 2026.02) [Graph database management system]*. https://neo4j.com

Snowflake, Inc. (2026). *Streamlit (Version 1.40) [Python web application framework]*. https://streamlit.io

Zotero. (2026). *Zotero (Version 7) [Reference management software]*. Corporation for Digital Scholarship. https://www.zotero.org

---

## 10. How to Cite

Please cite this technical report using the Zenodo DOI assigned to this record.

```
Holubar, P. (2026). Wicked AI Observatory: A Multi-Agent System for
Dynamic Mapping of Wicked Problems in Artificial Intelligence —
Architecture and Setup. Technical Report, Version 0.7.
BOKU University Vienna. Zenodo. (https://doi.org/10.5281/zenodo.19627548)>
```

BibTeX:

```bibtex
@techreport{holubar2026wao,
  author       = {Holubar, Peter},
  title        = {Wicked {AI} Observatory: A Multi-Agent System for
                  Dynamic Mapping of Wicked Problems in Artificial
                  Intelligence --- Architecture and Setup},
  institution  = {BOKU University Vienna},
  type         = {Technical Report},
  number       = {Version 0.7},
  year         = {2026},
  month        = {April},
  doi          = {<10.5281/zenodo.19627548>},
  url          = {(https://doi.org/10.5281/zenodo.19627548)>}
}
```

---

## 11. License

The code in the companion repository is released under the **MIT License**. The factor registry, prompt templates, and this documentation are released under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.

---

## 12. Data and Code Availability

- **Source code and configuration:** https://github.com/<your-org>/wicked-ai-observatory
- **Project website:** https://wicked-ai-observatory.org (see Section 13)
- **Initial factor registry and relationship data:** `data/factor_registry.csv` and `data/initial_relationships.csv` in the repository above.
- **Archived snapshot:** the repository state corresponding to Version 0.7 is archived with this Zenodo record.

---

## 13. Project Website

A project website is maintained at **https://wicked-ai-observatory.org** as a stable, citation-friendly entry point for non-specialist readers. It links to this Zenodo record, the companion GitHub repository, and contact information, and embeds an interactive visualization of the current knowledge graph (29 factors, their dimensions, and the `AMPLIFIES` / `CONFLICTS_WITH` relationships between them). The website is intended to make the system's structure explorable for audiences who will not install the prototype themselves — journalists, policymakers, educators, and informed citizens. Its content is regenerated from the same factor registry and graph export scripts described in Sections 4 and 5, so the visualization remains synchronized with the published data release.

---

## 14. Contributing

Contributions are welcome, particularly from researchers whose disciplinary, geographic, or institutional perspectives are underrepresented in the current system. See `docs/governance.md` for the planned curatorial governance structure and `CONTRIBUTING.md` for the technical contribution workflow.

---

## 15. Declaration of Generative AI Use

This technical report was drafted with assistance from Claude (Anthropic) for text editing and formatting. The system design, architecture decisions, code, configuration, and all analytical choices described here were made by the human author and reviewed by the author before publication.

---

## 16. Acknowledgements

This work was developed at BOKU University Vienna. The author thanks *(to be added)* for discussions on the system architecture and the wicked-problem framing.

**Funding:** *(to be added, or state "No external funding received for this work.")*

---

## 17. Contact

Peter Holubar — `peter.holubar@boku.ac.at`

For bug reports and feature requests, please open an issue on the GitHub repository.
