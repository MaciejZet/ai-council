/**
 * AI Council - Full SPA Application
 */

// ========== STATE ==========
let currentProvider = 'openai';
let currentModel = 'gpt-4o';
let attachmentText = '';
let lastResult = null;
let history = [];
let sessions = [];
let currentSessionId = null;
let chatMode = false;
let debateMode = false;  // Tryb debaty
let currentRound = 0;    // Aktualna runda debaty
let totalTokensUsed = 0;
let estimatedCost = 0;
let currentPage = 'dashboard';
let specialists = [];

// Models per provider with token costs
// Models per provider (will be loaded from API)
let MODELS = {
    openai: ['gpt-4o', 'gpt-4o-mini'],
    grok: ['grok-2', 'grok-beta'],
    gemini: ['gemini-1.5-pro'],
    deepseek: ['deepseek-chat'],
    openrouter: []
};

let AVAILABLE_PROVIDERS_LIST = ['openai', 'grok', 'gemini', 'deepseek', 'openrouter'];

const TOKEN_COSTS = {
    'gpt-4o': 0.005, 'gpt-4o-mini': 0.00015, 'gpt-4.1': 0.002, 'gpt-5': 0.01,
    'grok-2': 0.002, 'gemini-1.5-pro': 0.00125
};

const AGENT_COLORS = {
    // Core agents
    'Strateg': { bg: 'bg-blue-500/10', text: 'text-blue-500', icon: 'chess', color: '#3b82f6' },
    'Analityk': { bg: 'bg-green-500/10', text: 'text-green-500', icon: 'analytics', color: '#22c55e' },
    'Praktyk': { bg: 'bg-orange-500/10', text: 'text-orange-500', icon: 'construction', color: '#f97316' },
    'Ekspert': { bg: 'bg-purple-500/10', text: 'text-purple-500', icon: 'school', color: '#a855f7' },
    'Syntezator': { bg: 'bg-pink-500/10', text: 'text-pink-500', icon: 'auto_awesome', color: '#ec4899' },
    // Specialists
    'Social Media': { bg: 'bg-rose-500/10', text: 'text-rose-500', icon: 'smartphone', color: '#f43f5e' },
    'LinkedIn': { bg: 'bg-sky-500/10', text: 'text-sky-500', icon: 'business_center', color: '#0ea5e9' },
    'SEO': { bg: 'bg-lime-500/10', text: 'text-lime-500', icon: 'search', color: '#84cc16' },
    'Blog Post': { bg: 'bg-amber-500/10', text: 'text-amber-500', icon: 'edit_note', color: '#f59e0b' },
    'Branding': { bg: 'bg-fuchsia-500/10', text: 'text-fuchsia-500', icon: 'palette', color: '#d946ef' }
};

// ========== DOM ELEMENTS ==========
const queryForm = document.getElementById('query-form');
const queryInput = document.getElementById('query-input');
const fileInput = document.getElementById('file-input');
const fileIndicator = document.getElementById('file-indicator');
const fileName = document.getElementById('file-name');
const providerSelect = document.getElementById('provider-select');
const modelSelect = document.getElementById('model-select');
const kbToggle = document.getElementById('kb-toggle');
const welcomeState = document.getElementById('welcome-state');
const loadingState = document.getElementById('loading-state');
const resultsContent = document.getElementById('results-content');
const queryDisplay = document.getElementById('query-display');
const queryText = document.getElementById('query-text');
const agentTabs = document.getElementById('agent-tabs');
const tabContents = document.getElementById('tab-contents');
const agentsList = document.getElementById('agents-list');
const sourcesList = document.getElementById('sources-list');
const sourcesSection = document.getElementById('sources-section');
const recentSessionsList = document.getElementById('recent-sessions');

// ========== INITIALIZATION ==========
// ========== CUSTOM COMPONENTS ==========
class CustomSelect {
    constructor({ containerId, options, initialValue, onChange, renderLabel, icon, align = 'left' }) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.options = options || [];
        this.value = initialValue;
        this.onChange = onChange;
        this.renderLabel = renderLabel || ((opt) => opt.label);
        this.icon = icon;
        this.align = align;
        this.isOpen = false;

        this.init();
    }

    init() {
        this.container.classList.add('custom-select');

        // Ensure options are formatted correctly (handle simple strings)
        this.normalizeOptions();

        // Initial render
        this.render();

        // Click outside listener
        document.addEventListener('click', (e) => {
            if (this.isOpen && !this.container.contains(e.target)) {
                this.close();
            }
        });
    }

    normalizeOptions() {
        // Support both ['a', 'b'] and [{value:'a', label:'A'}] and groups
        // Structure: [{label: 'Group', options: [...]}, {value: ...}]
    }

    toggle() {
        if (this.isOpen) this.close(); else this.open();
    }

    open() {
        this.isOpen = true;
        this.container.querySelector('.select-options').classList.remove('hidden');
        this.container.querySelector('.select-trigger').classList.add('active');
    }

    close() {
        this.isOpen = false;
        this.container.querySelector('.select-options').classList.add('hidden');
        this.container.querySelector('.select-trigger').classList.remove('active');
    }

    setValue(value, triggerChange = true) {
        if (this.value === value && !triggerChange) return;
        this.value = value;
        this.updateTrigger();
        if (this.onChange && triggerChange) this.onChange(value);
        this.close();
    }

    setOptions(newOptions) {
        this.options = newOptions;
        this.renderOptions(this.container.querySelector('.select-options-content'));

        // Check if current value exists in new options
        const allValues = this.getAllValues();
        if (!allValues.includes(this.value) && allValues.length > 0) {
            this.setValue(allValues[0]);
        }
        this.updateTrigger();
    }

    getAllValues() {
        const values = [];
        this.options.forEach(opt => {
            if (opt.group) {
                opt.options.forEach(o => values.push(o.value));
            } else {
                values.push(opt.value);
            }
        });
        return values;
    }

    getSelectedOption() {
        let found = null;
        this.options.forEach(opt => {
            if (opt.group) {
                const inGroup = opt.options.find(o => o.value === this.value);
                if (inGroup) found = inGroup;
            } else if (opt.value === this.value) {
                found = opt;
            }
        });
        return found || { label: this.value, value: this.value };
    }

    render() {
        const alignClass = this.align === 'right' ? 'right-0' : 'left-0';
        this.container.innerHTML = `
            <button class="select-trigger flex items-center justify-between w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm hover:bg-white/10 transition-colors">
                <span class="value-display flex items-center gap-2 truncate"></span>
                <span class="material-symbols-outlined text-lg opacity-50">expand_more</span>
            </button>
            <div class="select-options hidden absolute top-full ${alignClass} min-w-full w-auto mt-1 bg-[#1a1f2e] border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100">
                <div class="select-options-content max-h-[400px] overflow-y-auto p-1 text-sm"></div>
            </div>
        `;

        this.updateTrigger();
        this.renderOptions(this.container.querySelector('.select-options-content'));

        this.container.querySelector('.select-trigger').addEventListener('click', (e) => {
            e.preventDefault();
            this.toggle();
        });
    }

    updateTrigger() {
        const option = this.getSelectedOption();
        const display = this.container.querySelector('.value-display');
        display.innerHTML = this.renderLabel(option);
    }

    renderOptions(container) {
        container.innerHTML = '';

        this.options.forEach(opt => {
            if (opt.group) {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'py-1';
                groupDiv.innerHTML = `<div class="px-2 py-1 text-xs font-bold text-text-secondary uppercase tracking-wider opacity-70 whitespace-nowrap">${opt.group}</div>`;

                opt.options.forEach(subOpt => {
                    groupDiv.appendChild(this.createOptionEl(subOpt));
                });
                container.appendChild(groupDiv);
            } else {
                container.appendChild(this.createOptionEl(opt));
            }
        });
    }

    createOptionEl(option) {
        const btn = document.createElement('button');
        btn.className = `w-full text-left px-2 py-1.5 rounded-md transition-colors flex items-center gap-2 whitespace-nowrap ${this.value === option.value ? 'bg-primary/20 text-white' : 'text-text-secondary hover:bg-white/5 hover:text-white'}`;
        btn.innerHTML = this.renderLabel(option);
        btn.onclick = (e) => {
            e.stopPropagation();
            this.setValue(option.value);
        };
        return btn;
    }
}

// Global Instances
let modeSelectInstance, providerSelectInstance, modelSelectInstance;

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadStats();
    loadAgents();
    loadSessions();
    loadSpecialists();
    setupEventListeners();

    // Initialize Custom Selects (after fetching providers)
    fetchProviders().then(() => {
        initCustomSelects();
        updateModels(); // Will use instance now
    });

    navigateTo('dashboard');
});

async function fetchProviders() {
    try {
        const response = await fetch('/api/providers');
        const data = await response.json();
        if (data.providers) {
            AVAILABLE_PROVIDERS_LIST = data.providers;
        }
        if (data.models) {
            MODELS = data.models;
        }
    } catch (e) {
        console.error("Failed to fetch providers", e);
    }
}

function initCustomSelects() {
    // 1. MODE SELECT
    const modeOptions = [
        {
            group: 'Podstawowe', options: [
                { value: 'council', label: 'Narada', emoji: '🏛️' },
                { value: 'debate', label: 'Debata', emoji: '⚔️' },
                { value: 'mentors', label: 'Ikony & Mentorzy', emoji: '🌟' }
            ]
        },
        {
            group: 'Zaawansowane', options: [
                { value: 'deep_dive', label: 'Deep Dive', emoji: '🔬' },
                { value: 'speed_round', label: 'Speed Round', emoji: '⚡' },
                { value: 'devils_advocate', label: 'Devil\'s Advocate', emoji: '🎯' },
                { value: 'swot', label: 'SWOT Analysis', emoji: '📊' },
                { value: 'red_team', label: 'Krytyk', emoji: '🧐' }
            ]
        }
    ];

    modeSelectInstance = new CustomSelect({
        containerId: 'mode-select-container',
        options: modeOptions,
        initialValue: currentMode,
        renderLabel: (opt) => `<span class="opacity-80">${opt.emoji}</span> <span>${opt.label}</span>`,
        onChange: (val) => setMode(val)
    });

    // 2. PROVIDER SELECT
    const providerEmojis = {
        'openai': '🤖',
        'grok': '🚀',
        'gemini': '💎',
        'deepseek': '🧠',
        'openrouter': '🌐',
        'perplexity': '🔍',
        'custom': '🔌'
    };

    const providerOptions = AVAILABLE_PROVIDERS_LIST.map(p => ({
        value: p,
        label: p.charAt(0).toUpperCase() + p.slice(1),
        emoji: providerEmojis[p] || '🔌'
    }));

    providerSelectInstance = new CustomSelect({
        containerId: 'provider-select-container',
        options: providerOptions,
        initialValue: currentProvider,
        renderLabel: (opt) => opt ? `<span class="opacity-80">${opt.emoji}</span> <span class="hidden sm:inline">${opt.label}</span>` : '?',
        onChange: (val) => {
            currentProvider = val;
            localStorage.setItem('ai_council_last_provider', val);
            updateModels();
            updateStatDisplay();
        },
        align: 'right'
    });

    // 3. MODEL SELECT (Empty initially, filled by updateModels)
    modelSelectInstance = new CustomSelect({
        containerId: 'model-select-container',
        options: [],
        initialValue: currentModel,
        renderLabel: (opt) => {
            if (!opt) return '?';
            const cost = TOKEN_COSTS[opt.value];
            const costBadge = cost ? `<span class="ml-auto text-xs opacity-50">$${cost}</span>` : '';
            return `<span class="truncate">${opt.label}</span> ${costBadge}`;
        },
        onChange: (val) => {
            currentModel = val;
            localStorage.setItem('ai_council_last_model', val);
        },
        align: 'right'
    });
}

// Patch setupEventListeners to skip missing elements
function setupEventListeners() {
    if (queryForm) queryForm.addEventListener('submit', handleSubmit);
    // Provider/Model listeners handled by CustomSelect now

    if (fileInput) fileInput.addEventListener('change', handleFileSelect);
    if (queryInput) {
        queryInput.addEventListener('input', autoResize);
        queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                queryForm.dispatchEvent(new Event('submit'));
            }
        });
    }

    // PDF import
    const pdfImportBtn = document.getElementById('pdf-import-btn');
    const pdfImportInput = document.getElementById('pdf-import-input');
    if (pdfImportBtn && pdfImportInput) {
        pdfImportBtn.addEventListener('click', () => pdfImportInput.click());
        pdfImportInput.addEventListener('change', handlePdfImport);
    }

    // Temperature slider
    const tempSlider = document.getElementById('setting-temperature');
    if (tempSlider) {
        tempSlider.addEventListener('input', (e) => {
            document.getElementById('temp-value').textContent = (e.target.value / 100).toFixed(1);
        });
    }
}

// ========== NAVIGATION ==========
function navigateTo(page) {
    currentPage = page;

    // Hide all pages
    document.querySelectorAll('.page-content').forEach(p => p.classList.add('hidden'));

    // Show selected page
    const pageEl = document.getElementById(`page-${page}`);
    if (pageEl) pageEl.classList.remove('hidden');

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        const isActive = link.dataset.page === page;
        link.classList.toggle('bg-primary/10', isActive);
        link.classList.toggle('text-primary', isActive);
        link.classList.toggle('dark:text-white', isActive);
        link.classList.toggle('font-medium', isActive);
        link.classList.toggle('text-slate-600', !isActive);
        link.classList.toggle('dark:text-text-secondary', !isActive);
        link.classList.toggle('hover:bg-slate-100', !isActive);
        link.classList.toggle('dark:hover:bg-white/5', !isActive);
    });

    // Load page-specific content
    if (page === 'history') renderHistoryPage();
    if (page === 'agents') renderAgentsPage();
    if (page === 'settings') loadSettingsPage();
}

