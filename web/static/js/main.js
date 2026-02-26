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
    const config = {
        headers: {
            "Content-Type": "application/json",
            ...(apiKey ? { "X-API-Key": apiKey } : {}),
            ...(options.headers || {}),
        },
        ...options,
    };

    const response = await fetch(url, config);
    let payload = {};
    try {
        payload = await response.json();
    } catch (error) {
        payload = { success: false, message: "Invalid server response" };
    }

    if (!response.ok || payload.success === false) {
        const message = payload.message || `Request failed (${response.status})`;
        throw new Error(message);
    }

    return payload;
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
