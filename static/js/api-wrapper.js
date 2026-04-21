/**
 * Wrapper functions for API calls with retry logic
 * Replace direct fetch calls with these functions
 */

// Check if _originalFetch exists (from error-recovery.js)
if (typeof _originalFetch === 'undefined') {
    console.error('ERROR: error-recovery.js must be loaded before api-wrapper.js');
}

// Override fetch for /api/ endpoints to add API keys automatically
window.fetch = function(url, options = {}) {
    // Only modify API calls
    if (typeof url === 'string' && url.startsWith('/api/')) {
        // Add API keys header
        if (!options.headers) {
            options.headers = {};
        }

        // Add API keys if not already present
        if (!options.headers['X-API-Keys']) {
            options.headers['X-API-Keys'] = apiKeyManager.encodeKeys();
        }
        try {
            const t = localStorage.getItem('ai_council_user_session_token');
            if (t && !options.headers['X-User-Session']) {
                options.headers['X-User-Session'] = t;
            }
        } catch { /* ignore */ }

        // Use fetchWithRetry for better error handling
        return fetchWithRetry(url, options).catch(error => {
            const errorInfo = handleError(error, `API call to ${url}`);

            // Queue request if it should be retried
            if (errorInfo.shouldQueue && options.method !== 'GET') {
                requestQueue.add({ url, options });
            }

            throw error;
        });
    }

    // Use original fetch for non-API calls
    return _originalFetch(url, options);
};

console.log('API calls enhanced with retry logic and API key support');
