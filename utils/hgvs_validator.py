def validate_hgvs(gene, variant):
    """
    Educational HGVS validator.

    Returns
    -------
    {
        "status": "Valid" | "Partially Valid" | "Invalid",
        "message": str
    }
    """

    if not variant:
        return {
            "status": "Invalid",
            "message": "No HGVS variant provided."
        }

    if variant.startswith(("c.", "g.", "p.", "n.", "m.")):
        return {
            "status": "Partially Valid",
            "message": (
                "Variant follows HGVS syntax but does not include a "
                "reference transcript accession."
            )
        }

    if ":" in variant and "NM_" in variant:
        return {
            "status": "Valid",
            "message": "Transcript-based HGVS expression detected."
        }

    return {
        "status": "Invalid",
        "message": "Variant does not resemble a valid HGVS expression."
    }