// ========== HISTORY PAGE ==========
function renderHistoryPage() {
    const container = document.getElementById('history-list');
    if (!container) return;

    if (sessions.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12 text-text-secondary">
                <span class="material-symbols-outlined text-4xl mb-4 block opacity-50">history</span>
                <p>Brak zapisanych sesji</p>
                <p class="text-sm mt-2">Twoje narady pojawią się tutaj</p>
            </div>
        `;
        return;
    }

    container.innerHTML = sessions.map(session => `
        <div class="bg-white dark:bg-surface-dark rounded-xl border border-gray-200 dark:border-white/10 p-4 hover:border-primary/50 transition-colors cursor-pointer" onclick="loadSession(${session.id})">
            <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                    <h4 class="font-medium text-slate-900 dark:text-white truncate">${escapeHtml(session.title)}</h4>
                    <p class="text-sm text-text-secondary mt-1">${formatDate(session.timestamp)}</p>
                    <p class="text-xs text-text-secondary mt-2">${session.history?.length || 0} wiadomości</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="event.stopPropagation(); deleteSession(${session.id})" class="p-2 text-text-secondary hover:text-red-400 transition-colors">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function deleteSession(sessionId) {
    sessions = sessions.filter(s => s.id !== sessionId);
    localStorage.setItem('ai_council_sessions', JSON.stringify(sessions));
    renderHistoryPage();
    renderSessions();
    showToast('Sesja usunięta', 'success');
}

function clearAllSessions() {
    if (confirm('Czy na pewno chcesz usunąć całą historię?')) {
        sessions = [];
        localStorage.removeItem('ai_council_sessions');
        renderHistoryPage();
        renderSessions();
        showToast('Historia wyczyszczona', 'success');
    }
}

// ========== AGENTS PAGE ==========
function renderAgentsPage() {
    const coreGrid = document.getElementById('core-agents-grid');
    const specialistsGrid = document.getElementById('specialists-grid');
    if (!coreGrid) return;

    fetch('/api/agents')
        .then(r => r.json())
        .then(agents => {
            coreGrid.innerHTML = agents.map(agent => {
                const colors = AGENT_COLORS[agent.name] || { bg: 'bg-gray-500/10', text: 'text-gray-500', icon: 'person', color: '#6b7280' };
                return `
                    <div class="bg-white dark:bg-surface-dark rounded-xl border border-gray-200 dark:border-white/10 p-5 hover:border-primary/30 transition-all">
                        <div class="flex items-start justify-between mb-4">
                            <div class="w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center text-2xl">
                                ${agent.emoji}
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" class="sr-only peer" ${agent.enabled ? 'checked' : ''} onchange="toggleAgentFromPage('${agent.name}', this.checked)">
                                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                            </label>
                        </div>
                        <h4 class="font-bold text-slate-900 dark:text-white">${agent.name}</h4>
                        <p class="text-sm text-text-secondary mt-1">${agent.role}</p>
                        <p class="text-xs text-text-secondary/70 mt-3">${agent.description}</p>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            coreGrid.innerHTML = '<p class="text-text-secondary col-span-3">Błąd ładowania agentów</p>';
        });

    // Render specialists
    if (specialistsGrid) {
        const specialistCards = specialists.map(spec => `
            <div class="bg-white dark:bg-surface-dark rounded-xl border border-gray-200 dark:border-white/10 p-5">
                <div class="flex items-start justify-between mb-4">
                    <div class="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-2xl">
                        ${spec.emoji}
                    </div>
                    <button onclick="deleteSpecialist('${spec.name}')" class="text-text-secondary hover:text-red-400">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
                <h4 class="font-bold text-slate-900 dark:text-white">${spec.name}</h4>
                <p class="text-sm text-text-secondary mt-1">${spec.role}</p>
            </div>
        `).join('');

        specialistsGrid.innerHTML = specialistCards + `
            <div class="border-2 border-dashed border-gray-300 dark:border-white/10 rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer hover:border-primary/50 transition-colors" onclick="showAddSpecialistModal()">
                <span class="material-symbols-outlined text-4xl text-text-secondary mb-2">add_circle_outline</span>
                <p class="text-sm text-text-secondary">Dodaj specjalistę</p>
            </div>
        `;
    }
}

async function toggleAgentFromPage(name, enabled) {
    try {
        await fetch(`/api/agents/${encodeURIComponent(name)}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        showToast(`${name} ${enabled ? 'włączony' : 'wyłączony'}`, 'success');
        loadAgents(); // Refresh sidebar
    } catch (err) {
        showToast('Błąd zmiany statusu', 'error');
    }
}

// ========== SPECIALISTS ==========
function showAddSpecialistModal() {
    document.getElementById('specialist-modal').classList.remove('hidden');
}

function hideAddSpecialistModal() {
    document.getElementById('specialist-modal').classList.add('hidden');
    document.getElementById('specialist-name').value = '';
    document.getElementById('specialist-role').value = '';
    document.getElementById('specialist-emoji').value = '';
    document.getElementById('specialist-prompt').value = '';
}

function addSpecialist() {
    const name = document.getElementById('specialist-name').value.trim();
    const role = document.getElementById('specialist-role').value.trim();
    const emoji = document.getElementById('specialist-emoji').value.trim() || '🔧';
    const prompt = document.getElementById('specialist-prompt').value.trim();

    if (!name || !role) {
        showToast('Wypełnij nazwę i rolę', 'error');
        return;
    }

    const specialist = { name, role, emoji, prompt, enabled: true };
    specialists.push(specialist);
    localStorage.setItem('ai_council_specialists', JSON.stringify(specialists));

    hideAddSpecialistModal();
    renderAgentsPage();
    showToast(`Dodano specjalistę: ${name}`, 'success');
}

function deleteSpecialist(name) {
    specialists = specialists.filter(s => s.name !== name);
    localStorage.setItem('ai_council_specialists', JSON.stringify(specialists));
    renderAgentsPage();
    showToast('Specjalista usunięty', 'success');
}

function loadSpecialists() {
    const saved = localStorage.getItem('ai_council_specialists');
    if (saved) specialists = JSON.parse(saved);
}

// ========== SETTINGS PAGE ==========
function loadSettingsPage() {
    const settings = JSON.parse(localStorage.getItem('ai_council_settings') || '{}');

    document.getElementById('setting-default-provider').value = settings.defaultProvider || 'openai';
    document.getElementById('setting-default-model').value = settings.defaultModel || 'gpt-4o';
    document.getElementById('setting-temperature').value = (settings.temperature || 0.7) * 100;
    document.getElementById('temp-value').textContent = (settings.temperature || 0.7).toFixed(1);
    document.getElementById('setting-kb-default').checked = settings.kbDefault !== false;
    document.getElementById('setting-show-sources').checked = settings.showSources !== false;

    // Load KB stats
    fetch('/api/stats')
        .then(r => r.json())
        .then(stats => {
            document.getElementById('settings-kb-count').textContent = (stats.total_vectors || 0).toLocaleString();
        });
}

function saveSettings() {
    const settings = {
        defaultProvider: document.getElementById('setting-default-provider').value,
        defaultModel: document.getElementById('setting-default-model').value,
        temperature: parseInt(document.getElementById('setting-temperature').value) / 100,
        kbDefault: document.getElementById('setting-kb-default').checked,
        showSources: document.getElementById('setting-show-sources').checked
    };

    localStorage.setItem('ai_council_settings', JSON.stringify(settings));
    showToast('Ustawienia zapisane', 'success');

    // Apply settings
    currentProvider = settings.defaultProvider;
    currentModel = settings.defaultModel;

    // Update custom selects
    if (typeof providerSelectInstance !== 'undefined' && providerSelectInstance) {
        providerSelectInstance.setValue(currentProvider, false);
    }

    updateModels();

    if (typeof modelSelectInstance !== 'undefined' && modelSelectInstance) {
        modelSelectInstance.setValue(currentModel, false);
    }

    if (kbToggle) kbToggle.checked = settings.kbDefault;
}

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('ai_council_settings') || '{}');
    const lastProvider = localStorage.getItem('ai_council_last_provider');
    const lastModel = localStorage.getItem('ai_council_last_model');

    if (lastProvider) currentProvider = lastProvider;
    else if (settings.defaultProvider) currentProvider = settings.defaultProvider;

    if (lastModel) currentModel = lastModel;
    else if (settings.defaultModel) currentModel = settings.defaultModel;

    if (settings.kbDefault !== undefined && kbToggle) kbToggle.checked = settings.kbDefault;
}

function resetSettings() {
    if (confirm('Przywrócić domyślne ustawienia?')) {
        localStorage.removeItem('ai_council_settings');
        loadSettingsPage();
        showToast('Przywrócono domyślne ustawienia', 'success');
    }
}

function setTheme(theme) {
    if (theme === 'light') {
        document.documentElement.classList.remove('dark');
    } else if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        // System
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }
    localStorage.setItem('ai_council_theme', theme);
}

function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    input.type = input.type === 'password' ? 'text' : 'password';
}

// ========== SETTINGS PANEL ==========
let currentSettingsTab = 'dashboard';

function openSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    if (panel) {
        panel.classList.remove('hidden');
        loadSettingsContent();
    }
}

function closeSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

function setSettingsTab(tabName) {
    currentSettingsTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.settings-tab').forEach(tab => {
        const isActive = tab.dataset.tab === tabName;
        tab.classList.toggle('active', isActive);
        tab.classList.toggle('border-primary', isActive);
        tab.classList.toggle('text-white', isActive);
        tab.classList.toggle('text-text-secondary', !isActive);
    });

    // Update tab content
    document.querySelectorAll('.settings-tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    const activeContent = document.getElementById(`settings-tab-${tabName}`);
    if (activeContent) {
        activeContent.classList.remove('hidden');
    }

    // Load tab-specific content
    if (tabName === 'agents') loadSettingsAgents();
    if (tabName === 'knowledge') loadSettingsKnowledge();
    if (tabName === 'dashboard') updateSettingsStats();
}

function loadSettingsContent() {
    updateSettingsStats();
    setSettingsTab('dashboard');
}

function updateSettingsStats() {
    // Sessions count
    const sessionsCount = sessions.length;
    const sessionsEl = document.getElementById('settings-stat-sessions');
    if (sessionsEl) sessionsEl.textContent = sessionsCount;

    // Tokens
    const tokensEl = document.getElementById('settings-stat-tokens');
    if (tokensEl) tokensEl.textContent = totalTokensUsed.toLocaleString();

    // Cost
    const costEl = document.getElementById('settings-stat-cost');
    if (costEl) costEl.textContent = `$${estimatedCost.toFixed(2)}`;

    // KB vectors
    fetch('/api/stats')
        .then(r => r.json())
        .then(stats => {
            const kbEl = document.getElementById('settings-stat-kb');
            if (kbEl) kbEl.textContent = (stats.total_vectors || 0).toLocaleString();
        });
}

function loadSettingsAgents() {
    const grid = document.getElementById('settings-agents-grid');
    if (!grid) return;

    fetch('/api/agents')
        .then(r => r.json())
        .then(agents => {
            grid.innerHTML = agents.map(agent => {
                const colors = AGENT_COLORS[agent.name] || { bg: 'bg-gray-500/10', text: 'text-gray-500' };
                return `
                    <div class="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center text-xl">
                                ${agent.emoji}
                            </div>
                            <div>
                                <p class="font-medium">${agent.name}</p>
                                <p class="text-xs text-text-secondary">${agent.role}</p>
                            </div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" class="sr-only peer" ${agent.enabled ? 'checked' : ''} 
                                onchange="toggleAgentFromSettings('${agent.name}', this.checked)">
                            <div class="w-11 h-6 bg-gray-200 rounded-full peer dark:bg-gray-700 peer-checked:bg-primary 
                                after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white 
                                after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
                        </label>
                    </div>
                `;
            }).join('');

            // Add specialists
            const specialistCards = specialists.map(spec => `
                <div class="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center text-xl">
                            ${spec.emoji}
                        </div>
                        <div>
                            <p class="font-medium">${spec.name}</p>
                            <p class="text-xs text-text-secondary">${spec.role}</p>
                        </div>
                    </div>
                    <button onclick="deleteSpecialist('${spec.name}'); loadSettingsAgents();" 
                        class="text-text-secondary hover:text-red-400 transition-colors">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
            `).join('');

            grid.innerHTML += specialistCards;
        })
        .catch(err => {
            grid.innerHTML = '<p class="text-text-secondary">Błąd ładowania agentów</p>';
        });
}

