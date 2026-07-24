"""
utils/ensembl.py

Thin wrapper around the public Ensembl REST API (VEP + symbol lookup)
used to annotate a gene/HGVS variant pair with its predicted molecular
consequence, transcript details, and protein change.

Educational use only -- this module makes live calls to Ensembl and
returns a defensive "Not available" placeholder structure (via
`failure()`) whenever the lookup cannot be completed, so the rest of
the application never has to special-case a missing annotation.
"""

import os
import requests
from urllib.parse import quote

# Set ENSEMBL_DEBUG=1 in the environment to print the raw VEP payload
# for each lookup. Off by default so normal runs don't flood the
# console/log aggregator with full API responses.
_DEBUG = True


def _base_url(genome_build):
    """
    Ensembl REST has separate servers per assembly. Any build other
    than "GRCh37" is routed to the GRCh38 (current) server -- callers
    should validate `genome_build` against a known set of options
    (e.g. a fixed dropdown) if it can come from unconstrained input.
    """

    if genome_build == "GRCh37":
        return "https://grch37.rest.ensembl.org"

    return "https://rest.ensembl.org"


def _resolve_canonical_transcript(gene, genome_build):
    """
    Resolve a gene symbol to its canonical Ensembl transcript.

    Returns None (rather than raising) on any network failure, non-200
    response, or malformed JSON body, so callers can treat "could not
    resolve" as a single, simple case.
    """

    url = (
        f"{_base_url(genome_build)}/lookup/"
        f"symbol/homo_sapiens/{quote(gene)}"
    )

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        # A 200 status does not guarantee a well-formed JSON body
        # (e.g. a proxy/gateway returning an HTML error page with a
        # 200 status). Treat this the same as "could not resolve".
        return None

    return data.get("canonical_transcript")



def get_ensembl_annotation(gene, variant, genome_build="GRCh38"):
    """
    Query Ensembl VEP using transcript-based HGVS notation.

    Always returns a dict with the full set of expected keys, even on
    failure, so downstream code (utils/acmg.py, utils/reasoning.py,
    templates, report_generator.py) never needs to guard against a
    missing key -- only against "Not available" values.
    """

    def failure(status, error=None):

        result = {
            "status": status,
            "gene": gene,
            "chromosome": "Not available",
            "position": "Not available",

            "transcript": "Not available",
            "protein_change": "Not available",
            "consequence": "Not available",
            "impact": "Not available",

            "gene_symbol": gene,
            "gene_id": "Not available",
            "biotype": "Not available",

            "exon": "Not available",
            "cds_position": "Not available",
            "protein_position": "Not available",

            "codons": "Not available",
            "amino_acids": "Not available",

            "sift": "Not available",
            "polyphen": "Not available",

            "hgvsc": "Not available",
            "hgvsp": "Not available",

            "allele_string": "Not available",
            "rsid": "Not available",

            "colocated_variants": [],

            

            "assembly": genome_build
        }

        if error:
            result["error"] = error

        return result

    transcript_id = _resolve_canonical_transcript(
        gene,
        genome_build
    )

    if not transcript_id:
        return failure("Gene symbol could not be resolved")

    hgvs_notation = f"{transcript_id}:{variant}"

    url = (
        f"{_base_url(genome_build)}/vep/human/hgvs/"
        f"{quote(hgvs_notation, safe=':')}"
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    params = {
        "hgvs": 1
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        print("\n========== ENSEMBL DEBUG ==========")
        print("URL:", response.url)
        print("Status:", response.status_code)
        print(response.text)
        print("==================================\n")

    except requests.exceptions.RequestException as error:

      return failure(
            "Ensembl connection error",
            str(error)
        )

    if response.status_code != 200:
        return failure(
            "Ensembl lookup failed",
            response.text
        )

    try:
        data = response.json()
    except ValueError as error:
        # A 200 status does not guarantee a well-formed JSON body.
        return failure(
            "Ensembl returned an invalid response",
            str(error)
        )

    if not data:
        return failure("No Ensembl annotation found")

    variant_data = data[0]

    transcripts = variant_data.get(
        "transcript_consequences",
        []
    )

    if not transcripts:
        # The top-level lookup succeeded, but VEP did not map the
        # variant onto any transcript -- every detail field would be
        # blank, so this is reported as its own distinct status rather
        # than the misleading "Ensembl annotation found".
        return failure(
            "Ensembl found the variant but returned no transcript "
            "consequence"
        )

    selected = transcripts[0]

    for transcript in transcripts:

        if transcript.get("canonical") == 1:
            selected = transcript
            break

    if _DEBUG:
        print("\n========== ENSEMBL RESPONSE ==========")
        print(variant_data)
        print("======================================\n")

    # `colocated_variants` may be present but empty (a variant with no
    # known dbSNP entry at that position is the common case, not the
    # exception), so this must not assume a non-empty list.
    colocated_variants = variant_data.get("colocated_variants") or []
    first_colocated = colocated_variants[0] if colocated_variants else {}

    # Best-effort only -- never allowed to raise or block the response.
    
    return {

        "status": "Ensembl annotation found",

        "gene": gene,

        "chromosome": variant_data.get(
            "seq_region_name",
            "Not available"
        ),

        "position": variant_data.get(
            "start",
            "Not available"
        ),

        "transcript": selected.get(
            "transcript_id",
            "Not available"
        ),

        "protein_change": selected.get(
            "hgvsp",
            "Not available"
        ),

        "consequence": ", ".join(
            selected.get(
                "consequence_terms",
                []
            )
        ) or "Not available",

        "impact": selected.get(
            "impact",
            "Not available"
        ),

        "gene_symbol": selected.get(
            "gene_symbol",
            gene
        ),

        "gene_id": selected.get(
            "gene_id",
            "Not available"
        ),

        "biotype": selected.get(
            "biotype",
            "Not available"
        ),

        "exon": selected.get(
            "exon",
            "Not available"
        ),

        "cds_position": selected.get(
            "cds_start",
            "Not available"
        ),

        "protein_position": selected.get(
            "protein_start",
            "Not available"
        ),

        "codons": selected.get(
            "codons",
            "Not available"
        ),

        "amino_acids": selected.get(
            "amino_acids",
            "Not available"
        ),

        "sift": selected.get(
            "sift_prediction",
            "Not available"
        ),

        "polyphen": selected.get(
            "polyphen_prediction",
            "Not available"
        ),

        "hgvsc": selected.get(
            "hgvsc",
            "Not available"
        ),

        "hgvsp": selected.get(
            "hgvsp",
            "Not available"
        ),

        "allele_string": variant_data.get(
            "allele_string",
            "Not available"
        ),

        "rsid": first_colocated.get(
            "id",
            "Not available"
        ),

        "colocated_variants": colocated_variants,

        

        "assembly": genome_build
    }