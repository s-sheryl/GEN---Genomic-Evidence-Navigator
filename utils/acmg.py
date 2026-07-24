"""
utils/acmg.py

Educational ACMG-inspired variant interpretation engine.

This implementation is designed for educational and portfolio use.
It is NOT a clinical ACMG implementation.
"""

from typing import Dict, Any, List, Optional, Tuple

# ==========================================================
# Constants
# ==========================================================

EvidenceTuple = Tuple[
    str,   # code
    str,   # strength
    str,   # source
    int,   # points
    str,   # status
    str    # explanation
]

PATHOGENIC_STRENGTHS = {
    "Very Strong": 4,
    "Strong": 3,
    "Moderate": 2,
    "Supporting": 1
}

BENIGN_STRENGTHS = {
    "Strong Benign",
    "Supporting Benign"
}


# ==========================================================
# Evidence Helper
# ==========================================================

def _add_evidence(
    evidence: List[Dict[str, Any]],
    code: str,
    strength: str,
    source: str,
    points: int,
    status: str,
    explanation: str
) -> int:
    """
    Stores one ACMG evidence record.
    """

    evidence.append(
        {
            "code": code,
            "strength": strength,
            "source": source,
            "points": points,
            "status": status,
            "explanation": explanation,
        }
    )

    return points


# ==========================================================
# HGVS Validation
# ==========================================================

def _hgvs_evidence(
    hgvs_valid: Optional[bool]
) -> EvidenceTuple:

    if hgvs_valid is None:

        return (
            "HGVS",
            "Not Assessed",
            "HGVS Validator",
            0,
            "Not Assessed",
            "HGVS validation was not performed."
        )

    if hgvs_valid:

        return (
            "HGVS",
            "Supporting",
            "HGVS Validator",
            5,
            "Met",
            "Variant follows HGVS nomenclature."
        )

    return (
        "HGVS",
        "Contradicting",
        "HGVS Validator",
        -10,
        "Not Met",
        "Variant does not follow HGVS nomenclature."
    )


# ==========================================================
# PVS1
# ==========================================================

def _pvs1_evidence(
    variant_type: str,
    ensembl: Optional[Dict[str, Any]]
) -> EvidenceTuple:
    """
    Evaluate loss-of-function evidence using
    Ensembl consequence first.
    """

    consequence = ""

    if ensembl:

        consequence = (
            ensembl.get("consequence", "")
            .strip()
            .lower()
        )

    # Canonical loss-of-function variants

    lof_terms = [

        "frameshift_variant",

        "stop_gained",

        "stop_lost",

        "start_lost",

        "splice_acceptor_variant",

        "splice_donor_variant"

    ]

    if any(term in consequence for term in lof_terms):

        return (

            "PVS1",

            "Very Strong",

            "Ensembl",

            30,

            "Met",

            f"Predicted loss-of-function ({consequence})."

        )

    # Splice region

    if "splice_region_variant" in consequence:

        return (

            "PVS1",

            "Supporting",

            "Ensembl",

            5,

            "Met",

            "Variant occurs in splice region."

        )

    # Missense

    if "missense_variant" in consequence:

        return (

            "PVS1",

            "Not Applicable",

            "Ensembl",

            0,

            "Not Applicable",

            "Missense variants do not satisfy PVS1."

        )

    # Synonymous

    if "synonymous_variant" in consequence:

        return (

            "PVS1",

            "Not Applicable",

            "Ensembl",

            0,

            "Not Applicable",

            "Synonymous variants do not satisfy PVS1."

        )

    # In-frame

    if (
        "inframe_deletion" in consequence
        or
        "inframe_insertion" in consequence
    ):

        return (

            "PVS1",

            "Not Applicable",

            "Ensembl",

            0,

            "Not Applicable",

            "In-frame variants are not automatically loss-of-function."

        )

    # ----------------------------------------------------
    # Fallback
    # ----------------------------------------------------

    if variant_type in [

        "Frameshift deletion",

        "Frameshift duplication",

        "Frameshift insertion",

        "Splice variant"

    ]:

        return (

            "PVS1",

            "Strong",

            "Variant Type",

            20,

            "Met",

            "Loss-of-function inferred from variant type."

        )

    return (

        "PVS1",

        "Not Met",

        "Variant Type",

        0,

        "Not Met",

        "No evidence for PVS1."

    )