async function toggleAgentFromSettings(name, enabled) {
    try {
        await fetch(`/api/agents/${encodeURIComponent(name)}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        showToast(`${name} ${enabled ? 'włączony' : 'wyłączony'}`, 'success');
        loadAgents(); // Refresh main sidebar
    } catch (err) {
        showToast('Błąd zmiany statusu', 'error');
    }
}

function loadSettingsKnowledge() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(stats => {
            const kbEl = document.getElementById('settings-kb-vectors');
            if (kbEl) kbEl.textContent = (stats.total_vectors || 0).toLocaleString();
        });
}

async function handleSettingsPdfImport(e) {
    const file = e.target.files[0];
    if (!file || !file.name.endsWith('.pdf')) {
        showToast('Wybierz plik PDF', 'error');
        return;
    }
    showToast('Importowanie do bazy wiedzy...', 'info');
    const formData = new FormData();
    formData.append('file', file);
    try {
        const response = await fetch('/api/ingest', { method: 'POST', body: formData });
        if (!response.ok) throw new Error((await response.json()).detail || 'Import failed');
        const result = await response.json();
        showToast(`✓ Zaimportowano ${result.chunks_count} chunków`, 'success');
        loadSettingsKnowledge();
        loadStats();
    } catch (err) {
        showToast('Błąd importu: ' + err.message, 'error');
    }
    e.target.value = '';
}

// ========== MODEL FUNCTIONS ==========
function updateModels() {
    let models = MODELS[currentProvider] || [];

    // For custom provider, use model from localStorage
    if (currentProvider === 'custom') {
        const customModel = apiKeyManager.getKey('custom_model') || 'local-model';
        models = [customModel];
        console.log(`Custom provider selected, model: ${customModel}`);
    }

    if (modelSelectInstance) {
        const options = models.map(m => ({ value: m, label: m }));
        modelSelectInstance.setOptions(options);

        // Always set to first model when switching providers
        if (models.length > 0) {
            currentModel = models[0];
            modelSelectInstance.setValue(currentModel, false); // Don't trigger change callback to avoid loop
            localStorage.setItem('ai_council_last_model', currentModel);
            console.log(`Model updated to: ${currentModel}`);
        }
    }
}

function autoResize() {
    if (queryInput) {
        queryInput.style.height = 'auto';
        queryInput.style.height = Math.min(queryInput.scrollHeight, 200) + 'px';
    }
}

// ========== FILE HANDLING ==========
async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    try {
        attachmentText = file.name.endsWith('.txt') || file.name.endsWith('.md')
            ? await file.text()
            : `[Załączony plik: ${file.name}]`;
        fileName.textContent = file.name;
        fileIndicator.classList.remove('hidden');
        updateContextFiles(file.name);
    } catch (err) {
        showToast('Błąd odczytu pliku', 'error');
    }
}

async function handlePdfImport(e) {
    const file = e.target.files[0];
    if (!file || !file.name.endsWith('.pdf')) {
        showToast('Wybierz plik PDF', 'error');
        return;
    }
    showToast('Importowanie do bazy wiedzy...', 'info');
    const formData = new FormData();
    formData.append('file', file);
    try {
        const response = await fetch('/api/ingest', { method: 'POST', body: formData });
        if (!response.ok) throw new Error((await response.json()).detail || 'Import failed');
        const result = await response.json();
        showToast(`✓ Zaimportowano ${result.chunks_count} chunków`, 'success');
        loadStats();
    } catch (err) {
        showToast('Błąd importu: ' + err.message, 'error');
    }
    e.target.value = '';
}

// ========== DELIBERATION ==========
let streamingAgentResponses = {};
let streamingEventSource = null;

async function handleSubmit(e) {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    // Cancel any existing stream
    if (streamingEventSource) {
        streamingEventSource.close();
        streamingEventSource = null;
    }

    queryText.textContent = query;
    queryDisplay.classList.remove('hidden');

    // Advanced modes use dedicated API
    const advancedModes = ['deep_dive', 'speed_round', 'devils_advocate', 'swot', 'red_team'];

    if (advancedModes.includes(currentMode)) {
        advancedModeStream(query, currentMode);
    } else if (currentMode === 'mentors') {
        mentorsStream(query);
    } else if (currentMode === 'debate') {
        debateStream(query);
    } else {
        deliberateStream(query);
    }

    queryInput.value = '';
    attachmentText = '';
    fileIndicator.classList.add('hidden');
    autoResize();
}

// ========== ADVANCED MODES (SWOT, Deep Dive, etc.) ==========
function advancedModeStream(query, mode) {
    const params = new URLSearchParams({
        mode: mode,
        query: query,
        provider: currentProvider,
        model: currentModel
    });

    streamingAgentResponses = {};
    showStreamingUI();

    streamingEventSource = new EventSource(`/api/council/mode/stream?${params}`);

    streamingEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.event) {
            case 'sources':
                handleSources(data.sources);
                break;

            case 'mode_start':
                showToast(`${data.emoji} ${data.mode} rozpoczęty`, 'info');
                break;

            case 'round_start':
                handleRoundStart(data.round, data.type, data.title);
                break;

            case 'agent_start':
                handleAdvancedAgentStart(data.agent, data.emoji, data.role, data.round);
                break;

            case 'delta':
                handleDelta(data.agent, data.content);
                break;

            case 'agent_done':
                handleAgentDone(data.agent);
                break;

            case 'round_done':
                // Round completed
                break;

            case 'complete':
                handleAdvancedComplete(data.total_rounds, data.total_agents);
                streamingEventSource.close();
                streamingEventSource = null;
                break;

            case 'error':
                showToast('Błąd: ' + data.message, 'error');
                streamingEventSource.close();
                streamingEventSource = null;
                showWelcome();
                break;
        }
    };

    streamingEventSource.onerror = (error) => {
        console.error('Advanced mode SSE Error:', error);
        streamingEventSource.close();
        streamingEventSource = null;
        showToast('Połączenie przerwane', 'error');
    };
}

function handleAdvancedAgentStart(agentName, emoji, role, round) {
    const placeholder = tabContents.querySelector('.streaming-placeholder');
    if (placeholder) placeholder.remove();

    streamingAgentResponses[agentName] = { emoji: emoji || '🎯', role: role || 'Agent', content: '' };

    // Add tab button
    const tabBtn = document.createElement('button');
    tabBtn.className = 'tab-button flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors active';
    tabBtn.dataset.tab = agentName;
    tabBtn.innerHTML = `
        <span class="text-lg">${emoji || '🎯'}</span>
        <span>${agentName}</span>
        <span class="typing-indicator ml-1"></span>
    `;
    tabBtn.onclick = () => switchTab(agentName);

    agentTabs.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    agentTabs.appendChild(tabBtn);

    // Add content area
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content active';
    contentDiv.id = `tab-${agentName}`;
    contentDiv.innerHTML = `
        <div class="agent-card">
            <div class="agent-card-header">
                <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-2xl">
                    ${emoji || '🎯'}
                </div>
                <div>
                    <h3 class="font-bold text-sm text-white">${emoji || '🎯'} ${agentName}</h3>
                    <p class="text-[10px] text-text-secondary uppercase tracking-wide">${role || 'Agent'}${round ? ' • Runda ' + round : ''}</p>
                </div>
                <span class="ml-auto text-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded streaming-badge">
                    <span class="animate-pulse">●</span> Streaming
                </span>
            </div>
            <div class="agent-content font-body streaming-content" id="content-${agentName}"><span class="typing-cursor"></span></div>
        </div>
    `;

    tabContents.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tabContents.appendChild(contentDiv);
}

function handleAdvancedComplete(totalRounds, totalAgents) {
    const agentResponses = Object.entries(streamingAgentResponses).map(([name, data]) => ({
        agent_name: `${data.emoji} ${name}`,
        role: data.role,
        content: data.content,
        provider_used: `${currentProvider} (${currentModel})`
    }));

    lastResult = {
        query: queryText.textContent,
        timestamp: new Date().toISOString(),
        agent_responses: agentResponses,
        synthesis: null,
        sources: []
    };

    saveCurrentSession(queryText.textContent);
    showToast(`Zakończono! ${totalRounds || '?'} rund, ${totalAgents || '?'} agentów`, 'success');
}

// ========== MENTORS (ICONS) MODE ==========
function mentorsStream(query) {
    const agentIds = selectedMentors.length > 0 ? selectedMentors.join(',') : '';

    const params = new URLSearchParams({
        query: query,
        agent_ids: agentIds,
        provider: currentProvider,
        model: currentModel,
        mode: 'deliberate',  // or 'debate' for multi-round
        include_synthesis: false
    });

    // Reset streaming state
    streamingAgentResponses = {};
    showStreamingUI();

    streamingEventSource = new EventSource(`/api/historical/deliberate/stream?${params}`);

    streamingEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.event) {
            case 'sources':
                handleSources(data.sources);
                break;

            case 'council_start':
            case 'debate_start':
                // Show which mentors are participating
                if (data.agents && data.agents.length > 0) {
                    const names = data.agents.map(a => `${a.emoji} ${a.name}`).join(', ');
                    showToast(`Rada: ${names}`, 'info');
                }
                break;

            case 'round_start':
                handleRoundStart(data.round, data.type, data.title);
                break;

            case 'agent_start':
                handleMentorStart(data.agent, data.emoji, data.role, data.round);
                break;

            case 'delta':
                handleDelta(data.agent, data.content);
                break;

            case 'agent_done':
                handleAgentDone(data.agent);
                break;

            case 'round_done':
                // Round completed
                break;

            case 'complete':
                handleMentorsComplete(data.total_agents);
                streamingEventSource.close();
                streamingEventSource = null;
                break;

            case 'error':
                showToast('Błąd: ' + data.message, 'error');
                streamingEventSource.close();
                streamingEventSource = null;
                showWelcome();
                break;
        }
    };

    streamingEventSource.onerror = (error) => {
        console.error('Mentors SSE Error:', error);
        streamingEventSource.close();
        streamingEventSource = null;
        showToast('Połączenie przerwane', 'error');
    };
}

function handleMentorStart(agentName, emoji, role, round) {
    // Similar to handleAgentStart but with mentor-specific styling
    const placeholder = tabContents.querySelector('.streaming-placeholder');
    if (placeholder) placeholder.remove();

    streamingAgentResponses[agentName] = { emoji: emoji || '🌟', role: role || 'Mentor', content: '' };

    // Mentor colors based on name
    const colors = { bg: 'bg-amber-500/10', text: 'text-amber-500', icon: 'auto_awesome' };

    // Add tab button
    const tabBtn = document.createElement('button');
    tabBtn.className = 'tab-button flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors active';
    tabBtn.dataset.tab = agentName;
    tabBtn.innerHTML = `
        <span class="text-lg">${emoji || '🌟'}</span>
        <span>${agentName}</span>
        <span class="typing-indicator ml-1"></span>
    `;
    tabBtn.onclick = () => switchTab(agentName);

    // Deactivate other tabs
    agentTabs.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    agentTabs.appendChild(tabBtn);

    // Add content area
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content active';
    contentDiv.id = `tab-${agentName}`;
    contentDiv.innerHTML = `
        <div class="agent-card">
            <div class="agent-card-header">
                <div class="w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center text-2xl">
                    ${emoji || '🌟'}
                </div>
                <div>
                    <h3 class="font-bold text-sm text-white">${emoji || '🌟'} ${agentName}</h3>
                    <p class="text-[10px] text-text-secondary uppercase tracking-wide">${role || 'Mentor'}</p>
                </div>
                <span class="ml-auto text-xs font-mono text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded streaming-badge">
                    <span class="animate-pulse">●</span> Streaming
                </span>
            </div>
            <div class="agent-content font-body streaming-content" id="content-${agentName}"><span class="typing-cursor"></span></div>
        </div>
    `;

    tabContents.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tabContents.appendChild(contentDiv);
}

function handleMentorsComplete(totalAgents) {
    const agentResponses = Object.entries(streamingAgentResponses).map(([name, data]) => ({
        agent_name: `${data.emoji} ${name}`,
        role: data.role,
        content: data.content,
        provider_used: `${currentProvider} (${currentModel})`
    }));

    const synthesis = streamingAgentResponses['Rada Mędrców'] ? {
        agent_name: '🔮 Rada Mędrców',
        role: 'Syntezator',
        content: streamingAgentResponses['Rada Mędrców'].content,
        provider_used: `${currentProvider} (${currentModel})`
    } : null;

    lastResult = {
        query: queryText.textContent,
        timestamp: new Date().toISOString(),
        agent_responses: agentResponses.filter(r => !r.agent_name.includes('Rada Mędrców')),
        synthesis: synthesis,
        sources: []
    };

    saveCurrentSession(queryText.textContent);
    showToast('Rada Mędrców zakończyła naradę', 'success');
}

function deliberateStream(query) {
    // Reset streaming state
    streamingAgentResponses = {};

    // Show streaming UI
    showStreamingUI();

    // Use streamWithFetch instead of EventSource (supports custom headers)
    const requestData = {
        query: query,
        provider: currentProvider,
        model: currentModel,
        use_knowledge_base: kbToggle?.checked ?? true
    };

    streamWithFetch(
        '/api/deliberate/stream',
        requestData,
        // onEvent
        (data) => {
            switch (data.event) {
                case 'sources':
                    handleSources(data.sources);
                    break;

                case 'agent_start':
                    handleAgentStart(data.agent, data.emoji, data.role);
                    break;

                case 'delta':
                    handleDelta(data.agent, data.content);
                    break;

                case 'agent_done':
                    handleAgentDone(data.agent);
                    break;

                case 'synthesis_start':
                    handleSynthesisStart(data.agent, data.emoji, data.role);
                    break;

                case 'synthesis_done':
                    handleSynthesisDone();
                    break;

                case 'complete':
                    handleComplete(data.total_agents);
                    break;

                case 'error':
                    showToast('Błąd streamingu: ' + data.message, 'error');
                    showWelcome();
                    break;
            }
        },
        // onError
        (error) => {
            console.error('Stream Error:', error);
            const errorInfo = handleError(error, 'streaming');
            if (errorInfo.shouldQueue) {
                requestQueue.add({
                    url: '/api/deliberate/stream',
                    options: {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestData)
                    }
                });
            }
            showWelcome();
        },
        // onComplete
        () => {
            console.log('Stream completed');
        }
    );
}

function showStreamingUI() {
    showResults();

    // Clear previous content
    agentTabs.innerHTML = '';
    tabContents.innerHTML = `
        <div class="streaming-placeholder text-center py-8 text-text-secondary">
            <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            <p>Agenci rozpoczynają analizę...</p>
        </div>
    `;
}

function handleSources(sources) {
    if (sources && sources.length > 0) {
        sourcesSection.classList.remove('hidden');
        sourcesList.innerHTML = sources.map(s =>
            `<div class="source-badge"><span>${s.emoji || '📄'}</span><span class="truncate">${s.title}</span></div>`
        ).join('');
    }
}

function handleAgentStart(agentName, emoji, role) {
    // Remove placeholder if exists
    const placeholder = tabContents.querySelector('.streaming-placeholder');
    if (placeholder) placeholder.remove();

    // Initialize agent response
    streamingAgentResponses[agentName] = { emoji, role, content: '' };

    // Get agent colors
    const colors = AGENT_COLORS[agentName] || { bg: 'bg-gray-500/10', text: 'text-gray-500', icon: 'person' };

    // Add tab button
    const tabBtn = document.createElement('button');
    tabBtn.className = 'tab-button flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors active';
    tabBtn.dataset.tab = agentName;
    tabBtn.innerHTML = `
        <div class="w-6 h-6 rounded-full ${colors.bg} flex items-center justify-center ${colors.text} text-xs">
            <span class="material-symbols-outlined text-[16px]">${colors.icon}</span>
        </div>
        <span>${agentName}</span>
        <span class="typing-indicator ml-1"></span>
    `;
    tabBtn.onclick = () => switchTab(agentName);

    // Deactivate other tabs
    agentTabs.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    agentTabs.appendChild(tabBtn);

    // Add content area
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content active';
    contentDiv.id = `tab-${agentName}`;
    contentDiv.innerHTML = `
        <div class="agent-card">
            <div class="agent-card-header">
                <div class="w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center ${colors.text}">
                    <span class="material-symbols-outlined">${colors.icon}</span>
                </div>
                <div>
                    <h3 class="font-bold text-sm text-white">${emoji} ${agentName}</h3>
                    <p class="text-[10px] text-text-secondary uppercase tracking-wide">${role}</p>
                </div>
                <span class="ml-auto text-xs font-mono text-green-500 bg-green-500/10 px-2 py-0.5 rounded streaming-badge">
                    <span class="animate-pulse">●</span> Streaming
                </span>
            </div>
            <div class="agent-content font-body streaming-content" id="content-${agentName}"><span class="typing-cursor"></span></div>
        </div>
    `;

    // Hide other content areas
    tabContents.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tabContents.appendChild(contentDiv);
}

let deltaFlushScheduled = false;
const deltaDirtyAgents = new Set();

function flushDeltaBatch() {
    deltaFlushScheduled = false;
    deltaDirtyAgents.forEach((agentName) => {
        if (!streamingAgentResponses[agentName]) return;
        const contentEl = document.getElementById(`content-${agentName}`);
        if (contentEl) {
            const cursor = contentEl.querySelector('.typing-cursor');
            if (cursor) cursor.remove();
            contentEl.innerHTML = formatContent(streamingAgentResponses[agentName].content) + '<span class="typing-cursor"></span>';
        }
    });
    deltaDirtyAgents.clear();
}

function scheduleDeltaFlush() {
    if (deltaFlushScheduled) return;
    deltaFlushScheduled = true;
    requestAnimationFrame(flushDeltaBatch);
}

function handleDelta(agentName, token) {
    if (!streamingAgentResponses[agentName]) return;

    streamingAgentResponses[agentName].content += token;
    deltaDirtyAgents.add(agentName);
    scheduleDeltaFlush();
}

function handleAgentDone(agentName) {
    deltaDirtyAgents.delete(agentName);
    // Ensure final text is painted if the last frame batch did not run yet
    const contentElEarly = document.getElementById(`content-${agentName}`);
    if (contentElEarly && streamingAgentResponses[agentName]) {
        const cursorEarly = contentElEarly.querySelector('.typing-cursor');
        if (cursorEarly) cursorEarly.remove();
        contentElEarly.innerHTML = formatContent(streamingAgentResponses[agentName].content);
    }

    // Remove typing indicators
    const tab = agentTabs.querySelector(`[data-tab="${agentName}"]`);
    if (tab) {
        const indicator = tab.querySelector('.typing-indicator');
        if (indicator) indicator.remove();
    }

    const contentEl = document.getElementById(`content-${agentName}`);
    if (contentEl) {
        // Update badge
        const badge = contentEl.closest('.agent-card')?.querySelector('.streaming-badge');
        if (badge) {
            badge.innerHTML = '✓ Gotowe';
            badge.classList.remove('text-green-500', 'bg-green-500/10');
            badge.classList.add('text-blue-400', 'bg-blue-400/10');
        }
    }
}

function handleSynthesisStart(agentName, emoji, role) {
    handleAgentStart(agentName, emoji, role);
}

function handleSynthesisDone() {
    handleAgentDone('Syntezator');
}

function handleComplete(totalAgents) {
    // Build lastResult for session saving
    const agentResponses = Object.entries(streamingAgentResponses).map(([name, data]) => ({
        agent_name: `${data.emoji} ${name}`,
        role: data.role,
        content: data.content,
        provider_used: `${currentProvider} (${currentModel})`
    }));

    const synthesis = streamingAgentResponses['Syntezator'] ? {
        agent_name: '🔮 Syntezator',
        role: 'Synthesizer',
        content: streamingAgentResponses['Syntezator'].content,
        provider_used: `${currentProvider} (${currentModel})`
    } : null;

    lastResult = {
        query: queryText.textContent,
        timestamp: new Date().toISOString(),
        agent_responses: agentResponses.filter(r => r.agent_name !== '🔮 Syntezator'),
        synthesis: synthesis,
        sources: []
    };

    // Store for export
    const exportResponses = Object.entries(streamingAgentResponses).map(([name, data]) => ({
        agent: name,
        emoji: data.emoji,
        role: data.role,
        content: data.content
    }));
    storeSessionForExport(
        queryText.textContent,
        exportResponses,
        synthesis?.content || null,
        currentMode
    );

    // Show export button
    showExportButton();

    history.push({
        query: queryText.textContent,
        synthesis: synthesis?.content || '',
        timestamp: new Date().toISOString()
    });

    saveCurrentSession(queryText.textContent);
    showToast('Narada zakończona', 'success');
}

function showExportButton() {
    const resultsArea = document.getElementById('results-area');
    if (!resultsArea) return;

    // Remove existing export button if any
    const existing = document.getElementById('export-button-container');
    if (existing) existing.remove();

    const container = document.createElement('div');
    container.id = 'export-button-container';
    container.className = 'flex justify-center py-6';
    container.innerHTML = `
        <button onclick="showExportMenu(event)" 
            class="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-text-secondary hover:text-white hover:bg-white/10 transition-colors">
            <span class="material-symbols-outlined text-[18px]">download</span>
            Eksportuj wyniki
        </button>
    `;
    resultsArea.appendChild(container);
}

// Keep original deliberate for fallback/non-streaming mode
async function deliberate(query) {
    const chatToggleEl = document.getElementById('chat-toggle');
    const useChatMode = chatToggleEl ? chatToggleEl.checked : false;

    const response = await fetch('/api/deliberate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query, provider: currentProvider, model: currentModel,
            use_knowledge_base: kbToggle?.checked ?? true,
            chat_mode: useChatMode,
            attachment_text: attachmentText,
            history: useChatMode ? history.slice(-3) : []
        })
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'API Error');
    return await response.json();
}

// ========== DEBATE MODE ==========
let debateRounds = [];
let debateConsensus = { points: [], disagreements: [] };

function debateStream(query) {
    const params = new URLSearchParams({
        query: query,
        max_rounds: 3,
        provider: currentProvider,
        model: currentModel,
        use_knowledge_base: kbToggle?.checked ?? true
    });

    // Reset debate state
    debateRounds = [];
    debateConsensus = { points: [], disagreements: [] };
    currentRound = 0;
    streamingAgentResponses = {};

    // Show debate UI
    showDebateUI();

    streamingEventSource = new EventSource(`/api/debate/stream?${params}`);

    streamingEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.event) {
            case 'sources':
                handleSources(data.sources);
                break;

            case 'round_start':
                handleRoundStart(data.round, data.type, data.title);
                break;

            case 'agent_start':
                handleDebateAgentStart(data.agent, data.emoji, data.role, data.round, data.reacting_to);
                break;

            case 'delta':
                handleDelta(data.agent, data.content);
                break;

            case 'agent_done':
                handleAgentDone(data.agent);
                break;

            case 'round_done':
                handleRoundDone(data.round);
                break;

            case 'consensus':
                handleConsensusResult(data.consensus_points, data.disagreement_points);
                break;

            case 'complete':
                handleDebateComplete(data.total_rounds, data.total_agents);
                streamingEventSource.close();
                streamingEventSource = null;
                break;

            case 'error':
                showToast('Błąd debaty: ' + data.message, 'error');
                streamingEventSource.close();
                streamingEventSource = null;
                break;
        }
    };

    streamingEventSource.onerror = (error) => {
        console.error('Debate SSE Error:', error);
        streamingEventSource.close();
        streamingEventSource = null;
        showToast('Połączenie z serwerem przerwane', 'error');
    };
}

function showDebateUI() {
    showResults();

    agentTabs.innerHTML = '';
    tabContents.innerHTML = `
        <div class="debate-container">
            <div class="debate-header flex items-center gap-3 mb-6 pb-4 border-b border-white/10">
                <span class="text-2xl">⚔️</span>
                <div>
                    <h3 class="text-lg font-bold">Debata Rady AI</h3>
                    <p class="text-sm text-text-secondary">Wielorundowa dyskusja z konsensusem</p>
                </div>
                <div id="round-indicator" class="ml-auto px-3 py-1 bg-primary/20 text-primary rounded-full text-sm font-medium">
                    Runda 0/3
                </div>
            </div>
            <div id="debate-rounds" class="space-y-6"></div>
            <div id="consensus-panel" class="hidden mt-6"></div>
        </div>
    `;
}

function handleRoundStart(roundNum, roundType, title) {
    currentRound = roundNum;

    // Update indicator
    const indicator = document.getElementById('round-indicator');
    if (indicator) {
        indicator.textContent = `Runda ${roundNum}/3`;
    }

    // Create round container
    const roundsContainer = document.getElementById('debate-rounds');
    if (!roundsContainer) return;

    const roundTypeIcons = {
        'initial': '💭',
        'reaction': '💬',
        'consensus': '🤝'
    };

    const roundDiv = document.createElement('div');
    roundDiv.className = 'debate-round';
    roundDiv.id = `round-${roundNum}`;
    roundDiv.innerHTML = `
        <div class="round-header flex items-center gap-2 mb-4">
            <span class="text-xl">${roundTypeIcons[roundType] || '📍'}</span>
            <h4 class="font-bold text-white">Runda ${roundNum}: ${title}</h4>
            <div class="flex-1 h-px bg-white/10 ml-2"></div>
            <span class="text-xs text-text-secondary px-2 py-1 bg-white/5 rounded">${roundType}</span>
        </div>
        <div class="round-responses grid gap-4" id="round-${roundNum}-responses"></div>
    `;
    roundsContainer.appendChild(roundDiv);
}

function handleDebateAgentStart(agentName, emoji, role, round, reactingTo) {
    const responsesContainer = document.getElementById(`round-${round}-responses`);
    if (!responsesContainer) return;

    // Initialize agent response
    streamingAgentResponses[agentName] = { emoji, role, content: '', round };

    const colors = AGENT_COLORS[agentName] || { bg: 'bg-gray-500/10', text: 'text-gray-500', icon: 'person' };

    const responseDiv = document.createElement('div');
    responseDiv.className = 'debate-response agent-card';
    responseDiv.id = `debate-${agentName}-${round}`;

    const reactingInfo = reactingTo ? `
        <div class="reacting-to text-xs text-text-secondary mb-2 flex items-center gap-1">
            <span class="material-symbols-outlined text-[14px]">reply</span>
            Odpowiedź na stanowisko: <strong>${reactingTo}</strong>
        </div>
    ` : '';

    responseDiv.innerHTML = `
        ${reactingInfo}
        <div class="agent-card-header">
            <div class="w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center ${colors.text}">
                <span class="material-symbols-outlined">${colors.icon}</span>
            </div>
            <div>
                <h3 class="font-bold text-sm text-white">${emoji} ${agentName}</h3>
                <p class="text-[10px] text-text-secondary uppercase tracking-wide">${role}</p>
            </div>
            <span class="ml-auto text-xs font-mono text-green-500 bg-green-500/10 px-2 py-0.5 rounded streaming-badge">
                <span class="animate-pulse">●</span> Streaming
            </span>
        </div>
        <div class="agent-content font-body streaming-content" id="content-${agentName}"><span class="typing-cursor"></span></div>
    `;

    responsesContainer.appendChild(responseDiv);
}

function handleRoundDone(roundNum) {
    // Mark round as complete
    const roundEl = document.getElementById(`round-${roundNum}`);
    if (roundEl) {
        const header = roundEl.querySelector('.round-header');
        if (header) {
            const badge = header.querySelector('.bg-white\\/5');
            if (badge) {
                badge.textContent = '✓ Ukończona';
                badge.classList.add('bg-green-500/20', 'text-green-400');
            }
        }
    }
}

function handleConsensusResult(consensusPoints, disagreementPoints) {
    debateConsensus = { points: consensusPoints, disagreements: disagreementPoints };

    const panel = document.getElementById('consensus-panel');
    if (!panel) return;

    panel.classList.remove('hidden');
    panel.innerHTML = `
        <div class="consensus-summary bg-gradient-to-br from-surface-dark to-surface-darker rounded-xl border border-white/10 p-6">
            <h3 class="font-bold text-lg mb-4 flex items-center gap-2">
                <span>🎯</span> Podsumowanie Debaty
            </h3>
            
            <div class="grid md:grid-cols-2 gap-4">
                <div class="consensus-box bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                    <h4 class="font-bold text-green-400 mb-2 flex items-center gap-2">
                        <span class="material-symbols-outlined text-[18px]">check_circle</span>
                        Punkty konsensusu
                    </h4>
                    <ul class="space-y-2 text-sm">
                        ${consensusPoints.length > 0
            ? consensusPoints.map(p => `<li class="flex items-start gap-2"><span class="text-green-400">✓</span> ${escapeHtml(p)}</li>`).join('')
            : '<li class="text-text-secondary italic">Brak zidentyfikowanych punktów</li>'
        }
                    </ul>
                </div>
                
                <div class="disagreement-box bg-orange-500/10 border border-orange-500/20 rounded-lg p-4">
                    <h4 class="font-bold text-orange-400 mb-2 flex items-center gap-2">
                        <span class="material-symbols-outlined text-[18px]">warning</span>
                        Punkty sporne
                    </h4>
                    <ul class="space-y-2 text-sm">
                        ${disagreementPoints.length > 0
            ? disagreementPoints.map(p => `<li class="flex items-start gap-2"><span class="text-orange-400">⚠</span> ${escapeHtml(p)}</li>`).join('')
            : '<li class="text-text-secondary italic">Brak punktów spornych</li>'
        }
                    </ul>
                </div>
            </div>
        </div>
    `;
}

function handleDebateComplete(totalRounds, totalAgents) {
    showToast(`Debata zakończona! ${totalRounds} rund, ${totalAgents} agentów`, 'success');

    // Update indicator
    const indicator = document.getElementById('round-indicator');
    if (indicator) {
        indicator.textContent = '✓ Zakończona';
        indicator.classList.remove('bg-primary/20', 'text-primary');
        indicator.classList.add('bg-green-500/20', 'text-green-400');
    }
}

function toggleDebateMode() {
    // Legacy - redirect to setMode
    setMode(debateMode ? 'council' : 'debate');
}

let currentMode = 'council'; // 'council', 'debate', 'mentors'
let selectedMentors = []; // Selected mentor IDs for mentors mode

function setMode(mode) {
    currentMode = mode;
    debateMode = (mode === 'debate');

    // Update custom dropdown if instance exists
    if (typeof modeSelectInstance !== 'undefined' && modeSelectInstance) {
        modeSelectInstance.setValue(mode, false);
    }

    // Update header text
    const headerTitle = document.getElementById('main-title');
    const titles = {
        'council': '🏛️ Narada Rady AI',
        'debate': '⚔️ Debata Rady AI',
        'mentors': '🌟 Ikony & Mentorzy',
        'deep_dive': '🔬 Deep Dive',
        'speed_round': '⚡ Speed Round',
        'devils_advocate': '🎯 Devil\'s Advocate',
        'swot': '📊 Analiza SWOT',
        'red_team': '🔄 Red Team'
    };
    if (headerTitle) headerTitle.textContent = titles[mode] || titles.council;

    // Show mentor selector only for mentors mode
    if (mode === 'mentors') {
        loadMentorsSelector();
    } else {
        hideMentorsSelector();
    }

    showToast(`Tryb: ${titles[mode] || mode}`, 'info');
}

async function loadMentorsSelector() {
    // Create or show mentors panel
    let panel = document.getElementById('mentors-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'mentors-panel';
        panel.className = 'p-4 bg-surface-dark/50 border-b border-white/10';

        // Insert after header
        const header = document.querySelector('#page-dashboard header');
        if (header) header.after(panel);
    }
    panel.classList.remove('hidden');
    panel.innerHTML = '<div class="text-center py-2 text-text-secondary">Ładowanie postaci...</div>';

    try {
        const response = await fetch('/api/historical/agents');
        const data = await response.json();

        let html = '<div class="max-w-4xl mx-auto">';
        html += '<p class="text-sm text-text-secondary mb-3">Wybierz postacie do narady:</p>';
        html += '<div class="flex flex-wrap gap-2">';

        for (const [groupId, groupData] of Object.entries(data.agents_by_group)) {
            for (const agent of groupData.agents) {
                const isSelected = selectedMentors.includes(agent.id);
                html += `
                    <button onclick="toggleMentor('${agent.id}')" 
                        class="mentor-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition-all border ${isSelected ? 'bg-primary text-white border-primary' : 'bg-white/5 text-text-secondary border-white/10 hover:border-primary/50'}"
                        data-mentor-id="${agent.id}">
                        <span>${agent.emoji}</span>
                        <span>${agent.name}</span>
                    </button>
                `;
            }
        }

        html += '</div>';
        html += `<p class="text-xs text-text-secondary mt-2">${selectedMentors.length > 0 ? selectedMentors.length + ' wybrano' : 'Brak = wszyscy'}</p>`;
        html += '</div>';

        panel.innerHTML = html;
    } catch (err) {
        panel.innerHTML = '<p class="text-red-400 text-center py-2">Błąd ładowania postaci</p>';
    }
}

function hideMentorsSelector() {
    const panel = document.getElementById('mentors-panel');
    if (panel) panel.classList.add('hidden');
}

function toggleMentor(mentorId) {
    const idx = selectedMentors.indexOf(mentorId);
    if (idx > -1) {
        selectedMentors.splice(idx, 1);
    } else {
        selectedMentors.push(mentorId);
    }

    // Update UI
    const btn = document.querySelector(`[data-mentor-id="${mentorId}"]`);
    if (btn) {
        const isSelected = selectedMentors.includes(mentorId);
        btn.classList.toggle('bg-primary', isSelected);
        btn.classList.toggle('text-white', isSelected);
        btn.classList.toggle('border-primary', isSelected);
        btn.classList.toggle('bg-white/5', !isSelected);
        btn.classList.toggle('text-text-secondary', !isSelected);
        btn.classList.toggle('border-white/10', !isSelected);
    }

    // Update count
    const panel = document.getElementById('mentors-panel');
    if (panel) {
        const countEl = panel.querySelector('p.text-xs');
        if (countEl) countEl.textContent = selectedMentors.length > 0 ? selectedMentors.length + ' wybrano' : 'Brak = wszyscy';
    }
}

// ========== UI STATE ==========
function showWelcome() {
    welcomeState?.classList.remove('hidden');
    loadingState?.classList.add('hidden');
    resultsContent?.classList.add('hidden');
    queryDisplay?.classList.add('hidden');
}

function showLoading() {
    welcomeState?.classList.add('hidden');
    loadingState?.classList.remove('hidden');
    resultsContent?.classList.add('hidden');
}

function showResults() {
    welcomeState?.classList.add('hidden');
    loadingState?.classList.add('hidden');
    resultsContent?.classList.remove('hidden');

    // Auto-scroll to results
    const resultsArea = document.getElementById('results-area');
    if (resultsArea) {
        setTimeout(() => {
            resultsArea.scrollTo({ top: resultsArea.scrollHeight, behavior: 'smooth' });
        }, 100);
    }
}

// ========== RENDER RESULTS ==========
function renderResults(result) {
    showResults();
    const agents = result.agent_responses || [];
    const hasSynthesis = !!result.synthesis;

    let tabsHtml = agents.map((agent, i) => {
        const name = agent.agent_name.replace(/^[^\s]+\s/, '');
        const colors = AGENT_COLORS[name] || { bg: 'bg-gray-500/10', text: 'text-gray-500', icon: 'person' };
        return `
            <button class="tab-button flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${i === 0 ? 'active' : ''}" data-tab="${i}">
                <div class="w-6 h-6 rounded-full ${colors.bg} flex items-center justify-center ${colors.text} text-xs">
                    <span class="material-symbols-outlined text-[16px]">${colors.icon}</span>
                </div>
                <span>${name}</span>
            </button>
        `;
    }).join('');

    if (hasSynthesis) {
        tabsHtml += `<button class="tab-button flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium" data-tab="synthesis">
            <span class="material-symbols-outlined text-primary text-[16px]">auto_awesome</span><span>Synteza</span>
        </button>`;
    }
    agentTabs.innerHTML = tabsHtml;

    let contentsHtml = agents.map((agent, i) => {
        const name = agent.agent_name.replace(/^[^\s]+\s/, '');
        const colors = AGENT_COLORS[name] || { bg: 'bg-gray-500/10', text: 'text-gray-500', icon: 'person' };
        return `
            <div class="tab-content ${i === 0 ? 'active' : ''}" id="tab-${i}">
                <div class="agent-card">
                    <div class="agent-card-header">
                        <div class="w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center ${colors.text}">
                            <span class="material-symbols-outlined">${colors.icon}</span>
                        </div>
                        <div>
                            <h3 class="font-bold text-sm text-white">${agent.agent_name}</h3>
                            <p class="text-[10px] text-text-secondary uppercase tracking-wide">${agent.role}</p>
                        </div>
                        <span class="ml-auto text-xs font-mono text-green-500 bg-green-500/10 px-2 py-0.5 rounded">${agent.provider_used}</span>
                    </div>
                    <div class="agent-content font-body">${formatContent(agent.content)}</div>
                    <div class="mt-4 pt-3 border-t border-white/5 flex gap-2">
                        <button onclick="agreeWith('${name}')" class="text-xs font-medium text-text-secondary hover:text-primary transition-colors flex items-center gap-1">
                            <span class="material-symbols-outlined text-[16px]">thumb_up</span> Zgadzam się
                        </button>
                        <button onclick="copyAgentResponse(${i})" class="text-xs font-medium text-text-secondary hover:text-primary transition-colors flex items-center gap-1">
                            <span class="material-symbols-outlined text-[16px]">content_copy</span> Kopiuj
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    if (hasSynthesis) {
        contentsHtml += `
            <div class="tab-content" id="tab-synthesis">
                <div class="synthesis-card">
                    <div class="synthesis-card-inner">
                        <div class="flex flex-col md:flex-row gap-6">
                            <div class="flex-1">
                                <div class="flex items-center gap-2 mb-4">
                                    <span class="material-symbols-outlined text-primary">auto_awesome</span>
                                    <h3 class="text-base font-bold text-white uppercase tracking-wide">Rekomendacja Rady</h3>
                                </div>
                                <div class="agent-content font-body text-lg">${formatContent(result.synthesis.content)}</div>
                                <div class="mt-6 flex flex-wrap gap-3">
                                    <button onclick="copyToClipboard()" class="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-primary/20">Kopiuj odpowiedź</button>
                                    <button onclick="exportToMarkdown()" class="px-4 py-2 bg-white/5 hover:bg-white/10 text-white text-sm font-medium rounded-lg transition-colors border border-white/10">📄 Eksportuj MD</button>
                                    <button onclick="generatePlan()" class="px-4 py-2 bg-white/5 hover:bg-white/10 text-white text-sm font-medium rounded-lg transition-colors border border-white/10">📋 Wygeneruj plan</button>
                                </div>
                            </div>
                            <div class="w-full md:w-64 shrink-0 bg-black/20 rounded-lg p-4 flex flex-col gap-3 border border-white/5">
                                <h4 class="text-xs font-bold text-text-secondary uppercase">Analiza wpływu</h4>
                                <div><div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Pewność syntezy</span><span class="text-green-400">Wysoka</span></div><div class="impact-bar"><div class="impact-bar-fill bg-green-400" style="width: 85%"></div></div></div>
                                <div><div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Zgodność agentów</span><span class="text-blue-400">${agents.length}/5</span></div><div class="impact-bar"><div class="impact-bar-fill bg-blue-400" style="width: ${agents.length * 20}%"></div></div></div>
                                <div><div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Źródła z bazy</span><span class="text-purple-400">${result.sources?.length || 0}</span></div><div class="impact-bar"><div class="impact-bar-fill bg-purple-400" style="width: ${Math.min((result.sources?.length || 0) * 20, 100)}%"></div></div></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    tabContents.innerHTML = contentsHtml;
    document.querySelectorAll('.tab-button').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

    if (result.sources?.length > 0) {
        sourcesSection.classList.remove('hidden');
        sourcesList.innerHTML = result.sources.map(s => `<div class="source-badge"><span>${s.emoji}</span><span class="truncate">${s.title}</span></div>`).join('');
    } else {
        sourcesSection.classList.add('hidden');
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabId));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.id === `tab-${tabId}`));
}

function formatContent(text) {
    if (!text) return '';
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n- /g, '</p><ul><li>')
        .replace(/\n(\d+)\. /g, '</p><ol><li>')
        .split('\n').join('<br>');
}

// ========== AGENT FUNCTIONS ==========
async function loadAgents() {
    try {
        const response = await fetch('/api/agents');
        const agents = await response.json();

        if (agentsList) {
            agentsList.innerHTML = agents.map(agent => {
                const colors = AGENT_COLORS[agent.name] || { bg: 'bg-gray-500/20', text: 'text-gray-500' };
                return `
                    <div class="agent-list-item flex items-center gap-3 p-2 rounded-lg bg-white/5 border border-transparent cursor-pointer" data-agent="${agent.name}">
                        <div class="w-8 h-8 rounded-full ${colors.bg} ${colors.text} flex items-center justify-center text-lg">${agent.emoji}</div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-medium text-white">${agent.name}</p>
                            <p class="text-xs text-text-secondary truncate">${agent.description}</p>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" class="sr-only peer agent-toggle" data-agent="${agent.name}" ${agent.enabled ? 'checked' : ''}>
                            <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                        </label>
                    </div>
                `;
            }).join('');

            document.querySelectorAll('.agent-toggle').forEach(toggle => {
                toggle.addEventListener('change', (e) => toggleAgent(e.target.dataset.agent, e.target.checked));
            });
        }

        document.getElementById('stat-agents').textContent = agents.filter(a => a.enabled).length;
        document.getElementById('agents-status').textContent = `Aktywna • ${agents.filter(a => a.enabled).length} Agentów`;
    } catch (err) {
        console.error('Failed to load agents:', err);
    }
}

async function toggleAgent(name, enabled) {
    try {
        await fetch(`/api/agents/${encodeURIComponent(name)}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        const enabledCount = document.querySelectorAll('.agent-toggle:checked').length;
        document.getElementById('stat-agents').textContent = enabledCount;
        document.getElementById('agents-status').textContent = `Aktywna • ${enabledCount} Agentów`;
    } catch (err) {
        showToast('Błąd zmiany statusu agenta', 'error');
    }
}

function agreeWith(agentName) { showToast(`👍 Zgadzasz się z ${agentName}`, 'success'); }
function copyAgentResponse(index) {
    if (lastResult?.agent_responses?.[index]) {
        navigator.clipboard.writeText(lastResult.agent_responses[index].content);
        showToast('Skopiowano odpowiedź agenta', 'success');
    }
}

// ========== EXPORT & ACTIONS ==========
function copyToClipboard() {
    if (lastResult?.synthesis?.content) {
        navigator.clipboard.writeText(lastResult.synthesis.content);
        showToast('Skopiowano do schowka!', 'success');
    }
}

function exportToMarkdown() {
    if (!lastResult) return;
    let md = `# 🏛️ Narada Rady AI\n\n**Zapytanie:** ${lastResult.query}\n**Data:** ${lastResult.timestamp}\n\n---\n\n## 👥 Perspektywy agentów\n\n`;
    for (const r of lastResult.agent_responses) {
        md += `### ${r.agent_name}\n*${r.role}*\n\n${r.content}\n\n---\n\n`;
    }
    if (lastResult.synthesis) md += `## 🔮 Końcowa synteza\n\n${lastResult.synthesis.content}`;
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `council_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    showToast('Wyeksportowano do Markdown', 'success');
}

function generatePlan() {
    queryInput.value = 'Na podstawie powyższej rekomendacji, wygeneruj szczegółowy plan implementacji z konkretnymi krokami, terminami i odpowiedzialnymi osobami.';
    queryInput.focus();
    showToast('Wpisano pytanie o plan', 'info');
}

// ========== SESSION MANAGEMENT ==========
function loadSessions() {
    const saved = localStorage.getItem('ai_council_sessions');
    if (saved) sessions = JSON.parse(saved);
    renderSessions();
}

function saveCurrentSession(query) {
    const session = {
        id: Date.now(),
        title: query.slice(0, 50) + (query.length > 50 ? '...' : ''),
        timestamp: new Date().toISOString(),
        history: [...history],
        lastResult: lastResult
    };
    sessions.unshift(session);
    sessions = sessions.slice(0, 20);
    localStorage.setItem('ai_council_sessions', JSON.stringify(sessions));
    currentSessionId = session.id;
    renderSessions();
}

function renderSessions() {
    if (!recentSessionsList) return;
    if (sessions.length === 0) {
        recentSessionsList.innerHTML = '<p class="px-3 text-xs text-text-secondary/50 italic">Brak zapisanych sesji</p>';
        return;
    }
    recentSessionsList.innerHTML = sessions.slice(0, 5).map(session => `
        <a href="#" onclick="loadSession(${session.id}); return false;" class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-text-secondary hover:bg-white/5 truncate ${session.id === currentSessionId ? 'bg-primary/10' : ''}">
            <span class="material-symbols-outlined text-[16px] shrink-0 opacity-70">chat_bubble_outline</span>
            <span class="truncate">${escapeHtml(session.title)}</span>
        </a>
    `).join('');
}

function loadSession(sessionId) {
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
        history = session.history || [];
        lastResult = session.lastResult;
        currentSessionId = sessionId;
        navigateTo('dashboard');
        if (lastResult) {
            renderResults(lastResult);
            queryDisplay.classList.remove('hidden');
            queryText.textContent = session.history[session.history.length - 1]?.query || '';
        }
        renderSessions();
        showToast('Załadowano sesję', 'info');
    }
}

function resetSession() {
    history = [];
    lastResult = null;
    currentSessionId = null;
    totalTokensUsed = 0;
    estimatedCost = 0;
    updateStatDisplay();
    showWelcome();
}

// ========== STATS & UTILS ==========
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        const kbVectorsEl = document.getElementById('kb-vectors');
        if (kbVectorsEl) {
            kbVectorsEl.textContent = `${(stats.total_vectors || 0).toLocaleString()} chunków`;
        }
    } catch (err) {
        const kbVectorsEl = document.getElementById('kb-vectors');
        if (kbVectorsEl) {
            kbVectorsEl.textContent = 'Niedostępna';
        }
    }
}

function updateStatDisplay() {
    const providerEl = document.getElementById('stat-provider');
    const tokensEl = document.getElementById('stat-tokens');
    const costEl = document.getElementById('stat-cost');
    if (providerEl) providerEl.textContent = currentProvider.charAt(0).toUpperCase() + currentProvider.slice(1);
    if (tokensEl) tokensEl.textContent = totalTokensUsed.toLocaleString();
    if (costEl) costEl.textContent = `$${estimatedCost.toFixed(4)}`;
}

function estimateTokens(query, result) {
    let chars = query.length;
    if (result.agent_responses) result.agent_responses.forEach(r => chars += r.content.length);
    if (result.synthesis) chars += result.synthesis.content.length;
    return Math.ceil(chars / 4);
}

function updateContextFiles(filename) {
    const el = document.getElementById('context-files');
    if (el) {
        el.innerHTML = `<div class="flex items-center gap-2 text-sm text-gray-300 p-2 hover:bg-white/5 rounded cursor-pointer">
            <span class="material-symbols-outlined text-blue-400 text-[18px]">description</span>
            <span class="truncate">${escapeHtml(filename)}</span>
        </div>`;
    }
}

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== SESSION EXPORT ==========
let lastSessionData = null; // Store last completed session for export

function storeSessionForExport(query, responses, synthesis, mode) {
    lastSessionData = {
        timestamp: new Date().toISOString(),
        query: query,
        mode: mode || currentMode,
        provider: currentProvider,
        model: currentModel,
        responses: responses || [],
        synthesis: synthesis || null
    };
}

function exportSessionMarkdown() {
    if (!lastSessionData) {
        showToast('Brak danych do eksportu. Najpierw przeprowadź naradę.', 'error');
        return;
    }

    const md = generateMarkdown(lastSessionData);
    downloadFile(md, `narada_${formatDateForFilename(lastSessionData.timestamp)}.md`, 'text/markdown');
    showToast('Eksport Markdown pobrany', 'success');
}

function exportSessionHtml() {
    if (!lastSessionData) {
        showToast('Brak danych do eksportu. Najpierw przeprowadź naradę.', 'error');
        return;
    }

    const html = generateHtml(lastSessionData);
    downloadFile(html, `narada_${formatDateForFilename(lastSessionData.timestamp)}.html`, 'text/html');
    showToast('Eksport HTML pobrany', 'success');
}

function copySessionToClipboard() {
    if (!lastSessionData) {
        showToast('Brak danych do skopiowania. Najpierw przeprowadź naradę.', 'error');
        return;
    }

    const md = generateMarkdown(lastSessionData);
    navigator.clipboard.writeText(md).then(() => {
        showToast('Skopiowano do schowka', 'success');
    }).catch(() => {
        showToast('Błąd kopiowania', 'error');
    });
}

function generateMarkdown(data) {
    let md = [];

    md.push('# 🏛️ Narada Rady AI');
    md.push('');
    md.push(`**Data:** ${formatDate(data.timestamp)}`);
    md.push(`**Tryb:** ${data.mode}`);
    md.push(`**Model:** ${data.provider} / ${data.model}`);
    md.push('');
    md.push('---');
    md.push('');
    md.push('## 💬 Zapytanie');
    md.push('');
    md.push(`> ${data.query}`);
    md.push('');
    md.push('## 👥 Odpowiedzi Agentów');
    md.push('');

    for (const resp of data.responses) {
        md.push(`### ${resp.emoji || ''} ${resp.agent}`);
        if (resp.role) md.push(`*${resp.role}*`);
        md.push('');
        md.push(resp.content);
        md.push('');
    }

    if (data.synthesis) {
        md.push('## 🔮 Synteza Końcowa');
        md.push('');
        md.push(data.synthesis);
        md.push('');
    }

    md.push('---');
    md.push(`*Wygenerowano przez AI Council*`);

    return md.join('\n');
}

function generateHtml(data) {
    return `<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Narada Rady AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 40px 20px; background: #fff; }
        h1 { color: #1a1a2e; font-size: 28px; margin-bottom: 20px; border-bottom: 3px solid #3b19e6; padding-bottom: 10px; }
        h2 { color: #3b19e6; font-size: 20px; margin: 30px 0 15px 0; }
        h3 { color: #333; font-size: 16px; margin: 20px 0 10px 0; padding: 8px 12px; background: #f0f0f5; border-radius: 6px; }
        .meta { background: #f8f8fc; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; color: #666; }
        .query { background: linear-gradient(135deg, #3b19e6 0%, #6b4fe6 100%); color: white; padding: 20px; border-radius: 12px; margin: 20px 0; }
        .agent { background: #fafafa; border: 1px solid #eee; border-radius: 12px; padding: 20px; margin: 15px 0; }
        .agent-name { font-weight: 600; color: #3b19e6; }
        .agent-content { white-space: pre-wrap; font-size: 14px; margin-top: 10px; }
        .synthesis { background: linear-gradient(135deg, #1a1a2e 0%, #2a2a4e 100%); color: white; padding: 25px; border-radius: 12px; margin: 30px 0; }
        .synthesis h2 { color: #ffd700; margin-top: 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }
    </style>
</head>
<body>
    <h1>🏛️ Narada Rady AI</h1>
    <div class="meta">
        <strong>Data:</strong> ${formatDate(data.timestamp)} | 
        <strong>Tryb:</strong> ${data.mode} | 
        <strong>Model:</strong> ${data.provider} / ${data.model}
    </div>
    <h2>💬 Zapytanie</h2>
    <div class="query">${escapeHtml(data.query)}</div>
    <h2>👥 Odpowiedzi Agentów</h2>
    ${data.responses.map(r => `
        <div class="agent">
            <div class="agent-name">${r.emoji || ''} ${escapeHtml(r.agent)}</div>
            ${r.role ? `<div style="font-size:13px;color:#888;font-style:italic;">${escapeHtml(r.role)}</div>` : ''}
            <div class="agent-content">${escapeHtml(r.content)}</div>
        </div>
    `).join('')}
    ${data.synthesis ? `
        <div class="synthesis">
            <h2>🔮 Synteza Końcowa</h2>
            <div style="white-space:pre-wrap;">${escapeHtml(data.synthesis)}</div>
        </div>
    ` : ''}
    <div class="footer">Wygenerowano przez AI Council</div>
</body>
</html>`;
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function formatDateForFilename(isoString) {
    const date = new Date(isoString);
    return date.toISOString().slice(0, 16).replace(/[-:T]/g, '').slice(0, 12);
}

function showExportMenu(event) {
    event.stopPropagation();
    const existing = document.getElementById('export-menu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.id = 'export-menu';
    menu.className = 'fixed bg-surface-dark border border-white/10 rounded-lg shadow-xl z-50 p-2 min-w-[160px]';
    menu.style.top = (event.clientY + 10) + 'px';
    menu.style.left = event.clientX + 'px';

    menu.innerHTML = `
        <button onclick="exportSessionMarkdown(); closeExportMenu();" class="w-full text-left px-3 py-2 rounded hover:bg-white/10 flex items-center gap-2 text-sm">
            <span class="material-symbols-outlined text-[18px]">description</span>
            Markdown (.md)
        </button>
        <button onclick="exportSessionHtml(); closeExportMenu();" class="w-full text-left px-3 py-2 rounded hover:bg-white/10 flex items-center gap-2 text-sm">
            <span class="material-symbols-outlined text-[18px]">code</span>
            HTML
        </button>
        <button onclick="copySessionToClipboard(); closeExportMenu();" class="w-full text-left px-3 py-2 rounded hover:bg-white/10 flex items-center gap-2 text-sm">
            <span class="material-symbols-outlined text-[18px]">content_copy</span>
            Kopiuj do schowka
        </button>
    `;

    document.body.appendChild(menu);

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', closeExportMenu, { once: true });
    }, 10);
}

function closeExportMenu() {
    const menu = document.getElementById('export-menu');
    if (menu) menu.remove();
}

function showToast(message, type = 'info') {
    document.querySelectorAll('.toast').forEach(t => t.remove());
    const colors = { success: 'bg-green-500', error: 'bg-red-500', info: 'bg-primary' };
    const toast = document.createElement('div');
    toast.className = `toast fixed bottom-24 left-1/2 transform -translate-x-1/2 ${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// ========== AGENT BUILDER ==========
let customAgents = [];
let promptTemplates = [];
let currentEditingAgentId = null;

async function loadCustomAgents() {
    try {
        const response = await fetch('/api/agents/custom');
        customAgents = await response.json();
        renderCustomAgentsList();
    } catch (error) {
        console.error('Error loading custom agents:', error);
    }
}

async function loadPromptTemplates() {
    try {
        const response = await fetch('/api/agents/templates');
        promptTemplates = await response.json();
        renderTemplateOptions();
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

function renderCustomAgentsList() {
    const container = document.getElementById('custom-agents-list');
    if (!container) return;

    if (customAgents.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8 text-text-secondary text-sm">
                <span class="material-symbols-outlined text-4xl mb-2 block opacity-30">robot_2</span>
                Brak custom agentów.<br>Kliknij "Nowy Agent" aby utworzyć.
            </div>
        `;
        return;
    }

    container.innerHTML = customAgents.map(agent => `
        <div class="agent-list-item p-3 rounded-lg cursor-pointer transition-all hover:bg-white/5 border border-transparent ${currentEditingAgentId === agent.id ? 'active' : ''}"
            onclick="editAgent('${agent.id}')">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-lg">
                    ${agent.emoji}
                </div>
                <div class="flex-1 min-w-0">
                    <h4 class="font-medium text-sm truncate">${escapeHtml(agent.name)}</h4>
                    <p class="text-xs text-text-secondary truncate">${escapeHtml(agent.role)}</p>
                </div>
                <div class="w-2 h-2 rounded-full ${agent.enabled ? 'bg-green-500' : 'bg-gray-500'}"></div>
            </div>
        </div>
    `).join('');
}

