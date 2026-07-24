# Variant Interpretation Pipeline

## Overview

GEN (Genomic Evidence Navigator) follows a modular variant interpretation workflow that integrates HGVS validation, external genomic databases, an ACMG-inspired evidence engine, and automated report generation.

The objective is to demonstrate how independent evidence sources can be combined into a transparent computational genomics workflow.

---

## Pipeline

```
User Input
    │
    ▼
HGVS Validation
    │
    ▼
ClinVar Retrieval
    │
    ▼
Ensembl VEP Annotation
    │
    ▼
Genomic Coordinate Mapping
    │
    ▼
ACMG-inspired Evidence Engine
    │
    ▼
Biological Interpretation
    │
    ▼
Scientific Report
    │
    ▼
PDF Export
```

---

## Step 1 — HGVS Validation

Module

```
utils/variant_utils.py
```

Responsibilities

- Validate HGVS coding notation
- Detect variant type
- Reject malformed variants
- Generate human-readable descriptions

---

## Step 2 — ClinVar

Module

```
utils/clinvar.py
```

Queries

NCBI E-utilities

Returns

- Clinical significance
- Review status
- Associated conditions

---

## Step 3 — Ensembl

Module

```
utils/ensembl.py
```

Queries

Ensembl REST API

Returns

- Canonical transcript
- Protein change
- Consequence
- Exon
- Impact
- SIFT
- PolyPhen

---

## Step 4 — Variant Mapping

Module

```
utils/variant_mapper.py
```

Maps

- chromosome
- genomic coordinate
- reference allele
- alternate allele

---

## Step 5 — ACMG Engine

Module

```
utils/acmg.py
```

Current evidence

- HGVS validation
- ClinVar
- PVS1 approximation

Implemented but inactive

- PM2
- PP3

---

## Step 6 — Narrative Generation

Module

```
utils/reasoning.py
```

Produces

- biological explanation
- interpretation summary
- confidence statement

---

## Step 7 — Report Generation

Module

```
utils/report_generator.py
```

Generates

- HTML report
- PDF report
