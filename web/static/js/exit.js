let stream = null;
let monitorTimer = null;
let sessionStopTimer = null;
let isBusy = false;
let lastGrayFrame = null;
let livenessDetector = null;
let livenessMonitorTimer = null;
let lastManualScanTime = 0;
const MANUAL_SCAN_COOLDOWN_MS = 3000; // 3 seconds cooldown between manual scans

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("exitRoot");
    if (!root) {
        return;
    }

    // Initialize liveness detector
    if (typeof LivenessDetector !== 'undefined') {
        livenessDetector = new LivenessDetector();
    }

    const baseScanInterval = Number(root.dataset.scanIntervalMs || 1500);
    const defaultRunInterval = Number(root.dataset.defaultRunInterval || 45);
    const defaultSessionDuration = Number(root.dataset.defaultSessionDuration || 90);
    const defaultMotionThreshold = Number(root.dataset.defaultMotionThreshold || 0.018);
    const defaultMinimumDuration = Number(root.dataset.defaultMinimumDuration || 90);

    const video = document.getElementById("liveVideo");
    const canvas = document.getElementById("frameCanvas");
    const cameraPanel = document.getElementById("cameraPanel");
    const livenessBadge = document.getElementById("livenessBadge");
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const scanBtn = document.getElementById("scanOnceBtn");
    const monitorBtn = document.getElementById("toggleMonitorBtn");
    const statusNode = document.getElementById("liveStatus");
    const resultBox = document.getElementById("resultBox");
    const resultContent = document.getElementById("resultContent");
    const recentList = document.getElementById("recentExitsList");
    const cameraPolicy = document.getElementById("cameraPolicy");
    const useYolo = document.getElementById("useYolo");
    const activeSubject = document.getElementById("activeSubject");
    const cameraRunMode = document.getElementById("cameraRunMode");
    const runInterval = document.getElementById("runInterval");
    const sessionDuration = document.getElementById("sessionDuration");
    const motionThreshold = document.getElementById("motionThreshold");
    const minimumDuration = document.getElementById("minimumDuration");
    const useLivenessDetection = document.getElementById("useLivenessDetection");
    const livenessStatusText = document.getElementById("livenessStatusText");

    runInterval.value = runInterval.value || String(defaultRunInterval);
    sessionDuration.value = sessionDuration.value || String(defaultSessionDuration);
    motionThreshold.value = motionThreshold.value || String(defaultMotionThreshold);
    minimumDuration.value = minimumDuration.value || String(defaultMinimumDuration);

    const setStatus = (text) => {
        statusNode.textContent = text;
    };

    const monitorRunning = () => Boolean(monitorTimer);

    const getSelectedMode = () => (cameraRunMode.value || "once").trim();

    const getIntervalMsForMode = () => {
        const mode = getSelectedMode();
        if (mode === "interval") {
            const seconds = Math.max(3, Number(runInterval.value || defaultRunInterval));
            return Math.round(seconds * 1000);
        }
        return Math.max(600, baseScanInterval);
    };

    const updateMonitorButton = () => {
        const mode = getSelectedMode();
        if (mode === "once") {
            monitorBtn.textContent = "Run Once Mode";
            monitorBtn.disabled = true;
            return;
        }
        monitorBtn.disabled = !stream;
        monitorBtn.textContent = monitorRunning() ? "Stop Monitor" : "Start Monitor";
    };

    const updateUIFeatureAvailability = () => {
        const policy = cameraPolicy.value;
        const mode = getSelectedMode();

        // If "Always On" is selected, disable "Run Once" mode
        if (policy === "always_on") {
            Array.from(cameraRunMode.options).forEach(option => {
                if (option.value === "once") {
                    option.disabled = true;
                }
            });
            // If current mode is "once", switch to "session"
            if (mode === "once") {
                cameraRunMode.value = "session";
            }
        } else {
            // Re-enable all run mode options
            Array.from(cameraRunMode.options).forEach(option => {
                option.disabled = false;
            });
        }

        // If "Run Once" is selected, disable "Always On" policy
        if (mode === "once") {
            Array.from(cameraPolicy.options).forEach(option => {
                if (option.value === "always_on") {
                    option.disabled = true;
                }
            });
            // If current policy is "always_on", switch to "on_demand"
            if (policy === "always_on") {
                cameraPolicy.value = "on_demand";
            }
        } else {
            // Re-enable all policy options
            Array.from(cameraPolicy.options).forEach(option => {
                option.disabled = false;
            });
        }

        // Enable/disable features based on run mode
        // Session Duration: only for "session" mode
        sessionDuration.disabled = (mode !== "session");
        sessionDuration.parentElement.style.opacity = (mode === "session") ? "1" : "0.5";

        // Interval Check: only for "interval" mode
        runInterval.disabled = (mode !== "interval");
        runInterval.parentElement.style.opacity = (mode === "interval") ? "1" : "0.5";

        // Fair Motion Threshold: only for "interval" mode
        motionThreshold.disabled = (mode !== "interval");
        motionThreshold.parentElement.style.opacity = (mode === "interval") ? "1" : "0.5";
    };

    const clearSessionTimer = () => {
        if (sessionStopTimer) {
            clearTimeout(sessionStopTimer);
            sessionStopTimer = null;
        }
    };

    const stopMonitoring = () => {
        if (monitorTimer) {
            clearInterval(monitorTimer);
            monitorTimer = null;
        }
        clearSessionTimer();
        updateMonitorButton();
    };

    const stopCamera = () => {
        stopMonitoring();
        stopLivenessMonitoring();
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
        stream = null;
        video.srcObject = null;
        lastGrayFrame = null;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        scanBtn.disabled = true;
        monitorBtn.disabled = true;
        setStatus("Idle");
    };

    const captureFrame = () => {
        if (!video.videoWidth || !video.videoHeight) {
            return null;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext("2d");
        context.drawImage(video, 0, 0);
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        return {
            jpeg: canvas.toDataURL("image/jpeg", 0.85),
            pixels: imageData.data,
        };
    };

    const computeMotionScore = (pixelBuffer) => {
        const sampleStep = 16;
        const current = [];

        for (let i = 0; i < pixelBuffer.length; i += sampleStep) {
            const r = pixelBuffer[i] || 0;
            const g = pixelBuffer[i + 1] || 0;
            const b = pixelBuffer[i + 2] || 0;
            current.push((r + g + b) / 3);
        }

        if (!lastGrayFrame) {
            lastGrayFrame = current;
            return 1;
        }

        let moved = 0;
        const threshold = 22;
        const size = Math.min(lastGrayFrame.length, current.length);
        for (let idx = 0; idx < size; idx += 1) {
            if (Math.abs(current[idx] - lastGrayFrame[idx]) > threshold) {
                moved += 1;
            }
        }
        lastGrayFrame = current;
        return size ? moved / size : 0;
    };

    // Liveness Detection Functions
    const updateLivenessDetectorStatus = () => {
        if (!livenessStatusText || !useLivenessDetection) {
            return;
        }

        if (!livenessDetector) {
            livenessStatusText.textContent = 'Not Available (Library Missing)';
            livenessStatusText.style.color = 'var(--warning)';
            useLivenessDetection.checked = false;
            useLivenessDetection.disabled = true;
        } else if (livenessDetector.isInitialized()) {
            livenessStatusText.textContent = 'Available';
            livenessStatusText.style.color = 'var(--success)';
            // Restore user preference
            const savedPref = localStorage.getItem('SMART_ATTENDANCE_USE_LIVENESS');
            if (savedPref !== null) {
                useLivenessDetection.checked = savedPref === 'true';
            }
        } else {
            livenessStatusText.textContent = 'Initialization Failed';
            livenessStatusText.style.color = 'var(--danger)';
            useLivenessDetection.checked = false;
            useLivenessDetection.disabled = true;
        }
    };

    const isLivenessEnabled = () => {
        return useLivenessDetection && useLivenessDetection.checked;
    };

    const startLivenessMonitoring = () => {
        // Check if liveness is enabled by user
        if (!isLivenessEnabled()) {
            console.info('Liveness detection disabled by user');
            return;
        }

        if (!livenessDetector || !livenessDetector.isInitialized()) {
            console.info('Liveness detection not available');
            return;
        }

        livenessDetector.reset();
        
        if (livenessBadge) {
            livenessBadge.hidden = false;
            livenessBadge.className = 'liveness-badge checking';
            livenessBadge.textContent = 'Checking Liveness...';
        }

        if (cameraPanel) {
            cameraPanel.classList.remove('liveness-verified', 'liveness-failed');
            cameraPanel.classList.add('liveness-checking');
        }

        livenessMonitorTimer = setInterval(async () => {
            if (!video || !stream) {
                stopLivenessMonitoring();
                return;
            }
            await livenessDetector.processFrame(video);
            updateLivenessUI();
        }, 100);
    };

    const stopLivenessMonitoring = () => {
        if (livenessMonitorTimer) {
            clearInterval(livenessMonitorTimer);
            livenessMonitorTimer = null;
        }
        if (livenessBadge) {
            livenessBadge.hidden = true;
        }
        if (cameraPanel) {
            cameraPanel.classList.remove('liveness-checking', 'liveness-verified', 'liveness-failed');
        }
        if (livenessDetector) {
            livenessDetector.reset();
        }
    };

    const updateLivenessUI = () => {
        if (!livenessDetector || !cameraPanel || !livenessBadge) {
            return;
        }
        const livenessResult = livenessDetector.getLivenessScore();
        if (livenessResult.isLive && livenessResult.score >= 60) {
            cameraPanel.classList.remove('liveness-checking', 'liveness-failed');
            cameraPanel.classList.add('liveness-verified');
            livenessBadge.className = 'liveness-badge verified';
            livenessBadge.textContent = 'Live Person Detected';
        } else if (livenessResult.score > 0 && livenessResult.score < 60) {
            cameraPanel.classList.remove('liveness-verified', 'liveness-failed');
            cameraPanel.classList.add('liveness-checking');
            livenessBadge.className = 'liveness-badge checking';
            livenessBadge.textContent = `Verifying... (${livenessResult.score}%)`;
        } else if (livenessResult.score === 0) {
            cameraPanel.classList.remove('liveness-verified', 'liveness-failed');
            cameraPanel.classList.add('liveness-checking');
            livenessBadge.className = 'liveness-badge checking';
            livenessBadge.textContent = 'Checking Liveness...';
        }
    };

    const checkLivenessBeforeScan = () => {
        // If liveness is disabled by user, skip check
        if (!isLivenessEnabled()) {
            return { allowed: true, reason: 'liveness_disabled' };
        }

        if (!livenessDetector || !livenessDetector.isInitialized()) {
            return { allowed: true, reason: 'liveness_not_available' };
        }
        const livenessResult = livenessDetector.getLivenessScore();
        if (!livenessResult.isLive) {
            if (cameraPanel) {
                cameraPanel.classList.remove('liveness-checking', 'liveness-verified');
                cameraPanel.classList.add('liveness-failed');
            }
            if (livenessBadge) {
                livenessBadge.className = 'liveness-badge failed';
                livenessBadge.textContent = 'Liveness Check Failed';
            }
            const details = livenessResult.details;
            let reason = 'Please ensure you are a live person. ';
            if (!details.hasBlinks) {
                reason += 'Blink your eyes naturally. ';
            }
            if (!details.hasMotion) {
                reason += 'Move your head slightly. ';
            }
            return { allowed: false, reason };
        }
        return { allowed: true, livenessData: livenessResult };
    };

    const renderRecent = (records) => {
        if (!records.length) {
            recentList.innerHTML = '<p class="meta-note">No exits yet.</p>';
            return;
        }

        recentList.innerHTML = records
            .map(
                (record) => `
                    <article class="activity-item">
                        <div>
                            <strong>${record.name}</strong>
                            <p>${record.subject} | ${record.status} | ${formatDuration(record.duration)}</p>
                        </div>
                        <time>${formatDateTime(record.exit_time)}</time>
                    </article>
                `
            )
            .join("");
    };

    const loadRecent = async () => {
        try {
            const payload = await apiRequest("/api/recent-exits");
            renderRecent(payload.exits || []);
        } catch (error) {
            recentList.innerHTML = `<p class="meta-note">${error.message}</p>`;
        }
    };

    const persistSettings = async () => {
        const settingsPayload = {
            camera_policy: cameraPolicy.value,
            camera_run_mode: cameraRunMode.value,
            active_subject: activeSubject.value,
            run_interval_seconds: Number(runInterval.value || defaultRunInterval),
            session_duration_minutes: Number(sessionDuration.value || defaultSessionDuration),
            fair_motion_threshold: Number(motionThreshold.value || defaultMotionThreshold),
            minimum_duration_minutes: Number(minimumDuration.value || defaultMinimumDuration),
            use_yolo: useYolo.checked,
        };

        const payload = await apiRequest("/api/settings", {
            method: "POST",
            body: JSON.stringify(settingsPayload),
        });

        if (payload.settings && payload.settings.yolo_supported === false) {
            useYolo.checked = false;
            useYolo.disabled = true;
        }
    };

    const showResult = (data) => {
        const statusClass = data.attendance_status === "PRESENT" ? "pill-success" : "pill-danger";
        resultBox.hidden = false;
        resultContent.innerHTML = `
            <dl class="result-grid">
                <dt>Student</dt><dd>${data.student_name}</dd>
                <dt>ID</dt><dd>${data.student_id}</dd>
                <dt>Subject</dt><dd>${data.subject || activeSubject.value}</dd>
                <dt>Entry</dt><dd>${formatDateTime(data.entry_time)}</dd>
                <dt>Exit</dt><dd>${formatDateTime(data.exit_time)}</dd>
                <dt>Duration</dt><dd>${formatDuration(data.duration_minutes)}</dd>
                <dt>Status</dt><dd><span class="pill ${statusClass}">${data.attendance_status}</span></dd>
            </dl>
        `;
    };

    const scanOnce = async (isAutoScan = false) => {
        if (isBusy || !stream) {
            return;
        }

        // Rate limiting for manual scans (not auto-monitoring)
        if (!isAutoScan) {
            const now = Date.now();
            const timeSinceLastScan = now - lastManualScanTime;
            if (timeSinceLastScan < MANUAL_SCAN_COOLDOWN_MS) {
                const remainingSeconds = Math.ceil((MANUAL_SCAN_COOLDOWN_MS - timeSinceLastScan) / 1000);
                showNotification(`Please wait ${remainingSeconds}s before scanning again`, "warning");
                return;
            }
            lastManualScanTime = now;
        }

        // Check liveness before scanning
        const livenessCheck = checkLivenessBeforeScan();
        if (!livenessCheck.allowed) {
            setStatus("Liveness Failed");
            showNotification(livenessCheck.reason, "warning");
            return;
        }

        const capture = captureFrame();
        if (!capture) {
            return;
        }

        // Only apply motion check during auto-monitoring in interval mode, NOT manual scans
        const mode = getSelectedMode();
        if (mode === "interval" && isAutoScan) {
            const motionScore = computeMotionScore(capture.pixels);
            const requiredMotion = Math.max(0, Number(motionThreshold.value || defaultMotionThreshold));
            if (motionScore < requiredMotion) {
                setStatus("Fair Check: no movement");
                return;
            }
        }

        isBusy = true;
        setStatus("Scanning...");

        try {
            const requestBody = {
                image: capture.jpeg,
                subject: activeSubject.value
            };
            if (livenessCheck.livenessData) {
                requestBody.liveness = livenessCheck.livenessData;
            }
            const data = await apiRequest("/api/recognize-exit", {
                method: "POST",
                body: JSON.stringify(requestBody),
            });

            showResult(data);
            setStatus("Matched");
            showNotification(`${data.student_name} marked ${data.attendance_status}`, "success");
            await loadRecent();
        } catch (error) {
            // Provide specific error messages instead of generic "No Match"
            const message = error.message || "Recognition failed";
            if (message.includes("no active entry")) {
                setStatus("No Entry Found");
            } else if (message.includes("not registered")) {
                setStatus("Not Registered");
            } else if (message.includes("no face") || message.includes("not recognized")) {
                setStatus("No Face Detected");
            } else {
                setStatus("No Match");
            }
            showNotification(message, "warning");
        } finally {
            isBusy = false;
        }
    };

    const startMonitoringForMode = () => {
        const mode = getSelectedMode();
        if (mode === "once") {
            updateMonitorButton();
            return;
        }

        stopMonitoring();
        const intervalMs = getIntervalMsForMode();
        // Pass true to indicate auto-scan (apply motion check)
        monitorTimer = setInterval(() => scanOnce(true), intervalMs);

        if (mode === "session") {
            const totalMinutes = Math.max(1, Number(sessionDuration.value || defaultSessionDuration));
            sessionStopTimer = setTimeout(() => {
                stopMonitoring();
                setStatus("Session completed");
                showNotification("Class session monitor completed", "info");
            }, totalMinutes * 60 * 1000);
        }

        updateMonitorButton();
    };

    startBtn.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: false,
            });
            video.srcObject = stream;
            lastGrayFrame = null;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            scanBtn.disabled = false;
            setStatus("Camera On");
            updateMonitorButton();
            
            // Start liveness monitoring
            startLivenessMonitoring();
            
            showNotification("Exit camera started", "success");

            if (cameraPolicy.value === "always_on" && getSelectedMode() !== "once") {
                startMonitoringForMode();
            }
        } catch (error) {
            showNotification(error.message, "error");
        }
    });

    stopBtn.addEventListener("click", () => {
        stopCamera();
        showNotification("Camera stopped", "info");
    });

    scanBtn.addEventListener("click", scanOnce);

    monitorBtn.addEventListener("click", () => {
        if (!stream) {
            showNotification("Start camera first", "warning");
            return;
        }
        if (getSelectedMode() === "once") {
            showNotification("Run Once mode uses the Scan Once button", "info");
            return;
        }
        if (monitorRunning()) {
            stopMonitoring();
            showNotification("Monitoring stopped", "info");
            return;
        }
        startMonitoringForMode();
        showNotification("Monitoring started", "success");
    });

    const onSettingsChanged = async () => {
        try {
            updateUIFeatureAvailability();
            await persistSettings();
            updateMonitorButton();
            showNotification("Teacher settings updated", "success");

            if (!monitorRunning()) {
                return;
            }
            if (getSelectedMode() === "once") {
                stopMonitoring();
                return;
            }
            startMonitoringForMode();
        } catch (error) {
            showNotification(error.message, "error");
        }
    };

    cameraPolicy.addEventListener("change", onSettingsChanged);
    useYolo.addEventListener("change", onSettingsChanged);
    activeSubject.addEventListener("change", onSettingsChanged);
    cameraRunMode.addEventListener("change", onSettingsChanged);
    runInterval.addEventListener("change", onSettingsChanged);
    sessionDuration.addEventListener("change", onSettingsChanged);
    motionThreshold.addEventListener("change", onSettingsChanged);
    minimumDuration.addEventListener("change", onSettingsChanged);

    // Liveness detection toggle
    if (useLivenessDetection) {
        useLivenessDetection.addEventListener("change", () => {
            const enabled = useLivenessDetection.checked;
            localStorage.setItem('SMART_ATTENDANCE_USE_LIVENESS', enabled.toString());
            
            if (enabled && stream) {
                startLivenessMonitoring();
                showNotification("Liveness detection enabled", "info");
            } else {
                stopLivenessMonitoring();
                showNotification("Liveness detection disabled", "info");
            }
        });
    }

    window.addEventListener("beforeunload", stopCamera);
    updateUIFeatureAvailability();
    updateMonitorButton();
    loadRecent();
    
    // Update liveness detector status after all functions are defined
    if (livenessDetector) {
        setTimeout(updateLivenessDetectorStatus, 2000);
    } else {
        updateLivenessDetectorStatus();
    }
});