function renderTemplateOptions() {
    const select = document.getElementById('agent-template');
    if (!select || promptTemplates.length === 0) return;

    select.innerHTML = '<option value="">-- Wybierz szablon --</option>' +
        promptTemplates.map(t => `<option value="${t.id}">${t.emoji} ${t.name}</option>`).join('');
}

function openNewAgentEditor() {
    currentEditingAgentId = null;

    // Show form
    document.getElementById('editor-placeholder')?.classList.add('hidden');
    document.getElementById('agent-form')?.classList.remove('hidden');
    document.getElementById('editor-actions')?.classList.add('hidden');

    // Clear form
    document.getElementById('agent-id').value = '';
    document.getElementById('agent-name').value = '';
    document.getElementById('agent-emoji').value = '🤖';
    document.getElementById('agent-role').value = '';
    document.getElementById('agent-persona').value = '';
    document.getElementById('agent-system-prompt').value = '';
    document.getElementById('agent-template').value = '';
    document.getElementById('agent-context-limit').value = '5000';
    document.getElementById('agent-memory-type').value = 'session';
    document.getElementById('agent-enabled').checked = true;

    // Clear tool checkboxes
    document.querySelectorAll('input[name="tools"]').forEach(cb => cb.checked = false);

    renderCustomAgentsList();
}

