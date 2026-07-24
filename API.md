# External APIs

GEN integrates several public biological databases.

---

## ClinVar

Purpose

Clinical significance

API

NCBI E-utilities

Documentation

https://www.ncbi.nlm.nih.gov/books/NBK25501/

---

## Ensembl REST

Purpose

Variant annotation

Documentation

https://rest.ensembl.org

---

## gnomAD

Purpose

Population frequency

Current Status

Implemented but not connected to the live workflow.

---

## Network Failure Handling

Every external request is wrapped in exception handling.

Failures return

```
Not Available
```

instead of crashing the application.
