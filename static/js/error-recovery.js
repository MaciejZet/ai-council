/**
 * Error Recovery and Retry Logic
 * Handles network errors, retries, and offline detection
 */

// Save original fetch BEFORE any modifications
const _originalFetch = window.fetch.bind(window);

// Request queue for failed requests
class RequestQueue {
    constructor() {
        this.queue = [];
        this.loadFromLocalStorage();
    }

    add(request) {
        this.queue.push({
            ...request,
            timestamp: Date.now()
        });
        this.saveToLocalStorage();
    }

    async retryAll() {
        if (this.queue.length === 0) return;

        const requests = [...this.queue];
        this.queue = [];

        for (const request of requests) {
            try {
                await fetchWithRetry(request.url, request.options);
                showNotification('✅ Queued request completed', 'success');
            } catch (error) {
                // Re-queue if still failing
                this.add(request);
            }
        }

        this.saveToLocalStorage();
    }

    saveToLocalStorage() {
        try {
            localStorage.setItem('ai_council_request_queue', JSON.stringify(this.queue));
        } catch (e) {
            console.error('Failed to save request queue:', e);
        }
    }

    loadFromLocalStorage() {
        try {
            const saved = localStorage.getItem('ai_council_request_queue');
            if (saved) {
                this.queue = JSON.parse(saved);
            }
        } catch (e) {
            console.error('Failed to load request queue:', e);
            this.queue = [];
        }
    }

    clear() {
        this.queue = [];
        this.saveToLocalStorage();
    }

    getCount() {
        return this.queue.length;
    }
}

// Global request queue
const requestQueue = new RequestQueue();

const USER_SESSION_STORAGE_KEY = 'ai_council_user_session_token';

function userSessionHeader() {
    try {
        const t = localStorage.getItem(USER_SESSION_STORAGE_KEY);
        return t ? { 'X-User-Session': t } : {};
    } catch {
        return {};
    }
}

/**
 * Fetch with automatic retry and exponential backoff
 */
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
    let lastError;

    // Add API keys to headers
    if (!options.headers) {
        options.headers = {};
    }
    Object.assign(options.headers, userSessionHeader());
    options.headers['X-API-Keys'] = apiKeyManager.encodeKeys();

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            // Use ORIGINAL fetch (not window.fetch which is overridden)
            const response = await _originalFetch(url, options);

            // Success
            if (response.ok) {
                return response;
            }

            // Don't retry on client errors (4xx)
            if (response.status >= 400 && response.status < 500) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Client error: ${response.status}`);
            }

            // Retry on server errors (5xx)
            lastError = new Error(`Server error: ${response.status}`);

        } catch (error) {
            lastError = error;

            // Don't retry on network errors if offline
            if (!navigator.onLine) {
                throw new Error('You are offline. Please check your connection.');
            }

            // Don't retry on client errors
            if (error.message && error.message.includes('Client error')) {
                throw error;
            }
        }

        // Exponential backoff: 1s, 2s, 4s
        if (attempt < maxRetries - 1) {
            const delay = Math.pow(2, attempt) * 1000;
            console.log(`Retry attempt ${attempt + 1}/${maxRetries} after ${delay}ms`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }

    throw lastError;
}

/**
 * Stream with fetch (replaces EventSource for custom headers support)
 */
async function streamWithFetch(url, data, onEvent, onError, onComplete) {
    try {
        // Encode API keys
        const encodedKeys = apiKeyManager.encodeKeys();
        console.log(`[streamWithFetch] URL: ${url}`);
        console.log(`[streamWithFetch] Provider: ${data.provider}, Model: ${data.model}`);
        console.log(`[streamWithFetch] API Keys encoded: ${encodedKeys ? 'Yes' : 'No'}`);

        // Use ORIGINAL fetch
        const response = await _originalFetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...userSessionHeader(),
                'X-API-Keys': encodedKeys
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                if (onComplete) onComplete();
                break;
            }

            // Decode chunk
            buffer += decoder.decode(value, { stream: true });

            // Parse SSE format (data: {...}\n\n)
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (onEvent) onEvent(data);
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }

    } catch (error) {
        console.error('Stream error:', error);
        if (onError) onError(error);
    }
}

/**
 * Handle errors with user-friendly messages
 */
function handleError(error, context = '') {
    console.error(`Error ${context}:`, error);

    let message = 'An error occurred';
    let type = 'error';
    let shouldQueue = false;

    const errorMsg = error.message || String(error);

    if (errorMsg.includes('offline') || !navigator.onLine) {
        message = '⚠️ You are offline. Request will retry when back online.';
        type = 'warning';
        shouldQueue = true;
    } else if (errorMsg.includes('429') || errorMsg.includes('rate limit')) {
        message = '⏱️ Rate limit exceeded. Please wait a moment.';
        type = 'warning';
    } else if (errorMsg.includes('401') || errorMsg.includes('authentication')) {
        message = '🔑 Invalid API key. Please check your settings.';
        type = 'error';
    } else if (errorMsg.includes('422') || errorMsg.includes('validation')) {
        message = '⚠️ Invalid input. Please check your query.';
        type = 'warning';
    } else if (errorMsg.includes('timeout')) {
        message = '⏱️ Request timed out. Retrying...';
        type = 'warning';
        shouldQueue = true;
    } else if (errorMsg.includes('network') || errorMsg.includes('fetch')) {
        message = '🌐 Network error. Retrying...';
        type = 'warning';
        shouldQueue = true;
    } else {
        message = `❌ ${errorMsg}`;
        type = 'error';
    }

    showNotification(message, type);

    return { shouldQueue, message, type };
}

/**
 * Offline/Online detection
 */
window.addEventListener('online', () => {
    console.log('Back online');
    showNotification('✅ Back online! Retrying queued requests...', 'success');
    requestQueue.retryAll();
});

window.addEventListener('offline', () => {
    console.log('Gone offline');
    showNotification('⚠️ You are offline. Requests will be queued.', 'warning');
});

/**
 * Show notification with auto-dismiss
 */
function showNotification(message, type = 'info', duration = 3000) {
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };

    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in`;
    notification.textContent = message;
    notification.style.animation = 'fadeIn 0.3s ease-in';

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

// CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(-10px); }
    }
`;
document.head.appendChild(style);

// Show queued requests count on startup
if (requestQueue.getCount() > 0) {
    showNotification(`📋 ${requestQueue.getCount()} queued requests will retry when online`, 'info');
}