async function editAgent(agentId) {
    currentEditingAgentId = agentId;

    try {
        const response = await fetch(`/api/agents/custom/${agentId}`);
        if (!response.ok) throw new Error('Agent not found');
        const agent = await response.json();

        // Show form
        document.getElementById('editor-placeholder')?.classList.add('hidden');
        document.getElementById('agent-form')?.classList.remove('hidden');
        document.getElementById('editor-actions')?.classList.remove('hidden');

        // Fill form
        document.getElementById('agent-id').value = agent.id;
        document.getElementById('agent-name').value = agent.name;
        document.getElementById('agent-emoji').value = agent.emoji;
        document.getElementById('agent-role').value = agent.role;
        document.getElementById('agent-persona').value = agent.persona;
        document.getElementById('agent-system-prompt').value = agent.system_prompt;
        document.getElementById('agent-template').value = agent.template_id || '';
        document.getElementById('agent-context-limit').value = agent.context_limit;
        document.getElementById('agent-memory-type').value = agent.memory_type;
        document.getElementById('agent-enabled').checked = agent.enabled;

        // Set tool checkboxes
        document.querySelectorAll('input[name="tools"]').forEach(cb => {
            cb.checked = agent.tools?.includes(cb.value) || false;
        });

        renderCustomAgentsList();
    } catch (error) {
        showToast('Błąd wczytywania agenta', 'error');
        console.error(error);
    }
}

