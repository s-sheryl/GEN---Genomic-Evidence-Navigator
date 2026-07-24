import requests

GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

ENSEMBL_SEQUENCE_URL = "https://rest.ensembl.org/sequence/region/human"
ENSEMBL_SEQUENCE_URL_GRCH37 = "https://grch37.rest.ensembl.org/sequence/region/human"


REQUEST_HEADERS = {
    "User-Agent": "GenomeVariantInterpretationAssistant/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
}


POPULATION_LABELS = {
    "afr": "African/African American",
    "amr": "Latino/Admixed American",
    "asj": "Ashkenazi Jewish",
    "eas": "East Asian",
    "fin": "Finnish",
    "nfe": "Non-Finnish European",
    "sas": "South Asian",
    "mid": "Middle Eastern",
    "remaining": "Remaining / Other"
}


def interpret_frequency(freq):

    if freq is None:
        return "Unavailable"

    if freq == 0:
        return "Not observed in population database"

    if freq < 0.0001:
        return "Very rare"

    if freq < 0.01:
        return "Rare"

    return "Common variant"


def _fetch_anchor_base(chromosome, position, genome_build):

    base_url = (
        ENSEMBL_SEQUENCE_URL_GRCH37
        if genome_build == "GRCh37"
        else ENSEMBL_SEQUENCE_URL
    )

    anchor = int(position) - 1

    url = f"{base_url}/{chromosome}:{anchor}-{anchor}"

    response = requests.get(
        url,
        headers={"Accept": "text/plain"},
        timeout=15
    )

    if response.status_code != 200:
        return None

    return response.text.strip().upper()


def _normalize_to_vcf(chromosome, position, allele_string, genome_build):

    if "/" not in allele_string:
        return position, None, None

    ref, alt = allele_string.split("/", 1)

    if ref != "-" and alt != "-":
        return position, ref, alt

    anchor = _fetch_anchor_base(chromosome, position, genome_build)

    if not anchor:
        return None, None, None

    anchor_position = int(position) - 1

    if alt == "-":
        return (
            anchor_position,
            anchor + ref,
            anchor
        )

    return (
        anchor_position,
        anchor,
        anchor + alt
    )


def _build_variant_id(
    chromosome,
    position,
    allele_string,
    genome_build
):

    position, ref, alt = _normalize_to_vcf(
        chromosome,
        position,
        allele_string,
        genome_build
    )

    if not all([position, ref, alt]):
        return None

    chromosome = str(chromosome).replace("chr", "")

    return f"{chromosome}-{position}-{ref}-{alt}"
def _query_gnomad(variant_id, dataset_id):

    query = """
    query VariantQuery($variantId: String!, $datasetId: DatasetId!) {
      variant(variantId: $variantId, dataset: $datasetId) {
        variant_id

        genome {
          ac
          an
        }

        exome {
          ac
          an
        }

        genome_populations: genome {
          populations {
            id
            ac
            an
          }
        }

        exome_populations: exome {
          populations {
            id
            ac
            an
          }
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "variantId": variant_id,
            "datasetId": dataset_id
        }
    }

    response = requests.post(
        GNOMAD_API_URL,
        json=payload,
        headers=REQUEST_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.json()
def get_gnomad_frequency(
    gene,
    variant,
    chromosome=None,
    position=None,
    allele_string=None,
    genome_build="GRCh38"
):

    def empty(status):

        return {
            "status": status,
            "gene": gene,
            "variant": variant,
            "frequency": None,
            "populations": [],
            "interpretation": "Unavailable"
        }

    if not chromosome or not position or not allele_string:
        return empty("Insufficient genomic coordinates")

    variant_id = _build_variant_id(
        chromosome,
        position,
        allele_string,
        genome_build
    )

    if not variant_id:
        return empty("Could not build gnomAD variant ID")

    dataset_id = (
        "gnomad_r4"
        if genome_build == "GRCh38"
        else "gnomad_r2_1"
    )

    try:
        payload = _query_gnomad(
            variant_id,
            dataset_id
        )

    except requests.exceptions.RequestException as e:

        result = empty("gnomAD connection error")
        result["error"] = str(e)
        return result

    if payload.get("errors"):

        result = empty("gnomAD lookup failed")
        result["error"] = payload["errors"]
        return result

    variant_data = (
        payload.get("data", {})
        .get("variant")
    )

    if not variant_data:
        return empty("Variant not found in gnomAD")

    source = (
        variant_data.get("genome")
        or variant_data.get("exome")
    )

    if not source:
        return empty("No population data")

    ac = source.get("ac")
    an = source.get("an")

    frequency = None

    if (
        ac is not None
        and an
        and an > 0
    ):
        frequency = ac / an

    populations = []

    population_source = (
        variant_data.get("genome_populations")
        or variant_data.get("exome_populations")
        or {}
    )

    for pop in population_source.get("populations", []):

        ac = pop.get("ac")
        an = pop.get("an")

        pop_freq = None

        if (
            ac is not None
            and an
            and an > 0
        ):
            pop_freq = ac / an

        populations.append({

            "population":
                POPULATION_LABELS.get(
                    pop.get("id"),
                    pop.get("id")
                ),

            "allele_frequency":
                pop_freq,

            "allele_count":
                ac,

            "allele_number":
                an
        })

    return {

        "status": "gnomAD data retrieved",

        "gene": gene,

        "variant": variant,

        "frequency": frequency,

        "populations": populations,

        "interpretation":
            interpret_frequency(frequency)
    }