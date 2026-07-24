"""
report_generator.py

Generates a professional, scientific-style PDF interpretation report
for the Genome Variant Interpretation Assistant (educational /
research use only).

Public entry point (unchanged, kept compatible with app.py):

    generate_pdf_report(title, filename, data=None)

`data` is the same result context app.py already builds and passes in
(gene, variant, genome_build, valid, variant_type, interpretation,
clinvar, ensembl, mapping, gnomad, acmg, reasoning). Every field is
optional -- missing values are rendered as "Not Available" and never
raise an exception or leak raw Python objects into the PDF.

Report sections (in order):
    1. Cover
    2. Executive Summary
    3. Variant Details
    4. Gene Summary
    5. Molecular Consequence (plain-English explanation, not just the raw term)
    6. Clinical Evidence (ClinVar)
    7. ACMG Evidence Assessment (each evidence code explained)
    8. Biological Interpretation (careful, non-definitive wording)
    9. Confidence Assessment (0-100 score with rationale)
    10. Analysis Workflow (text/vector diagram)
    11. Educational Disclaimer
"""
import uuid
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas as pdfcanvas


# ==================================================================
# COLOR PALETTE (professional, print-friendly)
# ==================================================================

HEADER_BLUE = colors.HexColor("#1e3a8a")
HEADER_BLUE_DARK = colors.HexColor("#172554")
HEADER_TEXT = colors.white
ACCENT_BLUE = colors.HexColor("#2563eb")
SLATE_TEXT = colors.HexColor("#1e293b")
SLATE_MUTED = colors.HexColor("#64748b")
SLATE_LINE = colors.HexColor("#cbd5e1")

ROW_LIGHT = colors.white
ROW_ALT = colors.HexColor("#eff6ff")
GRID_LINE = colors.HexColor("#cbd5e1")

BOX_BORDER_SUMMARY = colors.HexColor("#1d4ed8")
BOX_BG_SUMMARY = colors.HexColor("#eff6ff")

BOX_BORDER_CONSEQUENCE = colors.HexColor("#0891b2")
BOX_BG_CONSEQUENCE = colors.HexColor("#f0fdff")

BOX_BORDER_BIOLOGICAL = colors.HexColor("#4338ca")
BOX_BG_BIOLOGICAL = colors.HexColor("#eef2ff")

BOX_BORDER_CONFIDENCE = colors.HexColor("#0f766e")
BOX_BG_CONFIDENCE = colors.HexColor("#f0fdfa")

BOX_BORDER_DISCLAIMER = colors.HexColor("#dc2626")
BOX_BG_DISCLAIMER = colors.HexColor("#fef2f2")
DISCLAIMER_TEXT_COLOR = colors.HexColor("#7f1d1d")

BOX_BORDER_WORKFLOW = colors.HexColor("#0f766e")
BOX_BG_WORKFLOW = colors.HexColor("#f0fdfa")

CLASSIFICATION_COLORS = {
    "Pathogenic": colors.HexColor("#dc2626"),
    "Likely Pathogenic": colors.HexColor("#ea580c"),
    "Uncertain Significance": colors.HexColor("#ca8a04"),
    "Variant of Uncertain Significance": colors.HexColor("#ca8a04"),
    "VUS": colors.HexColor("#ca8a04"),
    "Likely Benign": colors.HexColor("#16a34a"),
    "Benign": colors.HexColor("#16a34a"),
}

POINTS_POSITIVE = colors.HexColor("#16a34a")
POINTS_NEGATIVE = colors.HexColor("#dc2626")
POINTS_NEUTRAL = colors.HexColor("#64748b")

CONFIDENCE_BAND_COLORS = [
    (80, colors.HexColor("#16a34a")),   # High
    (50, colors.HexColor("#ca8a04")),   # Moderate
    (0, colors.HexColor("#dc2626")),    # Low
]

# usable content width on a US-Letter page with 0.75in margins
CONTENT_WIDTH = 468
PAGE_W, PAGE_H = letter

REPORT_VERSION = "Version 2.2"


# ==================================================================
# VALUE HELPERS
# ==================================================================

def _safe(value, default="Not Available"):
    """
    Formats a value for display, gracefully handling missing data
    without ever printing a raw Python dict/list/None. Every place in
    this module that renders user/pipeline-supplied data routes
    through this helper so a missing field never crashes the report.
    """

    if value is None:
        return default

    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() == "not available":
            return default
        return stripped

    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value if v not in (None, "")]
        return ", ".join(items) if items else default

    if isinstance(value, dict):
        # Defensive fallback -- this function should never be handed a
        # raw dict for display, but if it is, avoid dumping Python repr.
        return default

    return str(value)


def _has_value(value):
    """True if `value` would render as real content rather than a placeholder."""
    return _safe(value, default="") != ""


def _classification_color(label):
    return CLASSIFICATION_COLORS.get(_safe(label), SLATE_TEXT)


def _confidence_color(score):
    for threshold, color in CONFIDENCE_BAND_COLORS:
        if score >= threshold:
            return color
    return POINTS_NEUTRAL


def _hex_color(color):
    """
    Converts a reportlab Color into a version-safe '#rrggbb' string
    suitable for use inside inline Paragraph markup, e.g.
    '<font color="#1e3a8a">'. `Color.hexval()` returns an internal
    '0xRRGGBBAA'-style representation that the Paragraph mini-HTML
    parser does not reliably accept, so this helper builds the string
    explicitly from the color's RGB channels instead.
    """
    return "#%02x%02x%02x" % (
        int(round(color.red * 255)),
        int(round(color.green * 255)),
        int(round(color.blue * 255)),
    )


# ==================================================================
# DOMAIN KNOWLEDGE: MOLECULAR CONSEQUENCE + ACMG CODE EXPLANATIONS
# ==================================================================

