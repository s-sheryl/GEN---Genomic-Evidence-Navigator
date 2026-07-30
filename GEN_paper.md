# GEN: An Educational Software Platform for ACMG-Inspired Genomic Variant Interpretation

****

### Citation

Sheryl S.
GEN: An Educational Software Platform for ACMG-Inspired Genomic Variant Interpretation.

2026

---

## Abstract

Interpreting the clinical significance of a genomic variant typically requires combining several independent lines of evidence — molecular consequence, population frequency, prior clinical observations, and computational prediction — into a single classification. The American College of Medical Genetics and Genomics and the Association for Molecular Pathology (ACMG/AMP) formalized this process in 2015 through a joint consensus framework built around roughly two dozen weighted evidence criteria. While the guidelines are widely used in clinical laboratories, the process of translating them into working software is rarely visible to students, since production-grade interpretation platforms are proprietary and clinical in scope. This paper describes GEN (Genomic Evidence Navigator), a Flask-based web application built as an educational exercise in integrating public genomic data sources into a simplified variant-interpretation workflow. GEN accepts a gene symbol, a coding-level HGVS variant string, and a genome build, validates the variant syntax, retrieves clinical significance data from the NCBI ClinVar database, retrieves molecular consequence data from the Ensembl Variant Effect Predictor, maps the variant to genomic coordinates, and scores it using an evidence engine that implements five of the ACMG/AMP criteria — HGVS validity, a PVS1-like loss-of-function check, PM2-like population-frequency reasoning, PP3-like computational-predictor reasoning, and ClinVar-derived evidence. Results are rendered as an interactive report and can be exported as a structured PDF document. This paper describes the system's architecture, implementation, and functional output, and discusses its limitations honestly: only a minority of ACMG/AMP criteria are implemented, two of the five evidence functions are not yet connected to the live request path, and the system holds no session state. No accuracy, sensitivity, or benchmark figures are reported, since no curated evaluation dataset was used. GEN is presented strictly as an educational artifact, not a diagnostic or clinical decision-support tool.

**Keywords** — genomic variant interpretation, HGVS nomenclature, ClinVar, Ensembl Variant Effect Predictor, ACMG/AMP guidelines, bioinformatics software, web application

---

## 1. Introduction

A variant found during sequencing might be common in the population, previously reported in a clinical database, predicted to disrupt a protein, or all three at once. None of those signals is reliable enough to act on by itself. Population frequency data can rule out a common variant but says little about a rare one. Computational predictors are useful heuristics, but different tools frequently disagree with each other. Clinical databases capture real prior observations, but individual submissions vary in how carefully they were reviewed.

The ACMG/AMP guidelines published by Richards et al. in 2015 [1] turned this into a structured process. Independent evidence types — predicted loss of function, population frequency, functional and segregation data, and prior clinical reports among them — are each assigned a strength (Supporting, Moderate, Strong, or Very Strong) and combined through a fixed rule set to reach one of five classifications: Pathogenic, Likely Pathogenic, Uncertain Significance, Likely Benign, or Benign. The ClinGen Sequence Variant Interpretation (SVI) Working Group has since published more detailed specifications for individual criteria, including a widely cited refinement of the PVS1 loss-of-function rule [2].

None of this works without first describing the variant precisely, which is the job of HGVS nomenclature — a text-based standard for representing substitutions, deletions, insertions, and other sequence changes relative to a reference sequence [3], [4].

What is easy to miss from reading the guidelines is how much of this process now runs on public infrastructure. ClinVar aggregates submitted variant–phenotype relationships along with a review status indicating how much consensus supports each one [5]. The Ensembl Variant Effect Predictor (VEP) annotates a variant against a reference transcript and reports its predicted molecular consequence [6], [7]. gnomAD provides population allele frequencies at a scale no single lab could assemble alone [8]. Each of these is reachable through a public REST API, which means a student, not just a certified laboratory, can query all three for a given variant.

That accessibility is what makes a project like this feasible to build alone. It is also where the real engineering work turned out to live. HGVS strings need validating before anything downstream can trust them. Ensembl and ClinVar occasionally return partial or slow responses more often than their documentation suggests. The ACMG combining rules read like a lookup table on paper, but deciding what to do when a criterion's evidence is simply missing, rather than negative, is not fully spelled out by the guidelines themselves. Working through these problems in code, rather than only in the abstract, was the actual reason for building GEN.

