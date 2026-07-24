import re





def validate_hgvs(variant):

    pattern = (
    # Coding SNV
    r"^c\.\d+[A-Z]>[A-Z]$|"

    # Intronic SNV
    r"^c\.\d+[+-]\d+[A-Z]>[A-Z]$|"

    # UTR
    r"^c\.\*\d+[A-Z]>[A-Z]$|"
    r"^c\.\-\d+[A-Z]>[A-Z]$|"

    # Range deletion
    r"^c\.\d+_\d+del[A-Z]*$|"

    # Single deletion
    r"^c\.\d+del[A-Z]*$|"

    # Duplication
    r"^c\.\d+dup[A-Z]*$|"
    r"^c\.\d+_\d+dup[A-Z]*$|"

    # Insertion
    r"^c\.\d+ins[A-Z]+$|"
    r"^c\.\d+_\d+ins[A-Z]+$|"

    # Delins
    r"^c\.\d+_\d+delins[A-Z]+$"
)


    



    return bool(
        re.match(
            pattern,
            variant
        )
    )







import re

def determine_variant_type(variant):
    """
    Determine the biological variant type from HGVS notation.

    Examples
    --------
    c.5946delT            -> Frameshift deletion
    c.1852_1854delAAG     -> In-frame deletion
    c.68_69delAG          -> Frameshift deletion
    c.123dupA             -> Frameshift duplication
    c.123_125dupATG       -> In-frame duplication
    c.123_124insA         -> Frameshift insertion
    c.123_124insATG       -> In-frame insertion
    """

    # ----------------------------
    # Deletion-Insertion
    # ----------------------------
    if "delins" in variant:
        return "Deletion-Insertion"

    # ----------------------------
    # Deletion
    # ----------------------------
    if "del" in variant:

        match = re.search(r"del([A-Z]+)$", variant)

        if match:
            deleted = match.group(1)

            if len(deleted) % 3 == 0:
                return "In-frame deletion"
            else:
                return "Frameshift deletion"

        return "Deletion"

    # ----------------------------
    # Duplication
    # ----------------------------
    if "dup" in variant:

        match = re.search(r"dup([A-Z]+)$", variant)

        if match:
            duplicated = match.group(1)

            if len(duplicated) % 3 == 0:
                return "In-frame duplication"
            else:
                return "Frameshift duplication"

        return "Duplication"

    # ----------------------------
    # Insertion
    # ----------------------------
    if "ins" in variant:

        match = re.search(r"ins([A-Z]+)$", variant)

        if match:
            inserted = match.group(1)

            if len(inserted) % 3 == 0:
                return "In-frame insertion"
            else:
                return "Frameshift insertion"

        return "Insertion"

    # ----------------------------
    # SNV
    # ----------------------------
    if re.search(r"[+-]\d+[A-Z]>[A-Z]", variant):
     return "Splice variant"

    if ">" in variant:
     return "Substitution"
    return "Unknown"


def preliminary_interpretation(variant_type):
    """
    Return a brief biological interpretation based on the detected
    variant type.
    """

    descriptions = {

        "Frameshift deletion":
        "Frameshift deletions disrupt the reading frame and frequently produce a truncated or non-functional protein.",

        "In-frame deletion":
        "An in-frame deletion removes one or more amino acids while preserving the reading frame. Functional impact depends on the affected protein region.",

        "Frameshift duplication":
        "Frameshift duplications alter the reading frame and often result in premature protein truncation.",

        "In-frame duplication":
        "An in-frame duplication adds amino acids without disrupting the reading frame. Functional impact depends on the duplicated region.",

        "Frameshift insertion":
        "Frameshift insertions disrupt the reading frame and are often associated with loss of protein function.",

        "In-frame insertion":
        "An in-frame insertion adds amino acids while preserving the reading frame. Functional impact depends on the protein context.",

        "Deletion-Insertion":
        "A complex deletion-insertion variant replaces one sequence with another. Functional consequences depend on the exact sequence change.",

        "Deletion":
        "A deletion variant was detected. Its biological impact depends on the number of deleted nucleotides and the affected region.",

        "Insertion":
        "An insertion variant was detected. Its biological impact depends on the inserted sequence and whether the reading frame is preserved.",

        "Duplication":
        "A duplication variant was detected. Functional impact depends on the size and location of the duplicated sequence.",

        "Substitution":
        "A single nucleotide substitution was detected. Additional clinical and functional evidence is required to determine its biological significance.",
        
        "Splice variant":
        "Variants affecting splice donor or splice acceptor regions may alter normal RNA splicing, potentially resulting in exon skipping, intron retention, or abnormal transcripts. Functional studies are often required to determine their biological impact.",
        
        "Unknown":
        "The variant type could not be determined from the supplied HGVS notation."
    }

    return descriptions.get(
        variant_type,
        "No interpretation available."
    )