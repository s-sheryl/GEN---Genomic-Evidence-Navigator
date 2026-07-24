# GEN — Genomic Evidence Navigator

![Python](https://img.shields.io/badge/python-3.x-blue)
![Flask](https://img.shields.io/badge/flask-web%20framework-black)
![ReportLab](https://img.shields.io/badge/reportlab-PDF%20generation-red)
![Status](https://img.shields.io/badge/status-educational%20project-yellow)
![License](https://img.shields.io/badge/license-MIT-green)

Educational Bioinformatics Project

**GEN (Genomic Evidence Navigator)** is a Flask web application that takes a gene symbol and an HGVS coding variant, runs it through HGVS validation, ClinVar lookup, and Ensembl VEP annotation, maps it to genomic coordinates, scores it with a small ACMG-inspired evidence engine, and generates a scientific-style PDF report.

This is a student project built to learn how the pieces of a variant interpretation pipeline fit together in practice — it is not a clinical tool, and it is not trying to be one. Full technical detail lives in [`docs/`](docs/); this file is the overview.

---
## 🌐 Demo

Try the application here:

**https://gen-genomic-evidence-navigator.onrender.com**

Example test case:

Gene:
TP53

Variant:
c.818G>A

Genome:
GRCh38

## Table of Contents

- Highlights
- Screenshots
- Why I Built This
- Architecture
- Features
- Supported HGVS Formats
- Example Pipeline
- Technologies Used
- Project Structure
- Installation
- Running
- Project Status
- Future Improvements
- Limitations
- References
- License

## Highlights

- Validates and classifies HGVS coding variants without relying on a third-party HGVS parsing library
- Retrieves live clinical significance from NCBI ClinVar and molecular consequence from Ensembl VEP within the same request
- Maps variants to genomic coordinates independently of the annotation call
- Scores variants with a transparent, documented ACMG-inspired evidence engine rather than an opaque black box
- Generates an eleven-section scientific PDF report, not just a results page
- Implemented as separate, independently testable modules rather than a single monolithic script

---

## Screenshots

The four screenshots below follow the actual user path through the app: landing page → input form → generated report → exported PDF.

**1. Home page**
Landing page introducing the project and summarizing the four-stage workflow shown in the UI (HGVS Input → Variant Validation → Evidence Retrieval → Interpretation).
<img width="1440" height="1431" alt="home" src="https://github.com/user-attachments/assets/99e93f30-a834-48d5-a4af-91e3c9247522" />


**2. Variant interpretation form**
Intake form for the gene symbol, HGVS coding variant, and genome build (GRCh37/GRCh38). This is the only user input the pipeline requires.
<img width="1440" height="490" alt="interpret" src="https://github.com/user-attachments/assets/444dd88a-22b3-4089-ba48-83bd8f8f7968" />



**3. Generated report (results page)**
Full evidence report for a submitted variant: variant summary, ClinVar clinical significance, Ensembl molecular consequence, genomic coordinates, and the ACMG-inspired evidence table with the resulting classification badge.

<img width="1440" height="2850" alt="results" src="https://github.com/user-attachments/assets/091ef5e2-3562-4b4a-9fe9-271b88c36c13" />


**4. Exported PDF report**
Cover page of the same report exported as a standalone PDF, including report ID, analysis type, and genome build.

<img width="1700" height="2200" alt="pdf_report" src="https://github.com/user-attachments/assets/902d7f12-5b75-4de2-850f-db7140d606b4" />



---

## Why I Built This

I study genetics and biotechnology, and one topic that kept coming up in coursework was ACMG/AMP variant classification — the idea that pathogenicity isn't decided by a single database lookup, but by combining several independent lines of evidence (functional consequence, population frequency, clinical databases, computational predictors) into a single classification.

Reading about that process in a paper is one thing. Wiring together a gene symbol, an HGVS string, a public API, and a scoring rule is a different kind of understanding. I wanted to see, hands-on, what it takes to:

- pattern-match and validate HGVS notation without a dedicated parsing library
- call ClinVar's and Ensembl's live REST APIs and handle the ways they fail (rate limits, unresolved transcripts, malformed responses)
- map a raw VEP consequence term onto an ACMG-style evidence criterion
- generate a report that reads like it came out of a real pipeline, not a print statement

This project is my own simplified, transparent version of that pipeline. It implements a handful of ACMG criteria and says so everywhere in the output — that honesty about scope mattered more to me than making the tool look more complete than it is.

---

## Architecture

```
                                              Browser
                                                 │
                                                 ▼
                                           Flask (app.py)
                                                 │
┌────────┬───────────────────┬───────────────────┬───────────────────┬───────────────────┬─────────┐
         ▼                   ▼                   ▼                   ▼                   ▼
   HGVS Validator      ClinVar Client      Ensembl Client      Variant Mapper        Gene Info
 (variant_utils.py)     (clinvar.py)        (ensembl.py)    (variant_mapper.py)    (gene_info.py)
         │                   │                   │                   │                   │
└────────┴───────────────────┴───────────────────┴───────────────────┴───────────────────┴─────────┘
                                                 │
                                                 ▼
                                       ACMG Engine (acmg.py)
                                                 │
                                                 ▼
                                 Narrative Generator (reasoning.py)
                                                 │
                                                 ▼
                                        Results Page (HTML)
                                                 │
                                                 ▼
                                PDF Generator (report_generator.py)

Not part of the active request flow (present in utils/, not imported by app.py):

    hgvs_validator.py        gnomad.py        report_storage.py
```

A submission flows from the browser into a single Flask route (`/results` in `app.py`), which fans out to five independent modules — the HGVS validator, the ClinVar client, the Ensembl client, the variant mapper, and the gene description lookup. Their combined output is passed into the ACMG engine, summarized by the narrative generator, rendered onto the results page, and optionally exported as a PDF on request. No stage depends on the internals of another; each one consumes plain dictionaries and returns plain dictionaries, so the pipeline can be traced (and debugged) one function call at a time.

Three modules in `utils/` are not part of this flow, and are shown separately in the diagram above rather than as pipeline stages. `hgvs_validator.py` implements a separate, transcript-accession-aware HGVS check, but `app.py` never imports it — `variant_utils.py` is the HGVS validator actually in use. `gnomad.py` implements a working gnomAD GraphQL client, but it is not currently called from `app.py`, so PM2 evidence has no population-frequency data to act on in the live app. `report_storage.py` implements JSON-based report persistence, but it is not currently invoked either. All three exist in the repository and work correctly in isolation; none of them execute during a live request.

**Why the modules are separated**

Each external data source (ClinVar, Ensembl) and each processing stage (validation, scoring, narrative generation, PDF export) lives in its own file with a single public function. This follows ordinary separation-of-concerns practice rather than any framework convention, and it has three concrete effects on this codebase:

- **Testability.** `variant_utils.py` and `acmg.py` are pure functions with no network dependency, so they can be unit-tested in isolation without mocking HTTP calls (this isn't done yet — see [Future Improvements](#future-improvements) — but the separation is what makes it feasible).
- **Fault isolation.** Every outbound call to ClinVar and Ensembl is wrapped in exception handling. Network errors, non-200 responses, and malformed JSON bodies are all caught and converted into a structured `"not available"` result rather than an unhandled exception, so a single failed API call degrades that section of the report instead of crashing the request.
- **Replaceability.** `clinvar.py`, `ensembl.py`, `variant_mapper.py`, `acmg.py`, `reasoning.py`, and `report_generator.py` each expose one function with a fixed input/output shape. Swapping the ClinVar client for a different variant database, for instance, would not require changes to the ACMG engine or the report generator.

**Known inefficiency:** Ensembl is called twice per submission — once for full annotation, once for coordinate mapping — because `ensembl.py` and `variant_mapper.py` independently resolve the canonical transcript rather than sharing one lookup. This is listed under [Future Improvements](#future-improvements) rather than fixed, since caching would need a decision about invalidation that's out of scope for this project's current size. Full request-by-request detail, including every module's failure handling, is in [docs/PIPELINE.md](docs/PIPELINE.md).

---

## Features

| Module | Description |
|---|---|
| **HGVS Validation** (`variant_utils.py`) | Regex-based validation of coding HGVS variant strings, covering substitutions, deletions, insertions, duplications, delins, intronic positions, and UTR positions. |
| **Variant Type Detection** (`variant_utils.py`) | Classifies frameshift vs. in-frame indels, substitutions, splice variants, and delins directly from the HGVS string. |
| **ClinVar Lookup** (`clinvar.py`) | Queries NCBI's [E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) (`esearch` → `esummary`) for clinical significance, review status, and associated conditions. |
| **Ensembl Annotation** (`ensembl.py`) | Resolves the gene symbol to its canonical transcript, then queries the [Ensembl VEP REST endpoint](https://rest.ensembl.org/documentation/info/vep_hgvs_get) for consequence, impact, protein change, exon, and SIFT/PolyPhen predictions, with GRCh37/GRCh38 build selection. |
| **Genomic Coordinate Mapping** (`variant_mapper.py`) | An independent VEP call that resolves chromosome, position, and allele string. |
| **ACMG-Inspired Evidence Engine** (`acmg.py`) | Combines HGVS validity, a PVS1-style loss-of-function check, and ClinVar significance into a 0–100 score, classification, and confidence level. See below for details. |
| **Biological Narrative Generation** (`reasoning.py`) | Writes a short, gene-specific explanation of the molecular consequence. |
| **PDF Report Generation** (`report_generator.py`) | Produces an eleven-section report — cover page, executive summary, variant details, gene summary, molecular consequence, clinical evidence, ACMG evidence table, biological interpretation, confidence assessment, workflow diagram, and disclaimer — built with ReportLab. |
| **Static Gene Descriptions** (`gene_info.py`) | Hand-written summaries for BRCA1, BRCA2, TP53, CFTR, and EGFR; any other gene receives a generic fallback description. |

  User Input
      │
      ▼
HGVS Validation
      │
      ▼
   ClinVar
      │
      ▼
   Ensembl
      │
      ▼
 ACMG Engine
      │
      ▼
Scientific Report
      │
      ▼
     PDF
### ACMG-Inspired Evidence Engine

`acmg.py` implements five evidence functions loosely inspired by the [2015 ACMG/AMP guidelines](https://doi.org/10.1038/gim.2015.30) (Richards et al.) — HGVS validity, PVS1-like loss-of-function reasoning, PM2-like population frequency reasoning, PP3-like computational predictor reasoning, and ClinVar significance — and combines them using simplified threshold rules into a score, classification, and confidence level. The [ClinGen Sequence Variant Interpretation (SVI) Working Group](https://clinicalgenome.org/working-groups/sequence-variant-interpretation/) has since published refined, criterion-specific specifications (e.g. for PVS1) that this engine does not implement; the PVS1-like function here is a simplified approximation of the original 2015 rule only.

Two of the five (PM2, PP3) are fully implemented and behave correctly in isolation, but `app.py` never supplies them with the data they need, so they always return `"Not Available"` in the running application. ClinVar and the PVS1-style check are the only sources that currently influence a live classification. The full scoring logic, including exact point values and threshold rules, is documented in [docs/ACMG_ENGINE.md](docs/ACMG_ENGINE.md).

> [!IMPORTANT]
> This is an **educational approximation**, not a clinical ACMG implementation. It evaluates 5 of the ~28 criteria defined in the 2015 ACMG/AMP guidelines and uses simple threshold counting instead of the full combining-rule matrix. It is not ACMG-compliant, clinical-grade, or diagnostic in any sense.

---

## Supported HGVS Formats

Checked against the regex patterns in `variant_utils.py`, based on the [HGVS sequence variant nomenclature](https://hgvs-nomenclature.org/stable/):

| Format | Example |
|---|---|
| Substitution | `c.20A>T` |
| Intronic substitution | `c.123+1G>A` |
| 5′/3′ UTR substitution | `c.-15A>G`, `c.*10A>G` |
| Deletion (single/range) | `c.5946delT`, `c.68_69delAG` |
| Duplication | `c.123dupA`, `c.123_125dupATG` |
| Insertion | `c.123_124insATG` |
| Deletion-insertion | `c.123_125delinsAT` |

**Not currently supported:** protein-level HGVS (`p.`), genomic-level HGVS (`g.`), mitochondrial HGVS (`m.`), and complex rearrangements beyond a single delins.

> [!NOTE]
> A separate module, `hgvs_validator.py`, contains logic for recognizing transcript-accession-prefixed HGVS strings (e.g. `NM_007294.4:c.68_69delAG`), but it is not currently imported by `app.py`, so it is not part of the active validation path.

---

## Example Pipeline

**Input**
```
Gene: TP53
Variant: c.743G>A
```

Submitting a gene/variant pair through `/interpret` runs the full pipeline described in Architecture. A completed request — for example, `HBB` / `c.20A>T` — produces a results page containing:

- the validated HGVS status and detected variant type
- a plain-language interpretation of that variant type
- the ClinVar record, if one is found (clinical significance, review status, associated conditions)
- the Ensembl annotation block (chromosome, position, transcript, protein change, consequence, impact, exon, SIFT/PolyPhen where available)
- the genomic mapping block (chromosome, position, allele string, assembly)
- the ACMG-inspired evidence table (each code, strength, points, status, and explanation)
- the overall classification, numeric score out of 100, and confidence level
- the auto-generated reasoning paragraph explaining how the classification was reached
- a "Download PDF Report" button, which regenerates the same data as an eleven-section PDF

```
✓ HGVS validation
✓ ClinVar evidence
✓ Ensembl annotation
✓ Genomic coordinates
✓ ACMG-inspired classification
✓ Scientific PDF report
```

Each checkmark corresponds to one pipeline stage. The actual values returned — clinical significance, consequence, coordinates, score — depend on the live ClinVar/Ensembl response for that specific variant at request time.

### Example Inputs

These are variants I used repeatedly while building and debugging the pipeline. The "Detected Variant Type" column is deterministic — it comes directly from `variant_utils.py`'s string parsing and does not depend on a live API call, so I can state it with confidence. Classification and ClinVar status are not included here because they depend on live network responses that vary by run; see the results page for those.

| Gene | Variant | Detected Variant Type |
|---|---|---|
| BRCA1 | `c.68_69delAG` | Frameshift deletion |
| CFTR | `c.1521_1523delCTT` | In-frame deletion |
| TP53 | `c.818G>A` | Substitution |
| HBB | `c.20A>T` | Substitution |
| APOE | `c.388T>C` | Substitution |

---

## Technologies Used

| Category | Technology |
|---|---|
| Programming Language | Python 3 |
| Web Framework | Flask (routing, templating, `render_template`, `send_file`) |
| Libraries | `requests` (HTTP), `re` (HGVS pattern matching), `json` and `uuid` (report persistence) |
| External APIs | [NCBI ClinVar E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/), [Ensembl REST API](https://rest.ensembl.org/) (`/lookup/symbol`, `/vep/human/hgvs`), [gnomAD GraphQL API](https://gnomad.broadinstitute.org/api) (implemented in `gnomad.py`, not yet wired into the request flow) |
| Frontend | Jinja2 templates, plain CSS |
| PDF Generation | [ReportLab](https://docs.reportlab.com/) — `platypus` flowables, a custom `Canvas` subclass for page numbers, `Table`/`TableStyle` for evidence tables, a custom `Flowable` for the workflow diagram |

No database is used. A full breakdown of how each library is used is in [docs/PIPELINE.md](docs/PIPELINE.md).

---

## Project Structure

```
genomic-evidence-navigator
│
├── app.py
│
├── utils
│   ├── acmg.py
│   ├── clinvar.py
│   ├── ensembl.py
│   ├── gene_info.py
│   ├── gnomad.py
│   ├── hgvs_validator.py
│   ├── reasoning.py
│   ├── report_generator.py
│   ├── report_storage.py
│   ├── variant_mapper.py
│   └── variant_utils.py
│
├── templates
│   ├── index.html
│   ├── interpret.html
│   ├── results.html
│   ├── about.html
│   └── contact.html
│
├── static
│   └── style.css
│
├── docs
│   ├── ACMG_ENGINE.md
│   ├── PIPELINE.md
│   └── LIMITATIONS.md
│
├── reports
│
├── LICENSE
└── requirements.txt
```

> [!NOTE]
> `requirements.txt` is not yet committed to the repository. Until it is, use the direct `pip install` command in [Installation](#installation). Pinning exact versions here is one of the near-term items in [Future Improvements](#future-improvements).

---

## Installation

```bash
git clone https://github.com/yourusername/genomic-evidence-navigator.git
cd genomic-evidence-navigator

python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

pip install -r requirements.txt
```

`requirements.txt` is not yet in the repository (see the note in [Project Structure](#project-structure)). Until it's added, install the three required packages directly:

```bash
pip install flask requests reportlab
```

---

## Running

```bash
python app.py
```

The app runs in debug mode by default. Open a browser to `http://127.0.0.1:5000`, go to **Interpret Variant**, enter a gene symbol (e.g. `BRCA1`) and an HGVS coding variant (e.g. `c.68_69delAG`), select a genome build, and submit. Results are generated from live ClinVar and Ensembl calls, so an internet connection is required — there is no offline or cached mode.

To download the PDF version of the most recent result, use the download link on the results page. This regenerates the PDF from the last submitted variant stored in memory, not per session — it will behave incorrectly if two people use the same running instance at the same time (see [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

---

## Project Status

**Version:** 1.0 (Educational Release)

**Working end to end**
- [x] HGVS validation and variant type detection
- [x] ClinVar lookup
- [x] Ensembl annotation and coordinate mapping
- [x] ACMG-inspired scoring (HGVS + PVS1 + ClinVar)
- [x] Narrative generation
- [x] PDF report generation

**Implemented but not connected**
- [ ] PM2 evidence (gnomAD client exists, not called from `app.py`)
- [ ] PP3 evidence (predictor logic exists, no data source wired in)
- [ ] JSON report persistence (`report_storage.py` exists, not called from `app.py`)

**Not started**
- [ ] Automated tests
- [ ] Session-based (per-user) result storage

---

## Future Improvements

**Near-term**
- Add an automated test suite (`pytest`) covering `variant_utils.py`'s regex patterns and `acmg.py`'s scoring logic — both are pure functions with no network dependency, so this needs no mocking to get started
- Pin dependencies in a committed `requirements.txt` for reproducible installs
- Wire `gnomad.py` into `app.py` so PM2 runs against live population frequency data
- Set up a GitHub Actions workflow to run the test suite and a linter (`ruff` or `flake8`) on every push

**Medium-term**
- Add a real computational predictor source (REVEL, AlphaMissense, or CADD) and connect it to the existing `_pp3_evidence()` logic
- SpliceAI integration for a better splice-impact estimate than the current substring match on consequence terms
- dbNSFP integration as a single source for multiple predictor scores
- Session-based result storage instead of the single global `LATEST_RESULT`
- Caching Ensembl/ClinVar responses to avoid duplicate canonical-transcript lookups per request
- A `Dockerfile` for a reproducible runtime environment

**Long-term**
- Expand the ACMG evidence engine beyond the current five criteria (e.g. PM1, PM4, PP2, BS1)
- VCF upload support, instead of one gene/variant pair typed in manually
- Batch variant analysis
- Expose the pipeline as a documented REST API (e.g. OpenAPI/Swagger spec) in addition to the current server-rendered HTML interface

# Future Version Roadmap
Version 1.0
✓ Educational pipeline

Version 2.0
• Population frequency integration

Version 3.0
• Batch VCF analysis

Version 4.0
• Full ACMG engine

---
## What I Learned

Through this project I gained experience with

- HGVS nomenclature
- REST API integration
- Variant annotation workflows
- Evidence-based variant interpretation
- Scientific report generation
- Modular software architecture
- Exception handling
- Bioinformatics pipeline design

## Limitations

> [!IMPORTANT]
> This is an educational project, and the limitations are as important as the features. In short: 5 of ~28 ACMG criteria are implemented, PM2/PP3 are coded but not connected to the live app, classification uses simple threshold counting rather than the full combining-rule matrix, gene background text covers only five genes, and the app has no authentication, caching, or per-user state.

Full detail is in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

---

## License

Released under the [MIT License](LICENSE).

---

## Disclaimer

> [!WARNING]
> This software is intended strictly for educational and research purposes. It must not be used for clinical diagnosis, patient care, or any medical decision-making. The classifications, scores, and interpretations it produces have not been reviewed by a certified clinical laboratory, molecular pathologist, or genetic counselor. Any real clinical question about a genetic variant should be directed to a qualified healthcare professional or an accredited clinical genetics laboratory.

---

## References

**Guidelines and standards**
- Richards S, et al. (2015). *Standards and guidelines for the interpretation of sequence variants: a joint consensus recommendation of the American College of Medical Genetics and Genomics and the Association for Molecular Pathology.* Genetics in Medicine. https://doi.org/10.1038/gim.2015.30
- ClinGen Sequence Variant Interpretation (SVI) Working Group — criterion-specific ACMG/AMP refinements published after 2015, not implemented in this project. https://clinicalgenome.org/working-groups/sequence-variant-interpretation/
- den Dunnen JT, et al. (2016). *HGVS Recommendations for the Description of Sequence Variants.* Human Mutation. https://doi.org/10.1002/humu.22981
- HGVS Nomenclature (current specification) — https://hgvs-nomenclature.org/

**Databases and tools**
- Landrum MJ, et al. (2018). *ClinVar: improving access to variant interpretations and supporting evidence.* Nucleic Acids Research. https://doi.org/10.1093/nar/gkx1153
- NCBI ClinVar — https://www.ncbi.nlm.nih.gov/clinvar/
- NCBI Entrez Programming Utilities (E-utilities) documentation — https://www.ncbi.nlm.nih.gov/books/NBK25501/
- McLaren W, et al. (2016). *The Ensembl Variant Effect Predictor.* Genome Biology. https://doi.org/10.1186/s13059-016-0974-4
- Ensembl REST API documentation — https://rest.ensembl.org/
- Karczewski KJ, et al. (2020). *The mutational constraint spectrum quantified from variation in 141,456 humans.* Nature (gnomAD flagship paper). https://doi.org/10.1038/s41586-020-2308-7
- gnomAD — https://gnomad.broadinstitute.org/
- ReportLab documentation (PDF generation library used by `report_generator.py`) — https://docs.reportlab.com/

---

## Author

**S.Sheryl**
B.Sc. Genetics • Biotechnology • Zoology • Biochemistry

Developed as an educational bioinformatics project to better understand how HGVS validation, public genomic databases, and evidence-based variant interpretation integrate into a modern computational genomics workflow.

The project emphasizes transparency, modular software design, and reproducible scientific reporting over clinical decision support.