GEN (Genomic Evidence Navigator) is a small Flask web application [9] that queries ClinVar and Ensembl live and applies a simplified evidence-scoring engine loosely modeled on the ACMG/AMP framework. It implements five of the roughly twenty-eight criteria defined in the 2015 guidelines, not the full set, and several of its evidence functions exist in the codebase without yet being wired into the running application. Both points are treated as central findings of this paper rather than footnotes, and are discussed in detail in Sections 3 and 5.

---

## 2. System Design

GEN follows a linear request pipeline built around a single Flask route. A user submits a gene symbol, an HGVS coding variant, and a genome build through an HTML form; the backend runs HGVS validation, a ClinVar lookup, an Ensembl VEP annotation call, a coordinate-mapping call, ACMG-inspired scoring, and narrative generation, then renders the result as an HTML report with an optional PDF export. Figure 1 shows the overall shape of this pipeline.


```
GEN request pipeline (text summary of Figure 1)

  Browser
     |
  Flask (app.py)
     |
     |-- HGVS Validator      (variant_utils.py)
     |-- ClinVar Client      (clinvar.py)
     |-- Ensembl Client      (ensembl.py)
     |-- Variant Mapper      (variant_mapper.py)
     |-- Gene Description    (gene_info.py)
     |
     v
  ACMG Evidence Engine       (acmg.py)
     |
     v
  Narrative Generator        (reasoning.py)
     |
     v
  Results Page (HTML)  -->  PDF Report (report_generator.py)
```

The five modules Flask calls directly share one convention: each accepts plain arguments and returns a plain dictionary, with no dependency on any other module's internal state. That convention was chosen for two reasons that go beyond code style.

The first is fault isolation. Every network call to ClinVar or Ensembl sits inside its own exception handler, so a timeout, a non-200 response, or a malformed JSON body gets converted into a structured placeholder result — a status field reading "ClinVar connection error," for instance — instead of propagating as an unhandled exception. A failure in one data source degrades only the corresponding section of the report; it does not take down the request.

The second is that plain-dictionary modules are easy to reason about in isolation. The HGVS validator and the ACMG scoring engine, in particular, are pure functions with no network dependency at all, which means their behavior can be checked directly against fixed inputs. No test suite currently does this — that gap is discussed in Section 5 — but the architecture is what makes it a realistic thing to add later rather than a rewrite.

The design has a real cost, too. The Ensembl client and the variant coordinate mapper each resolve the same canonical transcript and separately query the same VEP endpoint, so a single submission triggers two nearly identical Ensembl requests. This came from the two modules being written with narrower, separate responsibilities — full annotation versus coordinate extraction — rather than from a deliberate performance decision, and it is treated here as a known inefficiency rather than a strength.

Three further modules live in the codebase outside this active path. `hgvs_validator.py` implements a second, transcript-accession-aware HGVS check that `app.py` never imports; `variant_utils.py` is the validator actually in use. `gnomad.py` implements a working GraphQL client against the public gnomAD API, and `report_storage.py` implements JSON-based persistence of generated reports, but neither is currently called from the request path. Both are directly relevant to the evidence engine described in Section 3, and their disconnection is discussed again in Section 5.

For accessibility and reproducibility, the application is also deployed publicly on Render, so the pipeline described above can be exercised without a local installation. The deployment does not change anything about the architecture; it is mentioned here only because it affects how a reader can verify the system's behavior.

---

## 3. Implementation

### 3.1 HGVS Validator

`variant_utils.py` checks a submitted variant string against a fixed set of regular expressions covering the coding-sequence HGVS syntax GEN supports: substitutions, single and range deletions, duplications, insertions, deletion-insertions, intronic offsets, and untranslated-region positions. A string that fails every pattern is rejected outright rather than partially parsed, which matters because a partially parsed variant is worse than no variant at all — it looks valid downstream when it is not.

The same module also detects variant type without touching the network: it inspects the string for `del`, `dup`, `ins`, `delins`, or `>`, and for indels, compares the length of the affected sequence against a multiple of three to distinguish a frameshift from an in-frame change. This one check — length modulo three — is doing a surprising amount of work for how simple it is, since frame preservation is one of the clearest predictors of a severe consequence available without querying anything external. Because it depends only on the input string, its output is deterministic regardless of network conditions, unlike every later stage of the pipeline.