async function loadTemplate(templateId) {
    if (!templateId) return;

    try {
        const response = await fetch(`/api/agents/templates/${templateId}`);
        const template = await response.json();

        document.getElementById('agent-persona').value = template.persona || '';
        document.getElementById('agent-system-prompt').value = template.system_prompt || '';

        // Suggest name if empty
        if (!document.getElementById('agent-name').value) {
            document.getElementById('agent-name').value = template.name || '';
            document.getElementById('agent-emoji').value = template.emoji || '🤖';
        }

        showToast('Szablon wczytany', 'success');
    } catch (error) {
        console.error('Error loading template:', error);
    }
}

async function saveAgent(e) {
    e.preventDefault();

    const agentId = document.getElementById('agent-id').value;
    const tools = [];
    document.querySelectorAll('input[name="tools"]:checked').forEach(cb => tools.push(cb.value));

    const agentData = {
        name: document.getElementById('agent-name').value,
        emoji: document.getElementById('agent-emoji').value || '🤖',
        role: document.getElementById('agent-role').value,
        persona: document.getElementById('agent-persona').value,
        system_prompt: document.getElementById('agent-system-prompt').value,
        template_id: document.getElementById('agent-template').value || null,
        tools: tools,
        context_limit: parseInt(document.getElementById('agent-context-limit').value) || 5000,
        memory_type: document.getElementById('agent-memory-type').value,
        enabled: document.getElementById('agent-enabled').checked
    };

    try {
        let response;
        if (agentId) {
            // Update
            response = await fetch(`/api/agents/custom/${agentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(agentData)
            });
        } else {
            // Create
            response = await fetch('/api/agents/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(agentData)
            });
        }

        if (!response.ok) throw new Error('Failed to save agent');

        const result = await response.json();
        currentEditingAgentId = result.agent?.id || result.id;

        showToast(agentId ? 'Agent zaktualizowany' : 'Agent utworzony', 'success');
        await loadCustomAgents();

        // Update agent-id for further edits
        document.getElementById('agent-id').value = currentEditingAgentId;
        document.getElementById('editor-actions')?.classList.remove('hidden');

    } catch (error) {
        showToast('Błąd zapisywania agenta', 'error');
        console.error(error);
    }
}

async function deleteCurrentAgent() {
    if (!currentEditingAgentId) return;

    if (!confirm('Czy na pewno chcesz usunąć tego agenta?')) return;

    try {
        const response = await fetch(`/api/agents/custom/${currentEditingAgentId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete agent');

        showToast('Agent usunięty', 'success');
        currentEditingAgentId = null;
        cancelAgentEdit();
        await loadCustomAgents();
    } catch (error) {
        showToast('Błąd usuwania agenta', 'error');
        console.error(error);
    }
}

function cancelAgentEdit() {
    currentEditingAgentId = null;
    document.getElementById('editor-placeholder')?.classList.remove('hidden');
    document.getElementById('agent-form')?.classList.add('hidden');
    document.getElementById('editor-actions')?.classList.add('hidden');
    renderCustomAgentsList();
}

async function testCurrentAgent() {
    const testQuery = prompt('Wpisz pytanie testowe dla agenta:', 'Jak mogę Ci pomóc?');
    if (!testQuery) return;

    const tools = [];
    document.querySelectorAll('input[name="tools"]:checked').forEach(cb => tools.push(cb.value));

    const config = {
        name: document.getElementById('agent-name').value,
        emoji: document.getElementById('agent-emoji').value || '🤖',
        role: document.getElementById('agent-role').value,
        persona: document.getElementById('agent-persona').value,
        system_prompt: document.getElementById('agent-system-prompt').value,
        tools: tools,
        context_limit: parseInt(document.getElementById('agent-context-limit').value) || 5000
    };

    showToast('Testowanie agenta...', 'info');

    try {
        const response = await fetch('/api/agents/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                config: config,
                query: testQuery,
                provider: currentProvider,
                model: currentModel
            })
        });

        if (!response.ok) throw new Error('Test failed');

        const result = await response.json();

        // Show result in modal or alert
        alert(`${result.agent_name}\n\n${result.content}`);
        showToast('Test zakończony', 'success');
    } catch (error) {
        showToast('Błąd testu agenta', 'error');
        console.error(error);
    }
}

