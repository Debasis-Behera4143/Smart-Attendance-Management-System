document.addEventListener("DOMContentLoaded", () => {
    const searchBox = document.getElementById("searchBox");
    const generateBtn = document.getElementById("generateReportBtn");
    const reportDate = document.getElementById("reportDate");
    const reportType = document.getElementById("reportType");
    const reportSubject = document.getElementById("reportSubject");
    const table = document.getElementById("attendanceTable");

    if (searchBox && table) {
        searchBox.addEventListener("input", () => {
            const query = searchBox.value.trim().toLowerCase();
            const rows = table.querySelectorAll("tbody tr");
            rows.forEach((row) => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? "" : "none";
            });
        });
    }

    if (generateBtn) {
        generateBtn.addEventListener("click", async () => {
            const date = reportDate ? reportDate.value : "";
            const type = reportType ? reportType.value : "daily";
            const subject = reportSubject ? reportSubject.value : "";

            generateBtn.disabled = true;
            generateBtn.textContent = "Generating...";

            try {
                const payload = await apiRequest("/api/generate-report", {
                    method: "POST",
                    body: JSON.stringify({ date, type, subject }),
                });

                showNotification("Report generated", "success");
                window.location.href = `/api/download-report?file=${encodeURIComponent(payload.file_name)}`;
            } catch (error) {
                showNotification(error.message, "error");
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = "Generate and Download";
            }
        });
    }

    if (reportSubject) {
        reportSubject.addEventListener("change", () => {
            const subject = reportSubject.value;
            const next = new URL(window.location.href);
            if (subject) {
                next.searchParams.set("subject", subject);
            } else {
                next.searchParams.delete("subject");
            }
            window.location.href = next.toString();
        });
    }
});
