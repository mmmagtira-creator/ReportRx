/* ===================================================================
   ReportRx – Frontend Logic
   =================================================================== */

(function () {
    "use strict";

    const input      = document.getElementById("report-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const tbody      = document.getElementById("results-body");
    const exportBtn  = document.getElementById("export-btn");
    const clearBtn   = document.getElementById("clear-btn");
    const emptyState = document.getElementById("empty-state");
    const tableWrap  = document.getElementById("table-wrapper");

    /* ── Disclaimer modal ──────────────────────────────────────────── */
    const disclaimerOverlay = document.getElementById("disclaimer-overlay");
    const disclaimerAccept  = document.getElementById("disclaimer-accept-btn");

    disclaimerAccept.addEventListener("click", function () {
        disclaimerOverlay.style.display = "none";
    });

    /* ── Clear confirmation modal ──────────────────────────────────── */
    const clearOverlay   = document.getElementById("clear-overlay");
    const clearCancelBtn = document.getElementById("clear-cancel-btn");
    const clearConfirmBtn = document.getElementById("clear-confirm-btn");

    const ORIGINAL_BTN_TEXT = "Analyze Report";

    /* ── Helpers ────────────────────────────────────────────────────── */

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function createRow(r) {
        const tr = document.createElement("tr");
        // Truncate (not round) to N decimal places
        const trunc = (v, d) => { const f = Math.pow(10, d); return (Math.floor(v * f) / f).toFixed(d); };
        tr.innerHTML = [
            `<td>${escapeHtml(r.case_id)}</td>`,
            `<td>${escapeHtml(r.text_report)}</td>`,
            `<td>${escapeHtml(r.drug_mention)}</td>`,
            `<td>${escapeHtml(r.reaction_mention)}</td>`,
            `<td>${escapeHtml(r.onset)}</td>`,
            `<td>${trunc(r.raw_confidence, 4)}</td>`,
            `<td>${escapeHtml(r.status)}</td>`,
            `<td>${trunc(r.latency_ms, 4)}</td>`,
        ].join("");
        return tr;
    }

    function toggleEmptyState() {
        const hasRows = tbody.children.length > 0;
        emptyState.classList.toggle("visible", !hasRows);
        tableWrap.style.display = hasRows ? "" : "none";
    }

    function setLoading(loading) {
        analyzeBtn.disabled = loading;
        analyzeBtn.textContent = loading ? "Analyzing…" : ORIGINAL_BTN_TEXT;
    }

    /* ── Load existing reports on page load ─────────────────────────── */

    async function loadReports() {
        try {
            const res = await fetch("/api/reports");
            if (!res.ok) return;
            const reports = await res.json();
            reports.forEach(r => tbody.appendChild(createRow(r)));
        } catch (_) { /* silent */ }
        toggleEmptyState();
    }

    /* ── Analyze handler ───────────────────────────────────────────── */

    async function handleAnalyze() {
        const text = input.value.trim();
        if (!text) {
            input.focus();
            return;
        }

        setLoading(true);

        try {
            const res = await fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text_report: text }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || "Request failed");
            }

            const row = await res.json();
            tbody.appendChild(createRow(row));
            input.value = "";
            toggleEmptyState();

        } catch (err) {
            alert("Unable to analyze report right now. Please try again.");
        } finally {
            setLoading(false);
        }
    }

    /* ── Export handler ─────────────────────────────────────────────── */

    function handleExport() {
        window.open("/api/export/csv", "_blank");
    }

    /* ── Clear handler (custom modal) ──────────────────────────────── */

    function showClearModal() {
        clearOverlay.style.display = "flex";
    }

    function hideClearModal() {
        clearOverlay.style.display = "none";
    }

    async function executeClear() {
        hideClearModal();
        try {
            const res = await fetch("/api/reports", { method: "DELETE" });
            if (res.ok) {
                tbody.innerHTML = "";
                toggleEmptyState();
            }
        } catch (_) { /* silent */ }
    }

    clearCancelBtn.addEventListener("click", hideClearModal);
    clearConfirmBtn.addEventListener("click", executeClear);

    /* ── Event binding ─────────────────────────────────────────────── */

    analyzeBtn.addEventListener("click", handleAnalyze);

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.ctrlKey) {
            e.preventDefault();
            handleAnalyze();
        }
    });

    exportBtn.addEventListener("click", handleExport);
    clearBtn.addEventListener("click", showClearModal);

    /* ── Init ──────────────────────────────────────────────────────── */
    loadReports();

})();
