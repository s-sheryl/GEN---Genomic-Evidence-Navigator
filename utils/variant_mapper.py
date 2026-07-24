import requests
from urllib.parse import quote


def _base_url(genome_build):

    if genome_build == "GRCh37":
        return "https://grch37.rest.ensembl.org"

    return "https://rest.ensembl.org"


def _resolve_canonical_transcript(gene, genome_build):

    url = f"{_base_url(genome_build)}/lookup/symbol/homo_sapiens/{quote(gene)}"

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        return None

    data = response.json()

    return data.get("canonical_transcript")


def convert_hgvs_to_genomic(gene, hgvs, genome_build="GRCh38"):
    """
    Maps a gene symbol + coding HGVS variant to genomic coordinates.

    The old implementation POSTed "BRCA1:c.68_69delAG" to the batch
    endpoint, but a gene symbol is not a valid HGVS reference sequence,
    so every request failed with "Mapping failed". This resolves the
    canonical transcript first, then uses the single-variant GET
    endpoint, which returns allele_string/seq_region_name/start
    directly in its response.
    """

    def failure(status, error=None):
        result = {
            "status": status,
            "chromosome": "Not available",
            "position": "Not available",
            "allele_string": "Not available",
            "assembly": genome_build
        }
        if error is not None:
            result["error"] = error
        return result

    transcript_id = _resolve_canonical_transcript(gene, genome_build)

    if not transcript_id:
        return failure("Gene symbol could not be resolved")

    hgvs_notation = f"{transcript_id}:{hgvs}"

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
        response = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.exceptions.RequestException as error:
        return failure("Mapping connection error", str(error))

    if response.status_code != 200:
        return failure("Mapping failed", response.text)

    data = response.json()

    if not data:
        return failure("No mapping found")

    variant_data = data[0]

    return {
        "status": "Mapping successful",
        "chromosome": variant_data.get("seq_region_name", "Not available"),
        "position": variant_data.get("start", "Not available"),
        "allele_string": variant_data.get("allele_string", "Not available"),
        "assembly": variant_data.get("assembly_name", genome_build)
    }