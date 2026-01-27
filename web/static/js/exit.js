// Exit Camera Page JavaScript

let video = null;
let stream = null;
let recognitionInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    video = document.getElementById('video');
    
    const startCameraBtn = document.getElementById('startCamera');
    const stopCameraBtn = document.getElementById('stopCamera');
    const recognizeBtn = document.getElementById('recognizeBtn');
    
    // Start camera
    startCameraBtn.addEventListener('click', async function() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { width: 640, height: 480 } 
            });
            video.srcObject = stream;
            
            startCameraBtn.disabled = true;
            stopCameraBtn.disabled = false;
            recognizeBtn.disabled = false;
            
            showNotification('Exit camera started', 'success');
        } catch (error) {
            showNotification('Failed to access camera: ' + error.message, 'error');
        }
    });
    
    // Stop camera
    stopCameraBtn.addEventListener('click', function() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;
            
            if (recognitionInterval) {
                clearInterval(recognitionInterval);
                recognitionInterval = null;
            }
            
            startCameraBtn.disabled = false;
            stopCameraBtn.disabled = true;
            recognizeBtn.disabled = true;
            recognizeBtn.textContent = 'Start Recognition';
            
            showNotification('Camera stopped', 'info');
        }
    });
    
    // Start/Stop recognition
    recognizeBtn.addEventListener('click', function() {
        if (recognitionInterval) {
            // Stop recognition
            clearInterval(recognitionInterval);
            recognitionInterval = null;
            recognizeBtn.textContent = 'Start Recognition';
            recognizeBtn.classList.remove('btn-danger');
            recognizeBtn.classList.add('btn-success');
            showNotification('Recognition stopped', 'info');
        } else {
            // Start recognition
            recognitionInterval = setInterval(recognizeFace, 2000); // Recognize every 2 seconds
            recognizeBtn.textContent = 'Stop Recognition';
            recognizeBtn.classList.remove('btn-success');
            recognizeBtn.classList.add('btn-danger');
            showNotification('Recognition started - position your face in the camera', 'info');
        }
    });
});

async function recognizeFace() {
    try {
        // Create canvas to capture frame
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg');
        
        // Send to backend for recognition
        const response = await fetch('/api/mark-exit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Determine attendance status color
            let statusClass = 'warning';
            if (data.attendance_status === 'PRESENT') {
                statusClass = 'success';
            } else if (data.attendance_status === 'ABSENT') {
                statusClass = 'danger';
            }
            
            // Display success
            document.getElementById('recognitionResult').innerHTML = `
                <div class="alert alert-${statusClass}">
                    <h4>✓ Exit Marked!</h4>
                    <p><strong>Student:</strong> ${data.student_name}</p>
                    <p><strong>Roll Number:</strong> ${data.roll_number}</p>
                    <p><strong>Entry Time:</strong> ${formatDateTime(data.entry_time)}</p>
                    <p><strong>Exit Time:</strong> ${formatDateTime(data.exit_time)}</p>
                    <p><strong>Duration:</strong> ${formatDuration(data.duration_minutes)}</p>
                    <p><strong>Status:</strong> <span class="badge bg-${statusClass}">${data.attendance_status}</span></p>
                </div>
            `;
            
            showNotification(`Exit marked for ${data.student_name} - ${data.attendance_status}`, 'success');
            
            // Stop recognition after successful exit
            if (recognitionInterval) {
                clearInterval(recognitionInterval);
                recognitionInterval = null;
                document.getElementById('recognizeBtn').textContent = 'Start Recognition';
                document.getElementById('recognizeBtn').classList.remove('btn-danger');
                document.getElementById('recognizeBtn').classList.add('btn-success');
            }
            
            // Reload recent exits
            loadRecentExits();
            
        } else if (data.message === 'Face not recognized') {
            document.getElementById('recognitionResult').innerHTML = `
                <div class="alert alert-warning">
                    <p>❌ Face not recognized. Please try again.</p>
                </div>
            `;
        } else {
            showNotification(data.message, 'warning');
        }
        
    } catch (error) {
        console.error('Recognition error:', error);
    }
}

async function loadRecentExits() {
    try {
        const response = await fetch('/api/recent-exits');
        const data = await response.json();
        
        if (data.success) {
            const tbody = document.getElementById('recentExits');
            tbody.innerHTML = '';
            
            data.exits.forEach(exit => {
                let statusClass = 'warning';
                if (exit.attendance_status === 'PRESENT') {
                    statusClass = 'success';
                } else if (exit.attendance_status === 'ABSENT') {
                    statusClass = 'danger';
                }
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${exit.student_name}</td>
                    <td>${exit.roll_number}</td>
                    <td>${formatDateTime(exit.entry_time)}</td>
                    <td>${formatDateTime(exit.exit_time)}</td>
                    <td>${formatDuration(exit.duration_minutes)}</td>
                    <td><span class="badge bg-${statusClass}">${exit.attendance_status}</span></td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error loading recent exits:', error);
    }
}

// Load recent exits on page load
loadRecentExits();
