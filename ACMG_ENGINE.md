# ACMG-inspired Evidence Engine

## Overview

This project contains an educational implementation inspired by the ACMG/AMP 2015 guidelines.

It is **not** a clinical implementation.

---

## Implemented Criteria

| Criterion | Status |
|------------|--------|
| HGVS Validation | ✔ |
| ClinVar | ✔ |
| PVS1 Approximation | ✔ |
| PM2 | Implemented but inactive |
| PP3 | Implemented but inactive |

---

## Scoring

Evidence contributes points toward an overall score.

The score is converted into

- Benign
- Likely Benign
- Uncertain Significance
- Likely Pathogenic
- Pathogenic

using simplified thresholds.

---

## Why simplified?

The complete ACMG framework contains

- ~28 evidence codes
- complex combining rules
- gene-specific refinements

Implementing the entire specification would require substantially more clinical evidence than is available in this educational project.

---

## Disclaimer

This scoring engine should never be used for clinical interpretation.