CONSEQUENCE_EXPLANATIONS = {
    "missense_variant": (
        "A missense variant changes a single codon so that it specifies a different "
        "amino acid than the reference sequence. The functional impact depends heavily "
        "on the chemical properties of the substituted residue and its location within "
        "the protein -- a change in a catalytic site or structural core is more likely to "
        "be disruptive than a change on a flexible, solvent-exposed surface."
    ),
    "synonymous_variant": (
        "A synonymous (silent) variant alters the DNA sequence without changing the "
        "encoded amino acid, due to redundancy in the genetic code. Most synonymous "
        "variants are functionally neutral, though a subset can still affect splicing "
        "regulatory elements, mRNA stability, or translation kinetics."
    ),
    "frameshift_variant": (
        "A frameshift variant results from an insertion or deletion whose length is not "
        "a multiple of three nucleotides, shifting the downstream reading frame. This "
        "typically scrambles the amino acid sequence beyond the variant site and often "
        "introduces a premature stop codon, commonly resulting in a truncated or "
        "degraded protein product."
    ),
    "stop_gained": (
        "A stop-gained (nonsense) variant introduces a premature termination codon into "
        "the coding sequence. This usually leads to a truncated protein and, in many "
        "cases, triggers nonsense-mediated mRNA decay, reducing or eliminating "
        "functional protein product."
    ),
    "stop_lost": (
        "A stop-loss variant disrupts the natural termination codon, causing translation "
        "to continue into the normally untranslated region. This produces an abnormally "
        "extended protein whose added sequence may interfere with folding or function."
    ),
    "start_lost": (
        "A start-loss variant disrupts the canonical initiation codon. This can prevent "
        "normal translation initiation entirely, or shift initiation to a downstream "
        "alternate start site, typically reducing or eliminating normal protein "
        "production."
    ),
    "splice_region_variant": (
        "A splice-region variant lies near an exon-intron boundary, in a region that can "
        "influence how the spliceosome recognizes splice sites. Depending on its exact "
        "position, it may have no effect, or it may alter splicing efficiency, leading to "
        "exon skipping, intron retention, or use of a cryptic splice site."
    ),
    "splice_acceptor_variant": (
        "A splice-acceptor variant disrupts the conserved sequence at the 3' end of an "
        "intron that is required for normal splicing. Disruption commonly causes exon "
        "skipping or intron retention, frequently producing an abnormal transcript and "
        "protein."
    ),
    "splice_donor_variant": (
        "A splice-donor variant disrupts the conserved sequence at the 5' end of an "
        "intron required for splicing recognition. Similar to splice-acceptor changes, "
        "this can cause exon skipping or intron retention and commonly disrupts normal "
        "protein production."
    ),
    "intron_variant": (
        "An intronic variant falls within a non-coding intervening sequence that is "
        "normally removed from the mature transcript. Most intronic variants have no "
        "measurable effect on the protein product, but variants near splice junctions or "
        "within regulatory elements embedded in introns can still influence splicing or "
        "expression."
    ),
    "inframe_insertion": (
        "An in-frame insertion adds one or more codons without disrupting the reading "
        "frame. This adds extra amino acids to the protein, which may be tolerated or may "
        "disrupt local structure, depending on the size and location of the insertion."
    ),
    "inframe_deletion": (
        "An in-frame deletion removes one or more codons without disrupting the reading "
        "frame. This shortens the protein by the corresponding number of amino acids and "
        "may or may not compromise folding or function depending on which residues are "
        "lost."
    ),
    "5_prime_UTR_variant": (
        "A 5' UTR variant is located in the untranslated region preceding the start "
        "codon. It does not alter the protein sequence directly but can influence "
        "translation efficiency, ribosome binding, or introduce upstream open reading "
        "frames that alter normal translation."
    ),
    "3_prime_UTR_variant": (
        "A 3' UTR variant is located in the untranslated region following the stop "
        "codon. It does not alter the protein sequence but can affect mRNA stability, "
        "localization, or binding sites for regulatory microRNAs."
    ),
    "regulatory_region_variant": (
        "A regulatory-region variant is located within a sequence element (such as a "
        "promoter or enhancer) that helps control gene expression, rather than within "
        "the coding sequence itself. Its impact, if any, is typically on the level of "
        "gene expression rather than protein structure."
    ),
}

_GENERIC_CONSEQUENCE_TEMPLATE = (
    "The Ensembl-predicted molecular consequence for this variant is '{term}'. "
    "This describes the specific relationship between the variant and the affected "
    "transcript as defined by the Sequence Ontology; general characterization of its "
    "functional impact would require consulting the Sequence Ontology definition and, "
    "where available, transcript-specific functional data."
)


def _explain_consequence(consequence_term):
    """
    Returns a scientific, plain-English explanation of an Ensembl
    molecular consequence term. Falls back to a generic but still
    informative explanation for terms not in the curated dictionary,
    so this never simply echoes the raw term back to the reader.
    """

    if not _has_value(consequence_term):
        return (
            "No molecular consequence was returned for this variant by the annotation "
            "pipeline. Without this information, the downstream effect on the encoded "
            "protein cannot be characterized and should be investigated using an "
            "independent annotation tool."
        )

    normalized = _safe(consequence_term).strip().lower().replace(" ", "_")
    explanation = CONSEQUENCE_EXPLANATIONS.get(normalized)

    if explanation:
        return explanation

    readable_term = _safe(consequence_term).replace("_", " ")
    return _GENERIC_CONSEQUENCE_TEMPLATE.format(term=readable_term)


