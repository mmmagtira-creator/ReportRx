/* ===================================================================
   ReportRx - Frontend Logic
   =================================================================== */

(function () {
    "use strict";

    const input = document.getElementById("report-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const importBtn = document.getElementById("import-btn");
    const tbody = document.getElementById("results-body");
    const exportBtn = document.getElementById("export-btn");
    const clearBtn = document.getElementById("clear-btn");
    const emptyState = document.getElementById("empty-state");
    const tableWrap = document.getElementById("table-wrapper");
    const buttonRow = document.getElementById("button-row");
    const progressPanel = document.getElementById("import-progress");
    const progressLabel = document.getElementById("progress-label");
    const progressFill = document.getElementById("progress-fill");
    const progressMeta = document.getElementById("progress-meta");

    const disclaimerOverlay = document.getElementById("disclaimer-overlay");
    const disclaimerAccept = document.getElementById("disclaimer-accept-btn");

    const clearOverlay = document.getElementById("clear-overlay");
    const clearCancelBtn = document.getElementById("clear-cancel-btn");
    const clearConfirmBtn = document.getElementById("clear-confirm-btn");

    const importOverlay = document.getElementById("import-overlay");
    const importExitBtn = document.getElementById("import-exit-btn");
    const dropZone = document.getElementById("drop-zone");
    const csvFileInput = document.getElementById("csv-file-input");
    const importFeedback = document.getElementById("import-feedback");

    const completeOverlay = document.getElementById("complete-overlay");
    const completeMessage = document.getElementById("complete-message");
    const reloadBtn = document.getElementById("reload-btn");

    const reportTabBtn = document.getElementById("report-tab-btn");
    const analyticsTabBtn = document.getElementById("analytics-tab-btn");
    const reportView = document.getElementById("report-view");
    const analyticsView = document.getElementById("analytics-view");

    const analyticsFilterButtons = Array.from(document.querySelectorAll(".analytics-filter-btn"));
    const generateReportBtn = document.getElementById("generate-report-btn");
    const analyticsEmptyState = document.getElementById("analytics-empty-state");
    const analyticsGrid = document.getElementById("analytics-grid");

    const medicinesTableBody = document.getElementById("medicines-table-body");
    const associationTableBody = document.getElementById("association-table-body");
    const adrsTableBody = document.getElementById("adrs-table-body");

    const medicinesChartCanvas = document.getElementById("medicines-chart");
    const associationChartCanvas = document.getElementById("association-chart");
    const adrsChartCanvas = document.getElementById("adrs-chart");

    const ORIGINAL_ANALYZE_TEXT = "Analyze Report";
    const ORIGINAL_REPORT_TEXT = "Generate Report";
    const REPORTS_COLUMN_NAME = "reports";

    let activeTab = "report";
    let currentAnalyticsView = "all";
    let chartInstances = {
        medicines: null,
        association: null,
        adrs: null,
    };

    disclaimerAccept.addEventListener("click", function () {
        disclaimerOverlay.style.display = "none";
    });

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function trunc(value, decimals) {
        const factor = Math.pow(10, decimals);
        return (Math.floor(value * factor) / factor).toFixed(decimals);
    }

    function createRow(row) {
        const tr = document.createElement("tr");
        tr.innerHTML = [
            `<td>${escapeHtml(row.case_id)}</td>`,
            `<td>${escapeHtml(row.text_report)}</td>`,
            `<td>${escapeHtml(row.drug_mention)}</td>`,
            `<td>${escapeHtml(row.reaction_mention)}</td>`,
            `<td>${escapeHtml(row.onset)}</td>`,
            `<td>${trunc(row.raw_confidence, 4)}</td>`,
            `<td>${escapeHtml(row.status)}</td>`,
            `<td>${trunc(row.latency_ms, 4)}</td>`,
        ].join("");
        return tr;
    }

    function renderSimpleTable(target, rows, columns) {
        target.innerHTML = "";

        if (!rows.length) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="${columns.length}" class="analytics-table-empty">No data available</td>`;
            target.appendChild(tr);
            return;
        }

        rows.forEach(function (row) {
            const tr = document.createElement("tr");
            tr.innerHTML = columns.map(function (column) {
                return `<td>${escapeHtml(String(row[column] || ""))}</td>`;
            }).join("");
            target.appendChild(tr);
        });
    }

    function toggleEmptyState() {
        const hasRows = tbody.children.length > 0;
        emptyState.classList.toggle("visible", !hasRows);
        tableWrap.style.display = hasRows ? "" : "none";
    }

    function setSingleAnalyzeLoading(loading) {
        analyzeBtn.disabled = loading;
        importBtn.disabled = loading;
        analyzeBtn.textContent = loading ? "Analyzing..." : ORIGINAL_ANALYZE_TEXT;
    }

    function setBatchUiActive(active) {
        input.style.display = active ? "none" : "";
        buttonRow.style.display = active ? "none" : "";
        progressPanel.style.display = active ? "block" : "none";
        analyzeBtn.disabled = active;
        importBtn.disabled = active;
        exportBtn.disabled = active;
        clearBtn.disabled = active;
    }

    function updateProgress(processed, total, failures) {
        const percent = total > 0 ? (processed / total) * 100 : 0;
        progressFill.style.width = `${percent}%`;
        progressMeta.textContent = failures > 0
            ? `${processed} of ${total} reports processed - ${failures} failed`
            : `${processed} of ${total} reports processed`;
    }

    function resetProgressUi() {
        progressLabel.textContent = "Analyzing imported reports...";
        progressFill.style.width = "0%";
        progressMeta.textContent = "0 of 0 reports processed";
    }

    function showClearModal() {
        clearOverlay.style.display = "flex";
    }

    function hideClearModal() {
        clearOverlay.style.display = "none";
    }

    function showImportModal() {
        importFeedback.textContent = "";
        importFeedback.classList.remove("visible", "error", "success");
        csvFileInput.value = "";
        dropZone.classList.remove("drag-active");
        importOverlay.style.display = "flex";
    }

    function hideImportModal() {
        importOverlay.style.display = "none";
    }

    function showCompletionModal(message) {
        completeMessage.textContent = message;
        completeOverlay.style.display = "flex";
    }

    function setImportFeedback(message, type) {
        importFeedback.textContent = message;
        importFeedback.classList.add("visible");
        importFeedback.classList.remove("error", "success");
        importFeedback.classList.add(type);
    }

    function normalizeHeader(header) {
        return String(header || "").replace(/^\ufeff/, "").trim();
    }

    function parseCsv(text) {
        const rows = [];
        let row = [];
        let field = "";
        let inQuotes = false;

        for (let i = 0; i < text.length; i += 1) {
            const char = text[i];
            const next = text[i + 1];

            if (inQuotes) {
                if (char === "\"") {
                    if (next === "\"") {
                        field += "\"";
                        i += 1;
                    } else {
                        inQuotes = false;
                    }
                } else {
                    field += char;
                }
                continue;
            }

            if (char === "\"") {
                inQuotes = true;
            } else if (char === ",") {
                row.push(field);
                field = "";
            } else if (char === "\n") {
                row.push(field);
                rows.push(row);
                row = [];
                field = "";
            } else if (char === "\r") {
                if (next !== "\n") {
                    row.push(field);
                    rows.push(row);
                    row = [];
                    field = "";
                }
            } else {
                field += char;
            }
        }

        row.push(field);
        rows.push(row);

        return rows.filter(function (currentRow) {
            return currentRow.some(function (value) {
                return String(value).trim() !== "";
            });
        });
    }

    function extractReportsFromCsvText(text) {
        const rows = parseCsv(text);
        if (!rows.length) {
            throw new Error("The selected file is empty.");
        }

        const headers = rows[0].map(normalizeHeader);
        const reportIndex = headers.findIndex(function (header) {
            return header === REPORTS_COLUMN_NAME;
        });

        if (reportIndex === -1) {
            throw new Error('Upload rejected. Please use a CSV file that contains a column named "reports".');
        }

        const reports = rows
            .slice(1)
            .map(function (row) {
                return String(row[reportIndex] || "").trim();
            })
            .filter(Boolean);

        if (!reports.length) {
            throw new Error('The file was accepted, but no report entries were found under the "reports" column.');
        }

        return reports;
    }

    function setActiveTab(tab) {
        activeTab = tab;
        const onReport = tab === "report";

        reportTabBtn.classList.toggle("active", onReport);
        analyticsTabBtn.classList.toggle("active", !onReport);

        reportView.style.display = onReport ? "" : "none";
        analyticsView.style.display = onReport ? "none" : "";

        reportView.classList.toggle("active", onReport);
        analyticsView.classList.toggle("active", !onReport);
    }

    function destroyCharts() {
        Object.keys(chartInstances).forEach(function (key) {
            if (chartInstances[key]) {
                chartInstances[key].destroy();
                chartInstances[key] = null;
            }
        });
    }

    function pieChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 11,
                        },
                    },
                },
            },
        };
    }

    function renderAnalyticsCharts(summary) {
        destroyCharts();

        chartInstances.medicines = new Chart(medicinesChartCanvas, {
            type: "pie",
            data: {
                labels: summary.medicine_chart.map(function (item) { return item.name; }),
                datasets: [{
                    data: summary.medicine_chart.map(function (item) { return item.count; }),
                    backgroundColor: ["#1d4ed8", "#f97316", "#15803d", "#0ea5e9", "#7c3aed", "#facc15", "#64748b"],
                }],
            },
            options: pieChartOptions(),
        });

        chartInstances.association = new Chart(associationChartCanvas, {
            type: "bar",
            data: {
                labels: summary.association_chart.map(function (item) { return item.drug_name; }),
                datasets: [{
                    label: "Top ADR Count",
                    data: summary.association_chart.map(function (item) { return item.count; }),
                    backgroundColor: "#2563eb",
                    borderRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function (tooltipItems) {
                                return tooltipItems[0].label;
                            },
                            label: function (context) {
                                const item = summary.association_chart[context.dataIndex];
                                return [`Top ADR: ${item.top_adr}`, `Count: ${item.count}`];
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0,
                        },
                    },
                },
            },
        });

        chartInstances.adrs = new Chart(adrsChartCanvas, {
            type: "pie",
            data: {
                labels: summary.reaction_chart.map(function (item) { return item.name; }),
                datasets: [{
                    data: summary.reaction_chart.map(function (item) { return item.count; }),
                    backgroundColor: ["#1d4ed8", "#f97316", "#15803d", "#0ea5e9", "#7c3aed", "#facc15", "#64748b"],
                }],
            },
            options: pieChartOptions(),
        });
    }

    async function renderAnalytics() {
        analyticsFilterButtons.forEach(function (button) {
            button.classList.toggle("active", button.dataset.view === currentAnalyticsView);
        });

        try {
            const res = await fetch(`/api/analytics?view=${encodeURIComponent(currentAnalyticsView)}`);
            if (!res.ok) {
                throw new Error("Unable to load analytics data.");
            }

            const summary = await res.json();

            renderSimpleTable(medicinesTableBody, summary.medicine_table, ["name", "count"]);
            renderSimpleTable(associationTableBody, summary.association_table, ["drug_name", "top_adr", "count"]);
            renderSimpleTable(adrsTableBody, summary.reaction_table, ["name", "count"]);

            analyticsEmptyState.style.display = summary.has_data ? "none" : "block";
            analyticsGrid.style.display = summary.has_data ? "grid" : "none";
            generateReportBtn.disabled = !summary.has_data;

            if (summary.has_data) {
                renderAnalyticsCharts(summary);
            } else {
                destroyCharts();
            }
        } catch (_) {
            analyticsEmptyState.style.display = "block";
            analyticsGrid.style.display = "none";
            generateReportBtn.disabled = true;
            destroyCharts();
        }
    }

    async function generateAnalyticsReport() {
        generateReportBtn.disabled = true;
        generateReportBtn.textContent = "Generating...";

        try {
            const res = await fetch(`/api/analytics/report?view=${encodeURIComponent(currentAnalyticsView)}`);
            if (!res.ok) {
                const err = await res.json().catch(function () { return {}; });
                throw new Error(err.detail || "Unable to generate report.");
            }

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `reportrx_analytics_${currentAnalyticsView}.pdf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            alert(error && error.message ? error.message : "Unable to generate report right now.");
        } finally {
            generateReportBtn.disabled = false;
            generateReportBtn.textContent = ORIGINAL_REPORT_TEXT;
        }
    }

    async function loadReports() {
        try {
            const res = await fetch("/api/reports");
            if (!res.ok) {
                return;
            }
            const reports = await res.json();
            reports.forEach(function (row) {
                tbody.appendChild(createRow(row));
            });
        } catch (_) {
            /* silent */
        }
        toggleEmptyState();
    }

    async function analyzeSingleReport(text) {
        const res = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text_report: text }),
        });

        if (!res.ok) {
            const err = await res.json().catch(function () { return {}; });
            throw new Error(err.detail || "Request failed");
        }

        return res.json();
    }

    async function handleAnalyze() {
        const text = input.value.trim();
        if (!text) {
            input.focus();
            return;
        }

        setSingleAnalyzeLoading(true);

        try {
            const row = await analyzeSingleReport(text);
            tbody.appendChild(createRow(row));
            input.value = "";
            toggleEmptyState();
            if (activeTab === "analytics") {
                renderAnalytics();
            }
        } catch (_) {
            alert("Unable to analyze report right now. Please try again.");
        } finally {
            setSingleAnalyzeLoading(false);
        }
    }

    async function executeClear() {
        hideClearModal();
        try {
            const res = await fetch("/api/reports", { method: "DELETE" });
            if (res.ok) {
                tbody.innerHTML = "";
                toggleEmptyState();
                await renderAnalytics();
            }
        } catch (_) {
            /* silent */
        }
    }

    async function handleImportedFile(file) {
        if (!file) {
            return;
        }

        try {
            const text = await file.text();
            const reports = extractReportsFromCsvText(text);

            setImportFeedback(
                `File accepted. ${reports.length} report${reports.length === 1 ? "" : "s"} ready for analysis.`,
                "success"
            );

            hideImportModal();
            resetProgressUi();
            setBatchUiActive(true);

            let processed = 0;
            let failures = 0;
            updateProgress(processed, reports.length, failures);

            for (const reportText of reports) {
                try {
                    const row = await analyzeSingleReport(reportText);
                    tbody.appendChild(createRow(row));
                } catch (_) {
                    failures += 1;
                } finally {
                    processed += 1;
                    updateProgress(processed, reports.length, failures);
                }
            }

            setBatchUiActive(false);
            resetProgressUi();
            toggleEmptyState();
            await renderAnalytics();

            const successCount = reports.length - failures;
            const summary = failures > 0
                ? `Analysis complete. ${successCount} report${successCount === 1 ? "" : "s"} analyzed successfully and ${failures} failed. Reload the site to see the data.`
                : `Analysis complete. ${successCount} report${successCount === 1 ? "" : "s"} analyzed successfully. Reload the site to see the data.`;

            showCompletionModal(summary);
        } catch (error) {
            setImportFeedback(
                error && error.message
                    ? error.message
                    : 'Upload rejected. Please use a CSV file that contains a column named "reports".',
                "error"
            );
        }
    }

    function handleExport() {
        window.open("/api/export/csv", "_blank");
    }

    function openFilePicker() {
        csvFileInput.click();
    }

    clearCancelBtn.addEventListener("click", hideClearModal);
    clearConfirmBtn.addEventListener("click", executeClear);

    importExitBtn.addEventListener("click", hideImportModal);
    reloadBtn.addEventListener("click", function () {
        window.location.reload();
    });

    analyzeBtn.addEventListener("click", handleAnalyze);
    importBtn.addEventListener("click", showImportModal);
    exportBtn.addEventListener("click", handleExport);
    clearBtn.addEventListener("click", showClearModal);
    generateReportBtn.addEventListener("click", generateAnalyticsReport);

    reportTabBtn.addEventListener("click", function () {
        setActiveTab("report");
    });

    analyticsTabBtn.addEventListener("click", async function () {
        setActiveTab("analytics");
        await renderAnalytics();
    });

    analyticsFilterButtons.forEach(function (button) {
        button.addEventListener("click", async function () {
            currentAnalyticsView = button.dataset.view;
            await renderAnalytics();
        });
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && event.ctrlKey) {
            event.preventDefault();
            handleAnalyze();
        }
    });

    csvFileInput.addEventListener("change", function (event) {
        const file = event.target.files && event.target.files[0];
        handleImportedFile(file);
    });

    dropZone.addEventListener("click", openFilePicker);
    dropZone.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openFilePicker();
        }
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) {
            event.preventDefault();
            dropZone.classList.add("drag-active");
        });
    });

    ["dragleave", "dragend", "drop"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) {
            event.preventDefault();
            dropZone.classList.remove("drag-active");
        });
    });

    dropZone.addEventListener("drop", function (event) {
        const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        handleImportedFile(file);
    });

    loadReports();
})();
