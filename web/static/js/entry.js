// Entry Camera Page JavaScript

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
            
            showNotification('Entry camera started', 'success');
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
        const response = await fetch('/api/mark-entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Display success
            document.getElementById('recognitionResult').innerHTML = `
                <div class="alert alert-success">
                    <h4>✓ Entry Marked!</h4>
                    <p><strong>Student:</strong> ${data.student_name}</p>
                    <p><strong>Roll Number:</strong> ${data.roll_number}</p>
                    <p><strong>Entry Time:</strong> ${formatDateTime(data.entry_time)}</p>
                </div>
            `;
            
            showNotification(`Entry marked for ${data.student_name}`, 'success');
            
            // Stop recognition after successful entry
            if (recognitionInterval) {
                clearInterval(recognitionInterval);
                recognitionInterval = null;
                document.getElementById('recognizeBtn').textContent = 'Start Recognition';
                document.getElementById('recognizeBtn').classList.remove('btn-danger');
                document.getElementById('recognizeBtn').classList.add('btn-success');
            }
            
            // Reload recent entries
            loadRecentEntries();
            
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

async function loadRecentEntries() {
    try {
        const response = await fetch('/api/recent-entries');
        const data = await response.json();
        
        if (data.success) {
            const tbody = document.getElementById('recentEntries');
            tbody.innerHTML = '';
            
            data.entries.forEach(entry => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${entry.student_name}</td>
                    <td>${entry.roll_number}</td>
                    <td>${formatDateTime(entry.entry_time)}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error loading recent entries:', error);
    }
}

// Load recent entries on page load
loadRecentEntries();