ACMG_CODE_EXPLANATIONS = {
    "PVS1": "Very strong evidence of pathogenicity: the variant is predicted to cause loss "
            "of protein function (e.g. nonsense, frameshift, canonical splice-site, or "
            "initiation-codon change) in a gene where loss of function is an established "
            "disease mechanism.",
    "PS1": "Strong evidence of pathogenicity: the resulting amino acid change is identical "
           "to one already established as pathogenic, regardless of the underlying "
           "nucleotide change.",
    "PS2": "Strong evidence of pathogenicity: the variant arose de novo (with confirmed "
           "parentage) in a patient with the disease and no family history of it.",
    "PS3": "Strong evidence of pathogenicity: well-established in vitro or in vivo "
           "functional studies show a damaging effect on protein function or splicing.",
    "PS4": "Strong evidence of pathogenicity: the variant's prevalence in affected "
           "individuals is significantly increased compared to the prevalence in controls.",
    "PM1": "Moderate evidence of pathogenicity: the variant is located in a mutational hot "
           "spot or well-characterized functional domain without benign variation.",
    "PM2": "Moderate evidence of pathogenicity: the variant is absent, or present at only "
           "extremely low frequency, in population frequency databases such as gnomAD.",
    "PM3": "Moderate evidence of pathogenicity: the variant was detected in trans with a "
           "known pathogenic variant, consistent with a recessive disease mechanism.",
    "PM4": "Moderate evidence of pathogenicity: the variant changes protein length via an "
           "in-frame insertion/deletion or a stop-loss change, outside a repetitive region.",
    "PM5": "Moderate evidence of pathogenicity: a different missense change at the same "
           "residue has previously been classified as pathogenic.",
    "PM6": "Moderate evidence of pathogenicity: the variant is assumed de novo, but "
           "parentage has not been confirmed.",
    "PP1": "Supporting evidence of pathogenicity: the variant cosegregates with disease in "
           "multiple affected family members.",
    "PP2": "Supporting evidence of pathogenicity: the variant is a missense change in a "
           "gene with a low rate of benign missense variation, where missense changes are "
           "a common disease mechanism.",
    "PP3": "Supporting evidence of pathogenicity: multiple computational (in-silico) "
           "prediction tools support a deleterious effect on the gene or protein product.",
    "PP4": "Supporting evidence of pathogenicity: the patient's phenotype or family history "
           "is highly specific for a disease with a single genetic etiology.",
    "PP5": "Supporting evidence of pathogenicity: a reputable source recently classified "
           "the variant as pathogenic, though independent evidence is not yet publicly "
           "available.",
    "BA1": "Stand-alone evidence of benign impact: the variant's allele frequency is too "
           "high to be consistent with a disease-causing role.",
    "BS1": "Strong evidence of benign impact: the allele frequency is greater than would "
           "be expected for the associated disorder.",
    "BS2": "Strong evidence of benign impact: the variant is observed in healthy adults "
           "for a disorder with full penetrance expected at an early age.",
    "BS3": "Strong evidence of benign impact: well-established functional studies show no "
           "damaging effect on protein function or splicing.",
    "BS4": "Strong evidence of benign impact: the variant does not segregate with disease "
           "in affected family members.",
    "BP1": "Supporting evidence of benign impact: the variant is a missense change in a "
           "gene where truncating variants are the primary known disease mechanism.",
    "BP2": "Supporting evidence of benign impact: the variant was observed in trans or cis "
           "with a pathogenic variant without a clear additional phenotypic effect.",
    "BP3": "Supporting evidence of benign impact: an in-frame insertion/deletion falls in "
           "a repetitive region without a known function.",
    "BP4": "Supporting evidence of benign impact: multiple computational prediction tools "
           "suggest no significant effect on the gene or protein product.",
    "BP5": "Supporting evidence of benign impact: the variant was found in a case with an "
           "alternate, well-documented molecular basis for the disease.",
    "BP6": "Supporting evidence of benign impact: a reputable source classifies the "
           "variant as benign, though independent evidence is not yet publicly available.",
    "BP7": "Supporting evidence of benign impact: a synonymous variant with no predicted "
           "impact on splicing and low evolutionary conservation at the position.",
    "ClinVar": "Evidence drawn directly from ClinVar's aggregated variant classifications "
               "and their associated review status, used here as a concordance check "
               "against the other evidence codes.",
    "HGVS": "A data-quality check confirming the variant description follows valid HGVS "
            "nomenclature; this affects confidence in downstream annotation rather than "
            "pathogenicity itself.",
}

_ACMG_PREFIX_MEANING = {
    "PVS": ("Pathogenic", "Very Strong"),
    "PS": ("Pathogenic", "Strong"),
    "PM": ("Pathogenic", "Moderate"),
    "PP": ("Pathogenic", "Supporting"),
    "BA": ("Benign", "Stand-Alone"),
    "BS": ("Benign", "Strong"),
    "BP": ("Benign", "Supporting"),
}


def _explain_acmg_code(code):
    """
    Returns a plain-English explanation of an ACMG/AMP evidence code.
    Recognized codes (PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-7,
    plus this engine's ClinVar/HGVS codes) use a curated explanation.
    Unrecognized codes fall back to decoding the standard ACMG prefix
    convention (e.g. "PM" = moderate pathogenic evidence) so the
    reader still gets a meaningful explanation.
    """

    if not _has_value(code):
        return "No evidence code was provided by the ACMG engine for this entry."

    normalized = _safe(code).strip().upper()
    explanation = ACMG_CODE_EXPLANATIONS.get(normalized)
    if explanation:
        return explanation

    for prefix, (direction, strength) in sorted(
        _ACMG_PREFIX_MEANING.items(), key=lambda kv: -len(kv[0])
    ):
        if normalized.startswith(prefix):
            return (
                "This code follows the standard ACMG/AMP naming convention and "
                "represents {strength} evidence toward a {direction} classification. "
                "A specific description for '{code}' is not in the curated reference "
                "list; consult the ACMG/AMP 2015 guidelines for the exact criterion."
            ).format(strength=strength, direction=direction, code=normalized)

    return (
        "'{code}' does not follow a recognized ACMG/AMP evidence-code prefix. Refer to "
        "the originating evidence engine's documentation for its specific meaning."
    ).format(code=normalized)


# ==================================================================
# SMALL VECTOR ICONS
# (avoid unicode glyphs that some base-14 fonts render as solid boxes)
# ==================================================================

class StatusIcon(Flowable):
    """A small filled circle containing a vector check-mark or cross."""

    def __init__(self, ok, size=13):
        Flowable.__init__(self)
        self.ok = ok
        self.size = size

    def wrap(self, availWidth, availHeight):
        return (self.size, self.size)

    def draw(self):
        c = self.canv
        s = self.size
        color = POINTS_POSITIVE if self.ok else POINTS_NEGATIVE

        c.setFillColor(color)
        c.circle(s / 2.0, s / 2.0, s / 2.0, stroke=0, fill=1)

        c.setStrokeColor(colors.white)
        c.setLineWidth(1.4)
        c.setLineCap(1)

        if self.ok:
            c.line(s * 0.26, s * 0.50, s * 0.43, s * 0.30)
            c.line(s * 0.43, s * 0.30, s * 0.76, s * 0.70)
        else:
            c.line(s * 0.30, s * 0.30, s * 0.70, s * 0.70)
            c.line(s * 0.70, s * 0.30, s * 0.30, s * 0.70)


class BulletDot(Flowable):
    """A small colored circle used as a decorative list bullet."""

    def __init__(self, color=ACCENT_BLUE, size=6):
        Flowable.__init__(self)
        self.color = color
        self.size = size

    def wrap(self, availWidth, availHeight):
        return (self.size, self.size)

    def draw(self):
        c = self.canv
        s = self.size
        c.setFillColor(self.color)
        c.circle(s / 2.0, s / 2.0, s / 2.0, stroke=0, fill=1)


