function showNotification(message, type = "info") {
    const host = document.body;
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    node.textContent = message;
    host.appendChild(node);

    requestAnimationFrame(() => node.classList.add("show"));

    setTimeout(() => {
        node.classList.remove("show");
        setTimeout(() => node.remove(), 400);
    }, 3500);
}

async function apiRequest(url, options = {}) {
    const apiKey = window.localStorage.getItem("SMART_ATTENDANCE_API_KEY") || "";
    
    // Default timeout of 120 seconds for image processing endpoints
    const timeout = options.timeout || 120000;
    
    const config = {
        headers: {
            "Content-Type": "application/json",
            ...(apiKey ? { "X-API-Key": apiKey } : {}),
            ...(options.headers || {}),
        },
        ...options,
    };

    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    config.signal = controller.signal;
    
    // Retry logic for transient failures
    let lastError = null;
    const maxRetries = options.retry !== false ? 1 : 0; // Default 1 retry for non-upload requests
    const shouldRetry = options.method !== 'POST' || url.includes('/api/health'); // Don't retry POSTs except health
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const response = await fetch(url, config);
            clearTimeout(timeoutId);
            
            let payload = {};
            try {
                const text = await response.text();
                payload = text ? JSON.parse(text) : {};
            } catch (error) {
                payload = { success: false, message: "Invalid server response" };
            }

            if (!response.ok || payload.success === false) {
                const message = payload.message || `Request failed (${response.status})`;
                throw new Error(message);
            }

            return payload;
        } catch (error) {
            lastError = error;
            
            // Don't retry on abort or if this was the last attempt
            if (error.name === 'AbortError' || attempt >= maxRetries || !shouldRetry) {
                break;
            }
            
            // Only retry on network errors
            if (error.message.includes('fetch') || error.message.includes('Network')) {
                console.log(`Request failed (attempt ${attempt + 1}/${maxRetries + 1}), retrying...`);
                await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1s before retry
                continue;
            }
            
            // Don't retry other errors
            break;
        }
    }
    
    // Handle the final error
    clearTimeout(timeoutId);
    if (lastError.name === 'AbortError') {
        throw new Error('Request timeout - processing took too long. Please try again.');
    }
    // Handle network errors
    if (lastError.message === 'Failed to fetch' || lastError.message.includes('NetworkError')) {
        throw new Error('Network error - please check your connection and server status.');
    }
    // Handle TypeError from network issues
    if (lastError instanceof TypeError && !lastError.message) {
        throw new Error('Connection failed - please verify the server is running.');
    }
    throw lastError;
}

function formatDateTime(value) {
    if (!value) {
        return "-";
    }
    const parsed = new Date(value.replace(" ", "T"));
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleString();
}

function formatDuration(minutes) {
    const total = Number(minutes) || 0;
    const hrs = Math.floor(total / 60);
    const mins = total % 60;
    if (!hrs) {
        return `${mins}m`;
    }
    return `${hrs}h ${mins}m`;
}
