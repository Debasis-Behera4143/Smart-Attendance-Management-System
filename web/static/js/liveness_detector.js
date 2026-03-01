/**
 * Liveness Detection Module
 * Provides anti-spoofing mechanisms for face recognition
 * Uses MediaPipe FaceMesh for eye blink detection and motion analysis
 */

class LivenessDetector {
    constructor() {
        this.faceMesh = null;
        this.isReady = false;
        this.lastEARValues = [];
        this.blinkCount = 0;
        this.lastBlinkTime = 0;
        this.facePositions = [];
        this.initialized = false;
        
        // Eye Aspect Ratio (EAR) threshold for blink detection
        this.EAR_THRESHOLD = 0.25; // Increased from 0.21 for more sensitivity
        this.BLINK_COOLDOWN = 200; // ms - Increased to reduce false positives
        this.MAX_POSITION_HISTORY = 15; // More history for better motion detection
        this.MIN_MOTION_SCORE = 0.002; // Reduced from 0.005 for easier detection
        
        this.initializeFaceMesh();
    }

    async initializeFaceMesh() {
        try {
            // Check if MediaPipe library is available
            if (typeof window.FaceMesh === 'undefined') {
                console.warn('MediaPipe FaceMesh library not loaded - liveness detection disabled');
                this.isReady = false;
                this.initialized = false;
                return;
            }

            // Initialize FaceMesh with timeout
            const initTimeout = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Initialization timeout')), 10000)
            );

            const initFaceMesh = new Promise((resolve, reject) => {
                try {
                    this.faceMesh = new FaceMesh({
                        locateFile: (file) => {
                            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4/${file}`;
                        }
                    });

                    this.faceMesh.setOptions({
                        maxNumFaces: 1,
                        refineLandmarks: true,
                        minDetectionConfidence: 0.5,
                        minTrackingConfidence: 0.5
                    });

                    this.faceMesh.onResults((results) => this.onFaceMeshResults(results));
                    resolve();
                } catch (err) {
                    reject(err);
                }
            });

            await Promise.race([initFaceMesh, initTimeout]);
            
            this.isReady = true;
            this.initialized = true;
            console.log('✓ Liveness detection initialized successfully');
        } catch (error) {
            console.error('❌ Failed to initialize liveness detection:', error.message);
            this.isReady = false;
            this.initialized = false;
        }
    }

    onFaceMeshResults(results) {
        if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
            return;
        }

        const landmarks = results.multiFaceLandmarks[0];
        
        // Calculate Eye Aspect Ratio for blink detection
        const ear = this.calculateEAR(landmarks);
        this.lastEARValues.push(ear);
        if (this.lastEARValues.length > 10) {
            this.lastEARValues.shift();
        }

        // Detect blink
        if (ear < this.EAR_THRESHOLD) {
            const now = Date.now();
            if (now - this.lastBlinkTime > this.BLINK_COOLDOWN) {
                this.blinkCount++;
                this.lastBlinkTime = now;
            }
        }

        // Track face position for motion detection
        const noseTip = landmarks[1]; // Nose tip landmark
        this.facePositions.push({ x: noseTip.x, y: noseTip.y, z: noseTip.z });
        if (this.facePositions.length > this.MAX_POSITION_HISTORY) {
            this.facePositions.shift();
        }
    }

    /**
     * Calculate Eye Aspect Ratio (EAR) for blink detection
     * Using standard MediaPipe face mesh landmarks
     */
    calculateEAR(landmarks) {
        // Left eye landmarks
        const leftEye = {
            p1: landmarks[33],  // Left eye outer corner
            p2: landmarks[160], // Left eye top
            p3: landmarks[158], // Left eye bottom
            p4: landmarks[133], // Left eye inner corner
            p5: landmarks[153], // Left eye top middle
            p6: landmarks[145]  // Left eye bottom middle
        };

        // Right eye landmarks
        const rightEye = {
            p1: landmarks[362], // Right eye outer corner
            p2: landmarks[385], // Right eye top
            p3: landmarks[380], // Right eye bottom
            p4: landmarks[263], // Right eye inner corner
            p5: landmarks[386], // Right eye top middle
            p6: landmarks[374]  // Right eye bottom middle
        };

        const leftEAR = this.computeEyeEAR(leftEye);
        const rightEAR = this.computeEyeEAR(rightEye);

        return (leftEAR + rightEAR) / 2.0;
    }

    computeEyeEAR(eye) {
        // Vertical distances
        const v1 = this.euclideanDistance(eye.p2, eye.p3);
        const v2 = this.euclideanDistance(eye.p5, eye.p6);
        // Horizontal distance
        const h = this.euclideanDistance(eye.p1, eye.p4);
        
        return (v1 + v2) / (2.0 * h);
    }

    euclideanDistance(p1, p2) {
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dz = (p1.z || 0) - (p2.z || 0);
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /**
     * Process video frame for liveness detection
     */
    async processFrame(videoElement) {
        if (!this.isReady || !this.faceMesh || !videoElement) {
            return null;
        }

        try {
            await this.faceMesh.send({ image: videoElement });
            return true;
        } catch (error) {
            console.error('Error processing frame:', error);
            return null;
        }
    }

    /**
     * Calculate motion score based on face position changes
     */
    calculateMotionScore() {
        if (this.facePositions.length < 2) {
            return 0;
        }

        let totalMovement = 0;
        for (let i = 1; i < this.facePositions.length; i++) {
            const prev = this.facePositions[i - 1];
            const curr = this.facePositions[i];
            const dx = curr.x - prev.x;
            const dy = curr.y - prev.y;
            const dz = curr.z - prev.z;
            totalMovement += Math.sqrt(dx * dx + dy * dy + dz * dz);
        }

        return totalMovement / (this.facePositions.length - 1);
    }

    /**
     * Get liveness verification result
     */
    getLivenessScore() {
        const motionScore = this.calculateMotionScore();
        const hasBlinks = this.blinkCount > 0;
        const hasMotion = motionScore > this.MIN_MOTION_SCORE;
        const hasEyeData = this.lastEARValues.length >= 3; // Reduced from 5 for faster detection
        const hasFaceDetection = this.facePositions.length > 0;

        // More lenient scoring - just need 2 out of 3 criteria
        const criteriaCount = (hasBlinks ? 1 : 0) + (hasMotion ? 1 : 0) + (hasEyeData ? 1 : 0);
        const isLive = criteriaCount >= 2 && hasFaceDetection;

        return {
            isLive: isLive,
            score: Math.min(100, (
                (hasBlinks ? 35 : 0) +
                (hasMotion ? 35 : 0) +
                (hasEyeData ? 20 : 0) +
                (hasFaceDetection ? 10 : 0)
            )),
            details: {
                blinkCount: this.blinkCount,
                motionScore: motionScore.toFixed(4),
                hasBlinks,
                hasMotion,
                hasEyeData,
                hasFaceDetection,
                avgEAR: hasEyeData ? (this.lastEARValues.reduce((a, b) => a + b, 0) / this.lastEARValues.length).toFixed(3) : 'N/A'
            }
        };
    }

    /**
     * Reset detection state
     */
    reset() {
        this.blinkCount = 0;
        this.lastBlinkTime = 0;
        this.lastEARValues = [];
        this.facePositions = [];
    }

    /**
     * Check if detector is ready
     */
    isInitialized() {
        return this.initialized && this.isReady;
    }
}

// Export for global use
window.LivenessDetector = LivenessDetector;
