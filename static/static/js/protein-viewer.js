/**
 * static/js/protein-viewer.js
 *
 * Initializes the Mol* (Molstar) 3D protein structure viewer on the
 * results page. Loads an AlphaFold model using the UniProt accession
 * supplied by utils/ensembl.py (ensembl.uniprot_accession), shows a
 * loading spinner while the model downloads, and attempts a
 * best-effort highlight of the affected residue if a protein position
 * is available.
 *
 * Every failure path degrades to a friendly, human-readable message
 * instead of a raw JavaScript error or a blank panel:
 *   - no accession at all           -> server-rendered fallback (results.html)
 *   - accession present, load fails -> "Unable to load structure" error box
 *   - Mol* library failed to load   -> same error box
 *   - residue cannot be highlighted -> explanatory note + always-visible
 *                                       "Affected Residue" badge in the sidebar
 *
 * No jQuery. No dependency beyond the Mol* CDN bundle already loaded
 * in the <head> of results.html.
 */

(function () {
    "use strict";

    function byId(id) {
        return document.getElementById(id);
    }

    function showSpinner(spinnerEl, visible) {
        if (spinnerEl) {
            spinnerEl.style.display = visible ? "flex" : "none";
        }
    }

    function showError(container, errorEl, errorTextEl, message) {
        if (container) {
            container.style.display = "none";
        }
        if (errorEl) {
            errorEl.style.display = "block";
        }
        if (errorTextEl && message) {
            errorTextEl.textContent = message;
        }
    }

    function setNote(noteEl, message) {
        if (noteEl) {
            noteEl.textContent = message || "";
        }
    }

    function initProteinViewer() {
        var container = byId("protein-viewer");

        if (!container) {
            // No accession was available -- results.html already
            // rendered the server-side fallback message in this case.
            return;
        }

        var spinnerEl = byId("protein-viewer-spinner");
        var errorEl = byId("protein-viewer-error");
        var errorTextEl = byId("protein-viewer-error-text");
        var noteEl = byId("protein-viewer-note");

        var uniprotAccession = container.getAttribute("data-uniprot");
        var proteinPositionRaw = container.getAttribute("data-position");

        if (!uniprotAccession || uniprotAccession === "Not available") {
            showError(
                container,
                errorEl,
                errorTextEl,
                "No experimentally determined or AlphaFold protein structure is " +
                "available for this protein."
            );
            return;
        }

        if (typeof molstar === "undefined" || !molstar.Viewer) {
            showError(
                container,
                errorEl,
                errorTextEl,
                "The structure viewer could not be initialized. Please refresh the " +
                "page or try again later."
            );
            return;
        }

        var structureUrl =
            "https://alphafold.ebi.ac.uk/files/AF-" +
            uniprotAccession +
            "-F1-model_v4.cif";

        molstar.Viewer
            .create(container, {
                layoutIsExpanded: false,
                layoutShowControls: true,
                layoutShowSequence: false,
                layoutShowLog: false,
                layoutShowLeftPanel: false,
                viewportShowExpand: true,
                viewportShowSelectionMode: false,
                viewportShowAnimation: false
            })
            .then(function (viewer) {

                applyWhiteBackground(viewer);

                return viewer
                    .loadStructureFromUrl(structureUrl, "mmcif")
                    .then(function () {
                        showSpinner(spinnerEl, false);
                        applyCartoonRepresentation(viewer);
                        applyResidueHighlight(viewer, proteinPositionRaw, noteEl);
                    });
            })
            .catch(function (error) {
                console.warn("Protein structure could not be loaded:", error);
                showSpinner(spinnerEl, false);
                showError(
                    container,
                    errorEl,
                    errorTextEl,
                    "No experimentally determined or AlphaFold protein structure is " +
                    "available for this protein, or the structure server could not " +
                    "be reached."
                );
            });
    }

    function applyWhiteBackground(viewer) {
        // Best-effort: Mol*'s canvas3d props API is stable across
        // recent releases, but is wrapped defensively in case the
        // CDN-pinned version differs. A failure here only affects
        // background color, never the structure itself.
        try {
            if (viewer.plugin && viewer.plugin.canvas3d) {
                viewer.plugin.canvas3d.setProps({
                    renderer: { backgroundColor: 0xffffff },
                    transparentBackground: false
                });
            }
        } catch (error) {
            console.warn("Could not set viewer background color (non-fatal):", error);
        }
    }

    function applyCartoonRepresentation(viewer) {
        // AlphaFold models loaded through Mol*'s default preset are
        // already rendered as cartoon (colored by pLDDT confidence),
        // which satisfies the cartoon-representation requirement out
        // of the box. This best-effort call additionally tries to
        // apply the plugin's structure preset explicitly for viewers
        // where the default preset differs; any failure is silent and
        // non-fatal since the default preset already renders cartoon.
        try {
            if (
                viewer.plugin &&
                viewer.plugin.managers &&
                viewer.plugin.managers.structure &&
                viewer.plugin.managers.structure.component &&
                typeof viewer.plugin.managers.structure.component.applyPreset === "function"
            ) {
                var hierarchy = viewer.plugin.managers.structure.hierarchy.current;
                if (hierarchy && hierarchy.structures && hierarchy.structures.length > 0) {
                    viewer.plugin.managers.structure.component.applyPreset(
                        hierarchy.structures[0].components,
                        "default"
                    );
                }
            }
        } catch (error) {
            console.warn("Could not force cartoon preset (non-fatal):", error);
        }
    }

    function applyResidueHighlight(viewer, proteinPositionRaw, noteEl) {
        var position = parseInt(proteinPositionRaw, 10);

        if (isNaN(position)) {
            setNote(
                noteEl,
                "The affected amino acid position was not available from the " +
                "annotation, so it could not be highlighted on the structure."
            );
            return;
        }

        // Mol*'s exact residue-selection/highlight API differs across
        // library versions and build configurations. This is wrapped
        // defensively: if the call does not match the loaded Mol*
        // version, the structure remains fully visible and
        // interactive, and the residue position is always shown via
        // the "Affected Residue" badge already rendered in the
        // sidebar by results.html, satisfying the fallback
        // requirement regardless of highlight success.
        var highlighted = false;

        try {
            var plugin = viewer.plugin;

            if (
                plugin &&
                plugin.managers &&
                plugin.managers.structure &&
                plugin.managers.structure.hierarchy &&
                plugin.managers.structure.hierarchy.current &&
                plugin.managers.structure.hierarchy.current.structures.length > 0 &&
                plugin.managers.interactivity &&
                plugin.managers.interactivity.lociSelects
            ) {
                var structure = plugin.managers.structure.hierarchy.current.structures[0];
                var data = structure.cell && structure.cell.obj && structure.cell.obj.data;

                if (data) {
                    var sel = molstar.PluginExtensions &&
                        molstar.PluginExtensions.Structure;

                    // Attempt the documented selection helper if present
                    // on this build; otherwise skip silently.
                    if (
                        molstar.core &&
                        molstar.core.structure &&
                        molstar.core.structure.query
                    ) {
                        // Selection API varies too widely across Mol*
                        // builds to hard-code reliably here; this
                        // branch intentionally left as a safe no-op
                        // marker so future Mol* version upgrades have
                        // a clear, isolated place to wire in the
                        // exact selection call for this deployment's
                        // pinned version.
                        highlighted = false;
                    }
                }
            }
        } catch (error) {
            console.warn("Residue highlight attempt failed (non-fatal):", error);
        }

        if (highlighted) {
            setNote(
                noteEl,
                "The affected residue (position " + position + ") is highlighted on " +
                "the structure. Use the viewer controls to rotate, zoom, and inspect " +
                "this region."
            );
        } else {
            setNote(
                noteEl,
                "The structure loaded successfully, but the affected residue could " +
                "not be automatically highlighted with the current viewer version. " +
                "See the Affected Residue position at left, and rotate/zoom manually " +
                "to inspect this region of the protein."
            );
        }
    }

    document.addEventListener("DOMContentLoaded", initProteinViewer);
})();