# ==========================================================
# PM2
# ==========================================================

def _pm2_evidence(
    gnomad: Optional[Dict[str, Any]]
) -> EvidenceTuple:

    if not gnomad:

        return (
            "PM2",
            "Not Available",
            "gnomAD",
            0,
            "Not Available",
            "Population frequency unavailable."
        )

    interpretation = (
        gnomad.get("interpretation", "")
        .lower()
    )

    if "absent" in interpretation:

        return (
            "PM2",
            "Supporting",
            "gnomAD",
            10,
            "Met",
            "Variant absent from population databases."
        )

    if "rare" in interpretation:

        return (
            "PM2",
            "Supporting",
            "gnomAD",
            10,
            "Met",
            "Variant is extremely rare."
        )

    if "common" in interpretation:

        return (
            "PM2",
            "Not Applicable",
            "gnomAD",
            0,
            "Not Met",
            "Variant is common in the general population."
        )

    return (

        "PM2",

        "Not Applicable",

        "gnomAD",

        0,

        "Not Applicable",

        "Population evidence unavailable."

    )


# ==========================================================
# PP3
# ==========================================================

def _pp3_evidence(
    predictors: Optional[Dict[str, Any]]
) -> EvidenceTuple:

    if not predictors:

        return (
            "PP3",
            "Not Available",
            "Predictors",
            0,
            "Not Available",
            "Computational predictors unavailable."
        )

    damaging = 0
    benign = 0

    revel = predictors.get("revel")

    if revel is not None:

        try:

            revel = float(revel)

            if revel >= 0.7:
                damaging += 1
            else:
                benign += 1

        except ValueError:
            pass

    sift = (
        predictors.get("sift", "")
        .lower()
    )

    if "deleterious" in sift:
        damaging += 1

    elif "tolerated" in sift:
        benign += 1

    polyphen = (
        predictors.get("polyphen", "")
        .lower()
    )

    if "damaging" in polyphen:
        damaging += 1

    elif "benign" in polyphen:
        benign += 1

    alphamissense = (
        predictors.get("alphamissense", "")
        .lower()
    )

    if "pathogenic" in alphamissense:
        damaging += 1

    elif "benign" in alphamissense:
        benign += 1

    if damaging > benign:

        return (

            "PP3",

            "Supporting",

            "Predictors",

            10,

            "Met",

            "Majority of computational predictors suggest pathogenicity."

        )

    if benign > damaging:

        return (

            "PP3",

            "Not Applicable",

            "Predictors",

            0,

            "Not Met",

            "Majority of computational predictors suggest benign effect."

        )

    return (

        "PP3",

        "Not Applicable",

        "Predictors",

        0,

        "Not Applicable",

        "Computational predictions are inconclusive."

    )


# ==========================================================
# ClinVar
# ==========================================================

def _clinvar_evidence(
    clinvar: Optional[Dict[str, Any]]
) -> EvidenceTuple:

    if not clinvar:

        return (

            "ClinVar",

            "Not Available",

            "ClinVar",

            0,

            "Not Available",

            "ClinVar data unavailable."

        )

    significance = (

        clinvar.get(
            "clinical_significance",
            ""
        ).lower()

    )

    review = (

        clinvar.get(
            "review_status",
            ""
        ).lower()

    )

    if "pathogenic" in significance:

        if "expert panel" in review:

            return (

                "ClinVar",

                "Very Strong",

                "ClinVar",

                60,

                "Met",

                "ClinVar Expert Panel classified the variant as pathogenic."

            )

        if "multiple" in review:

            return (

                "ClinVar",

                "Strong",

                "ClinVar",

                50,

                "Met",

                "Multiple submitters classify the variant as pathogenic."

            )

        return (

            "ClinVar",

            "Moderate",

            "ClinVar",

            35,

            "Met",

            "ClinVar reports pathogenic."

        )

    if "benign" in significance:

        return (

            "ClinVar",

            "Strong Benign",

            "ClinVar",

            -30,

            "Met",

            "ClinVar reports benign."

        )

    return (

        "ClinVar",

        "Not Applicable",

        "ClinVar",

        0,

        "Not Applicable",

        "ClinVar does not provide strong evidence."

    )