A separate module, `hgvs_validator.py`, adds logic for recognizing transcript-accession-prefixed HGVS strings such as `NM_007294.4:c.68_69delAG`. It is not imported by `app.py`, so it plays no role in the live system.

### 3.2 ClinVar Client

`clinvar.py` reaches ClinVar through NCBI's Entrez Programming Utilities in two sequential calls: `esearch` to resolve a gene-and-variant query to a record identifier, then `esummary` to pull the clinical significance, review status, and associated conditions for that record [5], [10]. Splitting this into two calls is not a stylistic choice — it reflects how the underlying API is structured, and it doubles the number of ways the lookup can fail partway through. Both calls sit inside one exception handler, so a timeout on either step returns a "ClinVar connection error" status rather than an unhandled exception reaching the Flask route.

### 3.3 Ensembl Client

`ensembl.py` makes two calls of its own against the Ensembl REST API [6], [7]: first `/lookup/symbol/homo_sapiens/{gene}` to resolve the canonical transcript, then `/vep/human/hgvs/{transcript}:{variant}` for the predicted consequence, impact, protein change, exon, and available SIFT/PolyPhen scores. GRCh37 requests are routed to a separate assembly-specific mirror rather than the current-assembly server, since Ensembl does not serve both builds from the same endpoint. Every failure path here — network error, non-200 status, malformed JSON, or a VEP response with no usable consequence — collapses to the same dictionary shape with "Not available" placeholders, so nothing downstream has to special-case a missing key.

### 3.4 Variant Coordinate Mapper

`variant_mapper.py` converts the HGVS coding variant into genomic coordinates by making a second, structurally identical call to the same VEP endpoint used in Section 3.3, independently re-resolving the canonical transcript rather than reusing the result already obtained one step earlier. This is the clearest architectural inefficiency in the current implementation, already flagged in Section 2, and it exists because the two modules were written as separate, narrowly scoped clients rather than as one shared annotation step.

### 3.5 ACMG-Inspired Evidence Engine

`acmg.py` is where the distance between "inspired by" and "compliant with" the ACMG/AMP guidelines matters most to state precisely. It implements five evidence functions, each returning a code, a strength, and a point contribution.

The first is not really an ACMG criterion — it is a small sanity check on HGVS validity, folded into the same scoring system for convenience, contributing a modest positive score when the input passed the Section 3.1 validator and a negative score otherwise.

The second is a PVS1-like loss-of-function check. If the Ensembl consequence is `frameshift_variant`, `stop_gained`, `stop_lost`, `start_lost`, `splice_acceptor_variant`, or `splice_donor_variant`, it receives the maximum "Very Strong" weight; `splice_region_variant` gets a smaller weight; missense, synonymous, and in-frame consequences get none. When Ensembl annotation is unavailable, this function falls back to the HGVS-derived variant type from Section 3.1 instead, at a reduced weight — a deliberate degradation rather than a failure, since a rough signal from the input string is better than none. Unlike the ClinGen SVI Working Group's published PVS1 recommendations [2], this implementation does not evaluate disease mechanism, domain position, or nonsense-mediated decay.

The third and fourth functions — PM2-like population-frequency reasoning and PP3-like computational-predictor reasoning — are fully implemented and correct in isolation, but not connected to the live application. PM2 expects a population-frequency interpretation of the kind `gnomad.py` is built to supply; PP3 tallies a damaging-versus-benign vote across REVEL [11], SIFT, PolyPhen, and AlphaMissense [12] fields. Because `app.py` never constructs the `gnomad` or `predictors` arguments these functions need, both return "Not Available" in the running system regardless of the input variant. This is not a bug in the functions themselves — it is a missing wire between two otherwise-working pieces.

The fifth function scores ClinVar-derived evidence, weighting a Pathogenic assertion more heavily when the review status indicates expert-panel review than when it indicates a single submitter, and weighting Benign assertions negatively. It is a simplified proxy for several more granular clinical-evidence criteria in the original guidelines (PS1, PP5, BP6), used here because ClinVar's public summary endpoint is the one clinical evidence source GEN can query without a paid key.

