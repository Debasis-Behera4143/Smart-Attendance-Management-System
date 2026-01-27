// Register Student Page JavaScript

let video = null;
let canvas = null;
let context = null;
let stream = null;
let capturedImages = [];
const TOTAL_IMAGES = 20;

document.addEventListener('DOMContentLoaded', function() {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    context = canvas.getContext('2d');
    
    const startCameraBtn = document.getElementById('startCamera');
    const stopCameraBtn = document.getElementById('stopCamera');
    const captureBtn = document.getElementById('captureBtn');
    const registerForm = document.getElementById('registerForm');
    
    // Start camera
    startCameraBtn.addEventListener('click', async function() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { width: 640, height: 480 } 
            });
            video.srcObject = stream;
            
            startCameraBtn.disabled = true;
            stopCameraBtn.disabled = false;
            captureBtn.disabled = false;
            
            showNotification('Camera started successfully', 'success');
        } catch (error) {
            showNotification('Failed to access camera: ' + error.message, 'error');
        }
    });
    
    // Stop camera
    stopCameraBtn.addEventListener('click', function() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;
            
            startCameraBtn.disabled = false;
            stopCameraBtn.disabled = true;
            captureBtn.disabled = true;
            
            showNotification('Camera stopped', 'info');
        }
    });
    
    // Capture images
    captureBtn.addEventListener('click', function() {
        if (capturedImages.length >= TOTAL_IMAGES) {
            showNotification('Already captured 20 images', 'info');
            return;
        }
        
        // Capture image
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg');
        capturedImages.push(imageData);
        
        // Display thumbnail
        const img = document.createElement('img');
        img.src = imageData;
        document.getElementById('capturedImages').appendChild(img);
        
        // Update button text
        captureBtn.textContent = `Capture Images (${capturedImages.length}/20)`;
        
        // Enable submit button when enough images captured
        if (capturedImages.length >= TOTAL_IMAGES) {
            document.getElementById('submitBtn').disabled = false;
            captureBtn.disabled = true;
            showNotification('All images captured! Click Register Student', 'success');
        } else {
            showNotification(`Captured ${capturedImages.length}/${TOTAL_IMAGES}`, 'success');
        }
    });
    
    // Submit registration form
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const name = document.getElementById('name').value;
        const rollNumber = document.getElementById('rollNumber').value;
        
        if (capturedImages.length < TOTAL_IMAGES) {
            showNotification('Please capture all 20 images first', 'error');
            return;
        }
        
        // Generate student ID
        const studentId = `student_${rollNumber.padStart(3, '0')}_${name.replace(/ /g, '_')}`;
        
        try {
            // Register student
            const registerResponse = await fetch('/api/register-student', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ student_id: studentId, name, roll_number: rollNumber })
            });
            
            const registerData = await registerResponse.json();
            
            if (!registerData.success) {
                showNotification(registerData.message, 'error');
                return;
            }
            
            // Save images
            showNotification('Saving images...', 'info');
            
            const imagesResponse = await fetch('/api/save-face-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ student_id: studentId, images: capturedImages })
            });
            
            const imagesData = await imagesResponse.json();
            
            if (!imagesData.success) {
                showNotification(imagesData.message, 'error');
                return;
            }
            
            // Generate encodings
            showNotification('Generating face encodings...', 'info');
            
            const encodingsResponse = await fetch('/api/generate-encodings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const encodingsData = await encodingsResponse.json();
            
            if (encodingsData.success) {
                showNotification('Student registered successfully!', 'success');
                
                // Reset form
                registerForm.reset();
                capturedImages = [];
                document.getElementById('capturedImages').innerHTML = '';
                captureBtn.textContent = 'Capture Images (0/20)';
                document.getElementById('submitBtn').disabled = true;
                
                // Stop camera
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    video.srcObject = null;
                    startCameraBtn.disabled = false;
                    stopCameraBtn.disabled = true;
                    captureBtn.disabled = true;
                }
            } else {
                showNotification(encodingsData.message, 'error');
            }
            
        } catch (error) {
            showNotification('Error: ' + error.message, 'error');
        }
    });
});
