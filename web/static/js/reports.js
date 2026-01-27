// Reports Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const filterDateBtn = document.getElementById('filterDate');
    const filterAllBtn = document.getElementById('filterAll');
    const searchInput = document.getElementById('searchInput');
    const exportCsvBtn = document.getElementById('exportCsv');
    const exportTxtBtn = document.getElementById('exportTxt');
    
    // Load all attendance records on page load
    loadAttendance();
    
    // Filter by date
    filterDateBtn.addEventListener('click', function() {
        const dateInput = document.getElementById('dateInput').value;
        if (!dateInput) {
            showNotification('Please select a date', 'warning');
            return;
        }
        loadAttendance(dateInput);
    });
    
    // Filter all records
    filterAllBtn.addEventListener('click', function() {
        document.getElementById('dateInput').value = '';
        loadAttendance();
    });
    
    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = document.querySelectorAll('#attendanceTable tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
    
    // Export to CSV
    exportCsvBtn.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/export-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification(`Report exported to: ${data.file_path}`, 'success');
                
                // Download the file
                window.location.href = `/api/download-report?file=${encodeURIComponent(data.file_path)}`;
            } else {
                showNotification(data.message, 'error');
            }
        } catch (error) {
            showNotification('Export failed: ' + error.message, 'error');
        }
    });
    
    // Export to TXT
    exportTxtBtn.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/export-txt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification(`Report exported to: ${data.file_path}`, 'success');
                
                // Download the file
                window.location.href = `/api/download-report?file=${encodeURIComponent(data.file_path)}`;
            } else {
                showNotification(data.message, 'error');
            }
        } catch (error) {
            showNotification('Export failed: ' + error.message, 'error');
        }
    });
});

async function loadAttendance(date = null) {
    try {
        let url = '/api/get-attendance';
        if (date) {
            url += `?date=${date}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            const tbody = document.getElementById('attendanceTable').querySelector('tbody');
            tbody.innerHTML = '';
            
            if (data.records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">No records found</td></tr>';
                return;
            }
            
            data.records.forEach((record, index) => {
                let statusClass = 'warning';
                if (record.status === 'PRESENT') {
                    statusClass = 'success';
                } else if (record.status === 'ABSENT') {
                    statusClass = 'danger';
                }
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${record.student_name}</td>
                    <td>${record.roll_number}</td>
                    <td>${record.date}</td>
                    <td>${record.entry_time || 'N/A'}</td>
                    <td>${record.exit_time || 'N/A'}</td>
                    <td>${record.duration ? formatDuration(record.duration) : 'N/A'}</td>
                    <td><span class="badge bg-${statusClass}">${record.status}</span></td>
                `;
                tbody.appendChild(row);
            });
            
            // Update stats
            updateStats(data.records);
            
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        showNotification('Failed to load attendance: ' + error.message, 'error');
    }
}

function updateStats(records) {
    const totalStudents = records.length;
    const present = records.filter(r => r.status === 'PRESENT').length;
    const absent = records.filter(r => r.status === 'ABSENT').length;
    const pending = records.filter(r => r.status === 'PENDING').length;
    
    const presentPercent = totalStudents > 0 ? ((present / totalStudents) * 100).toFixed(1) : 0;
    
    document.getElementById('totalStudents').textContent = totalStudents;
    document.getElementById('presentCount').textContent = present;
    document.getElementById('absentCount').textContent = absent;
    document.getElementById('pendingCount').textContent = pending;
    document.getElementById('attendancePercent').textContent = presentPercent + '%';
}