The five outputs are combined by counting how many reached "Met" status at each strength level and applying threshold rules that mirror the shape of the ACMG/AMP combining rules — two or more Very Strong criteria, for instance, or one Very Strong plus one Strong, are treated as sufficient for Pathogenic — without reproducing the guidelines' full combinatorial logic. Confidence (Low, Moderate, or High) comes from a separate count of "Met" criteria; since PM2 and PP3 are disconnected, this count is in practice bounded by at most two informative sources per submission.

### 3.6 Reasoning Engine

`reasoning.py` writes a short natural-language paragraph describing the variant's molecular consequence, separately from the criterion-by-criterion explanation `acmg.py` builds internally. Both modules match Ensembl consequence terms by substring rather than exact equality, since a single VEP response can report several comma-separated terms for one transcript. Using the same matching approach in both places keeps the narrative consistent with the score it is describing.

### 3.7 Gene Description Module

`gene_info.py` supplies a static, hand-written background paragraph for five genes — BRCA1, BRCA2, TP53, CFTR, and EGFR — chosen as common teaching examples in clinical genetics coursework. Anything else falls back to a generic description rather than an error, so the pipeline stays usable, in reduced form, for genes without curated text.

### 3.8 PDF Report Generation



`report_generator.py` assembles the same result data into an eleven-section PDF — cover page, executive summary, variant details, gene summary, molecular consequence, clinical evidence, ACMG evidence table, biological interpretation, confidence assessment, a rendered workflow diagram, and a disclaimer — using ReportLab's `platypus` flowables [13], a custom `Canvas` subclass for page numbering, and a custom `Flowable` that draws the workflow diagram directly instead of embedding a static image. The export route regenerates this document from the most recently completed request, held in a single in-memory variable rather than a persistent, per-session store, a design choice examined in Section 5.

---

## 4. Results

Given a gene symbol, an HGVS coding variant, and a genome build, GEN produces an HTML results page and, on request, an equivalent PDF.


The results page surfaces the outcome of every stage in Section 3: HGVS validity and detected variant type, the ClinVar record if one exists, the Ensembl annotation block, the genomic coordinate mapping, the full ACMG-inspired evidence table with each criterion's status and point contribution, the resulting classification and confidence, and the narrative paragraph. When GEN's classification is more conservative than ClinVar's reported significance — which happens in practice, since PM2 and PP3 contribute nothing in the live application — the page includes an explicit note explaining the gap rather than showing the lower classification without comment.

Only one part of this is guaranteed to be reproducible: variant-type detection, since it depends solely on the input string. Everything else reflects a live ClinVar or Ensembl response at request time, so the same input can, in principle, produce a different report months apart if either database entry changes. No accuracy, sensitivity, specificity, or benchmark figures are reported for GEN's classifications anywhere in this paper, because no curated gold-standard variant set was assembled and no comparison against expert-reviewed clinical calls was performed.

Table I traces the documented scoring rules from Section 3.5 against three well-characterized variants to show how a concrete input maps to a concrete output. These rows were worked out by hand from the rules described above, not captured from a live run against the APIs — they are demonstration examples, not a benchmark, and no claim about GEN's real-world accuracy follows from them.


| Variant | HGVS Valid | ClinVar Significance | VEP Consequence | ACMG Score | Final Classification |
|---|---|---|---|---|---|
| BRCA1 c.68_69delAG | Yes | Pathogenic (expert panel) | frameshift_variant | 95 / 100 | Pathogenic |
| CFTR c.1521_1523delCTT | Yes | Pathogenic (expert panel) | inframe_deletion | 65 / 100 | Likely Pathogenic |
| TP53 c.818G>A | Yes | Pathogenic (multiple submitters) | missense_variant | 55 / 100 | Likely Pathogenic |

The CFTR row is a useful illustration of a known behavior rather than an anomaly: because in-frame deletions receive no PVS1-like weight, the engine's score here falls short of what a Very Strong plus Strong combination would require for a Pathogenic call, even though ClinVar itself lists the variant as Pathogenic under expert-panel review. This is exactly the situation Section 3.5 describes GEN flagging with an explicit discrepancy note rather than silently under-reporting.

---

## 5. Discussion

