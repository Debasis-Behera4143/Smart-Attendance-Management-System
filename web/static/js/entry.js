let stream = null;
let monitorTimer = null;
let sessionStopTimer = null;
let isBusy = false;
let lastGrayFrame = null;

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("entryRoot");
    if (!root) {
        return;
    }

    const baseScanInterval = Number(root.dataset.scanIntervalMs || 1500);
    const defaultRunInterval = Number(root.dataset.defaultRunInterval || 45);
    const defaultSessionDuration = Number(root.dataset.defaultSessionDuration || 90);
    const defaultMotionThreshold = Number(root.dataset.defaultMotionThreshold || 0.018);

    const video = document.getElementById("liveVideo");
    const canvas = document.getElementById("frameCanvas");
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const scanBtn = document.getElementById("scanOnceBtn");
    const monitorBtn = document.getElementById("toggleMonitorBtn");
    const statusNode = document.getElementById("liveStatus");
    const resultBox = document.getElementById("resultBox");
    const resultContent = document.getElementById("resultContent");
    const recentList = document.getElementById("recentEntriesList");
    const cameraPolicy = document.getElementById("cameraPolicy");
    const useYolo = document.getElementById("useYolo");
    const activeSubject = document.getElementById("activeSubject");
    const cameraRunMode = document.getElementById("cameraRunMode");
    const runInterval = document.getElementById("runInterval");
    const sessionDuration = document.getElementById("sessionDuration");
    const motionThreshold = document.getElementById("motionThreshold");

    runInterval.value = runInterval.value || String(defaultRunInterval);
    sessionDuration.value = sessionDuration.value || String(defaultSessionDuration);
    motionThreshold.value = motionThreshold.value || String(defaultMotionThreshold);

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

    const renderRecent = (entries) => {
        if (!entries.length) {
            recentList.innerHTML = '<p class="meta-note">No entries yet.</p>';
            return;
        }

        recentList.innerHTML = entries
            .map(
                (entry) => `
                    <article class="activity-item">
                        <div>
                            <strong>${entry.name}</strong>
                            <p>${entry.student_id}</p>
                        </div>
                        <time>${formatDateTime(entry.entry_time)}</time>
                    </article>
                `
            )
            .join("");
    };

    const loadRecent = async () => {
        try {
            const payload = await apiRequest("/api/recent-entries");
            renderRecent(payload.entries || []);
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
        resultBox.hidden = false;
        resultContent.innerHTML = `
            <dl class="result-grid">
                <dt>Student</dt><dd>${data.student_name}</dd>
                <dt>ID</dt><dd>${data.student_id}</dd>
                <dt>Confidence</dt><dd>${data.confidence}%</dd>
                <dt>Entry Time</dt><dd>${formatDateTime(data.entry_time)}</dd>
                <dt>Subject</dt><dd>${activeSubject.value}</dd>
            </dl>
        `;
    };

    const scanOnce = async () => {
        if (isBusy || !stream) {
            return;
        }

        const capture = captureFrame();
        if (!capture) {
            return;
        }

        const mode = getSelectedMode();
        if (mode === "interval") {
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
            const data = await apiRequest("/api/recognize-entry", {
                method: "POST",
                body: JSON.stringify({ image: capture.jpeg, subject: activeSubject.value }),
            });

            showResult(data);
            setStatus("Matched");
            showNotification(`${data.student_name} marked inside`, "success");
            await loadRecent();
        } catch (error) {
            setStatus("No Match");
            showNotification(error.message, "warning");
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
        monitorTimer = setInterval(scanOnce, intervalMs);

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
            showNotification("Entry camera started", "success");

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

    window.addEventListener("beforeunload", stopCamera);
    updateMonitorButton();
    loadRecent();
});
