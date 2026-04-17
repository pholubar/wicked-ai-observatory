# Wicked AI Observatory

**A multi-agent system for dynamic mapping of wicked problems in artificial intelligence governance.**

The Wicked AI Observatory (WAO) continuously monitors, classifies, and maps AI governance challenges across thirteen dimensions using a Neo4j knowledge graph, LLM-based classification, and human-in-the-loop calibration.

🌐 **Project website:** [wicked-ai-observatory.org](https://wicked-ai-observatory.org)
📄 **Technical Report:** [10.5281/zenodo.19627548]

---

## Overview

AI governance challenges are paradigmatic wicked problems: they resist definitive formulation, involve stakeholders with conflicting goals, evolve dynamically, and have no solutions that are unambiguously correct. WAO makes this complexity visible and navigable.

### Current State (April 2026, Version 0.7)

- **29 factors** across 13 dimensions (Political, Technical, Economic, Legal, Ethical, Societal, Pedagogical, Epistemic, Global, Environmental, Peace, War — grouped into Institutional, Societal, and Planetary clusters)
- **11 stakeholders** (European Commission, EU Parliament, Big Tech, Civil Society, US Government, China, UN/IAEA, ICRC, Academic Research, Media, Affected Communities)
- **172 events** ingested across 5 monitoring cycles
- **13 RSS feeds** + Zotero library integration

### Top Wickedness Scores

| Factor | Dimension | Score |
|--------|-----------|-------|
| Compressed Kill Chains | War | 96 |
| Regulatory Capture | Political | 91 |
| Autonomous Weapon Systems | War | 90 |
| Accountability Gaps | Ethical | 90 |
| Alignment Failures | Technical | 88 |

## Architecture

Seven specialized agents coordinated through a shared Neo4j knowledge graph:

| Layer | Agent | Function |
|-------|-------|----------|
| Ingestion | Monitor Agent | 13 RSS feeds + Zotero API |
| Ingestion | Classify Agent | AI-relevance filter, 29 factors (Claude Sonnet) |
| Analysis | Write Agent | MERGE-based Event → Neo4j with provenance |
| Analysis | Wickedness Agent | 14-parameter wickedness vector |
| Analysis | Proposal Agent | Score proposals with confidence + HITL |
| Output | Explanation Agent | Narrative summaries for different audiences |
| Output | Visualization Agent | 3 interactive HTML graph visualizations |

For the full architecture description, agent specifications, validation framework, and empirical findings, see the accompanying **Technical Report** (v0.7) on Zenodo.

## Installation

### Prerequisites

- [Neo4j Desktop](https://neo4j.com/download/) (version 2026.02+)
- [Anaconda](https://www.anaconda.com/download) (Python 3.11 or 3.12)
- [Anthropic API key](https://console.anthropic.com/)
- [Zotero](https://www.zotero.org/) account with a group library and API key

### Setup

**1. Clone the repository:**
```bash
git clone https://github.com/pholubar/wicked-ai-observatory.git
cd wicked-ai-observatory
```

**2. Create the conda environment:**
```bash
conda create -n wao python=3.12 -y
conda activate wao
pip install -r requirements.txt
```

**3. Configure Neo4j:**
- Open Neo4j Desktop → create an instance (e.g. `wao-v2`)
- Start the instance and create a database called `wao`
- Note the `bolt://` URI and the password you set

**4. Configure environment variables:**

Copy the template and fill in your own values:
```bash
cp .env.example .env
```

Edit `.env` with your Neo4j, Anthropic, and Zotero credentials:
```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password-here
NEO4J_DB=wao

ANTHROPIC_API_KEY=sk-ant-...
ZOTERO_GROUP_ID=your-group-id
ZOTERO_API_KEY=your-zotero-api-key
```

The `.env` file is excluded via `.gitignore` and must never be committed.

**5. Import the knowledge graph:**

Open Neo4j Browser and run the contents of:
```
data/wicked_ai_observatory_2026_04_14.cypher
```

This creates the 29 factors, 11 stakeholders, and the initial `AMPLIFIES` / `CONFLICTS_WITH` edges.

**6. Start the application:**
```bash
streamlit run app/wao_app.py
```

Open `http://localhost:8501` in your browser.

## Usage

The Streamlit interface provides five views:

- **📊 Dashboard** — real-time graph statistics, top 10 factors, latest events
- **🔄 Weekly Update** — one-click monitoring pipeline (Monitor → Classify → Write)
- **📋 Review Digest** — AI-generated score proposals with confirm / adjust / skip
- **⚖️ Source Weighting** — source credibility weights per factor
- **📤 Export** — Cypher export, factor tables, interactive HTML graph visualizations

Alternatively, for scripted or scheduled runs, use the Jupyter notebook in `notebooks/wao_notebook.ipynb`.

## Repository Structure

```
wicked-ai-observatory/
├── app/
│   └── wao_app.py                             # Streamlit application (main UI)
├── src/
│   └── wao_master_cell.py                     # All agent functions
├── notebooks/
│   └── wao_notebook.ipynb                     # Lightweight workflow notebook
├── data/
│   └── wicked_ai_observatory_2026_04_14.cypher  # Initial graph (reproducible import)
├── visualizations/
│   ├── wao_graph_faktoren.html                # Factor-only graph
│   ├── wao_graph_struktur.html                # Factor + Stakeholder graph
│   └── wao_graph_vollgraph.html               # Full graph with events
├── docs/
│   └── architecture.png                       # System architecture diagram
├── index.html                                 # Project landing page (GitHub Pages)
├── requirements.txt
├── .env.example                               # Template for local credentials
├── LICENSE-CODE                               # MIT License (code)
├── LICENSE-DOCS                               # CC BY 4.0 (documentation)
├── .gitignore
└── README.md
```

## Methodology

WAO applies **wicked problem theory** (Rittel & Webber, 1973) systematically to AI governance. Each factor is assessed on a **14-parameter wickedness vector** derived from Rittel and Webber's ten properties and Levin et al.'s (2012) four super-wicked criteria.

The system treats **uncertainty as a first-class output**: contested nodes, confidence scores, and provenance metadata are visible in all interfaces. Human-in-the-loop calibration ensures that normative weighting decisions are documented, transparent, and auditable.

A fuller treatment of the theoretical foundations, the four-level validation framework, and the empirical findings from the first five monitoring cycles is in preparation as a separate publication.

## License

- **Code:** MIT License — see [LICENSE-CODE](LICENSE-CODE)
- **Documentation, factor registry, and graph data:** CC BY 4.0 — see [LICENSE-DOCS](LICENSE-DOCS)

## Citation

If you use WAO or its factor registry in academic work, please cite the forthcoming Zenodo record:

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
  doi          = {<DOI-from-Zenodo>},
  url          = {https://doi.org/10.5281/zenodo.19627548}
}
```

## Contributing

WAO follows an open contribution model with curatorial quality assurance. Contributions are welcome — particularly from researchers whose disciplinary, geographic, or institutional perspectives are underrepresented in the current system. Please open an issue or pull request.

## Contact

Peter Holubar
Department of Biotechnology and Food Sciences
BOKU University Vienna
Muthgasse 18, A-1190 Vienna, Austria
[peter.holubar@boku.ac.at](mailto:peter.holubar@boku.ac.at)