class WorkflowDiagram(Flowable):
    """
    Renders the analysis workflow as a vertical sequence of rounded
    stage boxes connected by arrows -- drawn entirely with canvas
    primitives so it never depends on a particular font's glyph set.
    """

    def __init__(self, stages, width=CONTENT_WIDTH, box_height=28, gap=20):
        Flowable.__init__(self)
        self.stages = stages
        self.width = width
        self.box_height = box_height
        self.gap = gap

    def wrap(self, availWidth, availHeight):
        total_height = (
            len(self.stages) * self.box_height
            + (len(self.stages) - 1) * self.gap
        )
        return (self.width, total_height)

    def draw(self):
        c = self.canv
        box_w = 280
        x = (self.width - box_w) / 2.0
        y = self.wrap(0, 0)[1] - self.box_height  # start at top

        for i, stage in enumerate(self.stages):
            c.setFillColor(BOX_BG_WORKFLOW)
            c.setStrokeColor(BOX_BORDER_WORKFLOW)
            c.setLineWidth(1)
            c.roundRect(x, y, box_w, self.box_height, 7, stroke=1, fill=1)

            c.setFillColor(HEADER_BLUE_DARK)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawCentredString(
                self.width / 2.0, y + self.box_height / 2.0 - 3.3, stage
            )

            if i < len(self.stages) - 1:
                arrow_top = y
                arrow_bottom = y - self.gap + 6
                cx = self.width / 2.0

                c.setStrokeColor(SLATE_MUTED)
                c.setLineWidth(1.4)
                c.line(cx, arrow_top, cx, arrow_bottom)

                c.setFillColor(SLATE_MUTED)
                arrow_size = 4.5
                c.line(cx, arrow_bottom, cx - arrow_size, arrow_bottom + arrow_size)
                c.line(cx, arrow_bottom, cx + arrow_size, arrow_bottom + arrow_size)

            y -= self.box_height + self.gap


class ConfidenceGauge(Flowable):
    """A simple horizontal confidence bar from 0-100."""

    def __init__(self, score, width=CONTENT_WIDTH, height=20):
        Flowable.__init__(self)
        self.score = max(0, min(100, score))
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # track
        c.setFillColor(colors.HexColor("#e2e8f0"))
        c.roundRect(0, 0, w, h, h / 2.0, stroke=0, fill=1)

        # filled portion
        fill_w = max(h, w * (self.score / 100.0))
        c.setFillColor(_confidence_color(self.score))
        c.roundRect(0, 0, fill_w, h, h / 2.0, stroke=0, fill=1)

        # score label
        c.setFillColor(colors.white if self.score >= 15 else SLATE_TEXT)
        c.setFont("Helvetica-Bold", 10)
        label = "%d / 100" % self.score
        label_x = max(10, fill_w - 42)
        c.drawString(label_x, h / 2.0 - 3.5, label)


# ==================================================================
# STYLES
# ==================================================================

def _build_styles():

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#dbeafe"),
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="CoverSectionLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=SLATE_MUTED,
        spaceAfter=1,
    ))

    styles.add(ParagraphStyle(
        name="CoverSectionValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        textColor=SLATE_TEXT,
    ))

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=HEADER_BLUE,
        alignment=TA_LEFT,
        spaceAfter=2,
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=SLATE_MUTED,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=17,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
    ))

    styles.add(ParagraphStyle(
        name="SubHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=HEADER_BLUE_DARK,
        spaceBefore=8,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="TableHeaderText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=HEADER_TEXT,
    ))

    styles.add(ParagraphStyle(
        name="CellLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    ))

    styles.add(ParagraphStyle(
        name="CellValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=SLATE_TEXT,
    ))

    styles.add(ParagraphStyle(
        name="BoxText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=SLATE_TEXT,
    ))

    styles.add(ParagraphStyle(
        name="DisclaimerBoxText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=DISCLAIMER_TEXT_COLOR,
    ))

    styles.add(ParagraphStyle(
        name="RuleCode",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=HEADER_BLUE_DARK,
    ))

    styles.add(ParagraphStyle(
        name="RuleDescription",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=SLATE_TEXT,
        spaceBefore=2,
    ))

    styles.add(ParagraphStyle(
        name="FinalClassificationLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.white,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="FinalClassificationValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.white,
        alignment=TA_CENTER,
    ))

    return styles


# ==================================================================
# SHARED BUILDING BLOCKS
# ==================================================================

def _section_heading(text, styles):
    """A full-width dark blue banner used to open every report section."""

    table = Table(
        [[Paragraph(text, styles["SectionHeading"])]],
        colWidths=[CONTENT_WIDTH],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BLUE),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [table, Spacer(1, 8)]


def _divider(space_before=4, space_after=10):
    """A thin horizontal divider line used to visually separate content blocks."""

    return [
        Spacer(1, space_before),
        HRFlowable(width=CONTENT_WIDTH, thickness=0.75, color=SLATE_LINE,
                   spaceBefore=0, spaceAfter=0),
        Spacer(1, space_after),
    ]


def _kv_table(rows, styles, label_width=170):
    """
    Builds a professional two-column "Field / Detail" table with a
    blue header row and zebra-striped body rows. `rows` is a list of
    (label, value) tuples; values are passed through _safe().
    """

    table_data = [
        [
            Paragraph("Field", styles["TableHeaderText"]),
            Paragraph("Detail", styles["TableHeaderText"]),
        ]
    ]

    for label, value in rows:
        table_data.append([
            Paragraph(str(label), styles["CellLabel"]),
            Paragraph(_safe(value), styles["CellValue"]),
        ])

    table = Table(table_data, colWidths=[label_width, CONTENT_WIDTH - label_width])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_LIGHT, ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    return table


def _boxed_paragraph(text, style, border_color, background_color, title=None, styles=None):
    """A rounded, colored callout box used for narrative / disclaimer text."""

    display_text = _safe(text, default="No additional information was provided for this section.")

    cell_content = []
    if title and styles:
        cell_content.append(Paragraph(title, styles["SubHeading"]))
    cell_content.append(Paragraph(display_text, style))

    inner_table = Table([[cell_content]], colWidths=[CONTENT_WIDTH])
    inner_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.1, border_color),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("BACKGROUND", (0, 0), (-1, -1), background_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    return inner_table


def _pill(text, bg_color, text_color=colors.white, width=None, font_size=9.5):
    """A small rounded 'badge' table, e.g. for classification / status labels."""

    style = ParagraphStyle(
        name="PillText",
        fontName="Helvetica-Bold",
        fontSize=font_size,
        leading=font_size + 2,
        textColor=text_color,
        alignment=TA_CENTER,
    )

    table = Table([[Paragraph(_safe(text), style)]], colWidths=[width] if width else None)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return table


# ==================================================================
# 1. COVER
# ==================================================================

def _cover_page(data, styles, report_id, genome_build, analysis_type):

    elements = []

    banner_content = [
        Spacer(1, 6),
        Paragraph("Genome Variant Interpretation Report", styles["CoverTitle"]),
        Paragraph("Genome Variant Interpretation Assistant", styles["CoverSubtitle"]),
        Spacer(1, 10),
    ]

    banner_table = Table([[banner_content]], colWidths=[CONTENT_WIDTH])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BLUE_DARK),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ("TOPPADDING", (0, 0), (-1, -1), 26),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))

    elements.append(Spacer(1, 70))
    elements.append(banner_table)
    elements.append(Spacer(1, 14))

    badge = _pill("EDUCATIONAL / RESEARCH USE ONLY", colors.HexColor("#b91c1c"))
    badge_wrapper = Table([[badge]], colWidths=[CONTENT_WIDTH])
    badge_wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(badge_wrapper)
    elements.append(Spacer(1, 34))

    def fact_cell(label, value):
        return [
            Paragraph(label.upper(), styles["CoverSectionLabel"]),
            Paragraph(_safe(value), styles["CoverSectionValue"]),
        ]

    facts_table = Table(
        [
            [fact_cell("Report ID", report_id), fact_cell("Generated Date", datetime.now().strftime("%B %d, %Y"))],
            [fact_cell("Analysis Type", analysis_type), fact_cell("Genome Build", genome_build)],
        ],
        colWidths=[CONTENT_WIDTH / 2.0, CONTENT_WIDTH / 2.0],
    )
    facts_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, SLATE_LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.75, SLATE_LINE),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    elements.append(facts_table)
    elements.append(Spacer(1, 60))
    elements.append(Paragraph(
        "Generated by Genome Variant Interpretation Assistant &bull; %s" % REPORT_VERSION,
        ParagraphStyle(
            name="CoverFooterNote", parent=styles["Normal"], fontName="Helvetica",
            fontSize=9, textColor=SLATE_MUTED, alignment=TA_CENTER,
        ),
    ))

    elements.append(PageBreak())
    return elements


