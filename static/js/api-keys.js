/**
 * API Key Manager
 * Manages API keys in localStorage with encryption
 */

class APIKeyManager {
    constructor() {
        this.storageKey = 'ai_council_api_keys';
        this.keys = this.loadKeys();
    }

    /**
     * Load API keys from localStorage
     */
    loadKeys() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (e) {
            console.error('Failed to load API keys:', e);
        }
        return {
            openai: '',
            openai_base_url: '',
            grok: '',
            grok_base_url: '',
            gemini: '',
            deepseek: '',
            deepseek_base_url: '',
            perplexity: '',
            perplexity_base_url: '',
            openrouter: '',
            openrouter_base_url: '',
            custom: '',
            custom_base_url: '',
            custom_model: ''
        };
    }

    /**
     * Save API keys to localStorage
     */
    saveKeys() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.keys));
            return true;
        } catch (e) {
            console.error('Failed to save API keys:', e);
            return false;
        }
    }

    /**
     * Set API key for a provider
     */
    setKey(provider, value) {
        this.keys[provider] = value;
        this.saveKeys();
    }

    /**
     * Get API key for a provider
     */
    getKey(provider) {
        return this.keys[provider] || '';
    }

    /**
     * Check if provider has API key configured
     */
    hasKey(provider) {
        return !!this.keys[provider];
    }

    /**
     * Get all configured providers
     */
    getConfiguredProviders() {
        const providers = ['openai', 'grok', 'gemini', 'deepseek', 'perplexity', 'openrouter', 'custom'];
        return providers.filter(p => this.hasKey(p));
    }

    /**
     * Encode keys for API request header
     */
    encodeKeys() {
        try {
            const json = JSON.stringify(this.keys);
            return btoa(json);
        } catch (e) {
            console.error('Failed to encode keys:', e);
            return '';
        }
    }

    /**
     * Clear all API keys
     */
    clearKeys() {
        this.keys = this.loadKeys();
        Object.keys(this.keys).forEach(key => {
            this.keys[key] = '';
        });
        this.saveKeys();
    }

    /**
     * Export keys as JSON (for backup)
     */
    exportKeys() {
        return JSON.stringify(this.keys, null, 2);
    }

    /**
     * Import keys from JSON
     */
    importKeys(jsonString) {
        try {
            const imported = JSON.parse(jsonString);
            this.keys = { ...this.keys, ...imported };
            this.saveKeys();
            return true;
        } catch (e) {
            console.error('Failed to import keys:', e);
            return false;
        }
    }
}

// Global instance
const apiKeyManager = new APIKeyManager();

/**
 * Show API Keys Settings Modal
 */
