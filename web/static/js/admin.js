let allStudents = [];
let studentToDelete = null;
let currentSubjectFilter = "";

async function loadStudents() {
    try {
        const data = await apiRequest("/api/admin/students", {
            retry: false,
        });

        if (data.success) {
            allStudents = data.students || [];
            applyCurrentFilter();
        } else {
            showError("Failed to load students");
        }
    } catch (error) {
        console.error("Error loading students:", error);
        showError(error.message || "Error loading students");
    }
}

function filterBySubject(subject) {
    currentSubjectFilter = subject;

    document.querySelectorAll(".subject-filter-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.subject === subject);
    });

    document.getElementById("filterStatus").innerHTML =
        `Showing attendance for: <strong>${subject || "All Subjects"}</strong>`;

    applyCurrentFilter();
}

function applyCurrentFilter() {
    let filteredStudents = allStudents;

    if (currentSubjectFilter) {
        filteredStudents = allStudents.map((student) => {
            const subjectStats = student.subject_breakdown
                ? student.subject_breakdown.find((row) => row.subject === currentSubjectFilter)
                : null;

            if (!subjectStats) {
                return {
                    ...student,
                    total_classes: 0,
                    attendance_rate: 0,
                    filtered_subject: currentSubjectFilter,
                };
            }

            return {
                ...student,
                total_classes: subjectStats.total_classes,
                attendance_rate: subjectStats.attendance_rate,
                filtered_subject: currentSubjectFilter,
            };
        });
    }

    const query = document.getElementById("searchInput").value.toLowerCase().trim();
    if (query) {
        filteredStudents = filteredStudents.filter((student) =>
            student.student_id.toLowerCase().includes(query) ||
            student.name.toLowerCase().includes(query) ||
            student.roll_number.toLowerCase().includes(query)
        );
    }

    renderStudents(filteredStudents);
    updateStats(filteredStudents);
}

function updateStats(students) {
    const totalStudents = students.length;
    const avgAttendance = students.length > 0
        ? (students.reduce((sum, student) => sum + student.attendance_rate, 0) / students.length).toFixed(1)
        : 0;

    document.getElementById("totalStudents").textContent = totalStudents;
    document.getElementById("avgAttendance").textContent = `${avgAttendance}%`;
}

function renderStudents(students) {
    const container = document.getElementById("tableContainer");

    if (students.length === 0) {
        const emptyMessage = currentSubjectFilter
            ? `No students found for ${currentSubjectFilter}.`
            : "No students registered yet.";
        container.innerHTML = `<div class="no-students">${emptyMessage}</div>`;
        return;
    }

    const tableHTML = `
        <table class="students-table">
            <thead>
                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Roll Number</th>
                    <th>Registered Date</th>
                    <th>Classes</th>
                    <th>Attendance</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${students.map((student) => `
                    <tr>
                        <td><code>${student.student_id}</code></td>
                        <td><strong>${student.name}</strong></td>
                        <td>${student.roll_number}</td>
                        <td>${student.registered_date}</td>
                        <td>${student.total_classes}</td>
                        <td>${getAttendanceBadge(student.attendance_rate)}</td>
                        <td>
                            <button class="delete-btn" onclick="showDeleteModal('${student.student_id}', '${student.name}')">
                                Delete
                            </button>
                        </td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;

    container.innerHTML = tableHTML;
}

function getAttendanceBadge(rate) {
    let className = "attendance-poor";
    if (rate >= 90) className = "attendance-excellent";
    else if (rate >= 75) className = "attendance-good";
    else if (rate >= 60) className = "attendance-average";

    return `<span class="attendance-badge ${className}">${rate.toFixed(1)}%</span>`;
}

function showDeleteModal(studentId, studentName) {
    studentToDelete = studentId;
    document.getElementById("deleteStudentName").textContent = studentName;
    document.getElementById("deleteStudentId").textContent = studentId;
    document.getElementById("deleteModal").classList.add("active");
}

function closeDeleteModal() {
    studentToDelete = null;
    document.getElementById("deleteModal").classList.remove("active");
}

async function confirmDelete() {
    if (!studentToDelete) {
        return;
    }

    const confirmBtn = document.getElementById("confirmDeleteBtn");
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Deleting...";

    try {
        const data = await apiRequest("/api/admin/delete-student", {
            method: "POST",
            body: JSON.stringify({
                student_id: studentToDelete,
            }),
            retry: false,
        });

        if (data.success) {
            showSuccess(`Student ${data.student_name} deleted successfully`);
            closeDeleteModal();
            loadStudents();
        } else {
            showError(data.message || "Failed to delete student");
        }
    } catch (error) {
        console.error("Error deleting student:", error);
        showError(error.message || "Error deleting student");
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Delete Student";
    }
}

function showSuccess(message) {
    showNotification(message, "success");
}

function showError(message) {
    showNotification(message, "error");
}

document.addEventListener("DOMContentLoaded", () => {
    loadStudents();

    const searchInput = document.getElementById("searchInput");
    searchInput.addEventListener("input", applyCurrentFilter);

    document.getElementById("deleteModal").addEventListener("click", (event) => {
        if (event.target.id === "deleteModal") {
            closeDeleteModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeDeleteModal();
        }
    });
});