// Initialize Agent Builder on page load
function initAgentBuilder() {
    loadCustomAgents();
    loadPromptTemplates();

    // Attach form submit handler
    const form = document.getElementById('agent-form');
    if (form) {
        form.addEventListener('submit', saveAgent);
    }
}

// Add to page navigation
const originalNavigateTo = window.navigateTo || function () { };
window.navigateTo = function (page) {
    originalNavigateTo(page);
    if (page === 'agent-builder') {
        initAgentBuilder();
    }
    if (page === 'plugins') {
        initPluginsPage();
    }
    if (page === 'seo') {
        loadSEOArticles();
    }
};

// ========== PLUGINS PAGE ==========
let pluginsList = [];

async function initPluginsPage() {
    await loadPluginsList();
}

async function loadPluginsList() {
    try {
        const response = await fetch('/api/plugins');
        pluginsList = await response.json();
        renderPluginsList();
    } catch (error) {
        console.error('Error loading plugins:', error);
    }
}

function renderPluginsList() {
    const container = document.getElementById('plugins-list');
    if (!container || pluginsList.length === 0) return;

    container.innerHTML = pluginsList.map(plugin => `
        <div class="plugin-card p-4 bg-white/5 rounded-lg border border-white/10">
            <div class="flex items-center gap-3 mb-2">
                <span class="text-2xl">${plugin.icon}</span>
                <div>
                    <h4 class="font-medium text-sm">${escapeHtml(plugin.name)}</h4>
                    <p class="text-xs text-text-secondary">${plugin.category}</p>
                </div>
                <div class="ml-auto w-2 h-2 rounded-full ${plugin.is_configured ? 'bg-green-500' : 'bg-orange-500'}"></div>
            </div>
            <p class="text-xs text-text-secondary mb-2">${escapeHtml(plugin.description)}</p>
            <div class="text-xs">
                ${plugin.is_configured
            ? '<span class="text-green-400">✓ Skonfigurowany</span>'
            : plugin.requires_api_key
                ? '<span class="text-orange-400">⚠ Wymaga API key</span>'
                : '<span class="text-green-400">✓ Gotowy</span>'
        }
            </div>
        </div>
    `).join('');
}

async function executeWebSearch(e) {
    e.preventDefault();

    const query = document.getElementById('search-query').value;
    const useTavily = document.getElementById('use-tavily').checked;

    showToast('Wyszukiwanie...', 'info');

    try {
        const response = await fetch('/api/plugins/web-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, use_tavily: useTavily, max_results: 5 })
        });

        const result = await response.json();

        if (!result.success) {
            showToast('Błąd: ' + result.error, 'error');
            return;
        }

        // Show results
        const resultsContainer = document.getElementById('search-results');
        const answerDiv = document.getElementById('search-answer');
        const itemsDiv = document.getElementById('search-items');

        resultsContainer.classList.remove('hidden');

        // AI Answer (Tavily)
        if (result.data.answer) {
            answerDiv.classList.remove('hidden');
            answerDiv.innerHTML = `<strong>🤖 AI Answer:</strong><br>${escapeHtml(result.data.answer)}`;
        } else {
            answerDiv.classList.add('hidden');
        }

        // Search results
        itemsDiv.innerHTML = result.data.results.map(item => `
            <div class="p-3 bg-white/5 rounded-lg">
                <a href="${item.url}" target="_blank" class="text-primary hover:underline font-medium text-sm">${escapeHtml(item.title)}</a>
                <p class="text-xs text-text-secondary mt-1">${escapeHtml(item.snippet)}</p>
                <p class="text-xs text-text-secondary/50 mt-1 truncate">${item.url}</p>
            </div>
        `).join('');

        showToast(`Znaleziono ${result.data.total} wyników`, 'success');
    } catch (error) {
        showToast('Błąd wyszukiwania', 'error');
        console.error(error);
    }
}