function showAPIKeysModal() {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4';
    modal.innerHTML = `
        <div class="bg-white dark:bg-surface-dark rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div class="p-6 border-b border-gray-200 dark:border-white/10 flex justify-between items-center sticky top-0 bg-white dark:bg-surface-dark">
                <h2 class="text-2xl font-bold">🔑 API Keys Settings</h2>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="p-6 space-y-6">
                <!-- Info -->
                <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <p class="text-sm text-blue-800 dark:text-blue-200">
                        🔒 Keys are stored locally in your browser (localStorage). They are never sent to our servers except when making API calls.
                    </p>
                </div>

                <!-- OpenAI -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">OpenAI API Key</label>
                    <input type="password" id="key-openai" value="${apiKeyManager.getKey('openai')}"
                        placeholder="sk-..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-openai-base-url" value="${apiKeyManager.getKey('openai_base_url')}"
                        placeholder="Base URL (optional)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- Grok -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">Grok (xAI) API Key</label>
                    <input type="password" id="key-grok" value="${apiKeyManager.getKey('grok')}"
                        placeholder="xai-..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-grok-base-url" value="${apiKeyManager.getKey('grok_base_url')}"
                        placeholder="Base URL (optional)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- Gemini -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">Google Gemini API Key</label>
                    <input type="password" id="key-gemini" value="${apiKeyManager.getKey('gemini')}"
                        placeholder="AIza..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- DeepSeek -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">DeepSeek API Key</label>
                    <input type="password" id="key-deepseek" value="${apiKeyManager.getKey('deepseek')}"
                        placeholder="sk-..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-deepseek-base-url" value="${apiKeyManager.getKey('deepseek_base_url')}"
                        placeholder="Base URL (optional)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- Perplexity -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">Perplexity API Key</label>
                    <input type="password" id="key-perplexity" value="${apiKeyManager.getKey('perplexity')}"
                        placeholder="pplx-..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-perplexity-base-url" value="${apiKeyManager.getKey('perplexity_base_url')}"
                        placeholder="Base URL (optional)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- OpenRouter -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">OpenRouter API Key</label>
                    <input type="password" id="key-openrouter" value="${apiKeyManager.getKey('openrouter')}"
                        placeholder="sk-or-..."
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-openrouter-base-url" value="${apiKeyManager.getKey('openrouter_base_url')}"
                        placeholder="Base URL (optional)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                </div>

                <!-- Custom API -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium">Custom API (LM Studio, Ollama, etc.)</label>
                    <input type="password" id="key-custom" value="${apiKeyManager.getKey('custom')}"
                        placeholder="API Key (or 'dummy' for local)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-custom-base-url" value="${apiKeyManager.getKey('custom_base_url')}"
                        placeholder="http://localhost:1234/v1 or https://api.example.com/v1"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <input type="text" id="key-custom-model" value="${apiKeyManager.getKey('custom_model')}"
                        placeholder="Model name (e.g., llama-3.1-8b)"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-surface-darker">
                    <p class="text-xs text-text-secondary">
                        💡 Tip: Most OpenAI-compatible APIs require <code>/v1</code> at the end of the URL
                    </p>
                </div>

                <!-- Actions -->
                <div class="flex gap-3 pt-4 border-t border-gray-200 dark:border-white/10">
                    <button onclick="saveAPIKeys()"
                        class="flex-1 bg-primary hover:bg-primary-hover text-white px-6 py-3 rounded-lg font-medium transition">
                        💾 Save Keys
                    </button>
                    <button onclick="clearAPIKeys()"
                        class="px-6 py-3 rounded-lg border border-gray-300 dark:border-white/10 hover:bg-gray-100 dark:hover:bg-white/5 transition">
                        🗑️ Clear All
                    </button>
                </div>

                <!-- Export/Import -->
                <div class="flex gap-3">
                    <button onclick="exportAPIKeys()"
                        class="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 hover:bg-gray-100 dark:hover:bg-white/5 transition text-sm">
                        📤 Export
                    </button>
                    <button onclick="importAPIKeys()"
                        class="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 hover:bg-gray-100 dark:hover:bg-white/5 transition text-sm">
                        📥 Import
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

/**
 * Save API keys from modal
 */
function saveAPIKeys() {
    const fields = [
        'openai', 'openai_base_url',
        'grok', 'grok_base_url',
        'gemini',
        'deepseek', 'deepseek_base_url',
        'perplexity', 'perplexity_base_url',
        'openrouter', 'openrouter_base_url',
        'custom', 'custom_base_url', 'custom_model'
    ];

    fields.forEach(field => {
        const inputId = `key-${field.replace(/_/g, '-')}`;
        const input = document.getElementById(inputId);
        if (input) {
            let value = input.value.trim();

            // Auto-fix base URLs - ensure they end with /v1 if they look like API URLs
            if (field.endsWith('_base_url') && value && !value.includes('localhost')) {
                // Remove trailing slash
                value = value.replace(/\/$/, '');
                // Add /v1 if not present
                if (!value.endsWith('/v1')) {
                    value = value + '/v1';
                    console.log(`Auto-corrected ${field}: ${value}`);
                    input.value = value; // Update input to show correction
                }
            }

            apiKeyManager.setKey(field, value);
            console.log(`Saved ${field}: ${value ? '***' : '(empty)'}`);
        } else {
            console.warn(`Input not found: ${inputId}`);
        }
    });

    // Show success message
    showNotification('✅ API keys saved successfully!', 'success');

    // Close modal
    const modal = document.querySelector('.fixed.inset-0');
    if (modal) modal.remove();

    // Update models if custom provider is selected
    if (typeof updateModels === 'function') {
        updateModels();
    }
}

/**
 * Clear all API keys
 */
function clearAPIKeys() {
    if (confirm('Are you sure you want to clear all API keys?')) {
        apiKeyManager.clearKeys();
        showNotification('🗑️ All API keys cleared', 'info');
        document.querySelector('.fixed.inset-0').remove();
    }
}

/**
 * Export API keys
 */
function exportAPIKeys() {
    const json = apiKeyManager.exportKeys();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ai-council-api-keys.json';
    a.click();
    URL.revokeObjectURL(url);
    showNotification('📤 API keys exported', 'success');
}

/**
 * Import API keys
 */
function importAPIKeys() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = (e) => {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = (event) => {
            if (apiKeyManager.importKeys(event.target.result)) {
                showNotification('📥 API keys imported successfully!', 'success');
                document.querySelector('.fixed.inset-0').remove();
                showAPIKeysModal(); // Refresh modal
            } else {
                showNotification('❌ Failed to import API keys', 'error');
            }
        };
        reader.readAsText(file);
    };
    input.click();
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };

    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

/**
 * Add API keys to fetch request
 */
function addAPIKeysToRequest(options = {}) {
    const encodedKeys = apiKeyManager.encodeKeys();
    if (!options.headers) {
        options.headers = {};
    }
    options.headers['X-API-Keys'] = encodedKeys;
    return options;
}
