from utils.acmg import calculate_acmg_evidence


variant_type = "Deletion"


clinvar = {

    "clinical_significance": "Pathogenic"

}


gnomad = {

    "interpretation": "Rare variant"

}


result = calculate_acmg_evidence(
    variant_type,
    clinvar,
    gnomad
)


print(result)