GEN is not the first tool to sit between raw genomic databases and a variant classification, and it is worth being specific about where it does and does not add anything relative to what already exists. The ClinVar web interface is a browser for submitted assertions; it does not compute a classification of its own, only displays what has already been submitted. Ensembl VEP annotates molecular consequence but stops there — it has no concept of ACMG criteria or clinical significance. InterVar automates a much larger share of the ACMG/AMP criteria than GEN does and is widely used in research settings [14]. Commercial platforms such as Franklin integrate curated evidence from many more sources, including literature mining, and are built for laboratory workflows rather than teaching [15].

GEN does not compete with any of these on coverage or reliability. What it offers instead is legibility: every step between a submitted HGVS string and a final classification is a short, readable Python function a student can open, trace, and modify, rather than a service accessed as a black box. InterVar and Franklin are tools people use; GEN is closer to a worked example of how such a tool could be built, deliberately kept small enough to read in one sitting.

That legibility is also where most of the educational value sits. Several specific design decisions in this project — treating HGVS validity as an auxiliary score rather than a real ACMG criterion, falling back to string-derived variant type when Ensembl is unavailable, flagging discrepancies with ClinVar instead of hiding them — came directly from hitting cases the guidelines do not fully specify at implementation level. That gap between reading a standard and encoding it is not obvious until you try.

The limitations are substantial enough to restate plainly, since they are what stops GEN from being read as more than an implementation exercise. Only five of the roughly twenty-eight ACMG/AMP criteria are implemented, and even those five are considerably simplified relative to their published specifications. Two of the five — PM2 and PP3 — are fully coded but never receive the arguments they need from `app.py`, so they report as unavailable in every live request regardless of the variant submitted. Classification itself comes from threshold counting over strength categories rather than the full ACMG combining-rule matrix, and no functional assay, segregation, or de novo evidence category exists in the system at all.

The application also holds no per-user session state. A single in-memory variable stores the most recently completed result, which the PDF export route reads from — workable for one person exploring the tool locally, but two concurrent users on the same instance would see each other's most recent submission in their PDF downloads, and a process restart discards everything, since no database is used. `report_storage.py` already implements JSON-based persistence for exactly this purpose but is not yet called from the request path.

### Future Work

**Near-term.** No automated test suite exercises any part of the system, despite the HGVS validator and the ACMG evidence engine both being pure functions well suited to unit testing without network mocking. Adding a `pytest` suite, a GitHub Actions workflow to run it on every push, and a linter such as Ruff or Flake8 would raise the project's engineering maturity without changing its scope. Connecting the existing `gnomad.py` client so PM2 receives real population-frequency data is a similarly contained change, since the client itself already works correctly on its own.

**Medium-term.** Supplying PP3 with real predictor scores — REVEL or AlphaMissense values, or SpliceAI for a more principled splice estimate than the current substring match — would meaningfully strengthen the computational side of the engine. Replacing the shared in-memory result with session-based or database-backed storage, building on `report_storage.py`, would remove the concurrency issue above. Packaging the application with a Dockerfile would make the Render deployment reproducible elsewhere, and a documented REST API alongside the existing HTML interface would make the pipeline usable from other tools.

**Long-term.** Batch analysis from an uploaded VCF, rather than one gene-and-variant pair at a time, and coverage of a larger fraction of the ACMG/AMP criteria are the more ambitious extensions. Any claim of clinical utility would additionally require validating GEN's output against a curated, expert-reviewed dataset — a substantial undertaking in its own right, and one this paper does not attempt.

---

## 6. Conclusion

GEN integrates HGVS validation, live ClinVar and Ensembl VEP queries, coordinate mapping, a simplified ACMG-inspired evidence engine, and PDF reporting into one variant-interpretation pipeline. It is not a new interpretation method or a validated clinical system. Its contribution is a modular, publicly deployed implementation that makes the practical work of combining several genomic evidence sources readable, rather than treating interpretation as one opaque step — five criteria implemented honestly and legibly, instead of a larger number implemented as a black box.

The separation between data acquisition, scoring, and reporting kept the codebase approachable to build and should make individual pieces straightforward to test, replace, or extend on their own. The gaps documented here — a reduced criterion set, two evidence functions not yet connected, no session state, no automated tests — are a starting point for that extension rather than a final assessment.

GEN should not be used for clinical diagnosis or any medical decision-making, now or in any future version, without substantial additional validation. Its value is narrower and, hopefully, still useful: a concrete, inspectable example of how public genomic databases and a consensus interpretation framework can be assembled into working software.

---

## Software Availability

