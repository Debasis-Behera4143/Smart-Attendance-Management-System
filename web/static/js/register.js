
function showExtendedNotification(message, type = "info") {
    const host = document.body;
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    node.style.whiteSpace = "pre-line";
    node.style.maxWidth = "500px";
    node.textContent = message;
    host.appendChild(node);

    requestAnimationFrame(() => node.classList.add("show"));


    const timeout = type === "error" ? 8000 : 3500;
    setTimeout(() => {
        node.classList.remove("show");
        setTimeout(() => node.remove(), 400);
    }, timeout);
}

let stream = null;
let autoCaptureTimer = null;
let capturedImages = [];

const captureState = {
    running: false,
};

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("registerRoot");
    if (!root) {
        return;
    }

    const totalImages = Number(root.dataset.totalImages || 20);
    const video = document.getElementById("videoPreview");
    const canvas = document.getElementById("captureCanvas");
    const nameInput = document.getElementById("nameInput");
    const rollInput = document.getElementById("rollInput");
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const autoBtn = document.getElementById("autoCaptureBtn");
    const clearBtn = document.getElementById("clearCaptureBtn");
    const submitBtn = document.getElementById("submitBtn");
    const captureCount = document.getElementById("captureCount");
    const capturedGrid = document.getElementById("capturedGrid");
    const form = document.getElementById("registerForm");

    const setCaptureCount = () => {
        captureCount.textContent = `${capturedImages.length} / ${totalImages}`;
        submitBtn.disabled = capturedImages.length < totalImages;
    };

    const stopAutoCapture = () => {
        captureState.running = false;
        if (autoCaptureTimer) {
            clearInterval(autoCaptureTimer);
            autoCaptureTimer = null;
        }
        autoBtn.textContent = "Auto Capture";
    };

    const stopCamera = () => {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
        stream = null;
        video.srcObject = null;
        stopAutoCapture();
        startBtn.disabled = false;
        stopBtn.disabled = true;
        autoBtn.disabled = true;
    };

    const captureFrame = () => {
        if (!stream || capturedImages.length >= totalImages) {
            return;
        }
        if (!video.videoWidth || !video.videoHeight) {
            console.warn("Video not ready - dimensions:", video.videoWidth, video.videoHeight);
            showNotification("Video not ready - please wait a moment", "warning");
            stopAutoCapture();
            return;
        }

        const width = 640;
        const height = 480;
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, width, height);
        const imageData = canvas.toDataURL("image/jpeg", 0.9);
        capturedImages.push(imageData);

        const thumb = document.createElement("img");
        thumb.src = imageData;
        thumb.alt = `capture-${capturedImages.length}`;
        capturedGrid.appendChild(thumb);

        setCaptureCount();
        if (capturedImages.length >= totalImages) {
            stopAutoCapture();
            showNotification("All samples captured", "success");
        }
    };

    startBtn.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "user",
                },
                audio: false,
            });
            video.srcObject = stream;


            await new Promise((resolve) => {
                video.onloadedmetadata = () => {
                    video.play();
                    resolve();
                };
            });

            startBtn.disabled = true;
            stopBtn.disabled = false;
            autoBtn.disabled = false;
            showNotification("Camera started", "success");
        } catch (error) {
            showNotification(error.message, "error");
        }
    });

    stopBtn.addEventListener("click", () => {
        stopCamera();
        showNotification("Camera stopped", "info");
    });

    autoBtn.addEventListener("click", () => {
        if (!stream) {
            showNotification("Start camera first", "warning");
            return;
        }
        if (capturedImages.length >= totalImages) {
            showNotification("Target image count already reached", "info");
            return;
        }
        if (captureState.running) {
            stopAutoCapture();
            showNotification("Auto capture paused", "info");
            return;
        }


        if (!video.videoWidth || !video.videoHeight) {
            showNotification("Camera is loading - please wait and try again", "warning");
            return;
        }

        captureState.running = true;
        autoBtn.textContent = "Pause Capture";
        showNotification("Auto-capture starting - hold steady!", "success");


        setTimeout(() => {
            if (!captureState.running) return;

            captureFrame();


            autoCaptureTimer = setInterval(() => {
                captureFrame();
                if (capturedImages.length >= totalImages) {
                    stopAutoCapture();
                }
            }, 600);
        }, 800);
    });

    clearBtn.addEventListener("click", () => {
        capturedImages = [];
        capturedGrid.innerHTML = "";
        setCaptureCount();
        stopAutoCapture();
    });


    rollInput.addEventListener("input", () => {
        const original = rollInput.value;
        if (!original) {
            rollInput.style.borderColor = '';
            rollInput.title = '';
            return;
        }


        let cleaned = original.toUpperCase();


        cleaned = cleaned.replace(/[\s\-_/.,:\(\)\[\]]+/g, '');


        const prefixes = [
            'ROLLNUMBER', 'ROLLNO',
            'STUDENTNUMBER', 'STUDENTID', 'STUDENTNO', 'STUDENT',
            'REGISTRATIONNO', 'REGISTRATION',
            'REGNUMBER', 'REGNO', 'REG',
            'IDNUMBER', 'IDNO', 'ID',
            'ROLL', 'NUMBER', 'NO',
        ];

        for (const prefix of prefixes) {
            if (cleaned.startsWith(prefix)) {
                cleaned = cleaned.substring(prefix.length);
                break;
            }
        }


        cleaned = cleaned.replace(/[^A-Z0-9]/g, '');


        if (cleaned !== original.toUpperCase() && cleaned.length > 0) {
            rollInput.style.borderColor = '#4CAF50';
            rollInput.style.borderWidth = '2px';
            rollInput.title = `Will be formatted as: ${cleaned}`;
        } else {
            rollInput.style.borderColor = '';
            rollInput.style.borderWidth = '';
            rollInput.title = '';
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = (nameInput.value || "").trim();
        const rollNumber = (rollInput.value || "").trim();

        if (!name || !rollNumber) {
            showNotification("Name and roll number are required", "warning");
            return;
        }
        if (capturedImages.length < totalImages) {
            showNotification(`Capture ${totalImages} images before submitting`, "warning");
            return;
        }

        const studentId = `student_${rollNumber}_${name.replace(/\s+/g, "_")}`;

        submitBtn.disabled = true;
        submitBtn.textContent = "Registering...";

        try {

            submitBtn.textContent = "Validating images... (may take up to 90s)";

            const saveResult = await apiRequest("/api/save-face-images", {
                method: "POST",
                body: JSON.stringify({
                    student_id: studentId,
                    images: capturedImages,
                }),
                timeout: 120000,
                retry: false
            });


            if (saveResult.details) {
                console.log("Face validation results:", saveResult.details);
                const { saved, no_face_detected, invalid } = saveResult.details;
                if (no_face_detected > 0 || invalid > 0) {
                    showNotification(
                        `Processed: ${saved} valid, ${no_face_detected} no face, ${invalid} invalid`,
                        "info"
                    );
                }
            }


            submitBtn.textContent = "Registering student...";

            await apiRequest("/api/register-student", {
                method: "POST",
                body: JSON.stringify({
                    student_id: studentId,
                    name,
                    roll_number: rollNumber,
                }),
                timeout: 15000,
                retry: false
            });


            submitBtn.textContent = "Generating encodings...";


            await apiRequest(`/api/encode-student/${studentId}`, {
                method: "POST",
                timeout: 60000,
                retry: false
            });

            showNotification("Student registered successfully", "success");

            form.reset();
            capturedImages = [];
            capturedGrid.innerHTML = "";
            setCaptureCount();
            stopCamera();
        } catch (error) {

            showExtendedNotification(error.message, "error");


            console.error("Registration error:", error);
        } finally {
            submitBtn.textContent = "Register Student";
            submitBtn.disabled = capturedImages.length < totalImages;
        }
    });

    window.addEventListener("beforeunload", stopCamera);
    setCaptureCount();
});