# ==================================================================
# 2. EXECUTIVE SUMMARY
# ==================================================================

def _build_executive_summary(data, acmg, clinvar):

    gene = _safe(data.get("gene"), default="an unspecified gene")
    variant = _safe(data.get("variant"), default="an unspecified variant")
    variant_type = _safe(data.get("variant_type"), default="an unclassified")
    significance = _safe(
        clinvar.get("clinical_significance") or acmg.get("classification"),
        default="an undetermined",
    )
    final_interpretation = _safe(
        acmg.get("classification") or data.get("interpretation"),
        default="not yet determined",
    )

    summary = (
        "This report presents an educational, ACMG-informed interpretation of the "
        "variant {variant} identified in the {gene} gene. The variant has been "
        "characterized as a {variant_type} change and is associated with a clinical "
        "significance of \u201c{significance}\u201d based on the evidence sources "
        "consulted during this analysis, including ClinVar submissions, Ensembl "
        "functional annotation, and ACMG-style evidence weighting. Taken together, "
        "the available evidence supports a final interpretation of "
        "\u201c{final_interpretation}\u201d. As with any computationally assisted "
        "analysis, this classification is provisional and intended to illustrate the "
        "variant-interpretation workflow rather than to inform clinical decisions."
    ).format(
        variant=variant,
        gene=gene,
        variant_type=variant_type.lower(),
        significance=significance,
        final_interpretation=final_interpretation,
    )

    return summary


