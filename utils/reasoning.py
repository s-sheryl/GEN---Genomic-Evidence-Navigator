"""
utils/reasoning.py

Generates a scientific, plain-language narrative explaining WHY the
ACMG-inspired classification was reached. This is deliberately
separate from `acmg["reasoning"]` (built inside utils/acmg.py), which
walks through each evidence code in turn -- this module instead
produces a shorter, gene/biology-focused summary intended to be read
alongside, not instead of, the evidence-level narrative.

Educational use only.
"""


def generate_reasoning(
    gene,
    variant,
    variant_type,
    clinvar,
    ensembl,
    acmg
):
    """
    Generate a scientific narrative explaining WHY the ACMG-inspired
    classification was reached.

    This function intentionally avoids repeating information already
    displayed elsewhere in the report. Instead, it summarizes the
    biological significance and explains how the available evidence
    contributed to the final interpretation.

    Consequence matching uses substring checks (`term in consequence`)
    rather than exact equality, because utils/ensembl.py may return
    multiple comma-separated consequence terms for a single transcript
    (e.g. "frameshift_variant, NMD_transcript_variant"). This mirrors
    the matching approach used in utils/acmg.py's _pvs1_evidence(), so
    this narrative stays consistent with the score it is explaining.

    Educational use only.
    """

    reasoning = []

    # ----------------------------------------------------------
    # Extract data
    # ----------------------------------------------------------

    classification = acmg.get("classification", "Unavailable")
    score = acmg.get("score", "N/A")
    confidence = acmg.get("confidence", "Unknown")

    significance = clinvar.get("clinical_significance", "")
    review_status = clinvar.get("review_status", "")

    consequence = (ensembl.get("consequence") or "").lower()
    protein = ensembl.get("protein_change", "")
    transcript = ensembl.get("transcript", "")
    chromosome = ensembl.get("chromosome", "")

# ----------------------------------------------------------
# Gene / Variant overview
# ----------------------------------------------------------

    if transcript:

     reasoning.append(

        f"The variant is located within the {gene} gene on chromosome "
        f"{chromosome} and is annotated on transcript {transcript}. "
        f"It is described as {variant_type.lower()}."

    )
    # ----------------------------------------------------------
    # Overall conclusion
    # ----------------------------------------------------------

    reasoning.append(
    f"The submitted variant {gene}:{variant} was evaluated using "
    "multiple publicly available genomic resources including "
    "Ensembl, ClinVar, HGVS validation and the educational "
    "ACMG-inspired evidence engine."
)

    # ----------------------------------------------------------
    # ClinVar contribution
    # ----------------------------------------------------------

    if significance:

        sentence = (
            f"This interpretation is primarily supported by the "
            f"ClinVar clinical significance of '{significance}'."
        )

        if review_status:
            sentence += (
                f" The available record has a review status of "
                f"'{review_status}', providing additional confidence "
                f"in the submitted interpretation."
            )

        reasoning.append(sentence)

    # ----------------------------------------------------------
    # Molecular consequence
    #
    # Ordered from most to least specific/severe, and matched with
    # `in` rather than `==` since `consequence` may contain multiple
    # comma-separated terms. The first matching branch wins.
    # ----------------------------------------------------------

    if consequence:

        if "frameshift_variant" in consequence:

            reasoning.append(
                "Ensembl predicts a frameshift variant. "
                "Frameshift variants alter the reading frame and often "
                "introduce premature stop codons, which may produce a "
                "truncated or non-functional protein. Under this "
                "simplified ACMG-inspired framework, this supports "
                "loss-of-function evidence (PVS1-like)."
            )

        elif "stop_gained" in consequence:

            reasoning.append(
                "Ensembl predicts a stop-gained variant. "
                "Premature termination codons can truncate the encoded "
                "protein or trigger nonsense-mediated mRNA decay, making "
                "this consistent with a loss-of-function mechanism."
            )

        elif "splice_acceptor_variant" in consequence or "splice_donor_variant" in consequence:

            reasoning.append(
                "Ensembl predicts a canonical splice-site variant. "
                "Disruption of the splice acceptor or donor sequence "
                "commonly causes exon skipping or intron retention, "
                "frequently producing an abnormal transcript and protein "
                "and making this consistent with a loss-of-function "
                "mechanism (PVS1-like)."
            )

        elif "stop_lost" in consequence:

            reasoning.append(
                "Ensembl predicts a stop-loss variant. "
                "Loss of the normal termination codon causes translation "
                "to continue into the normally untranslated region, "
                "producing an abnormally extended protein whose added "
                "sequence may interfere with folding or function."
            )

        elif "missense_variant" in consequence:

            reasoning.append(
                "Ensembl predicts a missense variant. "
                "Missense substitutions alter a single amino acid but "
                "their biological impact depends on the affected residue "
                "and protein domain. Additional functional or "
                "computational evidence would normally be required."
            )

        elif "synonymous_variant" in consequence:

            reasoning.append(
                "Ensembl predicts a synonymous variant. "
                "Although synonymous variants do not change the amino "
                "acid sequence, some may influence RNA splicing or gene "
                "expression. No pathogenic evidence is assigned under "
                "this simplified model."
            )

        elif "inframe_deletion" in consequence:

            reasoning.append(
                "Ensembl predicts an in-frame deletion. "
                "Unlike frameshift variants, the reading frame remains "
                "intact. However, deletion of one or more amino acids "
                f"(observed here as {protein}) may still disrupt protein "
                "structure or function depending on the affected region. "
                "For this reason, the simplified ACMG-inspired engine "
                "does not automatically award PVS1-like evidence."
            )

        elif "inframe_insertion" in consequence:

            reasoning.append(
                "Ensembl predicts an in-frame insertion. "
                "The reading frame is preserved, although insertion of "
                "additional amino acids may alter protein structure or "
                "function depending on the affected region."
            )

        else:

            reasoning.append(
                f"Ensembl predicts the molecular consequence "
                f"'{consequence.replace('_', ' ')}'. "
                "This consequence is reported for completeness but is "
                "not specifically weighted by the simplified ACMG-inspired "
                "evidence engine."
            )

    # ----------------------------------------------------------
    # Final interpretation
    # ----------------------------------------------------------

    reasoning.append(

    f"Based on the currently available evidence, this educational "
    f"ACMG-inspired framework classifies the variant as "
    f"{classification}."

)

    if classification == "Variant of Uncertain Significance":

     reasoning.append(

        "The currently available evidence is insufficient to support "
        "either a pathogenic or benign interpretation. Additional "
        "population frequency data, computational prediction scores, "
        "functional assays and segregation studies would improve "
        "confidence in future analyses."

    )

    elif classification == "Likely Pathogenic":

     reasoning.append(

        "The available evidence supports a likely pathogenic "
        "interpretation, although additional clinical and functional "
        "evidence would further strengthen confidence."

    )

    elif classification == "Pathogenic":

     reasoning.append(

        "Multiple independent lines of evidence consistently support "
        "a pathogenic interpretation."

    )

    elif classification == "Likely Benign":

     reasoning.append(

        "The currently available evidence suggests the variant is "
        "unlikely to contribute to disease."

    )

    reasoning.append(

    "This report is intended exclusively for educational and research "
    "purposes and must not be used for clinical diagnosis or medical "
    "decision making."

)

    return "\n\n".join(reasoning)
