# utils/gene_info.py

def get_gene_description(gene):

    descriptions = {

        "BRCA1": (
            "BRCA1 is a tumor suppressor gene involved in homologous "
            "recombination DNA repair. Pathogenic variants increase the "
            "risk of hereditary breast and ovarian cancer."
        ),

        "BRCA2": (
            "BRCA2 is a tumor suppressor gene involved in homologous "
            "recombination DNA repair and maintenance of genomic stability. "
            "Pathogenic variants are associated with hereditary breast, "
            "ovarian, pancreatic, and prostate cancers."
        ),

        "TP53": (
            "TP53 encodes the p53 tumor suppressor protein, a key regulator "
            "of cell-cycle arrest, apoptosis, DNA repair, and genomic "
            "stability. Pathogenic variants cause Li-Fraumeni syndrome."
        ),

        "CFTR": (
            "CFTR encodes a chloride ion channel responsible for epithelial "
            "salt and water transport. Pathogenic variants cause cystic fibrosis."
        ),

        "EGFR": (
            "EGFR encodes the Epidermal Growth Factor Receptor, a receptor "
            "tyrosine kinase that regulates cell proliferation and survival. "
            "Activating variants are frequently observed in lung cancer and "
            "other solid tumors."
        ),

        "HBB": (
            "HBB encodes the beta-globin subunit of adult hemoglobin. "
            "Pathogenic variants are associated with beta-thalassemia, "
            "sickle cell disease, and other structural hemoglobin disorders."
        ),

        "F8": (
            "F8 encodes coagulation factor VIII. Pathogenic variants cause "
            "Hemophilia A."
        ),

        "F9": (
    "F9 encodes coagulation factor IX. Pathogenic variants cause "
    "Hemophilia B."
),
         "LDLR": (
    "LDLR encodes the low-density lipoprotein receptor responsible "
    "for cholesterol uptake. Variants cause familial "
    "hypercholesterolemia."
),
        "APOE": (
    "APOE encodes apolipoprotein E, a lipid transport protein. "
    "Specific alleles influence Alzheimer's disease risk."
), 
        

        "APC": (
            "APC is a tumor suppressor gene involved in regulation of the "
            "Wnt signaling pathway. Pathogenic variants cause Familial "
            "Adenomatous Polyposis (FAP)."
        ),

        "MLH1": (
            "MLH1 encodes a DNA mismatch repair protein. Pathogenic variants "
            "are associated with Lynch syndrome and hereditary colorectal cancer."
        ),

        "MSH2": (
            "MSH2 encodes a DNA mismatch repair protein essential for genomic "
            "stability. Pathogenic variants are associated with Lynch syndrome."
        ),

        "MSH6": (
    "MSH6 is a mismatch repair gene involved in maintaining genomic "
    "stability. Variants contribute to Lynch syndrome."
),
        "PMS2": (
    "PMS2 is a DNA mismatch repair gene. Pathogenic variants increase "
    "the risk of hereditary colorectal cancer."
),
        "PALB2": (
    "PALB2 partners with BRCA2 during homologous recombination DNA "
    "repair. Variants increase breast cancer risk."
),
        "ATM": (
    "ATM encodes a protein kinase that responds to DNA damage. "
    "Pathogenic variants increase susceptibility to several cancers."
),
        "KRAS": (
    "KRAS encodes a small GTPase involved in cellular signaling. "
    "Somatic mutations are common in colorectal, pancreatic and lung "
    "cancers."
),
        "NRAS": (
    "NRAS encodes a signaling GTPase involved in cell proliferation. "
    "Mutations occur in melanoma and hematological malignancies."
),
       "BRAF": (
    "BRAF encodes a serine/threonine protein kinase involved in the "
    "MAPK signaling pathway. Variants are common in melanoma and "
    "thyroid cancer."
),
        "RET": (
    "RET encodes a receptor tyrosine kinase involved in neural crest "
    "development. Pathogenic variants cause multiple endocrine "
    "neoplasia type 2."
),

        "PIK3CA": (
    "PIK3CA encodes the catalytic subunit of phosphatidylinositol "
    "3-kinase. Activating variants are frequent in many cancers."
),
       "ALK": (
    "ALK encodes a receptor tyrosine kinase. Gene rearrangements and "
    "mutations are important therapeutic targets in lung cancer."
),
        "ROS1": (
    "ROS1 encodes a receptor tyrosine kinase involved in cellular "
    "growth signaling. Gene fusions are clinically actionable in "
    "non-small cell lung cancer."
),

        "PTEN": (
            "PTEN is a tumor suppressor gene that negatively regulates the "
            "PI3K/AKT signaling pathway. Pathogenic variants are associated "
            "with Cowden syndrome and multiple cancers."
        )

    }

    return descriptions.get(
        gene.upper(),
        (
            f"{gene.upper()} is a protein-coding gene. "
            "A curated biological description is not yet available in "
            "the local knowledge base."
        )
    )