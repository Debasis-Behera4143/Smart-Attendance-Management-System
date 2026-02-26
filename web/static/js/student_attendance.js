document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("studentAttendanceRoot");
    if (!root) {
        return;
    }

    const studentIdInput = document.getElementById("studentIdInput");
    const subjectFilter = document.getElementById("studentSubjectFilter");
    const loadBtn = document.getElementById("loadStudentAttendanceBtn");
    const summaryGrid = document.getElementById("subjectSummaryGrid");
    const studentMetaCard = document.getElementById("studentMetaCard");
    const studentMetaBody = document.getElementById("studentMetaBody");
    const attendanceBody = document.getElementById("studentAttendanceBody");

    const renderSummary = (rows) => {
        if (!rows.length) {
            summaryGrid.innerHTML = '<div class="empty-state">No attendance summary available.</div>';
            return;
        }

        summaryGrid.innerHTML = rows
            .map(
                (row) => `
                    <article class="stat-card">
                        <span>${row.subject}</span>
                        <strong>${row.attendance_rate}%</strong>
                        <p class="meta-note">Present ${row.present_classes}/${row.total_classes}</p>
                    </article>
                `
            )
            .join("");
    };

    const renderRecords = (records) => {
        if (!records.length) {
            attendanceBody.innerHTML = '<tr><td colspan="6" class="empty-state">No attendance records found.</td></tr>';
            return;
        }

        attendanceBody.innerHTML = records
            .map(
                (record) => `
                    <tr>
                        <td>${record.date}</td>
                        <td>${record.subject}</td>
                        <td>${formatDateTime(record.entry_time)}</td>
                        <td>${formatDateTime(record.exit_time)}</td>
                        <td>${record.duration}</td>
                        <td><span class="pill ${record.status === "PRESENT" ? "pill-success" : "pill-danger"}">${record.status}</span></td>
                    </tr>
                `
            )
            .join("");
    };

    const renderStudentMeta = (student) => {
        studentMetaBody.innerHTML = `
            <dl class="result-grid">
                <dt>Name</dt><dd>${student.name}</dd>
                <dt>Student ID</dt><dd>${student.student_id}</dd>
                <dt>Roll Number</dt><dd>${student.roll_number}</dd>
                <dt>Registered</dt><dd>${student.registered_date}</dd>
            </dl>
        `;
        studentMetaCard.hidden = false;
    };

    const loadAttendance = async () => {
        const studentId = (studentIdInput.value || "").trim();
        const subject = subjectFilter.value;

        if (!studentId) {
            showNotification("Enter your student ID first", "warning");
            return;
        }

        loadBtn.disabled = true;
        loadBtn.textContent = "Loading...";

        try {
            const query = new URLSearchParams({
                student_id: studentId,
                limit: "200",
            });
            if (subject) {
                query.set("subject", subject);
            }

            const payload = await apiRequest(`/api/student-attendance?${query.toString()}`);
            renderStudentMeta(payload.student);
            renderSummary(payload.subject_summary || []);
            renderRecords(payload.records || []);
            showNotification("Attendance loaded", "success");
        } catch (error) {
            showNotification(error.message, "error");
            summaryGrid.innerHTML = '<div class="empty-state">No attendance summary available.</div>';
            attendanceBody.innerHTML = '<tr><td colspan="6" class="empty-state">No data loaded.</td></tr>';
            studentMetaCard.hidden = true;
        } finally {
            loadBtn.disabled = false;
            loadBtn.textContent = "Load Attendance";
        }
    };

    loadBtn.addEventListener("click", loadAttendance);
    studentIdInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            loadAttendance();
        }
    });
});