# ==========================================================
# Classification
# ==========================================================

def _determine_classification(evidence):

    very_strong = 0
    strong = 0
    moderate = 0
    supporting = 0
    benign = False

    for item in evidence:

        if item["status"] != "Met":
            continue

        strength = item["strength"]

        if strength in BENIGN_STRENGTHS:
            benign = True
            continue

        if strength == "Very Strong":
            very_strong += 1

        elif strength == "Strong":
            strong += 1

        elif strength == "Moderate":
            moderate += 1

        elif strength == "Supporting":
            supporting += 1

    if (
        very_strong >= 2
        or (very_strong >= 1 and strong >= 1)
        or (very_strong >= 1 and moderate >= 2)
    ):
        return "Pathogenic"

    if (
        very_strong >= 1
        or strong >= 1
        or moderate >= 2
        or (moderate >= 1 and supporting >= 1)
        or supporting >= 2
    ):
        return "Likely Pathogenic"

    if benign:
        return "Likely Benign"

    return "Variant of Uncertain Significance"


# ==========================================================
# Confidence
# ==========================================================

def _determine_confidence(evidence):

    met = sum(
        1 for item in evidence
        if item["status"] == "Met"
    )

    if met >= 4:
        return "High"

    if met >= 2:
        return "Moderate"

    return "Low"


# ==========================================================
# Reasoning
# ==========================================================

def _build_reasoning(
    evidence,
    classification,
    score,
    confidence
):

    paragraphs = []

    for item in evidence:

        paragraphs.append(
            f"{item['code']} ({item['strength']}): "
            f"{item['explanation']}"
        )

    paragraphs.append("")

    paragraphs.append(
        f"Overall ACMG-inspired classification: {classification}."
    )

    paragraphs.append(
        f"Confidence: {confidence}."
    )

    paragraphs.append(
        f"Visualization score: {score}/100."
    )

    paragraphs.append(
        "This interpretation is educational and should not be "
        "used for clinical decision making."
    )

    return "\n\n".join(paragraphs)


# ==========================================================
# Main ACMG Engine
# ==========================================================

def calculate_acmg_evidence(
    variant_type,
    clinvar,
    ensembl=None,
    hgvs_valid=None,
    gnomad=None,
    predictors=None
):

    evidence = []

    score = 0

    helpers = [

        _hgvs_evidence(hgvs_valid),

        _pvs1_evidence(
            variant_type,
            ensembl
        ),

        _pm2_evidence(
            gnomad
        ),

        _pp3_evidence(
            predictors
        ),

        _clinvar_evidence(
            clinvar
        )

    ]

    for item in helpers:

        score += _add_evidence(
            evidence,
            *item
        )

    score = max(0, min(score, 100))

    classification = _determine_classification(
        evidence
    )

    confidence = _determine_confidence(
        evidence
    )

    reasoning = _build_reasoning(
        evidence,
        classification,
        score,
        confidence
    )

    return {

        "classification": classification,

        "score": score,

        "confidence": confidence,

        "evidence": evidence,

        "reasoning": reasoning,

        "note": (
            "Educational ACMG-inspired classification. "
            "Not for clinical diagnosis."
        )

    }


# ==========================================================
# Evidence Object
# ==========================================================

class ACMGEvidence:

    def __init__(
        self,
        code,
        strength,
        source,
        points,
        status,
        explanation
    ):

        self.code = code
        self.strength = strength
        self.source = source
        self.points = points
        self.status = status
        self.explanation = explanation

    def to_dict(self):

        return {

            "code": self.code,

            "strength": self.strength,

            "source": self.source,

            "points": self.points,

            "status": self.status,

            "explanation": self.explanation

        }