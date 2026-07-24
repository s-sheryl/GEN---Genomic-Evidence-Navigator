from utils.report_storage import save_report
from flask import Flask, render_template, request, send_file
import tempfile
from utils.gene_info import get_gene_description

from utils.variant_utils import (
    validate_hgvs,
    determine_variant_type,
    preliminary_interpretation
)

from utils.clinvar import get_clinvar_data
from utils.ensembl import get_ensembl_annotation
from utils.variant_mapper import convert_hgvs_to_genomic
from utils.acmg import calculate_acmg_evidence
from utils.reasoning import generate_reasoning
from utils.report_generator import generate_pdf_report


app = Flask(__name__)

# Stores the latest interpretation so the PDF route can
# generate the report that matches the displayed results.
LATEST_RESULT = None


# ---------------------------------------------------
# Home
# ---------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------------------------------------------
# Interpret Page
# ---------------------------------------------------

@app.route("/interpret")
def interpret():
    return render_template("interpret.html")


# ---------------------------------------------------
# Results
# ---------------------------------------------------

@app.route("/results", methods=["GET", "POST"])
def results():

    global LATEST_RESULT
    report_id = None

    if request.method == "POST":

        gene = request.form.get("gene", "").strip()
        variant = request.form.get("variant", "").strip()
        genome_build = request.form.get("genome_build", "GRCh38")

        # -------------------------
        # HGVS Validation
        # -------------------------

        valid = validate_hgvs(variant)
        variant_type = determine_variant_type(variant)
        interpretation = preliminary_interpretation(variant_type)

        # -------------------------
        # ClinVar
        # -------------------------

        try:
            clinvar = get_clinvar_data(
                gene,
                variant
            )
        except Exception as error:
            print(f"ClinVar error: {error}")
            clinvar = {}

        # -------------------------
        # Ensembl
        # -------------------------

        try:
            ensembl = get_ensembl_annotation(
                gene,
                variant,
                genome_build
            )
        except Exception as error:
            print(f"Ensembl error: {error}")
            ensembl = {}

        # -------------------------
        # Variant Mapping
        # -------------------------

        try:
            mapping = convert_hgvs_to_genomic(
                gene,
                variant,
                genome_build
            )
        except Exception as error:
            print(f"Variant mapping error: {error}")
            mapping = {}

        # -------------------------
        # ACMG Evidence
        # -------------------------

        try:
            acmg = calculate_acmg_evidence(
                variant_type=variant_type,
                clinvar=clinvar,
                ensembl=ensembl,
                hgvs_valid=valid
            )
        except Exception as error:
            print(f"ACMG error: {error}")
            acmg = {
                "classification": "Unknown",
                "score": 0,
                "confidence": "Low",
                "evidence": []
            }
                # -------------------------
        # Biological Narrative
        # -------------------------

        try:
            reasoning = generate_reasoning(
                gene,
                variant,
                variant_type,
                clinvar,
                ensembl,
                acmg
            )
        except Exception as error:
            print(f"Reasoning error: {error}")
            reasoning = "Reasoning could not be generated."

        # -------------------------
        # Gene Description
        # -------------------------

        try:
            gene_description = get_gene_description(gene)
        except Exception as error:
            print(f"Gene description error: {error}")
            gene_description = "Gene description unavailable."

        # -------------------------
        # Automatic Classification Note
        # -------------------------

        classification_note = ""

        clinvar_classification = (
            clinvar.get("clinical_significance", "")
            if isinstance(clinvar, dict)
            else ""
        )

        if (
            clinvar_classification == "Pathogenic"
            and acmg.get("classification") == "Likely Pathogenic"
        ):

            classification_note = (
                "ClinVar currently classifies this variant as "
                "Pathogenic. This educational ACMG-inspired engine "
                "classified the variant as Likely Pathogenic because "
                "it evaluates only a subset of ACMG/AMP evidence "
                "criteria. Additional evidence such as population "
                "frequency (gnomAD), functional assays, segregation "
                "studies, computational prediction scores, and other "
                "ACMG criteria are not yet incorporated. Therefore, "
                "this project's classification should be interpreted "
                "as an educational approximation rather than a "
                "clinical ACMG classification."
            )

        LATEST_RESULT = {
            "gene": gene,
            "variant": variant,
            "genome_build": genome_build,
            "valid": valid,
            "variant_type": variant_type,
            "interpretation": interpretation,
            "clinvar": clinvar,
            "ensembl": ensembl,
            "mapping": mapping,
            "acmg": acmg,
            "reasoning": reasoning,
            "gene_description": gene_description,
            "classification_note": classification_note
        }

        report_id = save_report(LATEST_RESULT)
        

    if report_id:
        LATEST_RESULT["report_id"] = report_id

        return render_template(
            "results.html",
            **LATEST_RESULT
        )

    # ---------------------------------------------------
    # GET Request
    # ---------------------------------------------------

    return render_template(
        "results.html",
        gene="",
        variant="",
        genome_build="GRCh38",
        valid=False,
        variant_type="",
        interpretation="",
        clinvar={},
        ensembl={},
        mapping={},
        acmg={
            "classification": "",
            "score": 0,
            "confidence": "",
            "evidence": []
        },
        reasoning="",
        gene_description="",
        classification_note=""
    )


# ---------------------------------------------------
# Download PDF
# ---------------------------------------------------

@app.route("/download_report")
def download_report():

    if LATEST_RESULT is None:
        return (
            "No variant has been interpreted yet. "
            "Please interpret a variant first.",
            400,
        )

    
    
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    filename = temp.name
    temp.close()

    generate_pdf_report(
        title="Genome Variant Interpretation Report",
        filename=filename,
        data=LATEST_RESULT,
    )

    return send_file(
    filename,
    as_attachment=True,
    download_name="Genome_Variant_Report.pdf",
    max_age=0
)


# ---------------------------------------------------
# About
# ---------------------------------------------------

@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------
# Contact
# ---------------------------------------------------

@app.route("/contact")
def contact():
    return render_template("contact.html")


# ---------------------------------------------------
# Run
# ---------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)