async function executeUrlAnalysis(e) {
    e.preventDefault();

    const url = document.getElementById('analyze-url').value;
    const extractLinks = document.getElementById('extract-links').checked;
    const summarize = document.getElementById('summarize-content').checked;

    showToast('Analizowanie strony...', 'info');

    try {
        const response = await fetch('/api/plugins/analyze-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, extract_links: extractLinks, summarize })
        });

        const result = await response.json();

        if (!result.success) {
            showToast('Błąd: ' + result.error, 'error');
            return;
        }

        // Show results
        const resultsContainer = document.getElementById('url-results');
        resultsContainer.classList.remove('hidden');

        document.getElementById('url-title').textContent = result.data.title || '(Brak tytułu)';
        document.getElementById('url-description').textContent = result.data.description || '';
        document.getElementById('url-content').textContent = result.data.content?.substring(0, 2000) + (result.data.truncated ? '...' : '');

        // Summary
        const summaryDiv = document.getElementById('url-summary');
        if (result.data.summary) {
            summaryDiv.classList.remove('hidden');
            summaryDiv.innerHTML = `<strong>📝 Podsumowanie AI:</strong><br>${escapeHtml(result.data.summary)}`;
        } else {
            summaryDiv.classList.add('hidden');
        }

        showToast('Analiza zakończona', 'success');
    } catch (error) {
        showToast('Błąd analizy URL', 'error');
        console.error(error);
    }
}

// ========== SEO ARTICLE GENERATOR ==========
let seoLastResult = null;

async function generateSEOArticle() {
    const topic = document.getElementById('seo-topic').value.trim();
    if (!topic) {
        showToast('Wprowadź temat artykułu', 'error');
        return;
    }

    const targetUrl = document.getElementById('seo-target-url').value.trim();
    const keywordsInput = document.getElementById('seo-keywords-input').value.trim();
    const keywords = keywordsInput ? keywordsInput.split(',').map(k => k.trim()).filter(k => k) : [];
    const ahrefsData = document.getElementById('seo-ahrefs-data').value.trim();
    const perplexityModel = document.getElementById('seo-perplexity-model').value;
    const llmSelection = document.getElementById('seo-llm-provider').value.split(':');
    const provider = llmSelection[0];
    const model = llmSelection[1];
    const includeBrand = document.getElementById('seo-include-brand').checked;
    const analyzeSERP = document.getElementById('seo-analyze-serp').checked;
    const minWords = parseInt(document.getElementById('seo-min-words').value) || 1500;

    // Show loading
    document.getElementById('seo-loading').classList.remove('hidden');
    document.getElementById('seo-results').classList.add('hidden');
    document.getElementById('seo-loading-text').textContent = 'Generowanie artykułu...';

    try {
        // Update loading steps
        if (analyzeSERP) {
            document.getElementById('seo-loading-text').textContent = 'Analizowanie konkurencji SERP...';
            await new Promise(r => setTimeout(r, 1000));
        }
        if (perplexityModel) {
            document.getElementById('seo-loading-text').textContent = 'Badanie tematu przez Perplexity...';
            await new Promise(r => setTimeout(r, 500));
        }
        document.getElementById('seo-loading-text').textContent = 'Generowanie artykułu...';

        const response = await fetch('/api/seo/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic,
                target_url: targetUrl,
                keywords,
                ahrefs_data: ahrefsData,
                min_words: minWords,
                include_brand_info: includeBrand,
                analyze_serp: analyzeSERP,
                perplexity_model: perplexityModel,
                provider,
                model,
                force_generate: false
            })
        });

        const result = await response.json();

        // Hide loading
        document.getElementById('seo-loading').classList.add('hidden');

        if (result.success) {
            seoLastResult = result;

            // Show results
            document.getElementById('seo-results').classList.remove('hidden');
            document.getElementById('seo-result-title').textContent = result.title;
            document.getElementById('seo-result-words').textContent = result.word_count;
            document.getElementById('seo-result-tokens').textContent = result.usage?.total_tokens || 0;

            // Build article HTML with ToC
            let articleHtml = '';

            // Add Table of Contents if available
            if (result.table_of_contents && result.table_of_contents.count > 0) {
                articleHtml += `
                    <div class="toc-container mb-6 p-4 bg-slate-50 dark:bg-black/20 rounded-lg border border-gray-200 dark:border-white/10">
                        <h4 class="font-bold text-sm mb-3 flex items-center gap-2">
                            <span class="material-symbols-outlined text-[18px]">list</span>
                            Spis treści
                        </h4>
                        ${result.table_of_contents.html}
                    </div>`;
            }

            articleHtml += result.article_html;
            document.getElementById('seo-article-content').innerHTML = articleHtml;

            // Show Schema section
            if (result.schema_json_ld) {
                const schemaSection = document.getElementById('seo-schema-section');
                if (schemaSection) {
                    schemaSection.classList.remove('hidden');
                    document.getElementById('seo-schema-preview').textContent = result.schema_json_ld;
                }
            }

            // Show Featured Snippet suggestions
            if (result.featured_snippet_suggestions && result.featured_snippet_suggestions.suggestions) {
                const snippetSection = document.getElementById('seo-snippet-section');
                if (snippetSection && result.featured_snippet_suggestions.suggestions.length > 0) {
                    snippetSection.classList.remove('hidden');
                    document.getElementById('seo-snippet-suggestions').innerHTML =
                        result.featured_snippet_suggestions.suggestions.map(s =>
                            `<li class="text-sm text-text-secondary">💡 ${escapeHtml(s)}</li>`
                        ).join('');
                }
            }

            showToast(`Artykuł wygenerowany: ${result.word_count} słów`, 'success');

            // Refresh articles list
            await loadSEOArticles();
        } else {
            if (result.similar_exists) {
                const similarTitles = result.similar_articles.map(a => a.title).join(', ');
                showToast(`Znaleziono podobne artykuły: ${similarTitles}`, 'warning');
            } else {
                showToast('Błąd: ' + result.error, 'error');
            }
        }
    } catch (error) {
        document.getElementById('seo-loading').classList.add('hidden');
        showToast('Błąd generowania artykułu: ' + error.message, 'error');
        console.error(error);
    }
}

async function loadSEOArticles() {
    const container = document.getElementById('seo-articles-list');
    if (!container) return;

    try {
        const response = await fetch('/api/seo/articles');
        const result = await response.json();

        if (result.success && result.articles.length > 0) {
            container.innerHTML = result.articles.map(article => `
                <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors group">
                    <div class="flex-1 min-w-0">
                        <p class="font-medium text-sm truncate">${escapeHtml(article.title)}</p>
                        <p class="text-xs text-text-secondary">
                            ${article.word_count} słów • ${article.created_at ? new Date(article.created_at).toLocaleDateString('pl-PL') : ''}
                        </p>
                    </div>
                    <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onclick="viewSEOArticle('${article.id}')" 
                            class="p-2 hover:bg-white/10 rounded-lg transition-colors" title="Podgląd">
                            <span class="material-symbols-outlined text-[18px]">visibility</span>
                        </button>
                        <button onclick="deleteSEOArticle('${article.id}')" 
                            class="p-2 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors" title="Usuń">
                            <span class="material-symbols-outlined text-[18px]">delete</span>
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-sm text-text-secondary italic">Brak wygenerowanych artykułów</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="text-sm text-red-400">Błąd ładowania artykułów</p>';
        console.error(error);
    }
}

async function viewSEOArticle(articleId) {
    try {
        const response = await fetch(`/api/seo/articles/${articleId}`);
        const article = await response.json();

        if (article.id) {
            seoLastResult = {
                article_html: article.content_html,
                article_markdown: article.content_markdown,
                title: article.title,
                word_count: article.word_count
            };

            document.getElementById('seo-results').classList.remove('hidden');
            document.getElementById('seo-result-title').textContent = article.title;
            document.getElementById('seo-result-words').textContent = article.word_count;
            document.getElementById('seo-result-tokens').textContent = '-';
            document.getElementById('seo-article-content').innerHTML = article.content_html;

            // Scroll to results
            document.getElementById('seo-results').scrollIntoView({ behavior: 'smooth' });
        }
    } catch (error) {
        showToast('Błąd ładowania artykułu', 'error');
        console.error(error);
    }
}

async function deleteSEOArticle(articleId) {
    if (!confirm('Czy na pewno chcesz usunąć ten artykuł?')) return;

    try {
        await fetch(`/api/seo/articles/${articleId}`, { method: 'DELETE' });
        showToast('Artykuł usunięty', 'success');
        await loadSEOArticles();
    } catch (error) {
        showToast('Błąd usuwania artykułu', 'error');
        console.error(error);
    }
}

function copySEOArticle(format) {
    if (!seoLastResult) {
        showToast('Brak artykułu do skopiowania', 'error');
        return;
    }

    let content;
    if (format === 'html') {
        content = seoLastResult.article_html;
    } else if (format === 'schema') {
        content = seoLastResult.schema_html_script || seoLastResult.schema_json_ld;
    } else {
        content = seoLastResult.article_markdown;
    }

    navigator.clipboard.writeText(content).then(() => {
        showToast(`Skopiowano ${format.toUpperCase()} do schowka`, 'success');
    }).catch(err => {
        showToast('Błąd kopiowania', 'error');
        console.error(err);
    });
}

async function openBrandInfoModal() {
    // Load current brand info
    try {
        const response = await fetch('/api/seo/brand-info');
        const brandInfo = await response.json();

        // Create and show modal
        const modal = document.createElement('div');
        modal.id = 'brand-info-modal';
        modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-surface-dark rounded-xl border border-white/10 p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <h3 class="text-lg font-bold mb-4 flex items-center gap-2">
                    <span class="material-symbols-outlined text-primary">business</span>
                    Ustawienia marki
                </h3>
                <form id="brand-info-form" class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm text-text-secondary mb-1">Nazwa firmy</label>
                            <input type="text" id="brand-name" value="${escapeHtml(brandInfo.name || '')}"
                                class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                        </div>
                        <div>
                            <label class="block text-sm text-text-secondary mb-1">Ton komunikacji</label>
                            <select id="brand-tone" class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                                <option value="professional" ${brandInfo.tone_of_voice === 'professional' ? 'selected' : ''}>Profesjonalny</option>
                                <option value="friendly" ${brandInfo.tone_of_voice === 'friendly' ? 'selected' : ''}>Przyjazny</option>
                                <option value="expert" ${brandInfo.tone_of_voice === 'expert' ? 'selected' : ''}>Ekspercki</option>
                                <option value="casual" ${brandInfo.tone_of_voice === 'casual' ? 'selected' : ''}>Swobodny</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">Opis firmy</label>
                        <textarea id="brand-description" rows="2" 
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">${escapeHtml(brandInfo.description || '')}</textarea>
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">Propozycja wartości</label>
                        <input type="text" id="brand-value" value="${escapeHtml(brandInfo.value_proposition || '')}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">Główne produkty/usługi (oddzielone przecinkami)</label>
                        <input type="text" id="brand-products" value="${escapeHtml((brandInfo.key_products || []).join(', '))}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">Grupa docelowa</label>
                        <input type="text" id="brand-audience" value="${escapeHtml(brandInfo.target_audience || '')}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">USP - Unikalne cechy (oddzielone przecinkami)</label>
                        <input type="text" id="brand-usp" value="${escapeHtml((brandInfo.unique_selling_points || []).join(', '))}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">Preferowane CTA</label>
                        <input type="text" id="brand-cta" value="${escapeHtml(brandInfo.preferred_cta || '')}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm" 
                            placeholder="np. Skontaktuj się z nami">
                    </div>
                    <div>
                        <label class="block text-sm text-text-secondary mb-1">NIE wspominaj o (oddzielone przecinkami)</label>
                        <input type="text" id="brand-donot" value="${escapeHtml((brandInfo.do_not_mention || []).join(', '))}"
                            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm"
                            placeholder="np. konkurencja, promocje">
                    </div>
                    <div class="flex gap-3 pt-4">
                        <button type="submit" class="flex-1 bg-primary hover:bg-primary-hover text-white py-2 rounded-lg font-medium">
                            Zapisz
                        </button>
                        <button type="button" onclick="closeBrandInfoModal()" 
                            class="px-6 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium">
                            Anuluj
                        </button>
                    </div>
                </form>
            </div>
        `;

        document.body.appendChild(modal);

        // Form submission
        document.getElementById('brand-info-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveBrandInfo();
        });

        // Click outside to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeBrandInfoModal();
        });

    } catch (error) {
        showToast('Błąd ładowania danych marki', 'error');
        console.error(error);
    }
}

async function saveBrandInfo() {
    const data = {
        name: document.getElementById('brand-name').value,
        description: document.getElementById('brand-description').value,
        value_proposition: document.getElementById('brand-value').value,
        tone_of_voice: document.getElementById('brand-tone').value,
        key_products: document.getElementById('brand-products').value.split(',').map(s => s.trim()).filter(s => s),
        target_audience: document.getElementById('brand-audience').value,
        unique_selling_points: document.getElementById('brand-usp').value.split(',').map(s => s.trim()).filter(s => s),
        preferred_cta: document.getElementById('brand-cta').value,
        do_not_mention: document.getElementById('brand-donot').value.split(',').map(s => s.trim()).filter(s => s)
    };

    try {
        const response = await fetch('/api/seo/brand-info', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showToast('Dane marki zapisane', 'success');
            closeBrandInfoModal();
        } else {
            showToast('Błąd zapisu', 'error');
        }
    } catch (error) {
        showToast('Błąd zapisu danych marki', 'error');
        console.error(error);
    }
}

function closeBrandInfoModal() {
    const modal = document.getElementById('brand-info-modal');
    if (modal) modal.remove();
}