**Repository:**
https://github.com/s-sheryl/GEN---Genomic-Evidence-Navigator


**License:**
MIT

**Programming Language:**
Python 3

**Framework:**
Flask

---
Ethics Statement

GEN is intended exclusively for education, software engineering, and bioinformatics training. It is not designed, validated, or approved for clinical diagnosis or patient management. Any clinical interpretation of genetic variants should be performed by qualified professionals using validated diagnostic pipelines.

## References

[1] S. Richards, N. Aziz, S. Bale, D. Bick, S. Das, J. Gastier-Foster, W. W. Grody, M. Hegde, E. Lyon, E. Spector, K. Voelkerding, and H. L. Rehm, "Standards and guidelines for the interpretation of sequence variants: a joint consensus recommendation of the American College of Medical Genetics and Genomics and the Association for Molecular Pathology," *Genet. Med.*, vol. 17, no. 5, pp. 405–424, 2015.

[2] A. N. Abou Tayoun, T. Pesaran, M. T. DiStefano, et al., "Recommendations for interpreting the loss of function PVS1 ACMG/AMP variant criterion," *Hum. Mutat.*, vol. 39, no. 11, pp. 1517–1524, 2018.

[3] J. T. den Dunnen, R. Dalgleish, D. R. Maglott, R. K. Hart, M. S. Greenblatt, J. McGowan-Jordan, A.-F. Roux, T. Smith, S. E. Antonarakis, and P. E. M. Taschner, "HGVS Recommendations for the Description of Sequence Variants: 2016 Update," *Hum. Mutat.*, vol. 37, no. 6, pp. 564–569, 2016.

[4] HGVS Nomenclature Committee, "Sequence Variant Nomenclature," 2023. [Online]. Available: https://hgvs-nomenclature.org/

[5] M. J. Landrum, S. Chitipiralla, G. R. Brown, C. Chen, B. Gu, J. Hart, D. Hoffman, W. Jang, K. Karapetyan, K. Katz, C. Liu, Z. Maddipatla, A. Malheiro, K. McDaniel, M. Ovetsky, G. Riley, G. Zhou, B. L. Holmes, P. Kattman, and D. R. Maglott, "ClinVar: improving access to variant interpretations and supporting evidence," *Nucleic Acids Res.*, vol. 46, no. D1, pp. D1062–D1067, 2018.

[6] W. McLaren, L. Gil, S. E. Hunt, H. S. Riat, G. R. S. Ritchie, A. Thormann, P. Flicek, and F. Cunningham, "The Ensembl Variant Effect Predictor," *Genome Biol.*, vol. 17, art. no. 122, 2016.

[7] F. Cunningham, J. E. Allen, J. Allen, et al., "Ensembl 2022," *Nucleic Acids Res.*, vol. 50, no. D1, pp. D988–D995, 2022.

[8] K. J. Karczewski, L. C. Francioli, G. Tiao, et al., "The mutational constraint spectrum quantified from variation in 141,456 humans," *Nature*, vol. 581, pp. 434–443, 2020.

[9] Pallets Projects, "Flask Documentation," 2023. [Online]. Available: https://flask.palletsprojects.com/

[10] National Center for Biotechnology Information, "Entrez Programming Utilities Help," 2023. [Online]. Available: https://www.ncbi.nlm.nih.gov/books/NBK25501/

[11] N. M. Ioannidis, J. H. Rothstein, V. Pejaver, et al., "REVEL: An Ensemble Method for Predicting the Pathogenicity of Rare Missense Variants," *Am. J. Hum. Genet.*, vol. 99, no. 4, pp. 877–885, 2016.

[12] J. Cheng, G. Novati, J. Pan, et al., "Accurate proteome-wide missense variant effect prediction with AlphaMissense," *Science*, vol. 381, no. 6664, eadg7492, 2023.

[13] ReportLab, "ReportLab PDF Toolkit Documentation," 2023. [Online]. Available: https://docs.reportlab.com/

[14] Q. Li and K. Wang, "InterVar: Clinical Interpretation of Genetic Variants by the 2015 ACMG-AMP Guidelines," *Am. J. Hum. Genet.*, vol. 100, no. 2, pp. 267–280, 2017.

[15] Genoox, "Franklin by Genoox," 2023. [Online]. Available: https://franklin.genoox.com/