def _executive_summary_section(data, acmg, clinvar, styles):

    elements = []
    elements += _section_heading("Executive Summary", styles)

    elements.append(_boxed_paragraph(
        _build_executive_summary(data, acmg, clinvar),
        styles["BoxText"], BOX_BORDER_SUMMARY, BOX_BG_SUMMARY,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 3. VARIANT DETAILS
# ==================================================================

def _variant_details_section(data, ensembl, mapping, genome_build, styles):

    elements = []
    elements += _section_heading("Variant Details", styles)

    chromosome = ensembl.get("chromosome") or mapping.get("chromosome")
    position = ensembl.get("position") or mapping.get("position")

    elements.append(_kv_table([
        ("Gene", data.get("gene")),
        ("HGVS Notation", data.get("variant")),
        ("Variant Type", data.get("variant_type")),
        ("Chromosome", chromosome),
        ("Position", position),
        ("Transcript", ensembl.get("transcript")),
        ("Protein Change", ensembl.get("protein_change")),
        ("Genome Build", genome_build),
    ], styles))

    elements += _divider()
    return elements


# ==================================================================
# 4. GENE SUMMARY
# ==================================================================

def _gene_summary_section(data, ensembl, styles):
    """
    A short orienting paragraph naming the gene and its canonical
    transcript, placed right after Variant Details so the reader has
    gene-level context before the more technical sections that follow.

    Returns a list of Flowables (section heading banner, boxed
    narrative paragraph, and a trailing divider), consistent with
    every other `_*_section` helper in this module.
    """

    elements = []
    elements += _section_heading("Gene Summary", styles)

    gene = _safe(data.get("gene"))
    transcript = _safe(ensembl.get("transcript"))
    chromosome = _safe(ensembl.get("chromosome"))

    summary = (
        f"This analysis focuses on {gene}. "
        f"Ensembl reports the canonical transcript as {transcript}, "
        f"located on chromosome {chromosome}. "
        "This section provides context for the variant interpretation and helps the "
        "reader understand where the change occurs in the gene."
    )

    elements.append(_boxed_paragraph(
        summary,
        styles["BoxText"],
        BOX_BORDER_BIOLOGICAL,
        BOX_BG_BIOLOGICAL,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 5. MOLECULAR CONSEQUENCE
# ==================================================================

def _molecular_consequence_section(ensembl, styles):

    elements = []
    elements += _section_heading("Molecular Consequence", styles)

    consequence_term = ensembl.get("consequence")

    header_row = _kv_table([
        ("Ensembl Consequence Term", consequence_term),
    ], styles)
    elements.append(header_row)
    elements.append(Spacer(1, 10))

    elements.append(_boxed_paragraph(
        _explain_consequence(consequence_term),
        styles["BoxText"], BOX_BORDER_CONSEQUENCE, BOX_BG_CONSEQUENCE,
        title="Scientific Explanation", styles=styles,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 6. CLINICAL EVIDENCE
# ==================================================================

def _clinical_evidence_section(clinvar, styles):

    elements = []
    elements += _section_heading("Clinical Evidence", styles)

    significance = clinvar.get("clinical_significance")
    sig_color = _classification_color(significance)

    rows = [
        [
            Paragraph("Field", styles["TableHeaderText"]),
            Paragraph("Detail", styles["TableHeaderText"]),
        ],
        [
            Paragraph("ClinVar Significance", styles["CellLabel"]),
            Paragraph(
                '<font color="%s"><b>%s</b></font>' % (_hex_color(sig_color), _safe(significance)),
                styles["CellValue"],
            ),
        ],
        [Paragraph("Review Status", styles["CellLabel"]), Paragraph(_safe(clinvar.get("review_status")), styles["CellValue"])],
        [Paragraph("Disease Association", styles["CellLabel"]), Paragraph(_safe(clinvar.get("conditions")), styles["CellValue"])],
    ]

    table = Table(rows, colWidths=[170, CONTENT_WIDTH - 170])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_LIGHT, ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    why_it_matters = (
        "ClinVar aggregates variant classifications submitted by clinical laboratories, "
        "research groups, and expert panels, along with the review status describing how "
        "thoroughly each submission was vetted. A higher review status (for example, "
        "assertions reviewed by an expert panel or reflecting a multi-submitter "
        "consensus) indicates greater confidence in the reported significance, while a "
        "single, unreviewed submission carries substantially less weight. Evaluating "
        "both the significance and the review status together -- rather than the "
        "significance alone -- is essential to correctly gauge how much confidence this "
        "evidence source should contribute to an overall interpretation."
    )

    elements.append(_boxed_paragraph(
        why_it_matters, styles["BoxText"], BOX_BORDER_CONSEQUENCE, BOX_BG_CONSEQUENCE,
        title="Why ClinVar Evidence Matters", styles=styles,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 7. ACMG EVIDENCE ASSESSMENT
# ==================================================================

def _acmg_evidence_card(item, styles):
    """
    Renders one ACMG-inspired evidence item.

    Reads the current evidence schema produced by utils/acmg.py:
        code / strength / source / points / status / explanation

    ("status" is "Met" / "Not Met" / "Not Applicable" / "Not Available" /
    "Not Assessed" -- it is used to decide the check/cross icon, since
    it reflects whether the criterion actually fired, which a raw
    points sign alone cannot reliably tell us: "Not Applicable" and a
    genuinely failed check both carry 0 points but mean different
    things. If "status" is missing -- e.g. an older evidence payload --
    this falls back to a points-sign heuristic instead of crashing.)
    """

    if not isinstance(item, dict):
        item = {
            "code": _safe(item),
            "strength": "",
            "source": "",
            "status": "",
            "explanation": "",
            "points": None,
        }

    code = _safe(item.get("code"), default="Unlabeled Code")
    strength_text = _safe(item.get("strength"), default="")
    source_text = _safe(item.get("source"), default="")
    status_text = _safe(item.get("status"), default="")
    pipeline_explanation = item.get("explanation")
    points = item.get("points")

    if status_text:
        icon_ok = status_text.strip().lower() == "met"
    else:
        icon_ok = isinstance(points, (int, float)) and points > 0

    header_parts = [code]
    if strength_text:
        header_parts.append(strength_text)
    header_line = " &mdash; ".join(header_parts)
    if source_text:
        header_line += " (%s)" % source_text

    plain_english = _explain_acmg_code(code)

    description_parts = [plain_english]
    if _has_value(pipeline_explanation):
        description_parts.append("Engine note: %s" % _safe(pipeline_explanation))

    left_cell = [
        Paragraph(header_line, styles["RuleCode"]),
        Paragraph(" ".join(description_parts), styles["RuleDescription"]),
    ]

    strength_display = "%s pts" % points if isinstance(points, (int, float)) else "Unscored"
    if isinstance(points, (int, float)) and points > 0:
        pill_color = POINTS_POSITIVE
    elif isinstance(points, (int, float)) and points < 0:
        pill_color = POINTS_NEGATIVE
    else:
        pill_color = POINTS_NEUTRAL
    strength_pill = _pill(strength_display, pill_color, font_size=8.5, width=84)

    card = Table(
        [[StatusIcon(icon_ok, size=15), left_cell, strength_pill]],
        colWidths=[26, CONTENT_WIDTH - 26 - 100, 100],
    )
    card.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, SLATE_LINE),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("BACKGROUND", (0, 0), (-1, -1), ROW_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    return card


def _final_classification_banner(classification, score, confidence, styles):

    color = _classification_color(classification)
    score_display = "%s / 100" % score if isinstance(score, (int, float)) else "Not Scored"
    confidence_display = _safe(confidence)

    content = [
        Paragraph("FINAL CLASSIFICATION", styles["FinalClassificationLabel"]),
        Spacer(1, 4),
        Paragraph(_safe(classification, default="Not Determined"), styles["FinalClassificationValue"]),
        Spacer(1, 4),
        Paragraph(
            "ACMG Evidence Score: %s &nbsp;&nbsp;|&nbsp;&nbsp; Confidence: %s" % (score_display, confidence_display),
            styles["FinalClassificationLabel"],
        ),
    ]

    banner = Table([[content]], colWidths=[CONTENT_WIDTH])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    return banner


def _acmg_assessment_section(acmg, styles):

    elements = []
    elements += _section_heading("ACMG Evidence Assessment", styles)

    evidence = acmg.get("evidence") or []

    if not evidence:
        elements.append(Paragraph(
            "The ACMG engine did not return individual evidence codes for this variant.",
            styles["CellValue"],
        ))
        elements.append(Spacer(1, 8))
    else:
        for item in evidence:
            elements.append(KeepTogether([_acmg_evidence_card(item, styles), Spacer(1, 8)]))

    elements.append(Spacer(1, 4))
    elements.append(KeepTogether([_final_classification_banner(
        acmg.get("classification"), acmg.get("score"), acmg.get("confidence"), styles
    )]))

    elements += _divider()
    return elements


# ==================================================================
# 8. BIOLOGICAL INTERPRETATION
# ==================================================================

def _build_biological_interpretation(data, ensembl):
    """
    Produces careful, hedged scientific language about possible protein
    and disease effects. Deliberately avoids asserting pathogenicity --
    it discusses plausibility and uncertainty rather than concluding.
    """

    gene = _safe(data.get("gene"), default="the gene in question")
    consequence = _safe(ensembl.get("consequence"), default="an unspecified")

    paragraph = (
        "Based on the predicted {consequence} consequence, this variant may plausibly "
        "influence the structure, stability, or activity of the protein encoded by "
        "{gene}, though the direction and magnitude of any such effect cannot be "
        "determined from sequence-level annotation alone. Possible functional "
        "consequences range from negligible impact -- if the affected region tolerates "
        "substitution or truncation well -- to a meaningful disruption of protein "
        "function if the variant affects a critical domain, active site, or "
        "interaction surface. Whether such a disruption would meaningfully contribute "
        "to disease depends on additional factors not captured here, including the "
        "gene's mode of inheritance, tissue-specific expression, and the degree of "
        "functional redundancy with related genes. It is important to note that this "
        "assessment is inferential and does not constitute a claim of pathogenicity: "
        "confirming any real biological or clinical effect would require orthogonal "
        "functional studies, segregation data, or case-control evidence beyond the "
        "scope of this educational analysis."
    ).format(consequence=consequence.lower(), gene=gene)

    return paragraph


def _biological_interpretation_section(data, ensembl, styles):

    elements = []
    elements += _section_heading("Biological Interpretation", styles)

    elements.append(_boxed_paragraph(
        _build_biological_interpretation(data, ensembl),
        styles["BoxText"], BOX_BORDER_BIOLOGICAL, BOX_BG_BIOLOGICAL,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 9. CONFIDENCE ASSESSMENT
# ==================================================================

def _compute_confidence(data, clinvar, ensembl, acmg):
    """
    Derives a 0-100 confidence score from four inputs, each
    contributing up to 25 points:
      - HGVS validation (25 pts if valid)
      - ClinVar review quality (0-25 pts, scaled by review status)
      - ACMG evidence strength (0-25 pts, scaled by engine confidence
        or evidence count)
      - Ensembl annotation completeness (0-25 pts, scaled by how many
        of the five key fields are populated)

    Returns (score, breakdown) where breakdown is a list of
    (component_label, points_awarded, max_points, rationale) tuples,
    so the report can explain exactly how the score was assigned.
    """

    breakdown = []

    # --- HGVS validation ---
    hgvs_valid = bool(data.get("valid"))
    hgvs_points = 25 if hgvs_valid else 0
    breakdown.append((
        "HGVS Validation", hgvs_points, 25,
        "The submitted HGVS notation was successfully validated." if hgvs_valid
        else "The submitted HGVS notation could not be validated, reducing confidence "
             "in all downstream annotation."
    ))

    # --- ClinVar review quality ---
    review_status = _safe(clinvar.get("review_status"), default="").lower()
    if "expert panel" in review_status or "practice guideline" in review_status:
        clinvar_points, clinvar_note = 25, "Reviewed by an expert panel or practice guideline -- the highest ClinVar review tier."
    elif "multiple submitters" in review_status or "no conflicts" in review_status:
        clinvar_points, clinvar_note = 18, "Supported by multiple submitters with consistent classifications."
    elif "single submitter" in review_status:
        clinvar_points, clinvar_note = 10, "Supported by only a single ClinVar submitter."
    elif _has_value(clinvar.get("status")) or _has_value(clinvar.get("clinical_significance")):
        clinvar_points, clinvar_note = 8, "ClinVar data was retrieved, but review status detail was limited."
    else:
        clinvar_points, clinvar_note = 0, "No usable ClinVar data was available for this variant."
    breakdown.append(("ClinVar Review Quality", clinvar_points, 25, clinvar_note))

    # --- ACMG evidence strength ---
    acmg_confidence = _safe(acmg.get("confidence"), default="").lower()
    evidence_count = len(acmg.get("evidence") or [])
    if acmg_confidence == "high":
        acmg_points, acmg_note = 25, "The ACMG engine reported high confidence in its evidence weighting."
    elif acmg_confidence == "moderate":
        acmg_points, acmg_note = 16, "The ACMG engine reported moderate confidence in its evidence weighting."
    elif acmg_confidence == "low":
        acmg_points, acmg_note = 8, "The ACMG engine reported low confidence in its evidence weighting."
    elif evidence_count > 0:
        acmg_points = min(25, evidence_count * 5)
        acmg_note = "%d ACMG evidence code(s) were available, used as a proxy for evidence strength." % evidence_count
    else:
        acmg_points, acmg_note = 0, "No ACMG evidence codes or confidence rating were available."
    breakdown.append(("ACMG Evidence", acmg_points, 25, acmg_note))

    # --- Ensembl annotation completeness ---
    ensembl_fields = ["transcript", "protein_change", "chromosome", "position", "consequence"]
    populated = sum(1 for f in ensembl_fields if _has_value(ensembl.get(f)))
    ensembl_points = round((populated / len(ensembl_fields)) * 25)
    breakdown.append((
        "Ensembl Annotation Completeness", ensembl_points, 25,
        "%d of %d expected Ensembl annotation fields were populated." % (populated, len(ensembl_fields))
    ))

    total_score = sum(points for _, points, _, _ in breakdown)
    return total_score, breakdown


def _confidence_assessment_section(data, clinvar, ensembl, acmg, styles):

    elements = []
    elements += _section_heading("Confidence Assessment", styles)

    score, breakdown = _compute_confidence(data, clinvar, ensembl, acmg)

    gauge_wrapper = Table([[ConfidenceGauge(score)]], colWidths=[CONTENT_WIDTH])
    gauge_wrapper.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(gauge_wrapper)

    table_data = [[
        Paragraph("Component", styles["TableHeaderText"]),
        Paragraph("Points", styles["TableHeaderText"]),
        Paragraph("Rationale", styles["TableHeaderText"]),
    ]]

    for label, points, max_points, rationale in breakdown:
        table_data.append([
            Paragraph(label, styles["CellLabel"]),
            Paragraph("%d / %d" % (points, max_points), styles["CellValue"]),
            Paragraph(rationale, styles["CellValue"]),
        ])

    table = Table(table_data, colWidths=[140, 60, CONTENT_WIDTH - 140 - 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_LIGHT, ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    overall_note = (
        "This confidence score reflects the completeness and quality of the evidence "
        "gathered during analysis -- it is not a measure of how likely the variant is "
        "to be pathogenic. A low score most often indicates missing or low-quality "
        "annotation data rather than a benign variant, and a high score indicates that "
        "the interpretation rests on well-populated, higher-quality evidence sources."
    )
    elements.append(_boxed_paragraph(
        overall_note, styles["BoxText"], BOX_BORDER_CONFIDENCE, BOX_BG_CONFIDENCE,
        title="How to Read This Score", styles=styles,
    ))

    elements += _divider()
    return elements


# ==================================================================
# 10. ANALYSIS WORKFLOW
# ==================================================================

def _analysis_workflow_section(styles):

    elements = []
    elements += _section_heading("Analysis Workflow", styles)

    stages = [
        "HGVS Validation",
        "Variant Classification",
        "Ensembl Annotation",
        "ClinVar Retrieval",
        "ACMG Evidence Evaluation",
        "Biological Interpretation",
        "Final Report",
    ]

    wrapper = Table([[WorkflowDiagram(stages)]], colWidths=[CONTENT_WIDTH])
    wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(wrapper)
    elements += _divider()
    return elements


# ==================================================================
# 11. EDUCATIONAL DISCLAIMER
# ==================================================================

def _disclaimer_section(styles):

    elements = []
    elements += _section_heading("Educational Disclaimer", styles)

    disclaimer_text = (
        "This software is intended for educational and research purposes only and is "
        "not suitable for clinical diagnosis or medical decision-making. The "
        "classifications, scores, and narrative interpretations in this report are "
        "generated by an automated, ACMG-inspired pipeline and have not been reviewed "
        "by a certified clinical laboratory, molecular pathologist, or genetic "
        "counselor. Any real-world clinical question regarding this or any other "
        "genetic variant should be directed to a qualified healthcare professional or "
        "accredited clinical genetics laboratory."
    )

    elements.append(_boxed_paragraph(
        disclaimer_text, styles["DisclaimerBoxText"], BOX_BORDER_DISCLAIMER, BOX_BG_DISCLAIMER,
    ))

    return elements


# ==================================================================
# PAGE DECORATION: FOOTER / PAGE NUMBERS
# ==================================================================

class _NumberedCanvas(pdfcanvas.Canvas):
    """
    Buffers each page so the total page count is known up front, then
    stamps a footer rule, attribution text, and "Page X of Y" onto
    every page except the cover page.
    """

    def __init__(self, *args, **kwargs):
        pdfcanvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self._draw_footer(self._pageNumber, total_pages)
            pdfcanvas.Canvas.showPage(self)
        pdfcanvas.Canvas.save(self)

    def _draw_footer(self, page_number, total_pages):
        self.saveState()

        self.setStrokeColor(SLATE_LINE)
        self.setLineWidth(0.6)
        self.line(0.75 * inch, 0.62 * inch, PAGE_W - 0.75 * inch, 0.62 * inch)

        self.setFont("Helvetica", 8)
        self.setFillColor(SLATE_MUTED)
        self.drawString(
            0.75 * inch, 0.46 * inch,
            "Genome Variant Interpretation Assistant \u2022 %s \u2022 Educational Use Only" % REPORT_VERSION,
        )
        self.drawRightString(
            PAGE_W - 0.75 * inch, 0.46 * inch,
            "Page %d of %d" % (page_number - 1, total_pages - 1),
        )

        self.restoreState()


# ==================================================================
# REPORT ASSEMBLY
# ==================================================================

def _build_report_content(title, data, styles):
    """
    Assembles the full ordered list of flowables for the report body.
    This is the single place section order is defined; each section
    builder is called exactly once, in the order it should appear.
    """

    data = data or {}

    clinvar = data.get("clinvar") or {}
    ensembl = data.get("ensembl") or {}
    mapping = data.get("mapping") or {}
    acmg = data.get("acmg") or {}

    genome_build = data.get("genome_build")
    analysis_type = "Educational ACMG-Inspired Variant Interpretation"
    report_id = data.get("report_id") or ("GVIA-%s" % str(uuid.uuid4())[:8].upper())

    content = []

    # 1. Cover
    content += _cover_page(data, styles, report_id, genome_build, analysis_type)

    # Running title shown at the top of the content pages
    content.append(Paragraph(title or "Variant Interpretation Report", styles["ReportTitle"]))
    content.append(Paragraph(
        "Report ID: %s &nbsp;|&nbsp; Generated: %s" % (
            report_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        styles["ReportSubtitle"],
    ))
    content.append(Spacer(1, 10))

    # 2. Executive Summary
    content += _executive_summary_section(data, acmg, clinvar, styles)

    # 3. Variant Details
    content += _variant_details_section(data, ensembl, mapping, genome_build, styles)

    # 4. Gene Summary
    content += _gene_summary_section(data, ensembl, styles)

    # 5. Molecular Consequence
    content += _molecular_consequence_section(ensembl, styles)

    # 6. Clinical Evidence
    content += _clinical_evidence_section(clinvar, styles)

    # 7. ACMG Evidence Assessment
    content += _acmg_assessment_section(acmg, styles)

    # 8. Biological Interpretation
    content += _biological_interpretation_section(data, ensembl, styles)

    # 9. Confidence Assessment
    content += _confidence_assessment_section(data, clinvar, ensembl, acmg, styles)

    # 10. Analysis Workflow
    content += _analysis_workflow_section(styles)

    # 11. Educational Disclaimer
    content += _disclaimer_section(styles)

    return content


def generate_pdf_report(title, filename, data=None):
    """
    Generates the professional, scientific-style PDF variant
    interpretation report described in the module docstring.

    `data` is expected to be the same result context app.py already
    builds and passes in (gene, variant, genome_build, valid,
    variant_type, interpretation, clinvar, ensembl, mapping, gnomad,
    acmg, reasoning). Any missing fields are displayed as "Not
    Available" rather than raising an error or printing raw Python
    objects, so this remains safe to call even with partial or empty
    data, including `data=None`. The function signature is unchanged
    from previous versions of this module, so no changes are required
    in app.py.
    """

    data = data or {}

    document = SimpleDocTemplate(
        filename,
        pagesize=letter,
        topMargin=50,
        bottomMargin=60,
        leftMargin=72,
        rightMargin=72,
        title="Genome Variant Interpretation Report",
        author="Genome Variant Interpretation Assistant",
    )

    styles = _build_styles()
    content = _build_report_content(title, data, styles)

    document.build(content, canvasmaker=_NumberedCanvas)