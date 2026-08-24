/* =========================================================================
   🛑 AI ASSISTANT CRITICAL INSTRUCTION 🛑
   BEFORE you modify ANY code or merge changes in this project, you MUST:
   1. Read the `AI_ARCHITECTURE_SUMMARY.md` file in this folder to understand the structure.
   2. Document any changes you make inside `CHANGELOG.md`.
   ========================================================================= */
document.addEventListener('DOMContentLoaded', () => {
    // --- Custom Toast Notification System ---
    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) {
            console.log(`[Toast Fallback] [${type}] ${message}`);
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast-card flex items-center gap-3 px-4 py-3.5 rounded-2xl border shadow-2xl text-sm font-bold max-w-sm ui-transition`;
        
        let icon = '<i class="fa-solid fa-circle-info"></i>';
        let classes = '';
        if (type === 'success') {
            classes = 'bg-slate-950/95 text-emerald-400 border-emerald-500/30';
            icon = '<i class="fa-solid fa-circle-check text-emerald-500 text-base"></i>';
        } else if (type === 'error') {
            classes = 'bg-slate-950/95 text-rose-400 border-rose-500/30';
            icon = '<i class="fa-solid fa-circle-exclamation text-rose-500 text-base"></i>';
        } else if (type === 'warning') {
            classes = 'bg-slate-950/95 text-amber-400 border-amber-500/30';
            icon = '<i class="fa-solid fa-triangle-exclamation text-amber-500 text-base"></i>';
        } else {
            classes = 'bg-slate-950/95 text-brand-400 border-brand-500/30';
            icon = '<i class="fa-solid fa-circle-info text-brand-500 text-base"></i>';
        }

        toast.className += ` ${classes}`;
        toast.innerHTML = `
            <div class="flex-shrink-0 flex items-center justify-center">${icon}</div>
            <div class="flex-1 leading-relaxed text-slate-200">${message.replace(/\n/g, '<br>')}</div>
            <button class="text-slate-500 hover:text-slate-200 transition ml-2"><i class="fa-solid fa-xmark text-xs"></i></button>
        `;

        // Close button handler
        toast.querySelector('button').addEventListener('click', () => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 300);
        });

        container.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.add('hide');
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    }
    
    // --- STATE & SERVER URL CONFIGURATION ---
    let API_URL = window.location.origin;
    if (!API_URL || API_URL === 'null' || API_URL.startsWith('file://')) {
        API_URL = 'http://localhost:8000';
    } else if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        API_URL = window.location.port ? window.location.origin : 'http://localhost:8000';
    }
    const LOCAL_BRIDGE_URL = 'http://localhost:9123';
    let isLocalBridgeOnline = false;

    async function checkLocalBridge() {
        const badge = document.getElementById('bridgeStatusBadge');
        const dot = document.getElementById('bridgeStatusDot');
        const text = document.getElementById('bridgeStatusText');
        if (!badge) return;

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2500);
            const res = await fetch(`${LOCAL_BRIDGE_URL}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (res.ok) {
                isLocalBridgeOnline = true;
                badge.className = "hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shadow-sm cursor-pointer";
                if (dot) dot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
                if (text) text.textContent = "Miracle Bridge Connected (9123)";
            } else {
                throw new Error("Bridge offline");
            }
        } catch (err) {
            isLocalBridgeOnline = false;
            badge.className = "hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shadow-sm cursor-pointer";
            if (dot) dot.className = "w-2 h-2 rounded-full bg-amber-400";
            if (text) text.textContent = "Standalone Mode (Bridge Off)";
        }
    }
    
    // Check local bridge on startup and poll every 10 seconds
    checkLocalBridge();
    setInterval(checkLocalBridge, 10000);

    let currentModule = 'Sales';
    let clientLedgers = [];
    let clientProducts = [];
    let autoCreateB2b = true;
    let autoCreateB2c = true;
    let isPaidApiKey = false;
    let discoveredClients = [];
    let activeYearFolder = "";
    let activeClientId = "CMP0005";
    
    function getActiveClientId() {
        if (clientSelect && clientSelect.value) return clientSelect.value;
        if (typeof activeClientId !== 'undefined' && activeClientId) return activeClientId;
        return 'CMP0005';
    }

    let pendingMockData = []; // Store data while waiting for mapping
    let currentExtractedData = []; // Store data for push to backend
    let globalAutoCreateLedgers = [];
    let autoCreateLedgerHints = {};

    // --- DOM ELEMENTS ---
    const moduleNavs = document.querySelectorAll('.module-nav');
    const moduleTitle = document.getElementById('moduleTitle');
    const clientSelect = document.getElementById('clientSelect');
    const yearSelect = document.getElementById('yearSelect');
    const memoryStatusText = document.getElementById('memoryStatusText');
    
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const repairBalancesBtn = document.getElementById('repairBalancesBtn');
    
    const geminiApiKeyInput = document.getElementById('geminiApiKey');
    const geminiModelInput = document.getElementById('geminiModel');
    const toggleApiKeyBtn = document.getElementById('toggleApiKey');
    const miracleBasePathInput = document.getElementById('miracleBasePath');
    const refreshClientsBtn = document.getElementById('refreshClientsBtn');
    const refreshClientsStatus = document.getElementById('refreshClientsStatus');
    const settingsActiveClient = document.getElementById('settingsActiveClient');
    const memoryPathInput = document.getElementById('memoryPath');
    const backupPathInput = document.getElementById('backupPath');

    // ── Instant Pre-Fill Settings from Chrome localStorage (0ms Load) ─────
    function prefillSettingsFromLocalStorage() {
        const savedApiKey = localStorage.getItem('geminiApiKey') || '';
        if (savedApiKey && geminiApiKeyInput) geminiApiKeyInput.value = savedApiKey;

        const savedMiraclePath = localStorage.getItem('miracleBasePath') || '/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank';
        if (miracleBasePathInput) miracleBasePathInput.value = savedMiraclePath;

        const savedMemoryPath = localStorage.getItem('memoryPath') || '/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/AI_Memory_Vault';
        if (memoryPathInput) memoryPathInput.value = savedMemoryPath;

        const savedBackupPath = localStorage.getItem('backupPath') || '';
        if (savedBackupPath) {
            if (backupPathInput) backupPathInput.value = savedBackupPath;
            if (inlineBackupPath) inlineBackupPath.value = savedBackupPath;
        }
    }
    prefillSettingsFromLocalStorage();

    // ── Inline Backup Path Box (visible next to Push button) ──────────────
    const inlineBackupPath  = document.getElementById('inlineBackupPath');
    const backupPathStatus  = document.getElementById('backupPathStatus');

    function syncInlineBackupBadge() {
        if (!inlineBackupPath || !backupPathStatus) return;
        const val = inlineBackupPath.value.trim();
        if (val) {
            backupPathStatus.textContent = 'ACTIVE';
            backupPathStatus.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 transition-all bg-amber-500/20 text-amber-400 border border-amber-500/40';
        } else {
            backupPathStatus.textContent = 'SKIP';
            backupPathStatus.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 transition-all bg-slate-800 text-slate-500';
        }
    }
    if (inlineBackupPath) {
        // Live badge update as user types
        inlineBackupPath.addEventListener('input', () => {
            syncInlineBackupBadge();
            if (backupPathInput) backupPathInput.value = inlineBackupPath.value.trim();
            localStorage.setItem('backupPath', inlineBackupPath.value.trim());
        });
        const saved = localStorage.getItem('backupPath') || '';
        inlineBackupPath.value = saved;
        syncInlineBackupBadge();
    }
    const autoDetectBtn = document.getElementById('autoDetectBtn');
    const detectedRulesDisplay = document.getElementById('detectedRulesDisplay');
    const trainBrainBtn = document.getElementById('trainBrainBtn');
    const businessProfileInput = document.getElementById('businessProfileInput');
    const defaultProductSelect = document.getElementById('defaultProductSelect');
    
    const aiInstructionInput = document.getElementById('aiInstructionInput');
    const uploadBtn = document.getElementById('uploadBtn');
    
    let isServerConnected = false;

    function updateMonitoringStatus(clientId) {
        if (!memoryStatusText) return;
        const activeClientObj = discoveredClients.find(c => (typeof c === 'object' ? c.id : c) === clientId);
        const nameText = activeClientObj ? (typeof activeClientObj === 'object' ? activeClientObj.name : activeClientObj) : clientId;
        const displayName = (nameText && nameText !== clientId && nameText !== 'Unknown Company') ? `${clientId} — ${nameText}` : (clientId || 'PE PULSE PRIVATE LIMITED');
        memoryStatusText.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-emerald-500 flex-shrink-0 pulse-indicator"></span>✨ Active: ${displayName}</span>`;

        const headerClientBadge = document.getElementById('headerClientBadge');
        if (headerClientBadge) {
            headerClientBadge.textContent = displayName;
        }

        const headerYearBadge = document.getElementById('headerYearBadge');
        if (headerYearBadge && activeYearFolder) {
            headerYearBadge.textContent = activeYearFolder;
        }
    }

    async function loadSettingsFromServer() {
        try {
            const res = await fetch(`${API_URL}/api/settings`);
            if (!res.ok) throw new Error("Failed to fetch settings from backend.");
            const data = await res.json();
            
            isServerConnected = true;
            const settings = data.settings;
            discoveredClients = data.clients || [];

            // Update inputs with dual-layer fallback & path normalization
            const savedApiKey = settings.gemini_api_key || localStorage.getItem('geminiApiKey') || '';
            geminiApiKeyInput.value = savedApiKey;
            if (savedApiKey) localStorage.setItem('geminiApiKey', savedApiKey);

            if (geminiModelInput && settings.gemini_model) {
                geminiModelInput.value = settings.gemini_model;
            }

            let savedMiraclePath = settings.miracle_base_path || localStorage.getItem('miracleBasePath') || '';
            if (!savedMiraclePath || savedMiraclePath.includes('/Users/') || savedMiraclePath.includes('/home/')) {
                savedMiraclePath = 'C:\\Miracle';
            }
            miracleBasePathInput.value = savedMiraclePath;
            localStorage.setItem('miracleBasePath', savedMiraclePath);

            let savedMemoryPath = settings.memory_path || localStorage.getItem('memoryPath') || '';
            if (!savedMemoryPath || savedMemoryPath.includes('/Users/') || savedMemoryPath.includes('/home/')) {
                savedMemoryPath = 'C:\\Miracle\\AI_Memory_Vault';
            }
            memoryPathInput.value = savedMemoryPath;
            localStorage.setItem('memoryPath', savedMemoryPath);

            let savedBackupPath = settings.backup_path || localStorage.getItem('backupPath') || '';
            if (backupPathInput) {
                backupPathInput.value = savedBackupPath;
            }
            if (savedBackupPath) localStorage.setItem('backupPath', savedBackupPath);

            if (isLocalBridgeOnline) {
                try {
                    const localRes = await fetch(`${LOCAL_BRIDGE_URL}/api/local-clients?base_path=${encodeURIComponent(savedMiraclePath)}`);
                    if (localRes.ok) {
                        const localData = await localRes.json();
                        if (localData && localData.clients && localData.clients.length > 0) {
                            discoveredClients = localData.clients.map(c => typeof c === 'string' ? { id: c, name: c } : c);
                        }
                    }
                } catch (e) {
                    console.warn("Failed to fetch clients from local bridge:", e);
                }
            }

            if (inlineBackupPath) {
                inlineBackupPath.value = savedBackupPath;
                syncInlineBackupBadge();
            }
            if (savedBackupPath) localStorage.setItem('backupPath', savedBackupPath);
            
            const salesSetupIdInput = document.getElementById('salesSetupId');
            const purchaseSetupIdInput = document.getElementById('purchaseSetupId');
            if (salesSetupIdInput) salesSetupIdInput.value = settings.sales_setup_id || 5;
            if (purchaseSetupIdInput) purchaseSetupIdInput.value = settings.purchase_setup_id || 6;

            const autoCreateB2bCheck = document.getElementById('autoCreateB2bCheck');
            autoCreateB2b = settings.auto_create_b2b !== false;
            if (autoCreateB2bCheck) autoCreateB2bCheck.checked = autoCreateB2b;

            const autoCreateB2cCheck = document.getElementById('autoCreateB2cCheck');
            autoCreateB2c = settings.auto_create_b2c !== false;
            if (autoCreateB2cCheck) autoCreateB2cCheck.checked = autoCreateB2c;

            const isPaidApiKeyCheck = document.getElementById('isPaidApiKeyCheck');
            isPaidApiKey = settings.is_paid_api_key === true;
            if (isPaidApiKeyCheck) isPaidApiKeyCheck.checked = isPaidApiKey;

            activeYearFolder = settings.active_year_folder || "";
            if (settings.active_client_id) {
                activeClientId = settings.active_client_id;
            }

            // Update client dropdowns
            populateClientDropdowns(discoveredClients, settings.active_client_id);
            
            if (activeClientId) {
                fetchAutoSetupIds(activeClientId);
                await fetchClientYears(activeClientId, activeYearFolder);
            }
            
            // Update UI status
            updateMonitoringStatus(activeClientId);
            
            // Display business profile if it exists
            if (data.business_profile) {
                businessProfileInput.value = data.business_profile;
            } else {
                businessProfileInput.value = '';
            }
            
            // Check for saved product selection
            if (defaultProductSelect) {
                const savedProduct = localStorage.getItem('defaultProductSelection') || '';
                defaultProductSelect.value = savedProduct;
            }
            
            // Ensure they are always visible so user can type manually
            businessProfileInput.classList.remove('hidden');
            saveProfileBtn.classList.remove('hidden');
            
            // Load ledgers for active client
            await fetchLedgers();
            await fetchProducts();
            selectModule(currentModule || 'Sales');
        } catch (err) {
            console.error("Error loading system settings:", err);
            if (!isServerConnected) {
                if (memoryStatusText) {
                    memoryStatusText.innerHTML = `<span class="text-amber-400 font-semibold flex items-center gap-1.5"><i class="fa-solid fa-spinner fa-spin text-amber-400"></i> Connecting to Backend Server...</span>`;
                }
                // Auto-retry connection ONLY if server was not connected yet
                setTimeout(loadSettingsFromServer, 5000);
            }
            // Fallback to local storage if backend is offline
            geminiApiKeyInput.value = localStorage.getItem('geminiApiKey') || '';
            miracleBasePathInput.value = localStorage.getItem('miracleBasePath') || '';
            memoryPathInput.value = localStorage.getItem('memoryPath') || '';
            if (backupPathInput) {
                backupPathInput.value = localStorage.getItem('backupPath') || '';
            }
        }
    }

    function populateClientDropdowns(clients, selectedClientId) {
        if (!clients || !Array.isArray(clients)) return;
        if (clientSelect) clientSelect.innerHTML = '';
        if (settingsActiveClient) settingsActiveClient.innerHTML = '';
        
        if (selectedClientId) {
            activeClientId = selectedClientId;
        } else if (!activeClientId && clients.length > 0) {
            const first = clients[0];
            activeClientId = typeof first === 'object' ? first.id : first;
        }
        
        clients.forEach(client => {
            const cId = typeof client === 'object' ? client.id : client;
            const cName = typeof client === 'object' ? client.name : client;
            const displayName = (cName && cName !== cId && cName !== 'Unknown Company') ? `${cId} — ${cName}` : cId;
            
            if (clientSelect) {
                const opt1 = document.createElement('option');
                opt1.value = cId;
                opt1.className = 'bg-slate-800';
                opt1.innerText = displayName;
                if (cId === activeClientId) opt1.selected = true;
                clientSelect.appendChild(opt1);
            }

            if (settingsActiveClient) {
                const opt2 = document.createElement('option');
                opt2.value = cId;
                opt2.innerText = displayName;
                if (cId === activeClientId) opt2.selected = true;
                settingsActiveClient.appendChild(opt2);
            }
        });
    }


    async function fetchLedgers() {
        try {
            const clientId = getActiveClientId();
            const targetUrl = isLocalBridgeOnline
                ? `${LOCAL_BRIDGE_URL}/api/local-ledgers?client_id=${clientId}&year_folder=${activeYearFolder || 'YR25'}`
                : `${API_URL}/api/ledgers${activeYearFolder ? '?year=' + activeYearFolder : ''}`;
            const res = await fetch(targetUrl);
            if (!res.ok) throw new Error("Failed to retrieve ledgers.");
            const data = await res.json();
            clientLedgers = data.data || data.ledgers || [];
            window.clientLedgers = clientLedgers; // Expose globally for Bank Statement module
            console.log(`Loaded ${clientLedgers.length} classified ledgers for financial year ${data.year || activeYearFolder}`);
            
            // Populate Target Cash Account dropdown
            const targetCashSelect = document.getElementById('targetCashAccount');
            if (targetCashSelect) {
                targetCashSelect.innerHTML = '';
                const cashLedgers = clientLedgers.filter(led => (led.group_name && led.group_name.toUpperCase().includes('CASH')) || (led.name && led.name.toUpperCase().includes('CASH')) || (led.print_name && led.print_name.toUpperCase().includes('CASH')));
                cashLedgers.forEach((led) => {
                    const opt = document.createElement('option');
                    opt.value = led.code;
                    opt.innerText = `${led.print_name} (${led.code})`;
                    targetCashSelect.appendChild(opt);
                });
                
                if (cashLedgers.length > 0) {
                    targetCashSelect.selectedIndex = 0;
                }
                if (currentModule === 'Cash Entries' && targetCashSelect.options.length > 0) {
                    targetCashSelect.classList.remove('hidden');
                }
            }

            // Populate Target Bank Account dropdown
            const targetBankSelect = document.getElementById('targetBankAccount');
            if (targetBankSelect) {
                targetBankSelect.innerHTML = '';
                const bankLedgers = clientLedgers.filter(led => (led.group_name && led.group_name.toUpperCase().includes('BANK')) || (led.name && led.name.toUpperCase().includes('BANK')) || (led.print_name && led.print_name.toUpperCase().includes('BANK')));
                bankLedgers.forEach((led) => {
                    const opt = document.createElement('option');
                    opt.value = led.code;
                    opt.innerText = `${led.print_name} (${led.code})`;
                    targetBankSelect.appendChild(opt);
                });
                
                if (bankLedgers.length > 0) {
                    targetBankSelect.selectedIndex = 0;
                    window.currentBankName = bankLedgers[0].print_name;
                }
                if (currentModule === 'Bank Statements' && targetBankSelect.options.length > 0) {
                    targetBankSelect.classList.remove('hidden');
                }
                targetBankSelect.addEventListener('change', (e) => {
                    const selOpt = targetBankSelect.options[targetBankSelect.selectedIndex];
                    window.currentBankName = selOpt ? selOpt.text : 'Bank Account';
                });
            }
        } catch (err) {
            console.error("Error fetching client ledgers:", err);
        }
    }

    async function fetchProducts() {
        try {
            const res = await fetch(`${API_URL}/api/products${activeYearFolder ? '?year=' + activeYearFolder : ''}`);
            if (!res.ok) throw new Error("Failed to retrieve products.");
            const data = await res.json();
            clientProducts = data.data || [];
            console.log(`Loaded ${clientProducts.length} products for financial year ${data.year}`);
            populateDefaultProductSelect();
        } catch (err) {
            console.error("Error fetching client products:", err);
        }
    }

    async function saveSettings(silent = false) {
        const salesSetupIdInput = document.getElementById('salesSetupId');
        const purchaseSetupIdInput = document.getElementById('purchaseSetupId');
        
        const autoCreateB2bCheck = document.getElementById('autoCreateB2bCheck');
        if (autoCreateB2bCheck) {
            autoCreateB2b = autoCreateB2bCheck.checked;
        }

        const autoCreateB2cCheck = document.getElementById('autoCreateB2cCheck');
        if (autoCreateB2cCheck) {
            autoCreateB2c = autoCreateB2cCheck.checked;
        }

        const isPaidApiKeyCheck = document.getElementById('isPaidApiKeyCheck');
        if (isPaidApiKeyCheck) {
            isPaidApiKey = isPaidApiKeyCheck.checked;
        }

        const payload = {
            gemini_api_key: geminiApiKeyInput.value,
            gemini_model: geminiModelInput.value,
            miracle_base_path: miracleBasePathInput.value,
            active_client_id: settingsActiveClient.value,
            memory_path: memoryPathInput.value,
            sales_setup_id: salesSetupIdInput ? parseInt(salesSetupIdInput.value || 5) : 5,
            purchase_setup_id: purchaseSetupIdInput ? parseInt(purchaseSetupIdInput.value || 6) : 6,
            auto_create_b2b: autoCreateB2b,
            auto_create_b2c: autoCreateB2c,
            is_paid_api_key: isPaidApiKey,
            active_year_folder: activeYearFolder,
            backup_path: backupPathInput ? backupPathInput.value : ""
        };

        if (!payload.active_client_id) {
            if (!silent) showToast("Please select a valid Client Account from the dropdown. If the dropdown is empty, make sure your Miracle Base Directory Path is correct.", "warning");
            return;
        }

        // Disable save button to prevent double-clicking
        if (!silent) {
            saveSettingsBtn.disabled = true;
            saveSettingsBtn.innerText = "Saving...";
        }

        try {
            const res = await fetch(`${API_URL}/api/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error("Failed to save settings on backend.");
            const data = await res.json();
            
            // Sync nav dropdown
            clientSelect.value = payload.active_client_id;
            updateMonitoringStatus(payload.active_client_id);
            
            // Save local copy just in case
            localStorage.setItem('geminiApiKey', payload.gemini_api_key);
            localStorage.setItem('miracleBasePath', payload.miracle_base_path);
            localStorage.setItem('memoryPath', payload.memory_path);
            localStorage.setItem('backupPath', payload.backup_path);
            
            // Re-fetch client settings, profile, mappings, ledgers and products for newly selected client
            await loadSettingsFromServer();
            
            if (!silent) {
                saveSettingsBtn.innerText = "Saved!";
                saveSettingsBtn.classList.add('bg-green-500');
                setTimeout(() => {
                    saveSettingsBtn.innerText = "Save Configuration";
                    saveSettingsBtn.classList.remove('bg-green-500');
                    saveSettingsBtn.disabled = false;
                    closeSettings();
                }, 1000);
            }
        } catch (err) {
            console.error("Error saving settings:", err);
            if (!silent) {
                showToast("Could not connect to backend server. Settings saved locally only.", "error");
                saveSettingsBtn.innerText = "Save Configuration";
                saveSettingsBtn.disabled = false;
            }
            localStorage.setItem('geminiApiKey', payload.gemini_api_key);
            localStorage.setItem('miracleBasePath', payload.miracle_base_path);
            localStorage.setItem('memoryPath', payload.memory_path);
            localStorage.setItem('backupPath', payload.backup_path);
        }
    }

    async function fetchAutoSetupIds(clientId) {
        if (!clientId) return;
        try {
            const salesSetupIdStatus = document.getElementById('salesSetupIdStatus');
            const purchaseSetupIdStatus = document.getElementById('purchaseSetupIdStatus');
            const salesSetupIdInput = document.getElementById('salesSetupId');
            const purchaseSetupIdInput = document.getElementById('purchaseSetupId');
            
            if (salesSetupIdStatus) salesSetupIdStatus.innerHTML = '<span class="text-yellow-500"><i class="fa-solid fa-spinner fa-spin mr-1"></i> AI Scanning history...</span>';
            if (purchaseSetupIdStatus) purchaseSetupIdStatus.innerHTML = '<span class="text-yellow-500"><i class="fa-solid fa-spinner fa-spin mr-1"></i> AI Scanning history...</span>';
            
            const res = await fetch(`${API_URL}/api/client-setup-ids?client_id=${clientId}`);
            if (!res.ok) throw new Error("Failed to fetch setup IDs");
            const data = await res.json();
            
            if (salesSetupIdInput) {
                salesSetupIdInput.value = data.sales_setup_id;
            }
            if (purchaseSetupIdInput) {
                purchaseSetupIdInput.value = data.purchase_setup_id;
            }
            
            if (salesSetupIdStatus) salesSetupIdStatus.innerHTML = `<span class="text-green-400 font-semibold"><i class="fa-solid fa-check mr-1"></i> AI Auto-Detected: ${data.sales_setup_id}</span>`;
            if (purchaseSetupIdStatus) purchaseSetupIdStatus.innerHTML = `<span class="text-green-400 font-semibold"><i class="fa-solid fa-check mr-1"></i> AI Auto-Detected: ${data.purchase_setup_id}</span>`;
        } catch (err) {
            console.error(err);
        }
    }

    async function fetchClientYears(clientId, selectedYear = "") {
        if (!clientId) return;
        try {
            const currentMiraclePath = miracleBasePathInput ? miracleBasePathInput.value.trim() : 'C:\\Miracle';
            const yearFetchUrl = isLocalBridgeOnline
                ? `${LOCAL_BRIDGE_URL}/api/local-years?base_path=${encodeURIComponent(currentMiraclePath)}&client_id=${encodeURIComponent(clientId)}`
                : `${API_URL}/api/client-years?client_id=${encodeURIComponent(clientId)}`;

            const res = await fetch(yearFetchUrl);
            if (!res.ok) throw new Error("Failed to fetch client years");
            const data = await res.json();
            const years = data.years || [];
            
            yearSelect.innerHTML = '';
            let targetYear = selectedYear || activeYearFolder;
            
            const existsInClient = years.some(y => y.folder === targetYear);
            if (!existsInClient) {
                const rec = years.find(y => y.recommended);
                if (rec) targetYear = rec.folder;
                else if (years.length > 0) targetYear = years[0].folder;
                else targetYear = "";
            }
            
            years.forEach(y => {
                const opt = document.createElement('option');
                opt.value = y.folder || 'YR26';
                opt.innerText = y.label || y.folder || '2026-27 (YR26)';
                opt.className = 'bg-slate-800';
                if (y.folder === targetYear) opt.selected = true;
                yearSelect.appendChild(opt);
            });
            
            if (yearSelect.options.length === 0) {
                const opt = document.createElement('option');
                opt.value = 'YR26';
                opt.innerText = '2026-27 (YR26)';
                opt.className = 'bg-slate-800';
                opt.selected = true;
                yearSelect.appendChild(opt);
            }
            
            if (yearSelect.options.length > 0 && yearSelect.selectedIndex === -1) {
                yearSelect.selectedIndex = 0;
            }
            activeYearFolder = yearSelect.value || 'YR26';
            updateHeaderBadges();
        } catch (err) {
            console.error("Error fetching client years:", err);
            if (yearSelect && yearSelect.options.length === 0) {
                yearSelect.innerHTML = '<option value="YR26" class="bg-slate-800" selected>2026-27 (YR26)</option>';
                activeYearFolder = 'YR26';
                updateHeaderBadges();
            }
        }
    }

    function updateHeaderBadges() {
        const clientBadge = document.getElementById('headerClientBadge');
        const yearBadge = document.getElementById('headerYearBadge');
        if (clientBadge && clientSelect && clientSelect.options && clientSelect.selectedIndex >= 0) {
            const txt = clientSelect.options[clientSelect.selectedIndex].text;
            clientBadge.innerText = txt || clientSelect.value;
        }
        if (yearBadge) {
            let periodText = yearSelect && yearSelect.value ? yearSelect.value : (activeYearFolder || '2026-27 (YR26)');
            
            if (currentExtractedData && Array.isArray(currentExtractedData) && currentExtractedData.length > 0) {
                const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                const fullMonthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
                const monthsSet = new Set();
                const datesList = [];

                currentExtractedData.forEach(r => {
                    const rawDate = r.date || r.Date || r.voucher_date || '';
                    if (rawDate) {
                        const d = new Date(rawDate);
                        if (!isNaN(d.getTime())) {
                            monthsSet.add(`${d.getFullYear()}-${d.getMonth()}`);
                            datesList.push(d);
                        }
                    }
                });

                if (monthsSet.size === 1) {
                    const [y, mIdx] = Array.from(monthsSet)[0].split('-').map(Number);
                    periodText = `📅 ${fullMonthNames[mIdx]} ${y} (${currentExtractedData.length} Txns)`;
                } else if (monthsSet.size > 1 && datesList.length > 0) {
                    datesList.sort((a, b) => a - b);
                    const first = datesList[0];
                    const last = datesList[datesList.length - 1];
                    if (first.getFullYear() === last.getFullYear()) {
                        periodText = `📅 ${monthNames[first.getMonth()]} – ${monthNames[last.getMonth()]} ${first.getFullYear()} (${currentExtractedData.length} Txns)`;
                    } else {
                        periodText = `📅 ${monthNames[first.getMonth()]} ${first.getFullYear()} – ${monthNames[last.getMonth()]} ${last.getFullYear()} (${currentExtractedData.length} Txns)`;
                    }
                }
            }
            yearBadge.innerText = periodText;
        }
    }

    // Nav bar client selector changed
    clientSelect.addEventListener('change', async () => {
        settingsActiveClient.value = clientSelect.value;
        updateMonitoringStatus(clientSelect.value);
        fetchAutoSetupIds(clientSelect.value);
        await fetchClientYears(clientSelect.value);
        updateHeaderBadges();
        saveSettings(true); // Save silently in background
        await fetchLedgers();
        await fetchProducts();
    });

    // Settings client selector changed
    settingsActiveClient.addEventListener('change', async () => {
        clientSelect.value = settingsActiveClient.value;
        updateMonitoringStatus(settingsActiveClient.value);
        fetchAutoSetupIds(settingsActiveClient.value);
        await fetchClientYears(settingsActiveClient.value);
        updateHeaderBadges();
    });

    // Nav bar year selector changed
    yearSelect.addEventListener('change', async () => {
        activeYearFolder = yearSelect.value;
        updateHeaderBadges();
        saveSettings(true); // Save silently in background
        await fetchLedgers();
        await fetchProducts();
    });

    function selectModule(modName) {
        currentModule = modName || 'Sales';
        moduleNavs.forEach(n => {
            if (n.dataset.module === currentModule) {
                n.classList.remove('text-slate-400', 'border-transparent');
                n.classList.add('bg-brand-600/10', 'text-brand-500', 'border-brand-500/30', 'border-l-4', 'border-l-brand-500', 'active', 'shadow-inner');
            } else {
                n.classList.remove('bg-brand-600/10', 'text-brand-500', 'border-brand-500/30', 'border-l-4', 'border-l-brand-500', 'active', 'shadow-inner');
                n.classList.add('text-slate-400', 'border-transparent');
            }
        });
        
        if (moduleTitle) moduleTitle.innerText = currentModule;
        updateHeaderBadges();
        
        const grandTotals = document.getElementById('grandTotalsContainer');
        const targetCashSelect = document.getElementById('targetCashAccount');
        const opBalContainer = document.getElementById('openingBalanceContainer');
        const globalProductBulkBar = document.getElementById('globalProductBulkBar');
        const bankBulkBar = document.getElementById('bankBulkBar');
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            if (opBalContainer) opBalContainer.classList.remove('hidden');
            if (globalProductBulkBar) globalProductBulkBar.classList.add('hidden');
            if (bankBulkBar) bankBulkBar.classList.remove('hidden');
        } else {
            if (opBalContainer) opBalContainer.classList.add('hidden');
            if (globalProductBulkBar) globalProductBulkBar.classList.remove('hidden');
            if (bankBulkBar) bankBulkBar.classList.add('hidden');
        }
        
        if (currentModule === 'Opening Balances') {
            if (grandTotals) grandTotals.classList.add('hidden');
        } else {
            if (grandTotals) grandTotals.classList.remove('hidden');
        }

        const autoFillBtn = document.getElementById('autoFillDebtorsBtn');

        const targetBankSelect = document.getElementById('targetBankAccount');

        if (currentModule === 'Cash Entries') {
            if (targetCashSelect && targetCashSelect.options.length > 0) targetCashSelect.classList.remove('hidden');
            else if (targetCashSelect) targetCashSelect.classList.add('hidden');
            if (targetBankSelect) targetBankSelect.classList.add('hidden');
            if (autoFillBtn) autoFillBtn.classList.remove('hidden');
        } else if (currentModule === 'Bank Statements') {
            if (targetBankSelect && targetBankSelect.options.length > 0) targetBankSelect.classList.remove('hidden');
            else if (targetBankSelect) targetBankSelect.classList.add('hidden');
            if (targetCashSelect) targetCashSelect.classList.add('hidden');
            if (autoFillBtn) autoFillBtn.classList.add('hidden');
        } else {
            if (targetCashSelect) targetCashSelect.classList.add('hidden');
            if (targetBankSelect) targetBankSelect.classList.add('hidden');
            if (autoFillBtn) autoFillBtn.classList.add('hidden');
        }

        // Update Dropzone Card Heading & Description based on Active Module
        const dropzoneTitle = document.querySelector('#uploadZoneCard h3');
        const dropzoneDesc = document.querySelector('#uploadZoneCard p');
        if (dropzoneTitle && dropzoneDesc) {
            if (currentModule === 'Bank Statements') {
                dropzoneTitle.textContent = "Bank Statement Processing";
                dropzoneDesc.textContent = "Upload single or multiple Bank Statements (PDF, Excel, CSV, or Image). Gemini AI extracts and maps all entries automatically.";
            } else if (currentModule === 'Cash Entries') {
                dropzoneTitle.textContent = "Cash Voucher & Daybook Processing";
                dropzoneDesc.textContent = "Upload Cash Vouchers, Cash Daybooks, or Petty Cash Receipts (PDF/Image/Excel).";
            } else if (currentModule === 'Opening Balances') {
                dropzoneTitle.textContent = "Opening Balances Import";
                dropzoneDesc.textContent = "Upload Trial Balance or Opening Balance Schedule (Excel / CSV).";
            } else {
                dropzoneTitle.textContent = "Document Processing";
                dropzoneDesc.textContent = "Upload single or multiple sales/purchase bills (PDF/Image/Excel).";
            }
        }

        const recalcBtn = document.getElementById('recalculateMathBtn');
        const autoResolveBtn = document.getElementById('autoResolveSuspenseBtn');
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            if (recalcBtn) recalcBtn.classList.remove('hidden');
            if (autoResolveBtn) autoResolveBtn.classList.remove('hidden');
        } else {
            if (recalcBtn) recalcBtn.classList.add('hidden');
            if (autoResolveBtn) autoResolveBtn.classList.add('hidden');
        }
        
        const docPanel = document.getElementById('docViewerPanel');
        const resizer = document.getElementById('panelResizer');
        if (docPanel && !window.isDocViewerExplicitlyOpened && (!currentExtractedData || currentExtractedData.length === 0)) {
            docPanel.style.display = 'none';
        }
        if (resizer && !window.isDocViewerExplicitlyOpened && (!currentExtractedData || currentExtractedData.length === 0)) {
            resizer.style.display = 'none';
        }

        renderFilterBadgesForModule();
        renderEmptyState();
        recalcGrandTotals();
    }

    // --- SIDEBAR NAVIGATION ---
    moduleNavs.forEach(nav => {
        nav.addEventListener('click', (e) => {
            e.preventDefault();
            selectModule(nav.dataset.module);
        });
    });

    // --- SETTINGS MODAL EVENTS ---
    function openSettings() {
        const modal = document.getElementById('settingsModal') || settingsModal;
        if (modal) {
            modal.classList.remove('hidden');
            modal.style.display = 'flex';
        }
        const status = document.getElementById('refreshClientsStatus') || refreshClientsStatus;
        if (status) {
            status.innerHTML = 'The main folder containing all client directories (CMPxxxx).';
            status.className = 'text-sm text-slate-500 mt-1';
        }

        // Dynamically fetch the latest client folders from disk or local bridge
        const clientFetchUrl = isLocalBridgeOnline ? `${LOCAL_BRIDGE_URL}/api/local-clients` : `${API_URL}/api/clients`;
        fetch(clientFetchUrl)
            .then(res => res.json())
            .then(data => {
                if (data && data.clients) {
                    discoveredClients = data.clients.map(c => typeof c === 'string' ? { id: c, name: c } : c);
                    const activeVal = settingsActiveClient ? settingsActiveClient.value : "";
                    populateClientDropdowns(discoveredClients, activeVal);
                }
            })
            .catch(err => console.error("Failed to refresh clients:", err));
    }
    function closeSettings() {
        const modal = document.getElementById('settingsModal') || settingsModal;
        if (modal) {
            modal.classList.add('hidden');
            modal.style.display = 'none';
        }
    }

    // Expose to window for bulletproof inline onclick execution
    window.openSettings = openSettings;
    window.closeSettings = closeSettings;
    window.saveSettings = function(silent) { saveSettings(silent); };
    
    if (settingsBtn) settingsBtn.addEventListener('click', (e) => { e.preventDefault(); openSettings(); });
    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', (e) => { e.preventDefault(); closeSettings(); });
    if (cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', (e) => { e.preventDefault(); closeSettings(); });
    if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', (e) => { e.preventDefault(); saveSettings(false); });
    
    if (repairBalancesBtn) {
        repairBalancesBtn.addEventListener('click', async () => {
            const clientVal = clientSelect ? clientSelect.value : "";
            if (!clientVal) {
                showToast("Please select a Client first.", "warning");
                return;
            }
            const activeYear = yearSelect ? yearSelect.value : "";
            const yearStr = activeYear ? `for year ${activeYear}` : "for all years";
            
            if (!confirm(`Are you sure you want to repair the closing balance flags for all pushed bank and cash entries ${yearStr}? This will update existing records in-place and trigger table reindexing.`)) {
                return;
            }
            
            repairBalancesBtn.disabled = true;
            const originalText = repairBalancesBtn.innerHTML;
            repairBalancesBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Repairing...';
            
            try {
                let url = `${API_URL}/api/repair-bank-flags`;
                if (activeYear) {
                    url += `?year=${encodeURIComponent(activeYear)}`;
                }
                const res = await fetch(url, { method: 'POST' });
                const data = await res.json();

                // Also trigger narration repair pass
                let narrUrl = `${API_URL}/api/repair-narrations`;
                if (activeYear) {
                    narrUrl += `?year_folder=${encodeURIComponent(activeYear)}`;
                }
                await fetch(narrUrl, { method: 'POST' });
                
                if (res.ok && data.status === 'success') {
                    showToast(`Repair Successful!\n\n${data.message}\nNarrations & DBF tables updated successfully!\n\nNote: Please restart or reload your Miracle software to see the updated balances & narrations.`, "success");
                } else {
                    showToast(`Repair Failed: ${data.detail || data.message || 'Unknown error'}`, "error");
                }
            } catch (err) {
                console.error("Repair error:", err);
                showToast(`Connection Error: ${err.message}`, "error");
            } finally {
                repairBalancesBtn.innerHTML = originalText;
                repairBalancesBtn.disabled = false;
            }
        });
    }

    
    if (geminiApiKeyInput) {
        geminiApiKeyInput.addEventListener('input', () => {
            localStorage.setItem('geminiApiKey', geminiApiKeyInput.value.trim());
        });
    }

    if (miracleBasePathInput) {
        miracleBasePathInput.addEventListener('input', () => {
            localStorage.setItem('miracleBasePath', miracleBasePathInput.value.trim());
            if (refreshClientsStatus) {
                refreshClientsStatus.innerHTML = 'The main folder containing all client directories (CMPxxxx).';
                refreshClientsStatus.className = 'text-sm text-slate-500 mt-1';
            }
        });
    }

    if (memoryPathInput) {
        memoryPathInput.addEventListener('input', () => {
            localStorage.setItem('memoryPath', memoryPathInput.value.trim());
        });
    }

    if (backupPathInput) {
        backupPathInput.addEventListener('input', () => {
            localStorage.setItem('backupPath', backupPathInput.value.trim());
            if (inlineBackupPath) {
                inlineBackupPath.value = backupPathInput.value.trim();
                syncInlineBackupBadge();
            }
        });
    }

    if (refreshClientsBtn) {
        refreshClientsBtn.addEventListener('click', async () => {
            const path = miracleBasePathInput.value.trim();
            if (!path) {
                if (refreshClientsStatus) {
                    refreshClientsStatus.innerHTML = `<span class="text-red-400 font-semibold"><i class="fa-solid fa-circle-exclamation"></i> Path cannot be empty</span>`;
                }
                return;
            }
            
            refreshClientsBtn.disabled = true;
            const originalText = refreshClientsBtn.innerHTML;
            refreshClientsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...';
            
            if (refreshClientsStatus) {
                refreshClientsStatus.innerHTML = `<span class="text-slate-400"><i class="fa-solid fa-spinner fa-spin"></i> Scanning path...</span>`;
            }
            
            try {
                let res;
                if (isLocalBridgeOnline) {
                    res = await fetch(`${LOCAL_BRIDGE_URL}/api/local-clients?base_path=${encodeURIComponent(path)}`);
                } else {
                    res = await fetch(`${API_URL}/api/discover-clients`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: path })
                    });
                }
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(errorData.detail || errorData.error || "Failed to scan directory. Make sure the path exists.");
                }
                
                const data = await res.json();
                const clients = (data.clients || []).map(c => typeof c === 'string' ? { id: c, name: c } : c);
                
                if (clients.length === 0) {
                    if (refreshClientsStatus) {
                        refreshClientsStatus.innerHTML = `<span class="text-amber-400 font-semibold"><i class="fa-solid fa-triangle-exclamation"></i> No client folders starting with "CMP" found</span>`;
                    }
                } else {
                    discoveredClients = clients;
                    const currentSelected = settingsActiveClient.value;
                    populateClientDropdowns(clients, currentSelected);
                    
                    if (refreshClientsStatus) {
                        refreshClientsStatus.innerHTML = `<span class="text-emerald-400 font-semibold"><i class="fa-solid fa-circle-check"></i> Found ${clients.length} client folders (CMPxxxx)</span>`;
                    }
                }
            } catch (err) {
                console.error("Error dynamically scanning client path:", err);
                if (refreshClientsStatus) {
                    refreshClientsStatus.innerHTML = `<span class="text-red-400 font-semibold"><i class="fa-solid fa-circle-xmark"></i> ${err.message}</span>`;
                }
            } finally {
                refreshClientsBtn.disabled = false;
                refreshClientsBtn.innerHTML = originalText;
            }
        });
    }
    
    toggleApiKeyBtn.addEventListener('click', () => {
        if (geminiApiKeyInput.type === 'password') {
            geminiApiKeyInput.type = 'text';
            toggleApiKeyBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
        } else {
            geminiApiKeyInput.type = 'password';
            toggleApiKeyBtn.innerHTML = '<i class="fa-solid fa-eye"></i>';
        }
    });
    
    autoDetectBtn.addEventListener('click', async () => {
        autoDetectBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Discovering...';
        autoDetectBtn.disabled = true;
        detectedRulesDisplay.classList.add('hidden');
        try {
            const res = await fetch(`${API_URL}/api/auto_discover`, { method: 'POST' });
            if (!res.ok) throw new Error("Failed to auto-discover");
            const data = await res.json();
            
            const sp = data.discovered.sales_prefix || 'SS,SS';
            const pp = data.discovered.purchase_prefix || 'PP,PP';
            
            // Safety check: warn if prefixes look wrong
            const purchasePattern = /^(PP|PB|PU|PI|PO|PA)/i;
            const salesPattern = /^(SS|SL|SR|SA|SB|SC|SD)/i;
            const salesLooksWrong = purchasePattern.test(sp.trim()) && !salesPattern.test(sp.trim());
            const purchaseLooksWrong = salesPattern.test(pp.trim()) && !purchasePattern.test(pp.trim());
            
            let warningHtml = '';
            if (salesLooksWrong) {
                warningHtml += `
                <div class="mt-2 p-2 bg-amber-900/40 border border-amber-500/50 rounded text-amber-300 text-sm">
                    <i class="fa-solid fa-triangle-exclamation"></i> 
                    <strong>Warning:</strong> Sales prefix "<code>${sp}</code>" looks like a Purchase prefix! 
                    The system will auto-correct this to <code>SS,SS</code> when you push Sales entries.
                    You may want to manually set it to the correct sales series (e.g., <code>SS,SS</code>).
                </div>`;
            }
            if (purchaseLooksWrong) {
                warningHtml += `
                <div class="mt-2 p-2 bg-amber-900/40 border border-amber-500/50 rounded text-amber-300 text-sm">
                    <i class="fa-solid fa-triangle-exclamation"></i> 
                    <strong>Warning:</strong> Purchase prefix "<code>${pp}</code>" looks like a Sales prefix! 
                    The system will auto-correct to <code>PP,PP</code> when you push Purchase entries.
                </div>`;
            }
            
            detectedRulesDisplay.classList.remove('hidden');
            detectedRulesDisplay.innerHTML = `
                <div class="text-emerald-400 font-semibold mb-1"><i class="fa-solid fa-check-circle"></i> Successfully Discovered Rules</div>
                <div class="grid grid-cols-2 gap-2 mt-2">
                    <div>
                        <span class="text-slate-400">Sales Prefix:</span> 
                        <span class="text-white font-mono bg-slate-900 px-2 py-0.5 rounded border ${salesLooksWrong ? 'border-amber-500 text-amber-300' : 'border-slate-700'}">${sp}</span>
                        ${salesLooksWrong ? '<span class="text-amber-400 text-sm ml-1">⚠️ will auto-fix to SS,SS</span>' : ''}
                    </div>
                    <div>
                        <span class="text-slate-400">Purchase Prefix:</span> 
                        <span class="text-white font-mono bg-slate-900 px-2 py-0.5 rounded border ${purchaseLooksWrong ? 'border-amber-500 text-amber-300' : 'border-slate-700'}">${pp}</span>
                        ${purchaseLooksWrong ? '<span class="text-amber-400 text-sm ml-1">⚠️ will auto-fix to PP,PP</span>' : ''}
                    </div>
                </div>
                ${warningHtml}
            `;
        } catch(err) {
            console.error(err);
            detectedRulesDisplay.classList.remove('hidden');
            detectedRulesDisplay.innerHTML = `<div class="text-red-400"><i class="fa-solid fa-circle-exclamation"></i> Error auto-detecting rules. Make sure DBF exists.</div>`;
        } finally {
            autoDetectBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Auto-Detect Rules';
            autoDetectBtn.disabled = false;
        }
    });

    // Manual Prefix Override Save
    const savePrefixBtn = document.getElementById('savePrefixBtn');
    const salesPrefixInput = document.getElementById('salesPrefixInput');
    const purchasePrefixInput = document.getElementById('purchasePrefixInput');
    const prefixSaveStatus = document.getElementById('prefixSaveStatus');
    
    if (savePrefixBtn) {
        savePrefixBtn.addEventListener('click', async () => {
            const sp = (salesPrefixInput.value || 'SS,SS').trim();
            const pp = (purchasePrefixInput.value || 'PP,PP').trim();
            
            if (!sp || !pp) {
                prefixSaveStatus.className = 'text-sm text-red-400';
                prefixSaveStatus.textContent = '⚠️ Please enter both prefixes.';
                prefixSaveStatus.classList.remove('hidden');
                return;
            }
            
            savePrefixBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
            savePrefixBtn.disabled = true;
            prefixSaveStatus.classList.add('hidden');
            
            try {
                const res = await fetch(`${API_URL}/api/set-prefix`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sales_prefix: sp, purchase_prefix: pp })
                });
                if (!res.ok) throw new Error('Failed to save prefix');
                const data = await res.json();
                
                prefixSaveStatus.className = 'text-sm text-emerald-400';
                prefixSaveStatus.textContent = `✅ Saved! Sales: ${sp}, Purchase: ${pp} for ${data.client_id}`;
                prefixSaveStatus.classList.remove('hidden');
                
                // Clear inputs
                salesPrefixInput.value = '';
                purchasePrefixInput.value = '';
            } catch(err) {
                prefixSaveStatus.className = 'text-sm text-red-400';
                prefixSaveStatus.textContent = `❌ Error: ${err.message}`;
                prefixSaveStatus.classList.remove('hidden');
            } finally {
                savePrefixBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Prefix';
                savePrefixBtn.disabled = false;
            }
        });
    }


    const trainMappingsBtn = document.getElementById('trainMappingsBtn');
    
    // Batch Date Setter logic
    const btnApplyBatchDate = document.getElementById('btnApplyBatchDate');
    const batchDateInput = document.getElementById('batchDateInput');
    if (btnApplyBatchDate && batchDateInput) {
        btnApplyBatchDate.addEventListener('click', () => {
            const newDate = batchDateInput.value;
            if (!newDate) {
                alert("Please select a date first.");
                return;
            }
            if (currentExtractedData) {
                currentExtractedData.forEach(row => {
                    row.date = newDate;
                    row.Date = newDate;
                });
                renderGrid(currentExtractedData);
                alert(`Successfully applied date ${newDate} to all ${currentExtractedData.length} entries!`);
            } else {
                alert("No entries to apply date to.");
            }
        });
    }

    let currentMemoryVaultData = null;
    let currentMemoryTab = "expense_mappings";

    async function triggerMemoryAutoTrain(btnElement) {
        if (!btnElement) return;
        const origText = btnElement.innerHTML;
        btnElement.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Training...';
        btnElement.disabled = true;
        try {
            const res = await fetch(`${API_URL}/api/train-memory`, { method: 'POST' });
            if (!res.ok) throw new Error("Failed to train mappings");
            const data = await res.json();
            const toastMsg = data.message || data.msg || (data.trained_count !== undefined ? `Trained ${data.trained_count} clean expense mappings!` : "AI Memory Vault trained successfully!");
            showToast(`🧠 ${toastMsg}`, "success");
            if (currentMemoryVaultData) {
                await fetchAndRenderMemoryVault();
            }
        } catch (err) {
            console.error(err);
            showToast(`Error training memory: ${err.message}`, "error");
        } finally {
            btnElement.innerHTML = origText;
            btnElement.disabled = false;
        }
    }

    async function fetchAndRenderMemoryVault() {
        try {
            const res = await fetch(`${API_URL}/api/memory-vault`);
            if (!res.ok) throw new Error("Failed to load memory vault");
            const payload = await res.json();
            currentMemoryVaultData = payload.memory || {};
            
            const clientBadge = document.getElementById('mvClientIdBadge');
            if (clientBadge) clientBadge.textContent = payload.client_id || clientSelect.value;
            
            const expCount = Object.keys(currentMemoryVaultData.expense_mappings || {}).length;
            const prodCount = Object.keys(currentMemoryVaultData.product_catalog || {}).length;
            const supCount = Object.keys(currentMemoryVaultData.supplier_catalog || {}).length;
            
            document.getElementById('mvExpenseCount').textContent = expCount;
            document.getElementById('mvProductCount').textContent = prodCount;
            document.getElementById('mvSupplierCount').textContent = supCount;
            
            renderMemoryVaultTable(currentMemoryTab);
        } catch (err) {
            console.error("Error loading Memory Vault:", err);
            showToast(`Memory Vault Error: ${err.message}`, "error");
        }
    }

    let selectedMemoryItems = new Set();

    function renderMemoryVaultTable(category) {
        currentMemoryTab = category || 'expense_mappings';
        const tbody = document.getElementById('mvTableBody');
        const searchInput = document.getElementById('mvSearchInput');
        const searchVal = (searchInput ? searchInput.value : "").trim().toLowerCase();
        
        const aiSection = document.getElementById('mvAiAssistantSection');
        const simSection = document.getElementById('mvSimulatorSection');
        
        if (aiSection) {
            if (category === 'ai_assistant') aiSection.classList.remove('hidden');
            else aiSection.classList.add('hidden');
        }
        if (simSection) {
            if (category === 'simulator') simSection.classList.remove('hidden');
            else simSection.classList.add('hidden');
        }
        
        if (!tbody || !currentMemoryVaultData) return;
        
        // Reset selections
        selectedMemoryItems.clear();
        updateBulkDeleteButton();
        const selectAllCheck = document.getElementById('mvSelectAllCheck');
        if (selectAllCheck) selectAllCheck.checked = false;
        
        // Update active tab buttons
        document.querySelectorAll('.mv-tab-btn').forEach(btn => {
            if (btn.dataset.tab === category) {
                btn.className = "mv-tab-btn active text-xs font-bold px-3 py-1.5 rounded-lg border transition bg-purple-600/20 text-purple-300 border-purple-500/40 whitespace-nowrap shadow-sm";
            } else {
                btn.className = "mv-tab-btn text-xs font-bold px-3 py-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-white transition whitespace-nowrap";
            }
        });

        let rowsHtml = '';
        
        if (category === 'expense_mappings' || category === 'ai_assistant') {
            const mappings = currentMemoryVaultData.expense_mappings || {};
            const keys = Object.keys(mappings).sort();
            const filteredKeys = keys.filter(k => k.toLowerCase().includes(searchVal) || String(mappings[k]).toLowerCase().includes(searchVal));
            
            if (filteredKeys.length === 0) {
                rowsHtml = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500 italic">No expense mappings found. Type a prompt in the AI Assistant above or click "Auto-Train Memory" to learn from DBF history!</td></tr>`;
            } else {
                filteredKeys.forEach(k => {
                    const targetLedger = mappings[k];
                    const sourceTag = k.includes(' ') ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">🤖 AI Rule</span>' : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-300 border border-purple-500/20">📦 DBF Learned</span>';
                    
                    rowsHtml += `
                        <tr class="hover:bg-slate-900/60 transition group" data-cat="expense_mapping" data-key="${k}">
                            <td class="px-3 py-2.5 text-center">
                                <input type="checkbox" class="mv-row-check rounded bg-slate-800 border-slate-700 text-purple-600 focus:ring-0 cursor-pointer" data-cat="expense_mapping" data-key="${k}">
                            </td>
                            <td class="px-4 py-2.5 font-mono text-purple-300 font-semibold">${k}</td>
                            <td class="px-4 py-2.5 font-bold text-white">${targetLedger}</td>
                            <td class="px-3 py-2.5 text-center">${sourceTag}</td>
                            <td class="px-4 py-2.5 text-right">
                                <button class="mv-delete-btn text-slate-500 hover:text-red-400 p-1.5 rounded transition cursor-pointer" data-cat="expense_mapping" data-key="${k}" title="Delete Rule">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
        } else if (category === 'product_catalog') {
            const catalog = currentMemoryVaultData.product_catalog || {};
            const keys = Object.keys(catalog).sort();
            const filteredKeys = keys.filter(k => k.includes(searchVal) || String(catalog[k].display_name || '').toLowerCase().includes(searchVal));
            
            if (filteredKeys.length === 0) {
                rowsHtml = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500 italic">No learned product catalog entries yet. Products are learned automatically when pushing Sales/Purchases!</td></tr>`;
            } else {
                filteredKeys.forEach(k => {
                    const entry = catalog[k];
                    const dName = entry.display_name || k;
                    const hsn = entry.hsn || '-';
                    const gst = entry.gst_pct !== undefined ? `${entry.gst_pct}%` : '-';
                    const uom = entry.uom || 'PCS';
                    const rate = entry.last_rate ? `₹${entry.last_rate}` : '-';
                    const count = entry.seen_count || 1;
                    
                    rowsHtml += `
                        <tr class="hover:bg-slate-900/60 transition group" data-cat="product_catalog" data-key="${k}">
                            <td class="px-3 py-2.5 text-center">
                                <input type="checkbox" class="mv-row-check rounded bg-slate-800 border-slate-700 text-purple-600 focus:ring-0 cursor-pointer" data-cat="product_catalog" data-key="${k}">
                            </td>
                            <td class="px-4 py-2.5 font-bold text-slate-200">${dName} <span class="text-[10px] text-slate-500 font-mono">(${count}x)</span></td>
                            <td class="px-4 py-2.5 font-mono text-slate-300">HSN: <span class="text-purple-300 font-bold">${hsn}</span> | GST: <span class="text-emerald-400 font-bold">${gst}</span> | UOM: ${uom} | Rate: ${rate}</td>
                            <td class="px-3 py-2.5 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">📦 Catalog</span></td>
                            <td class="px-4 py-2.5 text-right">
                                <button class="mv-delete-btn text-slate-500 hover:text-red-400 p-1.5 rounded transition cursor-pointer" data-cat="product_catalog" data-key="${k}" title="Delete Item">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
        } else if (category === 'supplier_catalog') {
            const catalog = currentMemoryVaultData.supplier_catalog || {};
            const keys = Object.keys(catalog).sort();
            const filteredKeys = keys.filter(k => k.includes(searchVal) || String(catalog[k].display_name || '').toLowerCase().includes(searchVal));
            
            if (filteredKeys.length === 0) {
                rowsHtml = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500 italic">No supplier entries learned yet. Vendors are learned automatically from Purchase invoices!</td></tr>`;
            } else {
                filteredKeys.forEach(k => {
                    const entry = catalog[k];
                    const dName = entry.display_name || k;
                    const gstin = entry.gstin || '-';
                    const city = entry.city || '-';
                    const stateCode = entry.state_code ? `State: ${entry.state_code}` : '';
                    
                    rowsHtml += `
                        <tr class="hover:bg-slate-900/60 transition group" data-cat="supplier_catalog" data-key="${k}">
                            <td class="px-3 py-2.5 text-center">
                                <input type="checkbox" class="mv-row-check rounded bg-slate-800 border-slate-700 text-purple-600 focus:ring-0 cursor-pointer" data-cat="supplier_catalog" data-key="${k}">
                            </td>
                            <td class="px-4 py-2.5 font-bold text-slate-200">${dName}</td>
                            <td class="px-4 py-2.5 font-mono text-slate-300">GSTIN: <span class="text-purple-300 font-bold">${gstin}</span> | City: ${city} ${stateCode}</td>
                            <td class="px-3 py-2.5 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">🚚 Vendor</span></td>
                            <td class="px-4 py-2.5 text-right">
                                <button class="mv-delete-btn text-slate-500 hover:text-red-400 p-1.5 rounded transition cursor-pointer" data-cat="supplier_catalog" data-key="${k}" title="Delete Supplier">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        tbody.innerHTML = rowsHtml;

        // Bind Checkboxes
        tbody.querySelectorAll('.mv-row-check').forEach(chk => {
            chk.addEventListener('change', () => {
                const itemKey = `${chk.dataset.cat}:::${chk.dataset.key}`;
                if (chk.checked) selectedMemoryItems.add(itemKey);
                else selectedMemoryItems.delete(itemKey);
                updateBulkDeleteButton();
            });
        });

        // Bind delete buttons
        tbody.querySelectorAll('.mv-delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const cat = btn.dataset.cat;
                const key = btn.dataset.key;
                if (!confirm(`Are you sure you want to delete '${key}' from AI Memory?`)) return;
                
                try {
                    const res = await fetch(`${API_URL}/api/memory-vault/item?category=${encodeURIComponent(cat)}&key=${encodeURIComponent(key)}`, { method: 'DELETE' });
                    if (res.ok) {
                        showToast(`Deleted '${key}' from AI Memory Vault.`, "success");
                        await fetchAndRenderMemoryVault();
                    }
                } catch (err) {
                    showToast(`Error deleting key: ${err.message}`, "error");
                }
            });
        });
    }

    function updateBulkDeleteButton() {
        const bulkBtn = document.getElementById('mvBulkDeleteBtn');
        const countSpan = document.getElementById('mvSelectedCount');
        if (!bulkBtn || !countSpan) return;
        
        const count = selectedMemoryItems.size;
        countSpan.textContent = count;
        if (count > 0) bulkBtn.classList.remove('hidden');
        else bulkBtn.classList.add('hidden');
    }

    // Bind AI Memory Vault UI Event Listeners
    const memoryVaultModal = document.getElementById('memoryVaultModal');
    const openMemoryVaultModalBtn = document.getElementById('openMemoryVaultModalBtn');
    const closeMemoryVaultBtn = document.getElementById('closeMemoryVaultBtn');
    const closeMemoryVaultFooterBtn = document.getElementById('closeMemoryVaultFooterBtn');
    const modalAutoTrainMemoryBtn = document.getElementById('modalAutoTrainMemoryBtn');
    const mvSearchInput = document.getElementById('mvSearchInput');
    const mvSaveNewBtn = document.getElementById('mvSaveNewBtn');

    // New AI Assistant & Simulator Controls
    const mvGenerateAiRuleBtn = document.getElementById('mvGenerateAiRuleBtn');
    const mvAiPromptInput = document.getElementById('mvAiPromptInput');
    const mvAiRuleResultCard = document.getElementById('mvAiRuleResultCard');
    const mvAiResultBody = document.getElementById('mvAiResultBody');
    const mvAiResultSummary = document.getElementById('mvAiResultSummary');
    
    const mvSimulateBtn = document.getElementById('mvSimulateBtn');
    const mvSimulateInput = document.getElementById('mvSimulateInput');
    const mvSimulateResult = document.getElementById('mvSimulateResult');
    
    const mvSelectAllCheck = document.getElementById('mvSelectAllCheck');
    const mvBulkDeleteBtn = document.getElementById('mvBulkDeleteBtn');
    const mvExportBtn = document.getElementById('mvExportBtn');
    const mvImportTriggerBtn = document.getElementById('mvImportTriggerBtn');
    const mvImportFileInput = document.getElementById('mvImportFileInput');

    const vaultTriggers = document.querySelectorAll('.open-memory-vault-trigger, #openMemoryVaultModalBtn, #modalOpenMemoryVaultBtn');
    vaultTriggers.forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            const settingsModal = document.getElementById('settingsModal');
            if (settingsModal) {
                settingsModal.classList.add('hidden');
                settingsModal.style.display = 'none';
            }
            if (memoryVaultModal) {
                memoryVaultModal.classList.remove('hidden');
                memoryVaultModal.style.display = 'flex';
                fetchAndRenderMemoryVault();
            }
        });
    });

    if (closeMemoryVaultBtn) closeMemoryVaultBtn.addEventListener('click', (e) => {
        if (e) e.preventDefault();
        if (memoryVaultModal) {
            memoryVaultModal.classList.add('hidden');
            memoryVaultModal.style.display = 'none';
        }
    });
    if (closeMemoryVaultFooterBtn) closeMemoryVaultFooterBtn.addEventListener('click', (e) => {
        if (e) e.preventDefault();
        if (memoryVaultModal) {
            memoryVaultModal.classList.add('hidden');
            memoryVaultModal.style.display = 'none';
        }
    });
    if (modalAutoTrainMemoryBtn) modalAutoTrainMemoryBtn.addEventListener('click', () => triggerMemoryAutoTrain(modalAutoTrainMemoryBtn));
    if (trainMappingsBtn) trainMappingsBtn.addEventListener('click', () => triggerMemoryAutoTrain(trainMappingsBtn));

    if (mvSearchInput) {
        mvSearchInput.addEventListener('input', () => renderMemoryVaultTable(currentMemoryTab));
    }

    document.querySelectorAll('.mv-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => renderMemoryVaultTable(btn.dataset.tab));
    });

    // Preset Prompt Chips Click Handler
    document.querySelectorAll('.mv-preset-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (mvAiPromptInput) {
                mvAiPromptInput.value = chip.dataset.prompt;
                mvAiPromptInput.focus();
            }
        });
    });

    // 🤖 GEMINI AI PROMPT RULE GENERATOR EVENT LISTENER
    if (mvGenerateAiRuleBtn) {
        mvGenerateAiRuleBtn.addEventListener('click', async () => {
            const promptText = mvAiPromptInput ? mvAiPromptInput.value.trim() : "";
            if (!promptText) {
                showToast("Please enter a rule prompt for Gemini AI.", "warning");
                return;
            }

            const origHtml = mvGenerateAiRuleBtn.innerHTML;
            mvGenerateAiRuleBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Gemini Building...';
            mvGenerateAiRuleBtn.disabled = true;

            try {
                const res = await fetch(`${API_URL}/api/generate-memory-rule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: promptText, auto_save: true })
                });

                const data = await res.json();
                if (!res.ok || data.status !== 'success') {
                    throw new Error(data.detail || data.summary || "Failed to generate AI rule");
                }

                showToast(`✨ ${data.message}`, "success");
                
                // Render Generated Rule Details & Concrete Examples Card
                if (mvAiRuleResultCard && mvAiResultBody) {
                    mvAiRuleResultCard.classList.remove('hidden');
                    if (mvAiResultSummary) {
                        mvAiResultSummary.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.summary || 'Rule Generated & Saved to Vault!'}`;
                    }

                    let cardHtml = '';
                    (data.rules || []).forEach(r => {
                        const examplesHtml = (r.examples || []).map(ex => `
                            <div class="bg-slate-900 border border-slate-800 rounded-lg p-2 flex items-center justify-between text-[11px] font-mono">
                                <span class="text-slate-400">Input: "<span class="text-amber-300 font-bold">${ex.input}</span>"</span>
                                <i class="fa-solid fa-arrow-right text-purple-400"></i>
                                <span class="text-emerald-400 font-bold">Output: "${ex.output}"</span>
                            </div>
                        `).join('');

                        cardHtml += `
                            <div class="bg-slate-900/80 border border-purple-500/30 rounded-xl p-3 space-y-2">
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center gap-2">
                                        <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30">${r.category}</span>
                                        <span class="font-mono text-purple-300 font-bold text-sm">${r.key}</span>
                                        <i class="fa-solid fa-arrow-right text-slate-500 text-xs"></i>
                                        <span class="font-bold text-emerald-400 text-xs">${r.value}</span>
                                    </div>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">${r.rule_type || 'AI Match'}</span>
                                </div>
                                <p class="text-[11px] text-slate-300 italic"><i class="fa-solid fa-circle-info text-purple-400 mr-1"></i>${r.explanation || 'Rule created by Gemini AI Prompt Assistant'}</p>
                                <div class="space-y-1 pt-1">
                                    <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Concrete Execution Examples:</span>
                                    ${examplesHtml}
                                </div>
                            </div>
                        `;
                    });

                    mvAiResultBody.innerHTML = cardHtml;
                }

                // Refresh rule table
                await fetchAndRenderMemoryVault();
            } catch (err) {
                console.error("AI Rule Error:", err);
                showToast(`AI Rule Error: ${err.message}`, "error");
            } finally {
                mvGenerateAiRuleBtn.innerHTML = origHtml;
                mvGenerateAiRuleBtn.disabled = false;
            }
        });
    }

    // 🧪 LIVE RULE SIMULATOR EVENT LISTENER
    if (mvSimulateBtn) {
        mvSimulateBtn.addEventListener('click', async () => {
            const testText = mvSimulateInput ? mvSimulateInput.value.trim() : "";
            if (!testText) {
                showToast("Please enter test text to simulate.", "warning");
                return;
            }

            mvSimulateBtn.disabled = true;
            mvSimulateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Testing...';

            try {
                const res = await fetch(`${API_URL}/api/simulate-memory-rule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ test_text: testText })
                });

                const data = await res.json();
                if (mvSimulateResult) {
                    mvSimulateResult.classList.remove('hidden');
                    if (data.matched) {
                        mvSimulateResult.innerHTML = `
                            <div class="flex items-center justify-between text-emerald-400 font-bold">
                                <span><i class="fa-solid fa-circle-check"></i> MATCHED RULE: '${data.matched_key}'</span>
                                <span class="bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px]">Confidence: ${data.confidence}%</span>
                            </div>
                            <div class="text-slate-200 mt-1 font-mono">Mapped Target: <span class="text-purple-300 font-bold">${data.matched_value}</span> (${data.category})</div>
                            <div class="text-slate-400 italic text-[11px] mt-0.5">${data.explanation}</div>
                        `;
                    } else {
                        mvSimulateResult.innerHTML = `
                            <div class="text-amber-400 font-bold"><i class="fa-solid fa-triangle-exclamation"></i> NO MATCH FOUND</div>
                            <div class="text-slate-400 mt-0.5">${data.message || 'No memory vault rule matched this test string.'}</div>
                        `;
                    }
                }
            } catch (err) {
                showToast(`Simulation Error: ${err.message}`, "error");
            } finally {
                mvSimulateBtn.disabled = false;
                mvSimulateBtn.innerHTML = '<i class="fa-solid fa-play text-xs"></i> Run Test Match';
            }
        });
    }

    // Select All Checkbox
    if (mvSelectAllCheck) {
        mvSelectAllCheck.addEventListener('change', () => {
            const isChecked = mvSelectAllCheck.checked;
            document.querySelectorAll('.mv-row-check').forEach(chk => {
                chk.checked = isChecked;
                const itemKey = `${chk.dataset.cat}:::${chk.dataset.key}`;
                if (isChecked) selectedMemoryItems.add(itemKey);
                else selectedMemoryItems.delete(itemKey);
            });
            updateBulkDeleteButton();
        });
    }

    // Bulk Delete Action
    if (mvBulkDeleteBtn) {
        mvBulkDeleteBtn.addEventListener('click', async () => {
            if (selectedMemoryItems.size === 0) return;
            if (!confirm(`Are you sure you want to delete ${selectedMemoryItems.size} selected memory rule(s)?`)) return;

            const itemsArray = Array.from(selectedMemoryItems).map(str => {
                const parts = str.split(':::');
                return { category: parts[0], key: parts[1] };
            });

            mvBulkDeleteBtn.disabled = true;
            try {
                const res = await fetch(`${API_URL}/api/memory-vault/bulk-delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items: itemsArray })
                });

                if (res.ok) {
                    const data = await res.json();
                    showToast(`Deleted ${data.deleted_count} rules.`, "success");
                    await fetchAndRenderMemoryVault();
                }
            } catch (err) {
                showToast(`Bulk delete error: ${err.message}`, "error");
            } finally {
                mvBulkDeleteBtn.disabled = false;
            }
        });
    }

    // Clean & Deduplicate Rules
    const mvCleanVaultBtn = document.getElementById('mvCleanVaultBtn');
    if (mvCleanVaultBtn) {
        mvCleanVaultBtn.addEventListener('click', async () => {
            const orig = mvCleanVaultBtn.innerHTML;
            mvCleanVaultBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Cleaning...';
            mvCleanVaultBtn.disabled = true;
            try {
                const res = await fetch(`${API_URL}/api/clean-memory-vault`, { method: 'POST' });
                if (!res.ok) throw new Error("Failed to clean vault");
                const data = await res.json();
                showToast(`✨ ${data.message}`, "success");
                await fetchAndRenderMemoryVault();
            } catch (err) {
                showToast(`Clean error: ${err.message}`, "error");
            } finally {
                mvCleanVaultBtn.innerHTML = orig;
                mvCleanVaultBtn.disabled = false;
            }
        });
    }

    // Export Rules Excel/CSV
    const mvExportExcelBtn = document.getElementById('mvExportExcelBtn');
    if (mvExportExcelBtn) {
        mvExportExcelBtn.addEventListener('click', () => {
            window.location.href = `${API_URL}/api/memory-vault/export-excel`;
        });
    }

    // Export Rules JSON
    if (mvExportBtn) {
        mvExportBtn.addEventListener('click', () => {
            window.location.href = `${API_URL}/api/memory-vault/export`;
        });
    }

    // Import Rules (Excel .xlsx/.xls/.csv or JSON) with Gemini AI Auto-Mapping
    if (mvImportTriggerBtn && mvImportFileInput) {
        mvImportTriggerBtn.addEventListener('click', () => mvImportFileInput.click());
        mvImportFileInput.addEventListener('change', async () => {
            const file = mvImportFileInput.files[0];
            if (!file) return;

            const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls') || file.name.endsWith('.csv');

            if (isExcel) {
                showToast("✨ AI is analyzing Excel file & auto-mapping rules...", "info");
                const formData = new FormData();
                formData.append('file', file);
                try {
                    const res = await fetch(`${API_URL}/api/memory-vault/import-excel`, {
                        method: 'POST',
                        body: formData
                    });
                    if (!res.ok) throw new Error("Failed to process Excel file.");
                    const data = await res.json();
                    showToast(data.message, "success");
                    await fetchAndRenderMemoryVault();
                } catch (err) {
                    showToast(`Excel Import Error: ${err.message}`, "error");
                }
            } else {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    try {
                        const jsonData = JSON.parse(e.target.result);
                        const res = await fetch(`${API_URL}/api/memory-vault/import`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ memory: jsonData })
                        });
                        if (res.ok) {
                            showToast("Successfully imported memory vault rules!", "success");
                            await fetchAndRenderMemoryVault();
                        }
                    } catch (err) {
                        showToast(`Import error: ${err.message}`, "error");
                    }
                };
                reader.readAsText(file);
            }
            mvImportFileInput.value = '';
        });
    }

    if (mvSaveNewBtn) {
        mvSaveNewBtn.addEventListener('click', async () => {
            const keyInput = document.getElementById('mvNewKeyInput');
            const valInput = document.getElementById('mvNewValInput');
            const kVal = keyInput ? keyInput.value.trim() : "";
            const vVal = valInput ? valInput.value.trim() : "";

            if (!kVal || !vVal) {
                showToast("Please enter both a key and a target value.", "warning");
                return;
            }

            mvSaveNewBtn.disabled = true;
            try {
                const res = await fetch(`${API_URL}/api/memory-vault`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category: currentMemoryTab === 'ai_assistant' || currentMemoryTab === 'simulator' ? 'expense_mappings' : currentMemoryTab, key: kVal, value: vVal })
                });
                if (res.ok) {
                    showToast(`Saved '${kVal}' -> '${vVal}' in AI Memory Vault.`, "success");
                    if (keyInput) keyInput.value = "";
                    if (valInput) valInput.value = "";
                    await fetchAndRenderMemoryVault();
                }
            } catch (err) {
                showToast(`Error saving rule: ${err.message}`, "error");
            } finally {
                mvSaveNewBtn.disabled = false;
            }
        });
    }

    trainBrainBtn.addEventListener('click', async () => {
        trainBrainBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
        trainBrainBtn.disabled = true;
        
        try {
            const res = await fetch(`${API_URL}/api/train_brain`, { method: 'POST' });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to train brain");
            }
            const data = await res.json();
            
            businessProfileInput.classList.remove('hidden');
            saveProfileBtn.classList.remove('hidden');
            businessProfileInput.value = data.profile;
        } catch(err) {
            console.error(err);
            alert(`Error training brain: ${err.message}`);
        } finally {
            trainBrainBtn.innerHTML = '<i class="fa-solid fa-brain"></i> Train Full Company Brain';
            trainBrainBtn.disabled = false;
        }
    });

    saveProfileBtn.addEventListener('click', async () => {
        const originalHtml = saveProfileBtn.innerHTML;
        saveProfileBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        saveProfileBtn.disabled = true;
        
        try {
            const payload = { profile: businessProfileInput.value };
            const res = await fetch(`${API_URL}/api/save_profile`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error("Failed to save profile");
            
            saveProfileBtn.innerHTML = '<i class="fa-solid fa-check"></i> Saved!';
            setTimeout(() => {
                saveProfileBtn.innerHTML = originalHtml;
                saveProfileBtn.disabled = false;
            }, 2000);
        } catch (err) {
            console.error(err);
            saveProfileBtn.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Error';
            setTimeout(() => {
                saveProfileBtn.innerHTML = originalHtml;
                saveProfileBtn.disabled = false;
            }, 2000);
        }
    });

    function populateDefaultProductSelect() {
        if (!defaultProductSelect) return;
        const savedProduct = localStorage.getItem('defaultProductSelection') || '';
        
        let html = '<option value="">-- Auto-Detect (AI) --</option>';
        if (clientProducts && clientProducts.length > 0) {
            clientProducts.forEach(prod => {
                const isSelected = prod.name === savedProduct ? 'selected' : '';
                html += `<option value="${prod.name}" ${isSelected}>${prod.name} (${prod.code}) ${prod.hsn_code ? '- HSN: ' + prod.hsn_code : ''}</option>`;
            });
        }
        defaultProductSelect.innerHTML = html;

        // Also populate globalProductBulkSelect in grid header
        const globalProductBulkSelect = document.getElementById('globalProductBulkSelect');
        if (globalProductBulkSelect) {
            let bulkHtml = '<option value="">⚡ Bulk Set Product for All Rows...</option>';
            bulkHtml += generateProductOptions();
            globalProductBulkSelect.innerHTML = bulkHtml;
        }
    }

    if (defaultProductSelect) {
        defaultProductSelect.addEventListener('change', (e) => {
            localStorage.setItem('defaultProductSelection', e.target.value);
            console.log(`Saved default product: ${e.target.value}`);
        });
    }

    // --- 1-CLICK GLOBAL BULK PRODUCT MAPPING ACTION ---
    const applyGlobalProductBulkBtn = document.getElementById('applyGlobalProductBulkBtn');
    if (applyGlobalProductBulkBtn) {
        applyGlobalProductBulkBtn.addEventListener('click', async () => {
            const globalProductBulkSelect = document.getElementById('globalProductBulkSelect');
            if (!globalProductBulkSelect || !globalProductBulkSelect.value) {
                showToast("Please select a Miracle product from the dropdown first.", "warning");
                if (globalProductBulkSelect) globalProductBulkSelect.classList.add('border-amber-500', 'error-shake');
                return;
            }
            if (globalProductBulkSelect) globalProductBulkSelect.classList.remove('border-amber-500', 'error-shake');

            const selectedVal = globalProductBulkSelect.value;
            if (!currentExtractedData || currentExtractedData.length === 0) {
                showToast("No vouchers loaded in grid to update.", "info");
                return;
            }

            // Check if any rows are explicitly checked via checkbox
            const checkedCheckboxes = document.querySelectorAll('.row-select-checkbox:checked');
            const targetRows = [];
            if (checkedCheckboxes.length > 0) {
                // BUG FIX: attribute is data-idx not data-index
                checkedCheckboxes.forEach(cb => {
                    const rowIdx = parseInt(cb.dataset.idx);
                    if (!isNaN(rowIdx) && currentExtractedData[rowIdx]) {
                        targetRows.push(currentExtractedData[rowIdx]);
                    }
                });
            } else {
                // BUG FIX: use visible filtered rows (displayData) if available, not all rows
                const visibleRows = (typeof displayData !== 'undefined' && displayData && displayData.length > 0)
                    ? displayData : currentExtractedData;
                targetRows.push(...visibleRows);
            }

            let updatedCount = 0;
            targetRows.forEach(row => {
                if (!Array.isArray(row.items)) row.items = [];
                if (row.items.length === 0) {
                    row.items.push({ name: selectedVal, qty: 1, rate: 0, gst_pct: 18 });
                } else {
                    row.items.forEach(item => {
                        item.name = selectedVal;
                        item.autoCreate = (selectedVal === "AUTO_CREATE_PRODUCT");
                    });
                }
                updatedCount++;
            });

            // Re-render grid instantly
            renderGrid(currentExtractedData);
            recalcGrandTotals();

            // Save mapping rule to AI Memory Vault in background
            if (selectedVal !== "AUTO_CREATE_PRODUCT" && targetRows.length > 0) {
                // BUG FIX: use the actual first targeted row's party name, not always row 0
                const sampleParty = targetRows[0].party_name || targetRows[0].party || targetRows[0].narration || "FOOTWEAR";
                fetch(`${API_URL}/api/teach_product_mapping`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ extracted_name: sampleParty, mapped_product: selectedVal })
                }).catch(err => console.error("Error saving bulk product mapping rule:", err));
            }

            showToast(`⚡ Successfully mapped ${updatedCount} vouchers to '${selectedVal}'!`, "success");
        });
    }

    // --- 1-CLICK BANK STATEMENTS BULK LEDGER & GROUP MAPPING ACTION ---
    const applyBankBulkLedgerGroupBtn = document.getElementById('applyBankBulkLedgerGroupBtn');
    const bulkApplyPopup = document.getElementById('bulkApplyPopup');
    const closeBulkApplyPopupBtn = document.getElementById('closeBulkApplyPopupBtn');
    const cancelBulkApplyBtn = document.getElementById('cancelBulkApplyBtn');
    const confirmBulkApplyBtn = document.getElementById('confirmBulkApplyBtn');
    const bulkApplyLedgerInput = document.getElementById('bulkApplyLedgerInput');
    const bulkApplyLedgerDropdown = document.getElementById('bulkApplyLedgerDropdown');
    const bulkApplyGroupSelect = document.getElementById('bulkApplyGroupSelect');

    // Utility: Compute a clean narration key from a raw narration string
    function extractNarrationPatternKey(narration) {
        let pat = (narration || '').toUpperCase()
            .replace(/^(UPI|NEFT|IMPS|RTGS|ACH D|ACH C|POS|EFT|NACH)[-/_ \t]+/i, '')
            .replace(/@(okaxis|okicici|oka|waaxis|naviaxis|ptaxis|yescred|ptyes|axl|ybl|kotak|oksbi|okhdfcbank|hdfcbank)[A-Za-z0-9_.-]*/gi, '')
            .replace(/\b\d{5,}\b/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        const words = pat.split(/[-/_ \t]+/).filter(w => w.length >= 3 && !/^\d+$/.test(w));
        return words.length > 0 ? words[0] : pat.substring(0, 12);
    }

    // Dynamic Searchable Combobox renderer for Miracle Ledgers
    function renderBulkApplyLedgerDropdown(query = '') {
        if (!bulkApplyLedgerDropdown) return;
        const q = (query || '').trim().toUpperCase();

        const allCandidates = [];
        const seenNames = new Set();

        // 1. Master Miracle Ledgers
        if (clientLedgers && clientLedgers.length > 0) {
            clientLedgers.forEach(l => {
                const name = (l.name || '').trim();
                if (name && !seenNames.has(name.toUpperCase())) {
                    seenNames.add(name.toUpperCase());
                    allCandidates.push({
                        name: name,
                        group_name: l.group_name || 'Miracle Master',
                        type: 'master'
                    });
                }
            });
        }

        // 2. Global Auto-Create Ledgers
        if (globalAutoCreateLedgers && globalAutoCreateLedgers.length > 0) {
            globalAutoCreateLedgers.forEach(ul => {
                const name = (ul || '').trim();
                if (name && !seenNames.has(name.toUpperCase())) {
                    seenNames.add(name.toUpperCase());
                    const hint = (autoCreateLedgerHints && autoCreateLedgerHints[name.toUpperCase()]) || inferExpenseGroupHint(name);
                    allCandidates.push({
                        name: name,
                        group_name: hint || 'Auto-Create',
                        type: 'autocreate'
                    });
                }
            });
        }

        // 3. Currently loaded grid mapped ledgers
        if (currentExtractedData && currentExtractedData.length > 0) {
            currentExtractedData.forEach(r => {
                const name = (r.mapped_ledger || '').trim();
                if (name && name.toUpperCase() !== 'SUSPENSE ACCOUNT' && !seenNames.has(name.toUpperCase())) {
                    seenNames.add(name.toUpperCase());
                    const hint = r.group_hint || inferExpenseGroupHint(name, r.transaction_type);
                    allCandidates.push({
                        name: name,
                        group_name: hint || 'Grid Mapped',
                        type: 'grid'
                    });
                }
            });
        }

        const matches = allCandidates.filter(c => {
            if (!q) return true;
            return c.name.toUpperCase().includes(q) || c.group_name.toUpperCase().includes(q);
        }).slice(0, 50);

        if (matches.length === 0) {
            bulkApplyLedgerDropdown.innerHTML = `
                <div class="px-4 py-3 text-xs text-slate-400 italic flex items-center gap-2">
                    <i class="fa-solid fa-plus-circle text-cyan-400"></i>
                    <span>No matching Miracle master ledgers found. Will create <strong>"${query}"</strong> as Auto-Create Ledger.</span>
                </div>
            `;
        } else {
            bulkApplyLedgerDropdown.innerHTML = matches.map(c => `
                <div class="bulk-ledger-opt px-4 py-2.5 hover:bg-cyan-500/20 cursor-pointer flex justify-between items-center text-xs transition border-b border-slate-800/40 last:border-0" data-name="${c.name}" data-group="${c.group_name}">
                    <span class="text-slate-200 font-medium">${c.name}</span>
                    <span class="text-[10px] ${c.type === 'master' ? 'text-emerald-400 bg-emerald-950/80 border-emerald-800/50' : 'text-cyan-400 bg-cyan-950/80 border-cyan-800/50'} px-2 py-0.5 rounded border font-semibold">${c.group_name}</span>
                </div>
            `).join('');
        }

        bulkApplyLedgerDropdown.classList.remove('hidden');

        bulkApplyLedgerDropdown.querySelectorAll('.bulk-ledger-opt').forEach(optEl => {
            optEl.addEventListener('click', () => {
                const name = optEl.getAttribute('data-name');
                const group = optEl.getAttribute('data-group');
                if (bulkApplyLedgerInput) bulkApplyLedgerInput.value = name;
                bulkApplyLedgerDropdown.classList.add('hidden');

                if (group && bulkApplyGroupSelect) {
                    const cleanGroup = group.trim().toUpperCase();
                    for (const gOpt of bulkApplyGroupSelect.options) {
                        const valUp = gOpt.value.trim().toUpperCase();
                        if (valUp && (valUp === cleanGroup || cleanGroup.includes(valUp) || valUp.includes(cleanGroup))) {
                            gOpt.selected = true;
                            break;
                        }
                    }
                }
            });
        });
    }

    if (bulkApplyLedgerInput) {
        bulkApplyLedgerInput.addEventListener('focus', () => {
            renderBulkApplyLedgerDropdown(bulkApplyLedgerInput.value);
        });
        bulkApplyLedgerInput.addEventListener('input', (e) => {
            const val = e.target.value;
            renderBulkApplyLedgerDropdown(val);

            // Auto-sync Account Group dropdown when typing
            const cleanTyped = val.trim().toUpperCase();
            let matchedGroup = null;

            if (clientLedgers && clientLedgers.length > 0) {
                const matched = clientLedgers.find(l => (l.name || '').toUpperCase() === cleanTyped);
                if (matched && matched.group_name) matchedGroup = matched.group_name;
            }

            if (!matchedGroup && cleanTyped) {
                matchedGroup = inferExpenseGroupHint(val);
            }

            if (matchedGroup && bulkApplyGroupSelect) {
                const cleanGroup = matchedGroup.trim().toUpperCase();
                for (const gOpt of bulkApplyGroupSelect.options) {
                    const valUp = gOpt.value.trim().toUpperCase();
                    if (valUp && (valUp === cleanGroup || cleanGroup.includes(valUp) || valUp.includes(cleanGroup))) {
                        gOpt.selected = true;
                        break;
                    }
                }
            }
        });
    }

    document.addEventListener('click', (e) => {
        if (bulkApplyLedgerDropdown && bulkApplyLedgerInput) {
            if (!bulkApplyLedgerInput.contains(e.target) && !bulkApplyLedgerDropdown.contains(e.target)) {
                bulkApplyLedgerDropdown.classList.add('hidden');
            }
        }
    });

    if (applyBankBulkLedgerGroupBtn) {
        applyBankBulkLedgerGroupBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (!currentExtractedData || currentExtractedData.length === 0) {
                showToast("No transactions loaded in grid to update.", "info");
                return;
            }

            // ── STEP 1: Compute candidate sets ──
            const checkedCheckboxes = Array.from(document.querySelectorAll('.row-select-checkbox:checked'));
            const checkedRows = checkedCheckboxes.map(cb => {
                const idx = parseInt(cb.dataset.idx);
                return !isNaN(idx) ? currentExtractedData[idx] : null;
            }).filter(Boolean);

            const filteredRows = getFilteredData();

            let sourceRow = null;
            if (checkedRows.length > 0) sourceRow = checkedRows[0];

            if (!sourceRow && document.activeElement && document.activeElement.tagName === 'INPUT') {
                const tr = document.activeElement.closest('tr');
                if (tr) {
                    const cb = tr.querySelector('.row-select-checkbox');
                    if (cb && cb.dataset.idx) {
                        const idx = parseInt(cb.dataset.idx);
                        if (!isNaN(idx)) sourceRow = currentExtractedData[idx];
                    }
                }
            }

            if (!sourceRow) {
                sourceRow = filteredRows.find(r => r.mapped_ledger && r.mapped_ledger.toUpperCase() !== 'SUSPENSE ACCOUNT') || filteredRows[0];
            }

            if (!sourceRow) {
                showToast("No visible rows to apply to.", "warning");
                return;
            }

            const rawNarr = (sourceRow.narration || sourceRow.party_name || sourceRow.party || '').trim();
            const patternKey = extractNarrationPatternKey(rawNarr) || rawNarr.substring(0, 10);
            const patternRows = currentExtractedData.filter(r => {
                const rNarr = (r.narration || r.party_name || r.party || '').toUpperCase();
                return patternKey && rNarr.includes(patternKey.toUpperCase());
            });

            // ── STEP 2: Update radio labels in popup ──
            const scopeChecked = document.getElementById('scopeChecked');
            const scopeCheckedLabel = document.getElementById('scopeCheckedLabel');
            const scopeFiltered = document.getElementById('scopeFiltered');
            const scopeFilteredLabel = document.getElementById('scopeFilteredLabel');
            const scopePattern = document.getElementById('scopePattern');
            const scopePatternLabel = document.getElementById('scopePatternLabel');

            if (scopeCheckedLabel) scopeCheckedLabel.textContent = `Selected Checkbox Rows (${checkedRows.length} row${checkedRows.length !== 1 ? 's' : ''})`;
            if (scopeFilteredLabel) scopeFilteredLabel.textContent = `Currently Filtered Rows (${filteredRows.length} row${filteredRows.length !== 1 ? 's' : ''})`;
            if (scopePatternLabel) scopePatternLabel.textContent = `Narration Pattern "${patternKey}" (${patternRows.length} row${patternRows.length !== 1 ? 's' : ''})`;

            if (scopeChecked) {
                scopeChecked.disabled = (checkedRows.length === 0);
                if (checkedRows.length === 0 && scopeChecked.checked) {
                    if (scopeFiltered) scopeFiltered.checked = true;
                }
            }

            const hasActiveSearch = currentGridSearch && currentGridSearch.trim().length > 0;
            const hasActiveTabFilter = currentGridFilter && currentGridFilter !== 'all';
            if (checkedRows.length > 0) {
                if (scopeChecked) scopeChecked.checked = true;
            } else if (hasActiveSearch || hasActiveTabFilter) {
                if (scopeFiltered) scopeFiltered.checked = true;
            } else {
                if (scopePattern) scopePattern.checked = true;
            }

            bulkApplyPopup._checkedRows = checkedRows;
            bulkApplyPopup._filteredRows = filteredRows;
            bulkApplyPopup._patternRows = patternRows;
            bulkApplyPopup._patternKey = patternKey;

            // ── STEP 3: Pre-fill Ledger & Group defaults ──
            const preFillLedger = sourceRow.mapped_ledger && sourceRow.mapped_ledger.toUpperCase() !== 'SUSPENSE ACCOUNT' ? sourceRow.mapped_ledger : '';
            const preFillGroup = inferExpenseGroupHint(sourceRow.mapped_ledger, sourceRow.transaction_type, sourceRow.group_hint);

            if (bulkApplyLedgerInput) bulkApplyLedgerInput.value = preFillLedger || '';

            if (bulkApplyGroupSelect) {
                const cleanPreGroup = (preFillGroup || 'Indirect Expenses').trim().toUpperCase();
                let matchedOpt = false;
                for (const opt of bulkApplyGroupSelect.options) {
                    const valUp = opt.value.trim().toUpperCase();
                    if (valUp && (valUp === cleanPreGroup || cleanPreGroup.includes(valUp) || valUp.includes(cleanPreGroup))) {
                        opt.selected = true;
                        matchedOpt = true;
                        break;
                    }
                }
                if (!matchedOpt) {
                    for (const opt of bulkApplyGroupSelect.options) {
                        if (opt.value === 'Indirect Expenses') {
                            opt.selected = true;
                            break;
                        }
                    }
                }
            }

            // ── STEP 4: Open Popup ──
            if (bulkApplyPopup) {
                bulkApplyPopup.classList.remove('hidden');
                bulkApplyPopup.style.display = 'flex';
            }
        });
    }

    // Close popup handlers
    function closeBulkApplyPopup() {
        if (bulkApplyPopup) {
            bulkApplyPopup.classList.add('hidden');
            bulkApplyPopup.style.display = 'none';
            if (bulkApplyLedgerDropdown) bulkApplyLedgerDropdown.classList.add('hidden');
            if (bulkApplyPopup._checkedRows) delete bulkApplyPopup._checkedRows;
            if (bulkApplyPopup._filteredRows) delete bulkApplyPopup._filteredRows;
            if (bulkApplyPopup._patternRows) delete bulkApplyPopup._patternRows;
        }
    }
    if (closeBulkApplyPopupBtn) closeBulkApplyPopupBtn.addEventListener('click', (e) => { e.preventDefault(); closeBulkApplyPopup(); });
    if (cancelBulkApplyBtn) cancelBulkApplyBtn.addEventListener('click', (e) => { e.preventDefault(); closeBulkApplyPopup(); });

    // Confirm: Apply to selected target scope
    if (confirmBulkApplyBtn) {
        confirmBulkApplyBtn.addEventListener('click', async (e) => {
            e.preventDefault();

            const targetLedger = bulkApplyLedgerInput ? bulkApplyLedgerInput.value.trim() : '';
            const targetGroup = (bulkApplyGroupSelect ? bulkApplyGroupSelect.value : 'Indirect Expenses');

            if (!targetLedger) {
                showToast("Please type or select a Mapped Ledger before applying.", "warning");
                if (bulkApplyLedgerInput) bulkApplyLedgerInput.focus();
                return;
            }

            const selectedRadio = document.querySelector('input[name="bulkScope"]:checked');
            const selectedScope = selectedRadio ? selectedRadio.value : 'filtered';

            let targetRows = [];
            if (selectedScope === 'checked') {
                targetRows = bulkApplyPopup._checkedRows || [];
            } else if (selectedScope === 'filtered') {
                targetRows = bulkApplyPopup._filteredRows || getFilteredData();
            } else {
                targetRows = bulkApplyPopup._patternRows || [];
            }

            if (!targetRows || targetRows.length === 0) {
                showToast("No rows found matching the selected target scope.", "warning");
                return;
            }

            let updatedCount = 0;
            targetRows.forEach(row => {
                row.mapped_ledger = targetLedger;
                row.group_hint = targetGroup;
                row.status = 'Ready';
                row.confidence_score = 98;
                if (row.flags) {
                    row.flags = row.flags.filter(f => f !== 'Suspense Mapping' && f !== 'Unmapped Ledger');
                }
                updatedCount++;
            });

            // Update auto-create ledger hint lookup
            if (autoCreateLedgerHints) {
                autoCreateLedgerHints[targetLedger.toUpperCase()] = targetGroup;
            }

            populateGlobalLedgersDatalist();
            renderGrid(currentExtractedData);
            recalcGrandTotals();

            // Persist rule to AI Memory Vault automatically
            const activePattern = bulkApplyPopup._patternKey || extractNarrationPatternKey(targetRows[0].narration || targetLedger);
            if (activePattern) {
                try {
                    const activeClientId = activeClientSpan ? activeClientSpan.textContent.trim() : "CMP0001";
                    await fetch(`${API_URL}/api/memory-vault/item`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            client_id: activeClientId,
                            category: "expense_mappings",
                            key: activePattern,
                            value: targetLedger
                        })
                    });
                } catch (err) {
                    console.error("Error persisting bulk rule to AI Memory Vault:", err);
                }
            }

            closeBulkApplyPopup();
            showToast(`✨ Bulk applied '${targetLedger}' (${targetGroup}) to ${updatedCount} rows!`, "success");
        });
    }




    // --- UPLOAD FLOW ---
    // --- UPLOAD FLOW ---

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });
    
    const trainSpecBtn = document.getElementById('trainSpecBtn');
    const trainSpecInput = document.getElementById('trainSpecInput');
    
    if(trainSpecBtn) {
        trainSpecBtn.addEventListener('click', () => {
            trainSpecInput.click();
        });
        
        trainSpecInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (files.length === 0) return;
            
            const specFile = files[0];
            const loadingMsg = loadingState.querySelector('h3');
            const loadingSub = loadingState.querySelector('p');
            loadingMsg.innerText = `Training AI...`;
            loadingSub.innerText = `Memorizing specifications from ${specFile.name}`;
            loadingState.classList.remove('hidden');
            
            const formData = new FormData();
            formData.append("file", specFile);
            
            try {
                const res = await fetch(`${API_URL}/api/train_specifications`, {
                    method: "POST",
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(errorData.detail || "Failed to train specifications");
                }
                
                const data = await res.json();
                alert(`✨ Successfully trained AI Memory JSON from ${specFile.name}!\n\nLearned ${data.learned_rules_count || 0} direct ledger/product rules and updated client guidelines.`);
            } catch (err) {
                alert(`Error: ${err.message}`);
            } finally {
                loadingState.classList.add('hidden');
                e.target.value = "";
            }
        });
    }

    fileInput.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (files.length === 0) return;
        
        const loadingMsg = loadingState.querySelector('h3');
        const loadingSub = loadingState.querySelector('p');
        
        let allFormattedData = [];
        let globalIndexCounter = 0;
        
        try {
            for (let i = 0; i < files.length; i++) {
                const currentFile = files[i];
                loadingMsg.innerText = `Gemini AI is Extracting Data (${i + 1} of ${files.length})...`;
                loadingSub.innerText = `Reading ${currentFile.name} and applying client memory rules.`;
                loadingState.classList.remove('hidden');
                
                docViewerTitle.innerHTML = `<i class="fa-regular fa-file"></i> ${files.length > 1 ? 'Multiple Files' : currentFile.name}`;
                docViewerTitle.nextElementSibling.innerText = `${i + 1} of ${files.length}`;
                
                docPlaceholder.innerHTML = `
                    <i class="fa-solid fa-file-pdf text-5xl text-red-400 mb-3 block"></i>
                    <p class="text-base text-slate-400">Previewing: ${currentFile.name}</p>
                `;

                const formData = new FormData();
                formData.append("file", currentFile);
                formData.append("module", currentModule);
                formData.append("instruction", aiInstructionInput.value.trim());
                
                if ((currentModule === 'Bank Statements' || currentModule === 'Cash Entries') && clientLedgers.length > 0) {
                    const ledgerNames = clientLedgers.map(l => l.name).join(", ");
                    formData.append("ledgers_list", ledgerNames);
                }

                let res;
                let pollInterval = null;
                try {
                    // Start polling deep extraction progress status
                    pollInterval = setInterval(async () => {
                        try {
                            const statusRes = await fetch(`${API_URL}/api/upload-status`);
                            if (statusRes.ok) {
                                const statusData = await statusRes.json();
                                if (statusData && statusData.message && statusData.message !== "Idle") {
                                    const pct = statusData.progress_pct || statusData.percentage || 0;
                                    const pctStr = pct > 0 ? `[${pct}%] ` : "";
                                    loadingSub.innerText = `${pctStr}${statusData.message}`;
                                }
                            }
                        } catch (pollErr) {
                            console.error("Error polling upload status:", pollErr);
                        }
                    }, 1500);

                    if (currentModule === 'Opening Balances') {
                        res = await fetch(`${API_URL}/api/opening-balances/extract`, {
                            method: "POST",
                            body: formData
                        });
                    } else {
                        res = await fetch(`${API_URL}/api/upload`, {
                            method: "POST",
                            body: formData
                        });
                    }
                } finally {
                    if (pollInterval) {
                        clearInterval(pollInterval);
                    }
                }

                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    if (errorData && errorData.requires_password) {
                        pendingUploadContext = {
                            file: currentFile,
                            module: currentModule,
                            instruction: aiInstructionInput ? aiInstructionInput.value.trim() : ""
                        };
                        if (loadingState) loadingState.classList.add('hidden');
                        showPdfPasswordModal(errorData.message, errorData.detail === "PDF_PASSWORD_INCORRECT", currentFile.name);
                        return;
                    }
                    throw new Error(errorData.detail || `Failed to extract data from ${currentFile.name}`);
                }

                const resData = await res.json();
                const data = resData.data || resData; // Extract inner payload from /api/upload
                window.currentBankName = data.bank_name || "Bank Account";
                
                // --- Smart Year Auto-Detection ---
                let yearSwitched = false;
                if (resData.detected_year && resData.detected_year !== activeYearFolder) {
                    const originalYear = activeYearFolder;
                    activeYearFolder = resData.detected_year;
                    
                    if (yearSelect) {
                        yearSelect.value = activeYearFolder;
                    }
                    
                    await fetchLedgers();
                    await fetchProducts();
                    yearSwitched = true;
                    console.log(`Auto-switched financial year from ${originalYear} to ${activeYearFolder}`);
                }

                // --- Smart Client Auto-Detection ---
                let clientSwitched = false;
                if (resData.detected_client && resData.detected_client !== clientSelect.value) {
                    const originalClient = clientSelect.value;
                    const newClient = resData.detected_client;
                    
                    clientSelect.value = newClient;
                    settingsActiveClient.value = newClient;
                    fetchAutoSetupIds(newClient);
                    
                    await fetchClientYears(newClient, activeYearFolder); 
                    saveSettings(true); // Save silently in background
                    
                    await fetchLedgers();
                    await fetchProducts();
                    clientSwitched = true;
                    console.log(`Auto-switched client from ${originalClient} to ${newClient}`);
                }
                
                if (clientSwitched || yearSwitched) {
                    let msg = "🤖 Smart Auto-Detection Triggered:\n";
                    if (clientSwitched) {
                        const matchedOpt = clientSelect.options[clientSelect.selectedIndex];
                        msg += `• Selected Client: ${matchedOpt ? matchedOpt.innerText : clientSelect.value}\n`;
                    }
                    if (yearSwitched) {
                        const matchedOpt = yearSelect.options[yearSelect.selectedIndex];
                        msg += `• Financial Year: ${matchedOpt ? matchedOpt.innerText : activeYearFolder}\n`;
                    }
                    showToast(msg, "success");
                }

                if (data.opening_balance !== undefined) {
                    const opBalInput = document.getElementById('openingBalanceInput');
                    if (opBalInput) {
                        opBalInput.value = data.opening_balance;
                    }
                }

                window.lastProcessedData = data;
            
            // Find the array of invoices in whatever object Gemini returned
            let extractedArray = null;
            if (Array.isArray(data)) {
                extractedArray = data;
            } else if (data && typeof data === 'object') {
                if (Array.isArray(data.extracted_data)) extractedArray = data.extracted_data;
                else if (Array.isArray(data.data)) extractedArray = data.data;
                else if (Array.isArray(data.invoices)) extractedArray = data.invoices;
                else if (Array.isArray(data.results)) extractedArray = data.results;
                else {
                    // Try to find ANY array value in the object
                    const anyArray = Object.values(data).find(val => Array.isArray(val));
                    if (anyArray && anyArray.length > 0 && typeof anyArray[0] === 'object') {
                        extractedArray = anyArray;
                    } else if ((data.date || data.Date) && (data.party_name || data.party || data.PartyName)) {
                        extractedArray = [data]; // Fix: Fallback for single object payloads
                    }
                }
            }
                 // Consolidate duplicate invoice entries or Excel rows with matching Bill No, Date, and Party
            if (extractedArray && Array.isArray(extractedArray)) {
                if (currentModule !== 'Bank Statements' && currentModule !== 'Cash Entries' && currentModule !== 'Opening Balances') {
                    const grouped = {};
                    extractedArray.forEach(inv => {
                        if (!inv) return;
                        const rawBillNo = String(inv.bill_no || inv.billNo || inv.invoice_no || inv.Bill_No || "").trim();
                        const date = String(inv.date || inv.Date || "").trim();
                        const party = String(inv.party_name || inv.party || inv.PartyName || inv.Party_Name || "").trim();
                        const total = Number(inv.total || inv.total_amount || inv.Total || inv.taxable_amount || 0);
                        
                        // Normalize billNo key by stripping common prefixes (e.g. CR/, SS/, PP/, INV/) so CR/2026-27/395 and 2026-27/395 merge cleanly
                        const normBillNo = rawBillNo.replace(/^(CR\/|SS\/|PP\/|INV\/|BILL\/)/i, '').trim();
                        
                        // Generate key: if normBillNo is empty, do NOT merge (give it a unique random suffix so they stay separate)
                        const key = normBillNo ? `${normBillNo.toUpperCase()}|${date}|${party.toUpperCase()}` : `EMPTY_INV_${Math.random()}`;
                        
                        let invItems = inv.items;
                        if (!invItems || !Array.isArray(invItems) || invItems.length === 0) {
                            invItems = [{
                                name: inv.product_name || inv.item_name || inv.product || "General Items",
                                qty: Number(inv.qty || inv.quantity || 1),
                                rate: Number(inv.rate || inv.price || inv.taxable_amount || inv.taxable || 0),
                                amount: Number(inv.amount || inv.taxable_amount || inv.taxable || 0),
                                gst_pct: Number(inv.gst_pct || inv.rate_pct || 18.0),
                                hsn_code: String(inv.hsn_code || inv.hsn || ""),
                                uom: String(inv.uom || inv.unit || "NOS")
                            }];
                        }
                        
                        if (!grouped[key]) {
                            grouped[key] = {
                                ...inv,
                                items: [...invItems]
                            };
                        } else {
                            // If it's a duplicate check: same bill_no, same party, AND same total amount
                            const existingTotal = Number(grouped[key].total || grouped[key].total_amount || grouped[key].Total || grouped[key].taxable_amount || 0);
                            if (Math.abs(existingTotal - total) < 0.01) {
                                // EXACT DUPLICATE invoice (same bill_no, party, and amount). Skip to prevent doubling voucher.
                                console.log("🛡️ Dropped exact duplicate AI invoice:", inv);
                                return;
                            }
                            
                            // Otherwise, it's a multi-item invoice. Sum the taxable amounts and CGST/SGST/IGST and push the items.
                            const taxable1 = Number(grouped[key].taxable_amount || grouped[key].taxable || grouped[key].Taxable || 0);
                            const taxable2 = Number(inv.taxable_amount || inv.taxable || inv.Taxable || 0);
                            grouped[key].taxable_amount = taxable1 + taxable2;
                            
                            const cgst1 = Number(grouped[key].cgst || 0);
                            const cgst2 = Number(inv.cgst || 0);
                            grouped[key].cgst = cgst1 + cgst2;
                            
                            const sgst1 = Number(grouped[key].sgst || 0);
                            const sgst2 = Number(inv.sgst || 0);
                            grouped[key].sgst = sgst1 + sgst2;
                            
                            const igst1 = Number(grouped[key].igst || 0);
                            const igst2 = Number(inv.igst || 0);
                            grouped[key].igst = igst1 + igst2;
                            
                            const discount1 = Number(grouped[key].discount || 0);
                            const discount2 = Number(inv.discount || 0);
                            grouped[key].discount = discount1 + discount2;
 
                            const freight1 = Number(grouped[key].freight || 0);
                            const freight2 = Number(inv.freight || 0);
                            grouped[key].freight = freight1 + freight2;
 
                            const tcs1 = Number(grouped[key].tcs || 0);
                            const tcs2 = Number(inv.tcs || 0);
                            grouped[key].tcs = tcs1 + tcs2;
 
                            const tds1 = Number(grouped[key].tds || 0);
                            const tds2 = Number(inv.tds || 0);
                            grouped[key].tds = tds1 + tds2;
 
                            grouped[key].total = existingTotal + total;
                            
                            grouped[key].items.push(...invItems);
                        }
                    });
                    extractedArray = Object.values(grouped);
                } else if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                    // AI Page-Overlap Deduplication (Only run for PDF statements to prevent dropping genuine same-day identical transactions from Excel)
                    const isPdf = typeof currentFile !== 'undefined' && currentFile && currentFile.name && currentFile.name.toLowerCase().endsWith('.pdf');
                    if (isPdf) {
                        const uniqueTransactions = [];
                        const seenHashes = new Set();
                        extractedArray.forEach(row => {
                            if (!row) return;
                            // Normalize fields for strict exact matching
                            const date = String(row.date || row.Date || "").trim();
                            const amount = Number(row.amount || row.Amount || 0).toFixed(2);
                            const narration = String(row.narration || "").trim().toLowerCase();
                            const type = String(row.transaction_type || "").trim().toLowerCase();
                            const ref = String(row.reference_no || row.reference || "").trim().toLowerCase();
                            const mapped = String(row.mapped_ledger || "").trim().toLowerCase();
                            
                            const hash = `${date}|${amount}|${type}|${ref}|${narration}|${mapped}`;
                            
                            if (!seenHashes.has(hash)) {
                                seenHashes.add(hash);
                                uniqueTransactions.push(row);
                            } else {
                                console.log("Dropped AI duplicate bank transaction:", row);
                            }
                        });
                        extractedArray = uniqueTransactions;
                    }
                }
            }
            
            let formattedData = [];
            if (extractedArray && Array.isArray(extractedArray)) {
                formattedData = extractedArray.map((row) => {
                    if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                        const resolvedLedger = row.mapped_ledger || "Suspense Account";
                        const cleanLedger = resolvedLedger.trim().toUpperCase();
                        
                        let status = 'Review';
                        let isB2C = false;
                        let autoCreateB2B = false;
                        
                        if (cleanLedger === "SUSPENSE ACCOUNT") {
                            status = 'Review';
                        } else {
                            const match = clientLedgers.find(led => 
                                led.name.trim().toUpperCase() === cleanLedger || 
                                led.print_name.trim().toUpperCase() === cleanLedger ||
                                led.code.trim().toUpperCase() === cleanLedger
                            );
                            if (match) {
                                status = 'Ready'; // Mapped
                            } else {
                                status = 'Ready';
                                isB2C = false; // B2C is only for invoice modules, not Bank/Cash
                            }
                        }

                        return {
                            id: ++globalIndexCounter,
                            date: row.date || row.Date || "",
                            reference_no: row.reference_no || row.reference || "",
                            narration: row.narration || "",
                            party_name: resolvedLedger,
                            mapped_ledger: resolvedLedger,
                            party: resolvedLedger,
                            transaction_type: row.transaction_type || "Receipt",
                            amount: Number(row.amount || row.Amount || 0),
                            status: status,
                            isB2C: isB2C,
                            autoCreateB2B: autoCreateB2B,
                            group_hint: row.group_hint || ""
                        };
                    } else if (currentModule === 'Opening Balances') {
                        return {
                            id: ++globalIndexCounter,
                            ledger_name: row.ledger_name || "",
                            matched_code: row.matched_code || "",
                            balance: Number(row.balance || 0),
                            dr_cr: row.dr_cr || "D",
                            group_hint: row.group_hint || "",
                            status: row.matched_code ? 'Ready' : 'Review'
                        };
                    }

                    const party = row.party_name || row.party || row.PartyName || row.Party_Name || "UNKNOWN_PARTY: Missing";
                    const billNo = row.bill_no || row.billNo || row.invoice_no || row.Bill_No || "";
                    const taxable = row.taxable_amount || row.taxable || row.Taxable || 0;
                    const cgst = row.cgst || 0;
                    const sgst = row.sgst || 0;
                    const igst = row.igst || 0;
                    const gst = cgst + sgst + igst || row.gst || row.GST || 0;
                    const discount = row.discount || row.Discount || 0;
                    const freight = row.freight || row.Freight || 0;
                    const tcs = row.tcs || row.Tcs || row.TCS || 0;
                    const tds = row.tds || row.Tds || row.TDS || 0;
                    const total = row.total || row.total_amount || row.Total || 0;
                    
                    const partyGstin = String(row.party_gstin || row.gstin || "").trim();
                    const isUnregistered = !partyGstin || /^(urd|unregistered|b2c|consumer|none|na|-)$/i.test(partyGstin);
                    
                    const partyStr = String(party).trim();
                    let finalParty = partyStr;
                    let status = 'Ready';
                    let isB2C = false;
                    let autoCreateB2B = false;
                    
                    if (partyStr.startsWith('UNKNOWN_PARTY:') || partyStr.startsWith('UNKNOWN_NARRATION:') || partyStr.includes('Missing') || partyStr === "") {
                        status = 'Review';
                    } else {
                        const cleanParty = partyStr.toUpperCase();
                        const match = clientLedgers.find(led => 
                            led.name.trim().toUpperCase() === cleanParty || 
                            led.print_name.trim().toUpperCase() === cleanParty ||
                            led.code.trim().toUpperCase() === cleanParty
                        );
                        
                        if (match) {
                            finalParty = match.name;
                        } else {
                            if (isUnregistered) {
                                // B2C logic
                                if (autoCreateB2c) {
                                    finalParty = partyStr;
                                    status = 'Ready';
                                    isB2C = true;
                                } else {
                                    finalParty = `UNKNOWN_PARTY: ${partyStr}`;
                                    status = 'Review';
                                    isB2C = true;
                                }
                            } else {
                                if (autoCreateB2b) {
                                    finalParty = partyStr;
                                    status = 'Ready';
                                    isB2C = false;
                                    autoCreateB2B = true;
                                } else {
                                    // Unmapped registered party needs review
                                    finalParty = `UNKNOWN_PARTY: ${partyStr}`;
                                    status = 'Review';
                                    isB2C = false;
                                }
                            }
                        }
                    }
                    
                    return {
                        id: ++globalIndexCounter,
                        date: row.date || row.Date || "",
                        billNo: String(billNo),
                        party: finalParty,
                        party_gstin: isUnregistered ? "" : partyGstin,
                        party_address: row.party_address || "",
                        party_city: row.party_city || "",
                        party_pincode: row.party_pincode || "",
                        taxable: Number(taxable),
                        cgst: Number(cgst),
                        sgst: Number(sgst),
                        igst: Number(igst),
                        gst: Number(gst),
                        discount: Number(discount),
                        freight: Number(freight),
                        tcs: Number(tcs),
                        tds: Number(tds),
                        total: Number(total),
                        status: status,
                        isB2C: isB2C,
                        autoCreateB2B: autoCreateB2B,
                        items: row.items || []
                    };
                });
                allFormattedData.push(...formattedData);
            } else {
                console.error("Unexpected AI response format:", data);
                throw new Error(`Invalid response from AI for file. Looked like: ` + JSON.stringify(data).substring(0, 80));
            }
            
            } // End of for-loop over files

            // Display Warning Banner if backend returned extraction warnings
            const warningBanner = document.getElementById('extractionWarningBanner');
            if (warningBanner) {
                const collectedWarnings = [];
                if (window.lastProcessedData && window.lastProcessedData.warnings) {
                    collectedWarnings.push(...window.lastProcessedData.warnings);
                }
                if (collectedWarnings.length > 0) {
                    warningBanner.innerHTML = `
                        <div class="bg-amber-950/90 border border-amber-500/50 text-amber-200 px-4 py-3 rounded-2xl mb-4 shadow-xl flex items-start gap-3 animate-fade-in">
                            <div class="h-8 w-8 bg-amber-500/20 border border-amber-500/30 rounded-xl flex items-center justify-center text-amber-400 flex-shrink-0 mt-0.5">
                                <i class="fa-solid fa-triangle-exclamation text-lg"></i>
                            </div>
                            <div class="flex-1">
                                <div class="font-bold text-sm text-amber-300 flex items-center gap-2">
                                    Statement Extraction Discrepancy Warning
                                    <span class="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full font-mono uppercase tracking-wider">Action Required</span>
                                </div>
                                <div class="text-xs text-amber-200/90 mt-1 leading-relaxed">${collectedWarnings.join('<br>')}</div>
                            </div>
                            <button onclick="document.getElementById('extractionWarningBanner').classList.add('hidden')" class="text-amber-400 hover:text-white transition p-1 text-sm"><i class="fa-solid fa-xmark"></i></button>
                        </div>
                    `;
                    warningBanner.classList.remove('hidden');
                } else {
                    warningBanner.classList.add('hidden');
                }
            }

            // Intercept for AI Clarification (Sequential Modal flow)
            checkClarifications(allFormattedData);

        } catch (error) {
            console.error("Extraction error:", error);
            const errMsg = (error.message || '').toLowerCase();
            const isDisconnect = errMsg.includes('server disconnected') || errMsg.includes('connection') ||
                errMsg.includes('network') || errMsg.includes('timeout') || errMsg.includes('disconnected');
            if (isDisconnect) {
                showToast("⚡ Gemini AI network blip — the file is being retried automatically. Please wait...", "warning");
                // Auto-dismiss and do NOT block with alert for network blips
            } else {
                alert(`Extraction Failed: ${error.message}`);
            }

        } finally {
            loadingState.classList.add('hidden');
            // Clear inputs
            fileInput.value = "";
            aiInstructionInput.value = "";
        }
    });

    // Helper to generate grouped ledger options for dropdown
    function generateLedgerOptions(selectedCode = "", item = null) {
        // Classify and sort ledgers
        let suggested = [];
        let others = [];
        
        let targetClassification = "";
        let groupLabel = "Suggested Accounts";
        
        if (currentModule === 'Purchases') {
            targetClassification = "Creditor";
            groupLabel = "Sundry Creditors (Suppliers)";
        } else if (currentModule === 'Sales') {
            targetClassification = "Debtor";
            groupLabel = "Sundry Debtors (Customers)";
        } else if (currentModule === 'Expenses') {
            targetClassification = "Expense";
            groupLabel = "Expense Ledgers";
        }
        
        clientLedgers.forEach(led => {
            const optHtml = `<option value="${led.name}" ${led.name === selectedCode || led.code === selectedCode ? 'selected' : ''}>${led.print_name} (${led.code})</option>`;
            if (targetClassification && led.classification === targetClassification) {
                suggested.push(optHtml);
            } else {
                others.push(optHtml);
            }
        });
        
        let html = '<option value="">-- Select Miracle Ledger --</option>';
        if (item && item.party_gstin) {
            html += `<option value="AUTO_CREATE_B2B" ${selectedCode === 'AUTO_CREATE_B2B' ? 'selected' : ''} class="text-blue-400 font-semibold">[Auto-Create B2B Ledger with GST]</option>`;
        } else if (item && !item.party_gstin) {
            html += `<option value="AUTO_CREATE_B2C" ${selectedCode === 'AUTO_CREATE_B2C' ? 'selected' : ''} class="text-amber-500 font-semibold">[Auto-Create B2C Ledger (No GST)]</option>`;
        } else {
            html += `<option value="AUTO_CREATE_B2C" ${selectedCode === 'AUTO_CREATE_B2C' ? 'selected' : ''}>[Auto-Create as New B2C Ledger]</option>`;
        }

        if (suggested.length > 0) {
            html += `<optgroup label="${groupLabel}">
                ${suggested.join('')}
            </optgroup>`;
        }
        
        if (others.length > 0) {
            html += `<optgroup label="Other Accounts">
                ${others.join('')}
            </optgroup>`;
        }
        
        return html;
    }

    function showMappingModal(unknownItems) {
        mappingList.innerHTML = '';

        // Populate Top Bulk-Select Dropdown
        const globalPartySelect = document.getElementById('globalPartyMappingSelect');
        const countBadge = document.getElementById('unmappedPartyCountBadge');
        if (countBadge) countBadge.textContent = unknownItems.length;

        if (globalPartySelect) {
            let globalOpts = '<option value="">-- Select Bulk Mapping Action for All Parties --</option>';
            globalOpts += '<option value="AUTO_CREATE_B2C" class="text-amber-400 font-bold">✨ [Auto-Create All as B2C Retail Parties]</option>';
            globalOpts += '<option value="AUTO_CREATE_B2B" class="text-blue-400 font-bold">✨ [Auto-Create All as B2B Registered Parties]</option>';
            globalOpts += generateLedgerOptions("");
            globalPartySelect.innerHTML = globalOpts;
        }

        // Wire ⚡ Apply to All button
        const applyGlobalBtn = document.getElementById('applyGlobalPartyMappingBtn');
        if (applyGlobalBtn && globalPartySelect) {
            applyGlobalBtn.onclick = () => {
                const selectedVal = globalPartySelect.value;
                if (selectedVal) {
                    document.querySelectorAll('.mapping-select').forEach(sel => {
                        sel.value = selectedVal;
                        sel.classList.remove('border-red-500', 'error-shake');
                    });
                }
            };
        }

        unknownItems.forEach((item) => {
            const rawLabel = item.party.replace('UNKNOWN_PARTY: ', '').replace('UNKNOWN_NARRATION: ', '');
            const selectId = `select-${item.id}`;
            const optionsHtml = generateLedgerOptions("", item);
            
            let gstDisplay = '';
            if (item.party_gstin) {
                gstDisplay = `<span class="text-blue-400"><i class="fa-solid fa-building mr-1"></i> GSTIN: ${item.party_gstin} (B2B)</span>`;
            } else {
                gstDisplay = `<span class="text-amber-500"><i class="fa-solid fa-user mr-1"></i> GSTIN: None (B2C / URD)</span>`;
            }
            
            mappingList.innerHTML += `
                <div class="bg-slate-950/40 border border-slate-850 rounded-xl p-4 flex justify-between items-center mb-3">
                    <div>
                        <p class="text-base font-bold uppercase tracking-wider text-slate-500">${(currentModule === 'Bank Statements' || currentModule === 'Cash Entries') ? 'Unmapped Narration' : 'New Unmapped Party'}</p>
                        <p class="text-sm font-bold text-white mt-1">"${rawLabel}"</p>
                        <p class="text-[11px] mt-1.5 font-semibold">${gstDisplay}</p>
                        <p class="text-[11px] text-slate-450 mt-1"><i class="fa-solid fa-wallet mr-1 text-brand-500"></i> Total: ₹${item.total.toLocaleString('en-IN')}</p>
                    </div>
                    <div class="w-1/2 flex gap-2">
                        <select id="${selectId}" class="mapping-select w-full bg-slate-900 border border-slate-800 rounded-xl py-2 px-3 text-slate-200 text-sm focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 focus:ring-offset-obsidian-950 transition cursor-pointer" data-id="${item.id}" data-is-b2c="${!item.party_gstin}">
                            ${optionsHtml}
                        </select>
                        <button class="create-new-ledger-btn bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 px-3 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1 cursor-pointer shrink-0" title="Create New Miracle Ledger with Custom Group" data-raw-label="${rawLabel}" data-select-id="${selectId}">
                            <i class="fa-solid fa-plus-circle text-purple-400"></i> New
                        </button>
                        <button class="refresh-ledgers-btn bg-slate-900 hover:bg-slate-800 px-3 rounded-xl text-slate-300 transition border border-slate-800 flex items-center justify-center shrink-0" title="Refresh Ledgers from Miracle Database" data-select-id="${selectId}">
                            <i class="fa-solid fa-arrows-rotate"></i>
                        </button>
                    </div>
                </div>
            `;
        });

        // Add event listeners to refresh buttons to load fresh DBF records
        document.querySelectorAll('.refresh-ledgers-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const icon = e.currentTarget.querySelector('i');
                icon.classList.add('fa-spin', 'text-brand-500');
                
                const selectId = e.currentTarget.getAttribute('data-select-id');
                const selectEl = document.getElementById(selectId);
                const currentValue = selectEl.value;
                
                try {
                    // Pull fresh data from Miracle DBF files
                    const res = await fetch(`${API_URL}/api/refresh-ledgers`, { method: 'POST' });
                    if (!res.ok) throw new Error("Refresh failed.");
                    const data = await res.json();
                    
                    clientLedgers = data.data || [];
                    console.log(`Refreshed: ${clientLedgers.length} ledgers found.`);
                    
                    // Re-populate options while keeping current selection
                    selectEl.innerHTML = generateLedgerOptions(currentValue);
                    
                    // Success animation
                    icon.classList.remove('fa-spin', 'text-brand-500');
                    icon.classList.add('text-emerald-500');
                    setTimeout(() => icon.classList.remove('text-emerald-500'), 1500);
                } catch (err) {
                    console.error("Refresh error:", err);
                    icon.classList.remove('fa-spin', 'text-brand-500');
                    icon.classList.add('text-red-500');
                    setTimeout(() => icon.classList.remove('text-red-500'), 1500);
                }
            });
        });

        // Add event listeners for Create New Ledger buttons
        document.querySelectorAll('.create-new-ledger-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const rawLabel = e.currentTarget.getAttribute('data-raw-label') || '';
                const selectId = e.currentTarget.getAttribute('data-select-id') || '';
                openCreateLedgerModal(rawLabel, selectId);
            });
        });

        const mappingSearchInput = document.getElementById('mappingModalSearch');
        if (mappingSearchInput) {
            mappingSearchInput.value = '';
            mappingSearchInput.oninput = (e) => {
                const q = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#mappingList > div').forEach(card => {
                    const txt = card.innerText.toLowerCase();
                    card.style.display = (!q || txt.includes(q)) ? '' : 'none';
                });
            };
        }

        mappingModal.classList.remove('hidden');
    }

    // Modal Handlers for Create New Miracle Ledger
    let activeSelectIdForNewLedger = null;

    async function loadAccountGroupsDropdown(defaultGroupCode = '') {
        const select = document.getElementById('newLedgerGroup');
        if (!select) return;
        select.innerHTML = '<option value="">-- Loading Miracle Account Groups... --</option>';

        let targetDefault = defaultGroupCode;
        if (!targetDefault) {
            if (currentModule === 'Sales') targetDefault = 'G0000009'; // Sundry Debtors
            else if (currentModule === 'Purchases') targetDefault = 'G0000013'; // Sundry Creditors
            else targetDefault = 'G0000024'; // Indirect Expenses
        }

        try {
            const res = await fetch(`${API_URL}/api/groups${activeYearFolder ? '?year=' + activeYearFolder : ''}`);
            if (!res.ok) throw new Error("Failed to load account groups.");
            const data = await res.json();

            if (data.status === 'success' && data.data && data.data.length > 0) {
                select.innerHTML = '<option value="">-- Select Account Group --</option>';
                data.data.forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = g.code;
                    opt.textContent = `${g.code} - ${g.name} (${g.category || 'Group'})`;
                    if (g.code === targetDefault) opt.selected = true;
                    select.appendChild(opt);
                });
            } else {
                select.innerHTML = '<option value="G0000013">G0000013 - Sundry Creditors (Suppliers)</option><option value="G0000009">G0000009 - Sundry Debtors (Customers)</option><option value="G0000024">G0000024 - Indirect Expenses</option>';
            }
        } catch (err) {
            console.error("Error loading account groups:", err);
            select.innerHTML = '<option value="G0000013">G0000013 - Sundry Creditors (Suppliers)</option><option value="G0000009">G0000009 - Sundry Debtors (Customers)</option><option value="G0000024">G0000024 - Indirect Expenses</option>';
        }
    }

    function openCreateLedgerModal(defaultName = '', targetSelectId = null) {
        activeSelectIdForNewLedger = targetSelectId;
        const form = document.getElementById('createLedgerForm');
        if (form) form.reset();

        const nameInput = document.getElementById('newLedgerName');
        const printNameInput = document.getElementById('newLedgerPrintName');
        const modal = document.getElementById('createLedgerModal');

        if (nameInput) nameInput.value = defaultName;
        if (printNameInput) printNameInput.value = defaultName;
        if (modal) modal.classList.remove('hidden');

        loadAccountGroupsDropdown();
    }

    const newLedgerGstinInput = document.getElementById('newLedgerGstin');
    if (newLedgerGstinInput) {
        newLedgerGstinInput.addEventListener('input', () => {
            const val = newLedgerGstinInput.value.trim().toUpperCase();
            if (val.length >= 2) {
                const stCode = val.substring(0, 2);
                const stSelect = document.getElementById('newLedgerStateCode');
                if (stSelect && stSelect.querySelector(`option[value="${stCode}"]`)) {
                    stSelect.value = stCode;
                }
            }
            if (val.length >= 12) {
                const panVal = val.substring(2, 12);
                const panInput = document.getElementById('newLedgerPan');
                if (panInput && /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(panVal)) {
                    panInput.value = panVal;
                }
            }
        });
    }

    const closeLedgerModalBtn = document.getElementById('closeLedgerModalBtn');
    const cancelLedgerModalBtn = document.getElementById('cancelLedgerModalBtn');
    const createLedgerModal = document.getElementById('createLedgerModal');
    const createLedgerForm = document.getElementById('createLedgerForm');

    if (closeLedgerModalBtn && createLedgerModal) {
        closeLedgerModalBtn.addEventListener('click', () => createLedgerModal.classList.add('hidden'));
    }
    if (cancelLedgerModalBtn && createLedgerModal) {
        cancelLedgerModalBtn.addEventListener('click', () => createLedgerModal.classList.add('hidden'));
    }

    if (createLedgerForm) {
        createLedgerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('submitLedgerModalBtn');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating...';
            }

            const name = document.getElementById('newLedgerName').value.trim();
            const printName = document.getElementById('newLedgerPrintName') ? document.getElementById('newLedgerPrintName').value.trim() : '';
            const groupCode = document.getElementById('newLedgerGroup').value;
            const gstin = document.getElementById('newLedgerGstin').value.trim();
            const panNumber = document.getElementById('newLedgerPan') ? document.getElementById('newLedgerPan').value.trim() : '';
            const stateCode = document.getElementById('newLedgerStateCode') ? document.getElementById('newLedgerStateCode').value : '';
            const city = document.getElementById('newLedgerCity').value.trim();
            const saveMemory = document.getElementById('saveToMemoryVault').checked;

            try {
                const res = await fetch(`${API_URL}/api/create-ledger`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        print_name: printName || name,
                        group_code: groupCode,
                        gstin: gstin,
                        pan_number: panNumber,
                        state_code: stateCode,
                        city: city,
                        module_type: currentModule,
                        year: activeYearFolder,
                        save_memory: saveMemory
                    })
                });

                const data = await res.json();
                if (data.status === 'success') {
                    showToast(`✨ Created Miracle Ledger "${data.ledger_name}" (${data.ledger_code})!`);
                    if (createLedgerModal) createLedgerModal.classList.add('hidden');

                    // Refresh Miracle ledgers list
                    const refreshRes = await fetch(`${API_URL}/api/refresh-ledgers`, { method: 'POST' });
                    if (refreshRes.ok) {
                        const refreshData = await refreshRes.json();
                        clientLedgers = refreshData.data || [];
                    }

                    if (typeof activeSelectIdForNewLedger === 'number' && currentExtractedData && currentExtractedData[activeSelectIdForNewLedger]) {
                        currentExtractedData[activeSelectIdForNewLedger].mapped_ledger = data.ledger_name;
                        currentExtractedData[activeSelectIdForNewLedger].party_name = data.ledger_name;
                        currentExtractedData[activeSelectIdForNewLedger].party = data.ledger_name;
                    } else if (activeSelectIdForNewLedger) {
                        const targetSelect = document.getElementById(activeSelectIdForNewLedger);
                        if (targetSelect) {
                            targetSelect.innerHTML = generateLedgerOptions(data.ledger_name);
                            targetSelect.value = data.ledger_name;
                        }
                    }

                    // Update main data grid if matching rows exist in currentExtractedData
                    if (currentExtractedData && Array.isArray(currentExtractedData)) {
                        let updatedCount = 0;
                        currentExtractedData.forEach(row => {
                            const rawParty = String(row.party_name || row.party || "").trim();
                            const mapped = String(row.mapped_ledger || "").trim();
                            if (mapped === "Suspense Account" || mapped === "" || rawParty.toUpperCase().includes(name.toUpperCase()) || mapped.toUpperCase().includes(name.toUpperCase())) {
                                row.mapped_ledger = data.ledger_name;
                                row.party_name = data.ledger_name;
                                updatedCount++;
                            }
                        });
                        if (typeof renderGrid === 'function') {
                            renderGrid(currentExtractedData);
                        }
                    }
                } else {
                    alert(`❌ Failed to create ledger: ${data.message || 'Unknown error'}`);
                }
            } catch (err) {
                console.error("Error creating ledger:", err);
                alert(`❌ Error creating ledger: ${err.message}`);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            }
        });
    }

    let activeRowIndexForEditLedger = null;

    async function loadEditAccountGroupsDropdown(currentGroup = '') {
        const select = document.getElementById('editLedgerGroup');
        if (!select) return;
        select.innerHTML = '<option value="">-- Loading Account Groups... --</option>';

        try {
            const res = await fetch(`${API_URL}/api/groups${activeYearFolder ? '?year=' + activeYearFolder : ''}`);
            if (!res.ok) throw new Error("Failed to load account groups.");
            const data = await res.json();

            if (data.status === 'success' && data.data && data.data.length > 0) {
                select.innerHTML = '<option value="">-- Select Account Group --</option>';
                data.data.forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = g.code;
                    opt.textContent = `${g.code} - ${g.name} (${g.category || 'Group'})`;
                    if (currentGroup && (g.name.toUpperCase().includes(currentGroup.toUpperCase()) || g.code === currentGroup)) {
                        opt.selected = true;
                    }
                    select.appendChild(opt);
                });
            } else {
                select.innerHTML = '<option value="G0000013">G0000013 - Sundry Creditors (Suppliers)</option><option value="G0000009">G0000009 - Sundry Debtors (Customers)</option><option value="G0000024">G0000024 - Indirect Expenses</option>';
            }
        } catch (err) {
            console.error("Error loading account groups:", err);
        }
    }

    function openEditLedgerModal(rawLedgerName = '', rowIndex = null) {
        activeRowIndexForEditLedger = rowIndex;
        const form = document.getElementById('editLedgerForm');
        if (form) form.reset();

        const oldNameInput = document.getElementById('editLedgerOldName');
        const newNameInput = document.getElementById('editLedgerNewName');
        const printNameInput = document.getElementById('editLedgerPrintName');
        const modal = document.getElementById('editLedgerModal');

        const currentGroupHint = (rowIndex !== null && currentExtractedData && currentExtractedData[rowIndex]) ? (currentExtractedData[rowIndex].group_hint || '') : '';

        if (oldNameInput) oldNameInput.value = rawLedgerName;
        if (newNameInput) newNameInput.value = rawLedgerName;
        if (printNameInput) printNameInput.value = rawLedgerName;
        if (modal) modal.classList.remove('hidden');

        loadEditAccountGroupsDropdown(currentGroupHint);
    }

    const closeEditLedgerModalBtn = document.getElementById('closeEditLedgerModalBtn');
    const cancelEditLedgerModalBtn = document.getElementById('cancelEditLedgerModalBtn');
    const editLedgerModal = document.getElementById('editLedgerModal');
    const editLedgerForm = document.getElementById('editLedgerForm');

    if (closeEditLedgerModalBtn && editLedgerModal) {
        closeEditLedgerModalBtn.addEventListener('click', () => editLedgerModal.classList.add('hidden'));
    }
    if (cancelEditLedgerModalBtn && editLedgerModal) {
        cancelEditLedgerModalBtn.addEventListener('click', () => editLedgerModal.classList.add('hidden'));
    }

    if (editLedgerForm) {
        editLedgerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('submitEditLedgerModalBtn');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';
            }

            const oldName = document.getElementById('editLedgerOldName').value.trim();
            const newName = document.getElementById('editLedgerNewName').value.trim();
            const printName = document.getElementById('editLedgerPrintName').value.trim() || newName;
            const groupCode = document.getElementById('editLedgerGroup').value;
            const gstin = document.getElementById('editLedgerGstin').value.trim();
            const city = document.getElementById('editLedgerCity').value.trim();
            const syncDbf = document.getElementById('syncToMiracleDbf').checked;
            const saveMemory = document.getElementById('saveEditToMemoryVault').checked;

            try {
                const res = await fetch(`${API_URL}/api/update-ledger`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        old_name: oldName,
                        new_name: newName,
                        print_name: printName,
                        group_code: groupCode,
                        gstin: gstin,
                        city: city,
                        sync_dbf: syncDbf,
                        save_memory: saveMemory,
                        year: activeYearFolder
                    })
                });

                const data = await res.json();
                if (data.status === 'success') {
                    showToast(`✨ Updated Master Ledger "${newName}"!`);
                    if (editLedgerModal) editLedgerModal.classList.add('hidden');

                    const refreshRes = await fetch(`${API_URL}/api/refresh-ledgers`, { method: 'POST' });
                    if (refreshRes.ok) {
                        const refreshData = await refreshRes.json();
                        clientLedgers = refreshData.data || [];
                    }

                    if (typeof activeRowIndexForEditLedger === 'number' && currentExtractedData && currentExtractedData[activeRowIndexForEditLedger]) {
                        currentExtractedData[activeRowIndexForEditLedger].mapped_ledger = newName;
                        currentExtractedData[activeRowIndexForEditLedger].party_name = newName;
                    }

                    if (currentExtractedData && Array.isArray(currentExtractedData)) {
                        // Map groupCode to human-readable group name
                        const groupCodeToName = {
                            'G0000024': 'Indirect Expenses',
                            'G0000023': 'Direct Expenses',
                            'G0000017': 'Indirect Income',
                            'G0000016': 'Direct Income',
                            'G0000009': 'Sundry Debtors',
                            'G0000013': 'Sundry Creditors',
                            'G0000008': 'Investments',
                            'G0000001': 'Capital Account / Drawings',
                            'G0000002': 'Capital Account',
                            'G0000003': 'Secured Loans',
                            'G0000004': 'Unsecured Loans',
                            'G0000005': 'Cash-in-hand',
                            'G0000006': 'Duties & Taxes',
                            'G0000007': 'Fixed Assets',
                            'G0000010': 'Current Assets',
                            'G0000011': 'Bank Accounts',
                            'G0000012': 'Bank OD A/c',
                            'G0000014': 'Sales Accounts',
                            'G0000015': 'Purchase Accounts',
                            'G0000024': 'Indirect Expenses',
                            'G0000025': 'Suspense Account',
                        };
                        const newGroupHint = groupCodeToName[groupCode] || inferExpenseGroupHint(newName, '', null);

                        currentExtractedData.forEach(r => {
                            if ((r.mapped_ledger || '').trim().toLowerCase() === oldName.trim().toLowerCase() ||
                                (r.mapped_ledger || '').trim().toLowerCase() === newName.trim().toLowerCase()) {
                                r.mapped_ledger = newName;
                                r.party_name = newName;
                                r.group_hint = newGroupHint; // Update group too!
                                r.status = r.status === 'Suspense' ? 'Mapped' : r.status;
                            }
                        });
                        if (typeof renderGrid === 'function') {
                            renderGrid(currentExtractedData);
                            recalcGrandTotals();
                        }
                    }
                } else {
                    alert(`❌ Failed to update ledger: ${data.message || 'Unknown error'}`);
                }
            } catch (err) {
                console.error("Error updating ledger:", err);
                alert(`❌ Error updating ledger: ${err.message}`);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            }
        });
    }

    saveMappingBtn.addEventListener('click', () => {
        const selects = document.querySelectorAll('.mapping-select');
        let allMapped = true;
        
        selects.forEach(select => {
            if (select.value === "") {
                allMapped = false;
                select.classList.add('border-red-500', 'error-shake');
            } else {
                select.classList.remove('border-red-500', 'error-shake');
                const rowId = parseInt(select.getAttribute('data-id'));
                const row = pendingMockData.find(r => r.id === rowId);
                if (row) {
                    if (select.value === "AUTO_CREATE_B2C") {
                        const rawName = row.party.replace('UNKNOWN_PARTY: ', '').replace('UNKNOWN_NARRATION: ', '');
                        row.party = rawName;
                        row.status = 'Ready';
                        row.isB2C = true;
                        row.autoCreateB2B = false;
                    } else if (select.value === "AUTO_CREATE_B2B") {
                        const rawName = row.party.replace('UNKNOWN_PARTY: ', '').replace('UNKNOWN_NARRATION: ', '');
                        row.party = rawName;
                        row.status = 'Ready';
                        row.isB2C = false;
                        row.autoCreateB2B = true;
                    } else {
                        row.party = select.value;
                        row.status = 'Ready';
                        row.isB2C = false;
                        row.autoCreateB2B = false;
                    }
                }
            }
        });

        if (allMapped) {
            mappingModal.classList.add('hidden');
            checkClarifications(pendingMockData);
        }
    });

    cancelMappingBtn.addEventListener('click', () => {
        mappingModal.classList.add('hidden');
        pendingMockData = []; // Clear pending data
        renderEmptyState();
        docViewerTitle.innerHTML = '<i class="fa-regular fa-file-pdf mr-2"></i>No Document Loaded';
        docPlaceholder.innerHTML = '<i class="fa-regular fa-image text-4xl text-slate-600 mb-3 block"></i><p class="text-base text-slate-500">Document Viewer</p>';
    });

    // --- SEQUENTIAL CLARIFICATION FLOW ---
    function checkClarifications(data) {
        if (currentModule === 'Bank Statements' || currentModule === 'Opening Balances' || currentModule === 'Cash Entries') {
            finalizeExtraction(data);
            return;
        }
        // Step 1: Check Parties
        const unknownParties = data.filter(row => row.status === 'Review');
        if (unknownParties.length > 0) {
            pendingMockData = data;
            showMappingModal(unknownParties);
            return;
        }
        
        // Step 2: Check Products (Line Items)
        // Apply default product if selected
        const defaultProductSelect = document.getElementById('defaultProductSelect');
        const defaultProductVal = defaultProductSelect ? defaultProductSelect.value : '';
        if (defaultProductVal) {
            data.forEach(invoice => {
                if (Array.isArray(invoice.items)) {
                    invoice.items.forEach(item => {
                        const match = clientProducts.find(p => p.name === defaultProductVal);
                        if (match) {
                            item.name = match.name;
                            item.mapped_code = match.code;
                        }
                    });
                }
            });
        }

        const unknownProducts = [];
        data.forEach(invoice => {
            if (Array.isArray(invoice.items)) {
                invoice.items.forEach((item, idx) => {
                    const itemName = (item.name || '').trim();
                    if (!itemName) return;
                    
                    const match = clientProducts.find(p => 
                        p.name.trim().toUpperCase() === itemName.toUpperCase() ||
                        p.code.trim().toUpperCase() === itemName.toUpperCase()
                    );
                    
                    if (match) {
                        item.name = match.name;
                        item.mapped_code = match.code;
                    } else {
                        // Avoid duplicates in the clarification list
                        const key = `${itemName.toUpperCase()}|${item.hsn_code || ''}`;
                        if (!unknownProducts.some(p => p.key === key)) {
                            unknownProducts.push({
                                key: key,
                                name: itemName,
                                hsn_code: item.hsn_code || '',
                                uom: item.uom || '',
                                gst_pct: (item.gst_pct !== undefined && item.gst_pct !== null) ? item.gst_pct : 18.0,
                                invoiceId: invoice.id,
                                itemIndex: idx
                            });
                        }
                    }
                });
            }
        });
        
        if (unknownProducts.length > 0) {
            pendingMockData = data;
            showProductMappingModal(unknownProducts);
            return;
        }
        
        finalizeExtraction(data);
    }

    function generateProductOptions(selectedCode = "", rowGstPct = null) {
        let html = '<option value="">-- Select Miracle Product --</option>';
        html += `<option value="AUTO_CREATE_PRODUCT" ${selectedCode === 'AUTO_CREATE_PRODUCT' ? 'selected' : ''} class="text-purple-400 font-semibold">[Auto-Create ${rowGstPct !== null && rowGstPct !== undefined ? rowGstPct + '% ' : ''}Product]</option>`;
        
        if (clientProducts && clientProducts.length > 0) {
            // Group products by category / commodity
            const categories = {};
            clientProducts.forEach(prod => {
                const cat = (prod.category || prod.commodity || prod.commodity_type || "General Stock").trim();
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(prod);
            });

            const sortedCategories = Object.keys(categories).sort();
            sortedCategories.forEach(catName => {
                html += `<optgroup label="📦 ${catName.toUpperCase()}">`;
                categories[catName].forEach(prod => {
                    const isSelected = (prod.name === selectedCode || prod.code === selectedCode);
                    const pName = (prod.name || "").toUpperCase();
                    let matchesGst = false;
                    if (rowGstPct !== null && rowGstPct !== undefined) {
                        const gInt = Math.round(rowGstPct).toString();
                        if (pName.includes(`${gInt}%`) || pName.includes(`GST ${gInt}`) || pName.includes(`GST${gInt}`)) {
                            matchesGst = true;
                        }
                    }
                    const matchBadge = matchesGst ? ' ✅ [Matching GST Rate]' : '';
                    html += `<option value="${prod.name}" ${isSelected ? 'selected' : ''} class="${matchesGst ? 'text-emerald-400 font-bold' : ''}">${prod.name} (${prod.code})${matchBadge} ${prod.hsn_code ? '- HSN: ' + prod.hsn_code : ''}</option>`;
                });
                html += `</optgroup>`;
            });
        }
        return html;
    }

    async function showProductMappingModal(unknownProducts) {
        // Ensure products are loaded from DBFs across all years before building modal
        if (!clientProducts || clientProducts.length === 0) {
            try {
                const res = await fetch(`${API_URL}/api/products${activeYearFolder ? '?year=' + activeYearFolder : ''}`);
                if (res.ok) {
                    const data = await res.json();
                    clientProducts = data.data || [];
                }
            } catch (e) {
                console.error("Failed to pre-fetch products for mapping modal:", e);
            }
        }

        const productMappingModal = document.getElementById('productMappingModal');
        const productMappingList = document.getElementById('productMappingList');
        productMappingList.innerHTML = '';
        
        // Populate global product dropdown
        // Removed as it is now handled dynamically per GST group

        // Sort unknown products by GST % descending (e.g. 18%, 12%, 5%, 0%), then alphabetically
        unknownProducts.sort((a, b) => {
            if (b.gst_pct !== a.gst_pct) return b.gst_pct - a.gst_pct;
            return a.name.localeCompare(b.name);
        });
        
        let currentGst = null;
        
        unknownProducts.forEach((item, idx) => {
            const selectId = `prod-select-${idx}`;
            const optionsHtml = generateProductOptions("");
            
            // Inject GST Group Header if GST changed
            if (currentGst !== item.gst_pct) {
                currentGst = item.gst_pct;
                const groupClass = `gst-group-${currentGst.toString().replace('.', '-')}`;
                
                productMappingList.innerHTML += `
                    <div class="bg-brand-600/5 border border-brand-500/20 rounded-xl p-4 mt-4 mb-3 flex flex-col gap-2.5 shadow-sm">
                        <div class="flex justify-between items-center">
                            <label class="block text-base font-bold text-indigo-400 uppercase tracking-wider"><i class="fa-solid fa-layer-group mr-2"></i> ${currentGst}% GST Products</label>
                        </div>
                        <div class="flex gap-2 mt-1">
                            <select id="group-select-${groupClass}" class="bg-slate-900 border border-slate-800 rounded-xl py-2.5 px-3 text-slate-200 text-sm w-full focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 focus:ring-offset-obsidian-950 cursor-pointer">
                                ${optionsHtml}
                            </select>
                            <button type="button" class="apply-group-btn bg-brand-600 hover:bg-brand-500 text-white transform transition-all duration-200 hover:-translate-y-0.5 active:scale-95 px-4 py-2 rounded-xl text-sm font-bold transition whitespace-nowrap shadow-md" data-group="${groupClass}">
                                Apply to ${currentGst}% Items
                            </button>
                        </div>
                    </div>
                `;
            }
            
            const groupClass = `gst-group-${currentGst.toString().replace('.', '-')}`;
            
            productMappingList.innerHTML += `
                <div class="bg-slate-950/40 border border-slate-850 rounded-xl p-4 flex justify-between items-center mb-3 ml-4 border-l-2 border-l-brand-500/50 hover:bg-slate-900/60 transition">
                    <div>
                        <p class="text-base font-bold uppercase tracking-wider text-slate-500">New Unmapped Product / Item</p>
                        <p class="text-sm font-bold text-white mt-1">"${item.name}"</p>
                        <p class="text-base mt-1.5 text-indigo-400/90 font-semibold">
                            <span class="mr-3"><i class="fa-solid fa-barcode mr-1"></i> HSN: ${item.hsn_code || 'None'}</span>
                            <span class="mr-3"><i class="fa-solid fa-box mr-1"></i> UOM: ${item.uom || 'NOS'}</span>
                            <span><i class="fa-solid fa-percent mr-1"></i> GST: ${item.gst_pct}%</span>
                        </p>
                    </div>
                    <div class="w-1/2 flex gap-2">
                        <select id="${selectId}" class="product-mapping-select ${groupClass} w-full bg-slate-900 border border-slate-800 rounded-xl py-2 px-3 text-slate-200 text-sm focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 focus:ring-offset-obsidian-950 cursor-pointer" data-name="${(item.name || '').replace(/"/g, '&quot;')}">
                            ${optionsHtml}
                        </select>
                        <button class="refresh-products-btn bg-slate-900 hover:bg-slate-800 px-3 rounded-xl text-slate-350 transition border border-slate-800 flex items-center justify-center" title="Refresh Products from Miracle Database" data-select-id="${selectId}">
                            <i class="fa-solid fa-arrows-rotate"></i>
                        </button>
                    </div>
                </div>
            `;
        });

        // Wire up Apply to Group buttons
        document.querySelectorAll('.apply-group-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const groupClass = e.target.getAttribute('data-group');
                const groupSelect = document.getElementById(`group-select-${groupClass}`);
                const globalVal = groupSelect.value;
                if (globalVal) {
                    document.querySelectorAll(`.product-mapping-select.${groupClass}`).forEach(select => {
                        select.value = globalVal;
                    });
                }
            });
        });

        // Add event listeners to product refresh buttons
        document.querySelectorAll('.refresh-products-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const icon = e.currentTarget.querySelector('i');
                icon.classList.add('fa-spin', 'text-brand-500');
                
                const selectId = e.currentTarget.getAttribute('data-select-id');
                const selectEl = document.getElementById(selectId);
                const currentValue = selectEl.value;
                
                try {
                    const res = await fetch(`${API_URL}/api/refresh-products`, { method: 'POST' });
                    if (!res.ok) throw new Error("Refresh failed.");
                    const data = await res.json();
                    
                    clientProducts = data.data || [];
                    console.log(`Refreshed: ${clientProducts.length} products found.`);
                    
                    selectEl.innerHTML = generateProductOptions(currentValue);
                    
                    icon.classList.remove('fa-spin', 'text-brand-500');
                    icon.classList.add('text-emerald-500');
                    setTimeout(() => icon.classList.remove('text-emerald-500'), 1500);
                } catch (err) {
                    console.error("Refresh products error:", err);
                    icon.classList.remove('fa-spin', 'text-brand-500');
                    icon.classList.add('text-red-500');
                    setTimeout(() => icon.classList.remove('text-red-500'), 1500);
                }
            });
        });

        productMappingModal.classList.remove('hidden');
    }

    document.getElementById('saveProductMappingBtn').addEventListener('click', () => {
        const selects = document.querySelectorAll('.product-mapping-select');
        let allMapped = true;
        
        selects.forEach(select => {
            if (select.value === "") {
                allMapped = false;
                select.classList.add('border-red-500', 'error-shake');
            } else {
                select.classList.remove('border-red-500', 'error-shake');
                const rawName = (select.getAttribute('data-name') || '').trim();
                const selectedVal = select.value;
                
                // Update all matching items in pendingMockData
                pendingMockData.forEach(invoice => {
                    if (Array.isArray(invoice.items)) {
                        invoice.items.forEach(item => {
                            const itemName = (item.name || '').trim();
                            if (itemName && itemName.toUpperCase() === rawName.toUpperCase()) {
                                if (selectedVal === "AUTO_CREATE_PRODUCT") {
                                    item.autoCreate = true;
                                } else {
                                    item.name = selectedVal;
                                    item.autoCreate = false;
                                }
                            }
                        });
                    }
                });

                // Persist new keyword mapping rule to the backend
                if (selectedVal !== "AUTO_CREATE_PRODUCT" && rawName) {
                    fetch(`${API_URL}/api/teach_product_mapping`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            extracted_name: rawName,
                            mapped_product: selectedVal
                        })
                    }).then(res => res.json())
                      .then(d => console.log(`Persisted product mapping rule: ${rawName} -> ${selectedVal}`))
                      .catch(err => console.error("Error saving product mapping rule:", err));
                }
            }
        });
        
        if (allMapped) {
            document.getElementById('productMappingModal').classList.add('hidden');
            finalizeExtraction(pendingMockData);
        }
    });

    document.getElementById('cancelProductMappingBtn').addEventListener('click', () => {
        document.getElementById('productMappingModal').classList.add('hidden');
        pendingMockData = [];
        renderEmptyState();
        docViewerTitle.innerHTML = '<i class="fa-regular fa-file-pdf mr-2"></i>No Document Loaded';
        docPlaceholder.innerHTML = '<i class="fa-regular fa-image text-4xl text-slate-600 mb-3 block"></i><p class="text-base text-slate-500">Document Viewer</p>';
    });

    function normalizeRowFields(row, index = 0) {
        // Guarantee that bill numbers are auto-sequenced if blank
        const rawBill = String(row.billNo || row.bill_no || row.invoice_no || '').trim();
        if (!rawBill || rawBill.toLowerCase() === 'none' || rawBill.toLowerCase() === 'nan' || rawBill.toLowerCase() === 'null') {
            row.billNo = String(index + 1);
            row.bill_no = String(index + 1);
        } else {
            row.billNo = rawBill;
            row.bill_no = rawBill;
        }

        if (row.taxable === undefined || row.taxable === null || row.taxable === 0) {
            if (row.taxable_amount) row.taxable = parseFloat(row.taxable_amount) || 0;
        }
        if (row.gst === undefined || row.gst === null || row.gst === 0) {
            const g = parseFloat(row.gst_total || row.Total_GST || 0);
            const cgs = parseFloat(row.cgst || 0);
            const sgs = parseFloat(row.sgst || 0);
            const igs = parseFloat(row.igst || 0);
            row.gst = g > 0 ? g : (cgs + sgs + igs);
        }

        const disc = parseFloat(row.discount || 0);
        const frt = parseFloat(row.freight || 0);
        const tcs = parseFloat(row.tcs || 0);
        const tds = parseFloat(row.tds || 0);
        const tx = parseFloat(row.taxable || 0);
        const gst = parseFloat(row.gst || 0);

        const expNet = Math.round(((tx + frt) + gst + tcs - tds) * 100) / 100;
        const expGross = Math.round(((tx - disc + frt) + gst + tcs - tds) * 100) / 100;

        if (row.total === undefined || row.total === null || row.total === 0) {
            const t = parseFloat(row.grand_total || row.Grand_Total || row.total_amount || row.amount || 0);
            if (t > 0) row.total = t;
            else if (tx > 0 || gst > 0) row.total = (disc > 0 && tx > disc + 10) ? expGross : expNet;
        } else {
            // Re-verify calculated total if tax components exist
            const diffNet = Math.abs(row.total - expNet);
            const diffGross = Math.abs(row.total - expGross);
            if (diffNet > 0.05 && diffGross > 0.05) {
                row.total = (diffNet < diffGross) ? expNet : expGross;
            }
        }

        if (!row.party_gstin && row.gstin) row.party_gstin = row.gstin;
        if (!row.party_gstin && row.GSTIN) row.party_gstin = row.GSTIN;
        return row;
    }

    function parseDateForSort(dStr) {
        if (!dStr) return 0;
        const s = String(dStr).trim();
        if (/^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}$/.test(s)) {
            const parts = s.split(/[\/\-]/);
            return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0])).getTime();
        }
        if (/^\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}$/.test(s)) {
            const parts = s.split(/[\/\-]/);
            return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2])).getTime();
        }
        const t = new Date(s).getTime();
        return isNaN(t) ? 0 : t;
    }

    function finalizeExtraction(data) {
        // Normalize all field names before storing or rendering
        currentExtractedData = (data || []).map((r, i) => normalizeRowFields(r, i));
        
        // Auto-sort by Date ascending (earliest to latest) upon extraction
        currentExtractedData.sort((a, b) => parseDateForSort(a.date || a.Date) - parseDateForSort(b.date || b.Date));
        currentSortField = 'date';
        currentSortOrder = 'asc';

        renderFilterBadgesForModule();
        renderGrid(currentExtractedData);
        recalcGrandTotals();
        setTimeout(() => recalcGrandTotals(), 300);
        pushBtn.disabled = false;
        pushBtn.classList.remove('cursor-not-allowed', 'opacity-50');
    }

    // --- GRID RENDERING ---
    function renderEmptyState() {
        const ctrlBar = document.getElementById('gridControlBar');
        if (ctrlBar) ctrlBar.classList.remove('hidden');
        currentExtractedData = [];
        currentGridFilter = 'all';
        renderFilterBadgesForModule();
        updateFilterCounts();

        const mLower = String(currentModule || '').toLowerCase();
        let emptyDesc = 'Upload a PDF, image, or Excel file — Gemini AI will instantly extract and map all transactions.';
        if (mLower.includes('bank')) emptyDesc = 'Upload a Bank Statement (PDF, Excel, CSV) — Gemini AI will extract and map all transactions.';
        else if (mLower.includes('cash')) emptyDesc = 'Upload Cash Vouchers or Daybook — Gemini AI will extract and map all transactions.';
        else if (mLower.includes('purchase')) emptyDesc = 'Upload Purchase Bills (PDF, Image, Excel) — Gemini AI will extract and map all entries.';
        else if (mLower.includes('sale')) emptyDesc = 'Upload Sales Invoices (PDF, Image, Excel) — Gemini AI will extract and map all entries.';

        gridHeaderRow.innerHTML = '<th class="py-3"></th>';
        gridBody.innerHTML = `
            <tr>
                <td colspan="100" class="text-center py-0">
                    <div class="flex flex-col items-center justify-center py-10 md:py-14 px-6 space-y-4 max-w-sm mx-auto">
                        <div class="relative">
                            <div class="absolute inset-0 bg-brand-500/10 blur-2xl rounded-full scale-150"></div>
                            <div class="relative h-16 w-16 bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700/80 rounded-2xl flex items-center justify-center shadow-2xl">
                                <i class="fa-solid fa-cloud-arrow-up text-2xl text-brand-400"></i>
                                <div class="absolute -bottom-1.5 -right-1.5 h-6 w-6 bg-brand-600 rounded-lg flex items-center justify-center border-2 border-slate-950 animate-bounce" style="animation-duration:3s">
                                    <i class="fa-solid fa-sparkles text-white text-[10px]"></i>
                                </div>
                            </div>
                        </div>
                        <div class="text-center">
                            <p class="text-sm font-bold text-white uppercase tracking-wider font-heading">No Entries Loaded Yet</p>
                            <p class="text-xs text-slate-400 mt-1 leading-relaxed max-w-[260px]">${emptyDesc}</p>
                        </div>
                        <div class="flex gap-2 mt-0.5">
                            <button onclick="document.getElementById('fileInput').click()" class="bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs px-3.5 py-2 rounded-xl transition shadow-lg shadow-brand-600/30 flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-folder-open"></i> Browse Files
                            </button>
                            <button onclick="document.getElementById('addEntryBtn').click()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs px-3.5 py-2 rounded-xl transition border border-slate-700 flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-plus"></i> Add Manually
                            </button>
                        </div>
                    </div>
                </td>
            </tr>
        `;
        if (docViewerTitle) docViewerTitle.innerHTML = `<i class="fa-regular fa-file-pdf mr-2 text-brand-500"></i>No Document Loaded`;
        if (docViewerTitle && docViewerTitle.nextElementSibling) docViewerTitle.nextElementSibling.innerText = `0 of 0`;
        if (docPlaceholder) docPlaceholder.innerHTML = `
            <div class="h-16 w-16 bg-slate-900/50 border border-slate-800/80 rounded-2xl flex items-center justify-center mb-3">
                <i class="fa-regular fa-image text-3xl text-slate-700 animate-pulse"></i>
            </div>
            <p class="text-sm text-slate-400 font-bold uppercase tracking-wider font-heading">Document Viewer</p>
            <p class="text-xs text-slate-600 text-center mt-1.5 max-w-[220px] leading-relaxed">Upload a transaction document to review it side-by-side with AI extractions.</p>
        `;
        recalcGrandTotals();
        pushBtn.disabled = true;
        pushBtn.classList.add('cursor-not-allowed', 'opacity-50');
    }

    let currentSortField = null;
    let currentSortOrder = 'asc';

    function getSortIcon(field) {
        if (currentSortField !== field) return `<i class="fa-solid fa-sort ml-1 text-xs opacity-40 hover:opacity-100"></i>`;
        return currentSortOrder === 'asc' 
            ? `<i class="fa-solid fa-sort-up ml-1 text-xs text-brand-500"></i>` 
            : `<i class="fa-solid fa-sort-down ml-1 text-xs text-brand-500"></i>`;
    }

    function saveGridToExtractedData() {
        // No-op. Data is updated reactively in real-time.
    }

    function handleSort(field) {
        if (!currentExtractedData || !Array.isArray(currentExtractedData) || currentExtractedData.length === 0) return;
        saveGridToExtractedData();
        
        if (currentSortField === field) {
            currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            currentSortField = field;
            currentSortOrder = 'asc';
        }
        
        currentExtractedData.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];
            
            if (field === 'date') {
                const tA = parseDateForSort(valA || a.Date);
                const tB = parseDateForSort(valB || b.Date);
                return currentSortOrder === 'asc' ? tA - tB : tB - tA;
            }
            if (field === 'gst_pct') {
                const nA = parseFloat(a.gst_pct) || 0;
                const nB = parseFloat(b.gst_pct) || 0;
                return currentSortOrder === 'asc' ? nA - nB : nB - nA;
            }
            if (field === 'taxable' || field === 'gst' || field === 'total' || field === 'balance' || field === 'qty' || field === 'quantity' || field === 'discount') {
                const nA = parseFloat(valA) || 0;
                const nB = parseFloat(valB) || 0;
                return currentSortOrder === 'asc' ? nA - nB : nB - nA;
            }
            if (field === 'withdrawal') {
                const nA = a.transaction_type === 'Payment' ? (parseFloat(a.amount) || 0) : 0;
                const nB = b.transaction_type === 'Payment' ? (parseFloat(b.amount) || 0) : 0;
                return currentSortOrder === 'asc' ? nA - nB : nB - nA;
            }
            if (field === 'deposit') {
                const nA = a.transaction_type === 'Receipt' ? (parseFloat(a.amount) || 0) : 0;
                const nB = b.transaction_type === 'Receipt' ? (parseFloat(b.amount) || 0) : 0;
                return currentSortOrder === 'asc' ? nA - nB : nB - nA;
            }
            
            const sA = String(valA || '').toLowerCase();
            const sB = String(valB || '').toLowerCase();
            if (sA < sB) return currentSortOrder === 'asc' ? -1 : 1;
            if (sA > sB) return currentSortOrder === 'asc' ? 1 : -1;
            return 0;
        });
        
        renderGrid(currentExtractedData);
        recalcGrandTotals();
    }

    function renderGrid(data) {
        console.log("renderGrid called! data length:", data ? data.length : 0, "data:", data);
        currentExtractedData = data;
        if (typeof saveGridSnapshotToLocalStorage === 'function') {
            saveGridSnapshotToLocalStorage();
        }
        gridBody.innerHTML = '';
        const headerRow = document.getElementById('gridHeaderRow');
        if (!headerRow) {
            console.error("gridHeaderRow element not found!");
            return;
        }

        let hasDiscount = false, hasFreight = false, hasTcs = false, hasTds = false;
        data.forEach(row => {
            if (row.discount > 0) hasDiscount = true;
            if (row.freight > 0) hasFreight = true;
            if (row.tcs > 0) hasTcs = true;
            if (row.tds > 0) hasTds = true;
        });

        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            const opBalContainer = document.getElementById('openingBalanceContainer');
            if(opBalContainer) opBalContainer.classList.remove('hidden');
            headerRow.innerHTML = `
                <th class="px-2 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider text-center" style="width:40px;min-width:40px"><input type="checkbox" id="selectAllGridRows" class="cursor-pointer" title="Select All Rows"></th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="width:145px;min-width:145px" data-sort="date">Date ${getSortIcon('date')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="width:145px;min-width:145px" data-sort="reference_no">Ref / UTR ${getSortIcon('reference_no')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="min-width:260px" data-sort="narration">Narration / Description ${getSortIcon('narration')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider" style="min-width:240px">Mapped Ledger</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:130px;min-width:130px" data-sort="withdrawal">Dr (Out) ${getSortIcon('withdrawal')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:130px;min-width:130px" data-sort="deposit">Cr (In) ${getSortIcon('deposit')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right" style="width:145px;min-width:145px">Closing Bal</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:155px;min-width:155px">Status</th>
                <th class="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:44px;min-width:44px"></th>
            `;
        } else if (currentModule === 'Opening Balances') {
            const opBalContainer = document.getElementById('openingBalanceContainer');
            if(opBalContainer) opBalContainer.classList.add('hidden');
            headerRow.innerHTML = `
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="min-width:200px" data-sort="ledger_name">Ledger Name ${getSortIcon('ledger_name')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider" style="width:160px;min-width:160px">Match Status</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:100px;min-width:100px">Dr / Cr</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:160px;min-width:160px" data-sort="balance">Balance Amount ${getSortIcon('balance')}</th>
                <th class="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:44px;min-width:44px"></th>
            `;
        } else {
            const opBalContainer = document.getElementById('openingBalanceContainer');
            if(opBalContainer) opBalContainer.classList.add('hidden');
            headerRow.innerHTML = `
                <th class="px-2 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider text-center" style="width:40px;min-width:40px"><input type="checkbox" id="selectAllGridRows" class="cursor-pointer" title="Select All Rows"></th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="width:140px;min-width:140px" data-sort="date">Date ${getSortIcon('date')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="width:110px;min-width:110px" data-sort="billNo">Bill No ${getSortIcon('billNo')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition select-none sortable-header" style="min-width:200px" data-sort="party">Party Name ${getSortIcon('party')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:70px;min-width:70px" data-sort="qty">Qty ${getSortIcon('qty')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:120px;min-width:120px" data-sort="taxable">Taxable ${getSortIcon('taxable')}</th>
                ${hasDiscount ? '<th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right" style="width:100px;min-width:100px">Discount</th>' : ''}
                ${hasFreight ? '<th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right" style="width:100px;min-width:100px">Freight</th>' : ''}
                ${hasTcs ? '<th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right" style="width:90px;min-width:90px">TCS</th>' : ''}
                ${hasTds ? '<th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right" style="width:90px;min-width:90px">TDS</th>' : ''}
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center cursor-pointer hover:text-white transition select-none sortable-header" style="width:85px;min-width:85px" data-sort="gst_pct">GST % ${getSortIcon('gst_pct')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:110px;min-width:110px" data-sort="gst">GST Amt ${getSortIcon('gst')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-right cursor-pointer hover:text-white transition select-none sortable-header" style="width:120px;min-width:120px" data-sort="total">Total ${getSortIcon('total')}</th>
                <th class="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:140px;min-width:140px">Status</th>
                <th class="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider text-center" style="width:44px;min-width:44px"></th>
            `;
        }

        headerRow.querySelectorAll('.sortable-header').forEach(th => {
            th.addEventListener('click', () => {
                const sortField = th.getAttribute('data-sort');
                if (sortField) handleSort(sortField);
            });
        });

        // Set up the virtual scroll listener once on the container
        const container = document.getElementById('gridTableContainer');
        if (container && !container.dataset.listenerAttached) {
            container.dataset.listenerAttached = 'true';
            container.addEventListener('scroll', () => {
                renderVirtualGridRows();
            });
        }

        renderVirtualGridRows();
        // Defer recalc until AFTER browser paints all virtual rows — prevents race conditions
        requestAnimationFrame(() => recalcGrandTotals());
    }

    let currentGridFilter = 'all';
    let currentGridSearch = '';

    function renderFilterBadgesForModule() {
        const group = document.getElementById('filterBadgesGroup');
        const searchInput = document.getElementById('gridSearchInput');
        if (!group) return;

        let badgesHtml = '';
        if (currentModule === 'Sales') {
            if (searchInput) searchInput.placeholder = "Search invoice #, party, GSTIN, HSN, amount...";
            badgesHtml = `
                <button class="grid-filter-btn ${currentGridFilter === 'all' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="all">
                    All Sales (<span id="countFilterAll">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'b2b' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="b2b">
                    <i class="fa-solid fa-building-circle-check text-cyan-400 mr-1"></i> B2B Registered (<span id="countFilterB2B">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'b2c' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="b2c">
                    <i class="fa-solid fa-user text-indigo-400 mr-1"></i> B2C Retail (<span id="countFilterB2C">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'discount' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="discount">
                    <i class="fa-solid fa-percent text-emerald-400 mr-1"></i> With Discount (<span id="countFilterDiscount">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'gst_5' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="gst_5">
                    <i class="fa-solid fa-tag text-cyan-400 mr-1"></i> 5% GST (<span id="countFilterGst5">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'gst_0' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="gst_0">
                    <i class="fa-solid fa-ban text-slate-400 mr-1"></i> 0% Exempt (<span id="countFilterGst0">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'igst' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="igst">
                    <i class="fa-solid fa-plane-departure text-purple-400 mr-1"></i> Inter-State IGST (<span id="countFilterIGST">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'gst_mismatch' ? 'active bg-rose-600/20 text-rose-400 border-rose-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="gst_mismatch">
                    <i class="fa-solid fa-triangle-exclamation text-rose-400 mr-1"></i> GST Mismatch (<span id="countFilterGstMismatch">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'autocreate_item' ? 'active bg-cyan-600/20 text-cyan-400 border-cyan-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="autocreate_item">
                    <i class="fa-solid fa-boxes-packing text-cyan-400 mr-1"></i> Unmapped Items (<span id="countFilterAutoItem">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'review' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="review">
                    <i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i> Review (<span id="countFilterReview">0</span>)
                </button>
            `;
        } else if (currentModule === 'Purchases') {
            if (searchInput) searchInput.placeholder = "Search bill #, supplier, GSTIN, HSN, amount...";
            badgesHtml = `
                <button class="grid-filter-btn ${currentGridFilter === 'all' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="all">
                    All Purchases (<span id="countFilterAll">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'b2b' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="b2b">
                    <i class="fa-solid fa-truck-field text-emerald-400 mr-1"></i> B2B Vendors (<span id="countFilterB2B">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'b2c' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="b2c">
                    <i class="fa-solid fa-cash-register text-amber-400 mr-1"></i> Unregistered / Cash (<span id="countFilterB2C">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'freight' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="freight">
                    <i class="fa-solid fa-box text-cyan-400 mr-1"></i> Freight & Addons (<span id="countFilterFreight">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'review' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="review">
                    <i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i> Review (<span id="countFilterReview">0</span>)
                </button>
            `;
        } else {
            if (searchInput) searchInput.placeholder = "Search narration, ref/UTR, party, amount...";
            badgesHtml = `
                <button class="grid-filter-btn ${currentGridFilter === 'all' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="all">
                    All (<span id="countFilterAll">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'receipts' ? 'active bg-emerald-600/20 text-emerald-400 border-emerald-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="receipts">
                    <i class="fa-solid fa-arrow-down-left text-emerald-400 mr-1"></i> Receipts (<span id="countFilterReceipts">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'payments' ? 'active bg-rose-600/20 text-rose-400 border-rose-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="payments">
                    <i class="fa-solid fa-arrow-up-right text-rose-400 mr-1"></i> Payments (<span id="countFilterPayments">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'mapped' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="mapped">
                    <i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> Mapped (<span id="countFilterMapped">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'autocreate' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition whitespace-nowrap" data-filter="autocreate">
                    <i class="fa-solid fa-circle-plus text-cyan-400 mr-1"></i> Auto-Create (<span id="countFilterAutoCreate">0</span>)
                </button>
                <button class="grid-filter-btn ${currentGridFilter === 'review' ? 'active bg-brand-600/20 text-brand-400 border-brand-500/30' : 'border-slate-800 text-slate-400 hover:text-white'} text-xs font-bold px-2.5 py-1 rounded-lg border transition" data-filter="review">
                    <i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i> Review (<span id="countFilterReview">0</span>)
                </button>
            `;
        }

        group.innerHTML = badgesHtml;

        // Immediately update counts now that badge spans exist in DOM
        requestAnimationFrame(() => recalcGrandTotals());

        group.querySelectorAll('.grid-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                group.querySelectorAll('.grid-filter-btn').forEach(b => {
                    b.classList.remove('active', 'bg-brand-600/20', 'text-brand-400', 'border-brand-500/30', 'bg-emerald-600/20', 'text-emerald-400', 'border-emerald-500/30', 'bg-rose-600/20', 'text-rose-400', 'border-rose-500/30');
                    b.classList.add('border-slate-800', 'text-slate-400');
                });
                btn.classList.add('active', 'bg-brand-600/20', 'text-brand-400', 'border-brand-500/30');
                btn.classList.remove('border-slate-800', 'text-slate-400');
                currentGridFilter = btn.getAttribute('data-filter') || 'all';
                recalcGrandTotals();
                renderVirtualGridRows();
            });
        });
    }

    function getFilteredData() {
        if (!currentExtractedData || !Array.isArray(currentExtractedData)) return [];
        return currentExtractedData.filter(row => {
            const gstin = (row.party_gstin || row.gstin || row.GSTIN || row.Party_GSTIN || "").trim();
            const hasGstin = gstin.length >= 10;
            const mappedLedgerStr = (row.mapped_ledger || row.party_name || row.party || "").trim().toUpperCase();
            const isSuspense = !mappedLedgerStr || mappedLedgerStr === "SUSPENSE ACCOUNT" || mappedLedgerStr.indexOf("UNKNOWN_PARTY:") === 0;
            const txType = (row.transaction_type || row.Transaction_Type || 'Receipt').toLowerCase();

            if (currentGridFilter !== 'all') {
                if (currentModule === 'Sales') {
                    if (currentGridFilter === 'b2b' && (!hasGstin || row.isB2C)) return false;
                    if (currentGridFilter === 'b2c' && (hasGstin && !row.isB2C)) return false;
                    if (currentGridFilter === 'discount' && parseCurrency(row.discount || row.Discount || 0) <= 0) return false;
                    if (currentGridFilter === 'gst_5' && Math.abs((parseFloat(row.gst_pct) || 0) - 5.0) > 0.5) return false;
                    if (currentGridFilter === 'gst_0' && (parseFloat(row.gst_pct) || 0) > 0.5) return false;
                    if (currentGridFilter === 'igst' && parseCurrency(row.igst || row.IGST || 0) <= 0) return false;
                    if (currentGridFilter === 'gst_mismatch') {
                        const hasMismatchFlag = row.flags && (row.flags.includes("GST DBF Mismatch") || row.flags.includes("GST Mismatch"));
                        const isLowConf = (row.confidence_score !== undefined && row.confidence_score < 75);
                        if (!hasMismatchFlag && !isLowConf) return false;
                    }
                    if (currentGridFilter === 'autocreate_item') {
                        const itemName = (row.items && row.items.length > 0) ? row.items[0].name : "";
                        if (itemName !== "AUTO_CREATE_PRODUCT" && itemName !== "") return false;
                    }
                    if (currentGridFilter === 'review' && !isSuspense) return false;
                } else if (currentModule === 'Purchases') {
                    if (currentGridFilter === 'b2b' && !hasGstin) return false;
                    if (currentGridFilter === 'b2c' && hasGstin) return false;
                    if (currentGridFilter === 'freight' && parseCurrency(row.freight || row.Freight || 0) <= 0 && parseCurrency(row.discount || row.Discount || 0) <= 0) return false;
                    if (currentGridFilter === 'review' && !isSuspense) return false;
                } else {
                    if (currentGridFilter === 'receipts' && txType !== 'receipt') return false;
                    if (currentGridFilter === 'payments' && txType !== 'payment') return false;

                    let exists = false;
                    if (clientLedgers && clientLedgers.length > 0 && !isSuspense) {
                        exists = !!findMatchingClientLedger(mappedLedgerStr, clientLedgers) || clientLedgers.some(led => 
                            led.name.trim().toUpperCase() === mappedLedgerStr || 
                            led.print_name.trim().toUpperCase() === mappedLedgerStr ||
                            led.code.trim().toUpperCase() === mappedLedgerStr
                        );
                    }
                    if (currentGridFilter === 'review' && !isSuspense) return false;
                    if (currentGridFilter === 'mapped' && (isSuspense || !exists)) return false;
                    if (currentGridFilter === 'autocreate' && (isSuspense || exists)) return false;
                }
            }

            if (currentGridSearch) {
                const q = currentGridSearch.toLowerCase().trim();
                let exists = false;
                if (clientLedgers && clientLedgers.length > 0 && !isSuspense) {
                    exists = !!findMatchingClientLedger(mappedLedgerStr, clientLedgers) || clientLedgers.some(led => 
                        led.name.trim().toUpperCase() === mappedLedgerStr || 
                        led.print_name.trim().toUpperCase() === mappedLedgerStr ||
                        led.code.trim().toUpperCase() === mappedLedgerStr
                    );
                }
                const statusTag = isSuspense ? "review suspense" : (exists ? "mapped" : "autocreate auto-create");
                const numVal = parseCurrency(row.amount || row.total || 0);
                const formattedNum = numVal ? numVal.toLocaleString('en-IN') : '';
                const groupTag = (row.group_hint || "").toLowerCase();

                const itemNames = (row.items || []).map(i => `${i.name || ''} ${i.hsn_code || i.hsn || ''}`).join(' ');
                const textStr = `${row.date || ''} ${row.billNo || row.bill_no || ''} ${row.reference_no || ''} ${row.party || row.party_name || ''} ${row.mapped_ledger || ''} ${row.narration || ''} ${gstin} ${itemNames} ${row.total || row.amount || ''} ${formattedNum} ${txType} ${groupTag} ${statusTag}`.toLowerCase();
                
                if (!textStr.includes(q)) return false;
            }
            return true;
        });
    }

    function updateFilterCounts() {
        if (!currentExtractedData || !Array.isArray(currentExtractedData)) return;

        let cntAll = currentExtractedData.length;
        let cntMapped = 0, cntAutoCreate = 0, cntReview = 0;
        let cntReceipts = 0, cntPayments = 0;
        let cntB2B = 0, cntB2C = 0, cntIGST = 0, cntFreight = 0, cntDiscount = 0, cntGst5 = 0, cntGst0 = 0;
        let cntGstMismatch = 0, cntAutoItem = 0;

        let sumDr = 0, sumCr = 0;
        currentExtractedData.forEach(r => {
            const gstin = (r.party_gstin || r.gstin || r.GSTIN || r.Party_GSTIN || "").trim();
            const hasGstin = gstin.length >= 10;
            const mappedLedgerStr = (r.mapped_ledger || r.party_name || r.party || "").trim().toUpperCase();
            const isSuspense = !mappedLedgerStr || mappedLedgerStr === "SUSPENSE ACCOUNT" || mappedLedgerStr.indexOf("UNKNOWN_PARTY:") === 0;
            const txType = (r.transaction_type || r.Transaction_Type || 'Receipt').toLowerCase();
            const amtVal = parseCurrency(r.amount || r.total || 0);

            if (hasGstin && !r.isB2C) cntB2B++;
            else cntB2C++;

            if (parseCurrency(r.igst || r.IGST || 0) > 0) cntIGST++;
            if ((parseCurrency(r.freight || r.Freight || 0)) > 0) cntFreight++;
            if (parseCurrency(r.discount || r.Discount || 0) > 0) cntDiscount++;
            
            const gPct = parseFloat(r.gst_pct) || 0;
            if (Math.abs(gPct - 5.0) <= 0.5) cntGst5++;
            if (gPct <= 0.5) cntGst0++;

            const hasMismatchFlag = r.flags && (r.flags.includes("GST DBF Mismatch") || r.flags.includes("GST Mismatch"));
            const isLowConf = (r.confidence_score !== undefined && r.confidence_score < 75);
            if (hasMismatchFlag || isLowConf) cntGstMismatch++;

            const itemName = (r.items && r.items.length > 0) ? r.items[0].name : "";
            if (itemName === "AUTO_CREATE_PRODUCT" || itemName === "") cntAutoItem++;

            if (txType === 'receipt') {
                cntReceipts++;
                sumCr += amtVal;
            } else if (txType === 'payment') {
                cntPayments++;
                sumDr += amtVal;
            }

            if (isSuspense) {
                cntReview++;
            } else {
                let exists = false;
                if (clientLedgers && clientLedgers.length > 0) {
                    exists = !!findMatchingClientLedger(mappedLedgerStr, clientLedgers) || clientLedgers.some(led => 
                        led.name.trim().toUpperCase() === mappedLedgerStr || 
                        led.print_name.trim().toUpperCase() === mappedLedgerStr ||
                        led.code.trim().toUpperCase() === mappedLedgerStr
                    );
                }
                if (exists) cntMapped++;
                else cntAutoCreate++;
            }
        });

        const setTxt = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.innerText = val;
        };

        setTxt('countFilterAll', cntAll);
        setTxt('countFilterReceipts', cntReceipts);
        setTxt('countFilterPayments', cntPayments);
        setTxt('countFilterMapped', cntMapped);
        setTxt('countFilterAutoCreate', cntAutoCreate);
        setTxt('countFilterReview', cntReview);
        setTxt('countFilterB2B', cntB2B);
        setTxt('countFilterB2C', cntB2C);
        setTxt('countFilterDiscount', cntDiscount);
        setTxt('countFilterGst5', cntGst5);
        setTxt('countFilterGst0', cntGst0);
        setTxt('countFilterIGST', cntIGST);
        setTxt('countFilterFreight', cntFreight);
        setTxt('countFilterGstMismatch', cntGstMismatch);
        setTxt('countFilterAutoItem', cntAutoItem);
    }

    // Set up the virtual scroll listener once on the container
    const container = document.getElementById('gridTableContainer');
    if (container && !container.dataset.listenerAttached) {
        container.dataset.listenerAttached = 'true';
        let isTicking = false;
        container.addEventListener('scroll', () => {
            if (!isTicking) {
                window.requestAnimationFrame(() => {
                    renderVirtualGridRows();
                    isTicking = false;
                });
                isTicking = true;
            }
        }, { passive: true });
    }

    function populateGlobalLedgersDatalist() {
        const datalist = document.getElementById('globalMiracleLedgersDatalist');
        if (!datalist) return;
        let optionsHtml = '';

        const autoLedgers = (typeof globalAutoCreateLedgers !== 'undefined' && Array.isArray(globalAutoCreateLedgers)) ? globalAutoCreateLedgers : [];
        const hints = (typeof autoCreateLedgerHints !== 'undefined' && autoCreateLedgerHints) ? autoCreateLedgerHints : {};

        if (clientLedgers && Array.isArray(clientLedgers) && clientLedgers.length > 0) {
            clientLedgers.forEach(l => {
                const name = (l.name || '').trim();
                if (name) {
                    optionsHtml += `<option value="${name}">${l.group_name || 'Miracle Master'}</option>`;
                }
            });
        }

        if (autoLedgers.length > 0) {
            autoLedgers.forEach(ul => {
                const name = (ul || '').trim();
                if (name) {
                    const hint = hints[name.toUpperCase()] || (typeof inferExpenseGroupHint === 'function' ? inferExpenseGroupHint(name) : 'Auto-Create');
                    optionsHtml += `<option value="${name}">${name} (Auto-Create → ${hint})</option>`;
                }
            });
        }

        if (currentExtractedData && Array.isArray(currentExtractedData) && currentExtractedData.length > 0) {
            const seen = new Set();
            currentExtractedData.forEach(r => {
                if (r.mapped_ledger && r.mapped_ledger.toUpperCase() !== 'SUSPENSE ACCOUNT') {
                    const name = r.mapped_ledger.trim();
                    if (!seen.has(name.toUpperCase())) {
                        seen.add(name.toUpperCase());
                        optionsHtml += `<option value="${name}">${name}</option>`;
                    }
                }
            });
        }

        datalist.innerHTML = optionsHtml;
    }

    function renderVirtualGridRows() {
        if (!currentExtractedData || !Array.isArray(currentExtractedData)) return;
        populateGlobalLedgersDatalist();
        
        const container = document.getElementById('gridTableContainer');
        if (!container) return;

        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            calculateRollingBalances();
        }
        
        const displayData = getFilteredData();
        const totalRows = displayData.length;
        
        if (totalRows === 0) {
            let colSpan = 12;
            if (currentModule === 'Opening Balances') colSpan = 6;
            else if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') colSpan = 10;
            gridBody.innerHTML = `
                <tr id="emptyGridHeroRow">
                    <td colspan="${colSpan}" class="py-0">
                        <div class="flex flex-col items-center justify-center py-20 px-8">
                            <div class="relative mb-5">
                                <div class="absolute inset-0 bg-brand-500/8 blur-3xl rounded-full scale-[2]"></div>
                                <div class="relative h-20 w-20 bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700/80 rounded-3xl flex items-center justify-center shadow-2xl">
                                    <i class="fa-solid fa-cloud-arrow-up text-3xl text-brand-400"></i>
                                    <div class="absolute -bottom-2 -right-2 h-8 w-8 bg-brand-600 rounded-xl flex items-center justify-center border-2 border-slate-950 animate-bounce" style="animation-duration:3s">
                                        <i class="fa-solid fa-sparkles text-white text-xs"></i>
                                    </div>
                                </div>
                            </div>
                            <h3 class="text-base font-bold text-white font-heading">No Transactions Extracted Yet</h3>
                            <p class="text-xs text-slate-500 mt-2 max-w-[280px] text-center leading-relaxed">
                                Upload a Bank Statement, Purchase Bill, or Sales Invoice — Gemini AI will extract and map all entries automatically.
                            </p>
                            <div class="flex items-center gap-3 mt-6">
                                <button onclick="document.getElementById('fileInput').click()" class="bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl transition shadow-lg shadow-brand-600/30 flex items-center gap-2 cursor-pointer">
                                    <i class="fa-solid fa-folder-open"></i> Browse Files (Multiple)
                                </button>
                                <button onclick="document.getElementById('addEntryBtn').click()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs px-4 py-2.5 rounded-xl transition border border-slate-700 flex items-center gap-2 cursor-pointer">
                                    <i class="fa-solid fa-plus"></i> Add Manual Row
                                </button>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        // For datasets under 150 rows (e.g. Purchases/Sales), render natively for 100% smooth jitter-free scrolling
        if (totalRows <= 150) {
            if (gridBody.children.length === totalRows && !gridBody.dataset.needsFullRender) {
                return;
            }
            gridBody.dataset.needsFullRender = '';
            gridBody.innerHTML = '';
            
            let globalAutoCreateLedgers = [];
            let autoCreateLedgerHints = {};
            if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                const uniqueLedgers = new Set();
                currentExtractedData.forEach(d => {
                    const l = (d.mapped_ledger || "").trim();
                    if (l && l.toUpperCase() !== "SUSPENSE ACCOUNT") {
                        uniqueLedgers.add(l);
                        if (!autoCreateLedgerHints[l.toUpperCase()] && d.group_hint) {
                            autoCreateLedgerHints[l.toUpperCase()] = d.group_hint;
                        }
                    }
                });
                uniqueLedgers.forEach(ul => {
                    let exists = false;
                    if (clientLedgers && clientLedgers.length > 0) {
                        exists = clientLedgers.some(led => 
                            led.name.trim().toUpperCase() === ul.toUpperCase() || 
                            led.print_name.trim().toUpperCase() === ul.toUpperCase() ||
                            led.code.trim().toUpperCase() === ul.toUpperCase()
                        );
                    }
                    if (!exists) {
                        globalAutoCreateLedgers.push(ul);
                    }
                });
            }

            displayData.forEach((row, idx) => {
                const tr = createRowElement(row, idx, globalAutoCreateLedgers, autoCreateLedgerHints);
                gridBody.appendChild(tr);
            });
            return;
        }

        // For large datasets (>150 rows), use virtual slicing with generous buffer
        const scrollTop = container.scrollTop;
        const viewportHeight = container.clientHeight;
        const buffer = 20;
        const rowHeight = 72;
        
        const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - buffer);
        const endIndex = Math.min(totalRows, Math.floor((scrollTop + viewportHeight) / rowHeight) + buffer);
        
        const topPadding = startIndex * rowHeight;
        const bottomPadding = Math.max(0, (totalRows - endIndex) * rowHeight);
        
        gridBody.innerHTML = '';
        
        if (topPadding > 0) {
            const topSpacer = document.createElement('tr');
            topSpacer.style.height = `${topPadding}px`;
            let colSpan = 12;
            if (currentModule === 'Opening Balances') colSpan = 6;
            else if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') colSpan = 10;
            topSpacer.innerHTML = `<td colspan="${colSpan}" style="padding: 0; border: none; height: ${topPadding}px"></td>`;
            gridBody.appendChild(topSpacer);
        }
        
        const visibleSlice = displayData.slice(startIndex, endIndex);
        
        let globalAutoCreateLedgers = [];
        let autoCreateLedgerHints = {};
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            const uniqueLedgers = new Set();
            currentExtractedData.forEach(d => {
                const l = (d.mapped_ledger || "").trim();
                if (l && l.toUpperCase() !== "SUSPENSE ACCOUNT") {
                    uniqueLedgers.add(l);
                    if (!autoCreateLedgerHints[l.toUpperCase()] && d.group_hint) {
                        autoCreateLedgerHints[l.toUpperCase()] = d.group_hint;
                    }
                }
            });
            uniqueLedgers.forEach(ul => {
                let exists = false;
                if (clientLedgers && clientLedgers.length > 0) {
                    exists = clientLedgers.some(led => 
                        led.name.trim().toUpperCase() === ul.toUpperCase() || 
                        led.print_name.trim().toUpperCase() === ul.toUpperCase() ||
                        led.code.trim().toUpperCase() === ul.toUpperCase()
                    );
                }
                if (!exists) {
                    globalAutoCreateLedgers.push(ul);
                }
            });
        }

        visibleSlice.forEach((row, sliceIndex) => {
            const globalIndex = startIndex + sliceIndex;
            const tr = createRowElement(row, globalIndex, globalAutoCreateLedgers, autoCreateLedgerHints);
            gridBody.appendChild(tr);
        });
        
        if (bottomPadding > 0) {
            const bottomSpacer = document.createElement('tr');
            bottomSpacer.style.height = `${bottomPadding}px`;
            let colSpan = 12;
            if (currentModule === 'Opening Balances') colSpan = 6;
            else if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') colSpan = 10;
            bottomSpacer.innerHTML = `<td colspan="${colSpan}" style="padding: 0; border: none; height: ${bottomPadding}px"></td>`;
            gridBody.appendChild(bottomSpacer);
        }

        // Trigger Phase 4 GSTIN validation for visible rows
        const gstinElements = gridBody.querySelectorAll('.gstin-verify');
        gstinElements.forEach(async (el) => {
            const gstin = el.getAttribute('data-gstin');
            if (!gstin || el.dataset.checked === 'true') return;
            el.dataset.checked = 'true';
            try {
                const res = await fetch(`${API_URL}/api/verify_gstin`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gstin: gstin })
                });
                const data = await res.json();
                if (data.valid) {
                    el.innerHTML = `<i class="fa-solid fa-check text-emerald-500"></i> <span class="text-emerald-500">Verified</span>`;
                } else {
                    el.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-500"></i> <span class="text-amber-500" title="${data.message}">Invalid Format</span>`;
                }
            } catch (e) {
                el.innerHTML = `<i class="fa-solid fa-circle-xmark text-red-500"></i> <span class="text-red-500">Check Failed</span>`;
            } finally {
                // Always recalc after GSTIN verify resolves so filter counts & totals refresh
                recalcGrandTotals();
            }
        });

        // Trigger Phase 6 Bill Matching for Bank Statements visible rows
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            const billTargets = gridBody.querySelectorAll('.bill-match-target');
            billTargets.forEach(async (el) => {
                const party = el.getAttribute('data-party');
                const amt = parseFloat(el.getAttribute('data-amount')) || 0;
                if (!party || party.toUpperCase().includes('CASH') || amt <= 0 || el.dataset.checked === 'true') return;
                el.dataset.checked = 'true';
                try {
                    const res = await fetch(`${API_URL}/api/find_matching_bill`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ party_name: party, amount: amt })
                    });
                    const data = await res.json();
                    if (data.matched && data.bill_no) {
                        el.innerHTML = `<i class="fa-solid fa-link text-emerald-400"></i> <span class="text-emerald-400 font-semibold">Matches Invoice #${data.bill_no}</span>`;
                        el.classList.remove('hidden');
                    }
                } catch (e) {
                    console.error("Bill match failed", e);
                }
            });
        }

        // Bind Master Header Checkbox & Bulk Actions Toolbar
        const selectAllHeader = document.getElementById('selectAllGridRows');
        const bulkToolbar = document.getElementById('bulkActionToolbar');
        const selectedBadge = document.getElementById('selectedRowCountBadge');

        function updateBulkActionToolbar() {
            const checkedBoxes = gridBody.querySelectorAll('.row-select-checkbox:checked');
            const count = checkedBoxes.length;
            if (selectedBadge) selectedBadge.textContent = count;
            if (bulkToolbar) {
                if (count > 0) {
                    bulkToolbar.classList.remove('hidden');
                    const bulkSelectedProductSelect = document.getElementById('bulkSelectedProductSelect');
                    if (bulkSelectedProductSelect && bulkSelectedProductSelect.options.length <= 1) {
                        let bulkHtml = '<option value="">⚡ Set Product for Selected...</option>';
                        bulkHtml += generateProductOptions();
                        bulkSelectedProductSelect.innerHTML = bulkHtml;
                    }
                } else {
                    bulkToolbar.classList.add('hidden');
                }
            }
            if (selectAllHeader) {
                const totalBoxes = gridBody.querySelectorAll('.row-select-checkbox');
                selectAllHeader.checked = (totalBoxes.length > 0 && count === totalBoxes.length);
            }
        }

        if (selectAllHeader) {
            selectAllHeader.checked = false;
            selectAllHeader.onclick = (e) => {
                const isChecked = e.target.checked;
                gridBody.querySelectorAll('.row-select-checkbox').forEach(cb => cb.checked = isChecked);
                updateBulkActionToolbar();
            };
        }

        gridBody.querySelectorAll('.row-select-checkbox').forEach(cb => {
            cb.onchange = updateBulkActionToolbar;
        });

        // Bulk Action Toolbar Buttons
        const btnBulkApplyProduct = document.getElementById('btnBulkApplyProduct');
        const btnBulkDelete = document.getElementById('btnBulkDeleteSelected');
        const btnBulkToggle = document.getElementById('btnBulkToggleTxType');
        const btnBulkClear = document.getElementById('btnBulkClearSelection');

        if (btnBulkApplyProduct) {
            btnBulkApplyProduct.onclick = () => {
                const checkedBoxes = Array.from(gridBody.querySelectorAll('.row-select-checkbox:checked'));
                if (checkedBoxes.length === 0) {
                    showToast("No rows selected.", "info");
                    return;
                }
                const bulkSelectedProductSelect = document.getElementById('bulkSelectedProductSelect');
                if (!bulkSelectedProductSelect || !bulkSelectedProductSelect.value) {
                    showToast("Please select a Miracle product from the dropdown first.", "warning");
                    if (bulkSelectedProductSelect) bulkSelectedProductSelect.classList.add('border-amber-500', 'error-shake');
                    return;
                }
                if (bulkSelectedProductSelect) bulkSelectedProductSelect.classList.remove('border-amber-500', 'error-shake');

                const selectedVal = bulkSelectedProductSelect.value;
                let updatedCount = 0;
                checkedBoxes.forEach(cb => {
                    const idx = parseInt(cb.getAttribute('data-idx'));
                    if (!isNaN(idx) && currentExtractedData[idx]) {
                        const row = currentExtractedData[idx];
                        if (!Array.isArray(row.items)) row.items = [];
                        if (row.items.length === 0) {
                            row.items.push({ name: selectedVal, qty: 1, rate: 0, gst_pct: 18 });
                        } else {
                            row.items.forEach(item => {
                                item.name = selectedVal;
                                item.autoCreate = (selectedVal === "AUTO_CREATE_PRODUCT");
                            });
                        }
                        updatedCount++;
                    }
                });

                renderGrid(currentExtractedData);
                recalcGrandTotals();

                // Save rule to AI Memory Vault
                // BUG FIX: use the checked row's actual party name, not always currentExtractedData[0]
                if (selectedVal !== "AUTO_CREATE_PRODUCT" && checkedBoxes.length > 0) {
                    const firstIdx = parseInt(checkedBoxes[0].getAttribute('data-idx'));
                    const firstRow = (!isNaN(firstIdx) && currentExtractedData[firstIdx]) ? currentExtractedData[firstIdx] : null;
                    const sampleParty = firstRow
                        ? (firstRow.party_name || firstRow.party || firstRow.narration || "FOOTWEAR")
                        : "FOOTWEAR";
                    fetch(`${API_URL}/api/teach_product_mapping`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ extracted_name: sampleParty, mapped_product: selectedVal })
                    }).catch(err => console.error("Error saving bulk product mapping rule:", err));
                }

                showToast(`⚡ Successfully set product '${selectedVal}' for ${updatedCount} selected rows!`, "success");
            };
        }

        if (btnBulkDelete) {
            btnBulkDelete.onclick = () => {
                const checkedBoxes = Array.from(gridBody.querySelectorAll('.row-select-checkbox:checked'));
                if (checkedBoxes.length === 0) return;
                const indices = checkedBoxes.map(cb => parseInt(cb.getAttribute('data-idx'))).filter(n => !isNaN(n)).sort((a, b) => b - a);
                if (confirm(`Are you sure you want to delete ${indices.length} selected row(s)?`)) {
                    indices.forEach(idx => {
                        if (idx >= 0 && idx < currentExtractedData.length) {
                            currentExtractedData.splice(idx, 1);
                        }
                    });
                    renderGrid(currentExtractedData);
                    recalcGrandTotals();
                    showToast(`Deleted ${indices.length} selected rows!`, "success");
                }
            };
        }

        if (btnBulkToggle) {
            btnBulkToggle.onclick = () => {
                const checkedBoxes = Array.from(gridBody.querySelectorAll('.row-select-checkbox:checked'));
                if (checkedBoxes.length === 0) return;
                let toggledCount = 0;
                checkedBoxes.forEach(cb => {
                    const idx = parseInt(cb.getAttribute('data-idx'));
                    if (!isNaN(idx) && currentExtractedData[idx]) {
                        const row = currentExtractedData[idx];
                        const curType = (row.transaction_type || 'Receipt').toLowerCase();
                        row.transaction_type = (curType === 'receipt') ? 'Payment' : 'Receipt';
                        toggledCount++;
                    }
                });
                renderGrid(currentExtractedData);
                recalcGrandTotals();
                showToast(`Toggled Receipt/Payment type for ${toggledCount} selected rows!`, "success");
            };
        }

        if (btnBulkClear) {
            btnBulkClear.onclick = () => {
                gridBody.querySelectorAll('.row-select-checkbox').forEach(cb => cb.checked = false);
                if (selectAllHeader) selectAllHeader.checked = false;
                updateBulkActionToolbar();
            };
        }
    }

    function findMatchingClientLedger(aiLedger, clientLedgersList) {
        if (!aiLedger || !clientLedgersList || clientLedgersList.length === 0) return null;
        const cleanAi = aiLedger.toUpperCase().trim();
        if (cleanAi === "SUSPENSE ACCOUNT") return null;

        // 1. Exact Name match
        let match = clientLedgersList.find(l => (l.name || '').toUpperCase().trim() === cleanAi || (l.print_name || '').toUpperCase().trim() === cleanAi || (l.code || '').toUpperCase().trim() === cleanAi);
        if (match) return match;

        // 2. Normalized Synonyms (e.g. SALARY -> Salary Expenses / Salary A/c / Salary Account)
        const SYNONYMS = {
            'SALARY': ['SALARY EXPENSES', 'SALARY A/C', 'SALARY ACCOUNT', 'SALARIES', 'SALARIES EXPENSES'],
            'RENT': ['RENT EXPENSES', 'RENT A/C', 'RENT ACCOUNT', 'OFFICE RENT'],
            'PETROL': ['PETROL EXPENSES', 'PETROL & DIESEL', 'FUEL EXPENSES', 'VEHICLE EXPENSES'],
            'ELECTRICITY': ['ELECTRICITY EXPENSES', 'ELECTRICITY BILL', 'POWER & FUEL'],
            'BANK CHARGES': ['BANK CHARGE', 'BANK EXPENSES', 'BANK CHARGES A/C'],
            'PRINTING': ['PRINTING & STATIONERY', 'STATIONERY EXPENSES', 'PRINTING EXP'],
            'TELEPHONE': ['TELEPHONE EXPENSES', 'MOBILE RECHARGE', 'TELEPHONE & INTERNET'],
            'REPAIR': ['REPAIRS & MAINTENANCE', 'REPAIR EXPENSES', 'REPAIR & MAINTENANCE']
        };

        for (const [key, synList] of Object.entries(SYNONYMS)) {
            if (cleanAi === key || synList.includes(cleanAi)) {
                match = clientLedgersList.find(l => {
                    const nameUp = (l.name || '').toUpperCase().trim();
                    return nameUp === key || synList.includes(nameUp);
                });
                if (match) return match;
            }
        }

        return null;
    }

    function normalizeAccountingGroup(rawGroupName) {
        if (!rawGroupName) return 'Suspense Account';
        const gUp = rawGroupName.trim().toUpperCase();

        if (gUp === 'SUSPENSE ACCOUNT' || gUp === 'SUSPENSE' || gUp === 'G0000028') return 'Suspense Account';

        // Expenses
        if (gUp.includes('BANK CHARG')) return 'Bank Charges';
        if (gUp.includes('DIRECT EXPENSE') || gUp.includes('EXPENSES (DIRECT)')) return 'Direct Expenses';
        if (gUp.includes('INDIRECT EXPENSE') || gUp.includes('EXPENSES (INDIRECT)') || gUp.includes('EXPENSE ACCOUNT') || gUp.includes('EXPENSE')) return 'Indirect Expenses';

        // Incomes
        if (gUp.includes('DIRECT INCOME') || gUp.includes('INCOME (TRADING)')) return 'Direct Income';
        if (gUp.includes('INDIRECT INCOME') || gUp.includes('INCOME (OTHER THEN SALES)') || gUp.includes('INCOME')) return 'Indirect Income';

        // Debtors & Creditors
        if (gUp.includes('CREDITOR') || gUp.includes('SUPPLIER') || gUp === 'G0000013') return 'Sundry Creditors';
        if (gUp.includes('DEBTOR') || gUp.includes('CUSTOMER') || gUp === 'G0000009') return 'Sundry Debtors';

        // Statutory & Taxes
        if (gUp.includes('DUTIES') || gUp.includes('TAX') || gUp.includes('GST') || gUp === 'G0000014') return 'Duties & Taxes';

        // Banks & Cash
        if (gUp.includes('CASH') || gUp === 'G0000005') return 'Cash-in-Hand';
        if (gUp.includes('BANK') || gUp === 'G0000004') return 'Bank Accounts';

        // Assets & Investments
        if (gUp.includes('FIXED ASSET') || gUp === 'G0000006') return 'Fixed Assets';
        if (gUp.includes('INVEST') || gUp === 'G0000007') return 'Investments';
        if (gUp.includes('DEPOSIT') || gUp.includes('CURRENT ASSET')) return 'Current Assets';
        if (gUp.includes('LOAN') && gUp.includes('ASSET')) return 'Loans & Advances (Asset)';

        // Liabilities & Capital
        if (gUp.includes('DRAWING')) return 'Capital Account / Drawings';
        if (gUp.includes('CAPITAL') || gUp === 'G0000001') return 'Capital Account';
        if (gUp.includes('UNSECURED') || gUp === 'G0000019') return 'Unsecured Loans';
        if (gUp.includes('SECURED') || gUp === 'G0000008') return 'Secured Loans';
        if (gUp.includes('CURRENT LIABIL') || gUp.includes('PROVISION')) return 'Current Liabilities';
        if (gUp.includes('BRANCH')) return 'Branch / Divisions';

        // Sales & Purchases
        if (gUp.includes('PURCHASE')) return 'Purchase Accounts';
        if (gUp.includes('SALES') || gUp.includes('SALE')) return 'Sales Accounts';

        return rawGroupName;
    }

    function inferExpenseGroupHint(mappedLedger, transactionType, rowHint) {
        const legUp = (mappedLedger || '').toUpperCase().trim();
        const isPayment = (transactionType || 'Receipt').toLowerCase() === 'payment';
        const isReceipt = (transactionType || 'Receipt').toLowerCase() === 'receipt';

        // 0. ABSOLUTE TOP PRIORITY: Bank Charges, Service Charges, InstaAlert & SMS Charges (ALWAYS Indirect Expenses)
        if (/BANK CHARG|BANK CHAG|SMS CHARG|ALERTCHG|INSTAALERT|NACH CHARG|ECS CHARG|CHQ BOUNCE|ATM CHG|DEBIT CARD CHG|POS RENTAL|SOUND BOX/i.test(legUp)) {
            return 'Indirect Expenses';
        }

        // 1. TOP PRIORITY: Check master Miracle ledgers (clientLedgers) loaded from RKACCM01 DBF
        if (typeof clientLedgers !== 'undefined' && clientLedgers && clientLedgers.length > 0 && legUp && legUp !== 'SUSPENSE ACCOUNT') {
            const masterMatch = clientLedgers.find(l => 
                (l.name || '').trim().toUpperCase() === legUp || 
                (l.print_name || '').trim().toUpperCase() === legUp
            );
            if (masterMatch && masterMatch.group_name && masterMatch.group_name.toUpperCase() !== 'UNKNOWN' && masterMatch.group_name.toUpperCase() !== 'MIRACLE MASTER') {
                const normGroup = normalizeAccountingGroup(masterMatch.group_name);
                if (/BANK CHARG|BANK CHAG|SMS CHARG|ALERTCHG|INSTAALERT/i.test(legUp)) {
                    return 'Indirect Expenses';
                }
                return normGroup;
            }
        }

        // 2. Check if autoCreateLedgerHints has an explicit user-defined group for this auto-create ledger
        if (typeof autoCreateLedgerHints !== 'undefined' && autoCreateLedgerHints && autoCreateLedgerHints[legUp]) {
            return normalizeAccountingGroup(autoCreateLedgerHints[legUp]);
        }

        // 3. If mappedLedger is SUSPENSE ACCOUNT or empty, return Suspense Account
        if (!legUp || legUp === 'SUSPENSE ACCOUNT') {
            return 'Suspense Account';
        }

        // 4. Check explicit custom user / rowHint override (ONLY if rowHint is NOT default 'Suspense Account' or 'Review')
        const BAD_DR_GROUPS = ['Sales Accounts', 'Sales Accounts (Product Stock)', 'Direct Income', 'Sundry Debtors'];
        const BAD_CR_GROUPS = ['Sundry Creditors', 'Purchase Accounts'];
        const BAD_BANK_HINTS = ['Sales Accounts (Product Stock)', 'Sales Accounts', 'Trading Account', 'Purchase Accounts'];

        const hintUp = (rowHint || '').toUpperCase().trim();
        const isValidCustomHint = rowHint && 
            hintUp !== 'SUSPENSE ACCOUNT' && 
            hintUp !== 'SUSPENSE ACCOUNT (REVIEW)' &&
            hintUp !== 'REVIEW' &&
            hintUp !== 'GRID MAPPED' &&
            hintUp !== 'AUTO-CREATE';

        const hintViolatesDR = isPayment && BAD_DR_GROUPS.some(b => hintUp.includes(b.toUpperCase()));
        const hintViolatesCR = isReceipt && BAD_CR_GROUPS.some(b => hintUp.includes(b.toUpperCase()));

        if (isValidCustomHint && !BAD_BANK_HINTS.some(b => hintUp.includes(b.toUpperCase())) && !hintViolatesDR && !hintViolatesCR) {
            return normalizeAccountingGroup(rowHint);
        }

        // 5. Hard Cash & Bank group overrides
        if (/CASH/i.test(legUp) && !/CASHFLOW|CASHBACK/i.test(legUp)) {
            return 'Cash-in-Hand';
        }
        if (/^SBI$|^HDFC$|^ICICI$|^AXIS$|^KOTAK$|^BOB$/i.test(legUp) || (/BANK A\/C|BANK ACCOUNT/i.test(legUp))) {
            return 'Bank Accounts';
        }

        // 6. Statutory Taxes & Govt Duties
        if (/TDS|INCOME TAX|PROFESSIONAL TAX|PTAX|GST|CGST|SGST|IGST|DUTIES & TAXES|CHALLAN|GSTPMT|NSDL|TRACES|TAX PAYMENT/i.test(legUp)) {
            return 'Duties & Taxes';
        }

        // 7. Regex signals for expenses/investments/banks
        const isKnownExpense = /EXPENSE|EXPENSES|OTHER EXPENSE|KASAR|SALARY|SALARIES|WAGES|STIPEND|BONUS|PF |ESI|REMUNERATION|PETROL|DIESEL|FUEL|RENT|ELECTRICITY|POWER|WATER|TELEPHONE|MOBILE|INTERNET|BROADBAND|PRINTING|STATIONERY|FOOD|SNACKS|STAFF|REPAIR|SERVICE|MAINTENANCE|FREIGHT|TRANSPORT|CONVEYANCE|COURIER|ADVERTISEMENT|MARKETING|SOFTWARE|AUDIT|LEGAL|BANK CHARG|CHARGES|DISCOUNT|ZOMATO|SWIGGY|BLINKIT|ZEPTO|INSTAMART|CRED|DUNZO|BIGBASKET|URBAN COMPANY|URBANCLAP|HOUSEJOY|SULEKHA|MILKBASKET/i.test(legUp);
        const isKnownBankCharge = /NACH CHARGE|ECS CHARGE|ACH CHARGE|MANDATE CHARGE|BILL PAYMENT|INSURANCE PREMIUM|NACH DEBIT/i.test(legUp);
        const isKnownInvestment = /GROWW|ZERODHA|UPSTOX|SHARE KHAN|ANGEL BROKING|KOTAK SEC|ICICI DIRECT|HDFC SEC|PAYTM MONEY|MUTUAL FUND|SIP AUTO|DEMAT|NEXTBILLION|INDIAN CLEARING|CLEARING CORP|NSCCL|BSCCL|ICCL/i.test(legUp);
        const isKnownBank = /^(HDFC|ICICI|AXIS|SBI|IDFC|KOTAK|INDUSIND|BANK OF BARODA|UNION BANK|CANARA BANK|PUNJAB NATIONAL|CENTRAL BANK|BANK OF INDIA)/i.test(legUp);
        const isEcom = /AMAZON|FLIPKART|MYNTRA|MEESHO|SNAPDEAL|NYKAA|AJIO/i.test(legUp);

        if (isEcom) {
            return isPayment ? 'Indirect Expenses' : 'Sundry Debtors';
        }
        if (isKnownInvestment) {
            return 'Investments';
        }
        if (isKnownExpense || isKnownBankCharge) {
            return 'Indirect Expenses';
        }
        if (isKnownBank) {
            return 'Bank Accounts';
        }

        // 8. Personal Expenses & Drawings
        if (/DRAWING|PERSONAL|CAPITAL|MOM|WIFE|SELF|FAMILY|LIC|MEDICLAIM/i.test(legUp)) {
            return 'Capital Account / Drawings';
        }

        // 9. Final DR/CR gate for unknown person/vendor names
        return isPayment ? 'Sundry Creditors' : 'Sundry Debtors';
    }




    function createRowElement(row, index, globalAutoCreateLedgers, autoCreateLedgerHints) {
        let cScore = row.confidence_score !== undefined ? row.confidence_score : 95;
        
        // 🚨 DBF Product GST Mismatch Check 🚨
        let gstMismatchDetected = false;
        if (currentModule === 'Sales' || currentModule === 'Purchases') {
            const mappedItemName = (row.items && row.items.length > 0) ? row.items[0].name : "";
            if (mappedItemName && clientProducts && clientProducts.length > 0) {
                const mappedProduct = clientProducts.find(p => p.name === mappedItemName);
                if (mappedProduct) {
                    const mappedComm = (mappedProduct.commodity || mappedProduct.commodity_code || mappedProduct.M21F27 || "").trim().toUpperCase();
                    const rowGst = parseFloat(row.gst_pct) || 0;
                    const expectedComm = rowGst <= 0 ? "CNGT" : (rowGst <= 5 ? "C002" : (rowGst <= 12 ? "C003" : (rowGst <= 18 ? "C004" : "C005")));
                    
                    if (mappedComm !== "" && mappedComm !== expectedComm && mappedItemName !== "AUTO_CREATE_PRODUCT") {
                        gstMismatchDetected = true;
                    }
                }
            }
        }
        
        if (gstMismatchDetected) {
            cScore = Math.floor(cScore / 2); // Drop confidence to half
            if (!row.flags) row.flags = [];
            if (!row.flags.includes("GST DBF Mismatch")) row.flags.push("GST DBF Mismatch");
        }

        let borderHighlight = '';
        if (cScore < 80) {
            borderHighlight = 'border-l-2 border-l-amber-500/60';
        }
        const tr = document.createElement('tr');
        tr.className = `hover:bg-slate-800/30 transition group cursor-text ${borderHighlight}`;
        
        let confColorClass = 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20';
        if (cScore < 70) {
            confColorClass = 'text-rose-400 bg-rose-500/10 border border-rose-500/20';
        } else if (cScore < 85) {
            confColorClass = 'text-amber-400 bg-amber-500/10 border border-amber-500/20';
        }
        
        let flagsHtml = '';
        if (row.flags && row.flags.length > 0) {
            flagsHtml = `
                <div class="mt-1 flex flex-wrap gap-1 justify-center max-w-[150px]">
                    ${row.flags.map(f => `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/15" title="${f}">
                            ${f}
                        </span>
                    `).join('')}
                </div>
            `;
        }
        
        let statusColor = 'text-amber-500 bg-amber-500/10 border-amber-500/20';
        let statusIcon = 'fa-triangle-exclamation';
        let statusText = 'Review';

        if (row.status === 'Ready') {
            if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                let hasMappedMatch = false;
                const cleanLedger = (row.mapped_ledger || "").trim().toUpperCase();
                let matchedLedgerObj = null;

                if (clientLedgers && clientLedgers.length > 0) {
                    matchedLedgerObj = findMatchingClientLedger(row.mapped_ledger, clientLedgers);
                    if (matchedLedgerObj) {
                        hasMappedMatch = true;
                        row.mapped_ledger = matchedLedgerObj.name;
                        // ONLY pre-fill default group from master if user HAS NOT EXPLICITLY set a group_hint!
                        if (!row.group_hint && matchedLedgerObj.group_name) {
                            row.group_hint = matchedLedgerObj.group_name;
                        }
                    } else {
                        hasMappedMatch = clientLedgers.some(led => 
                            led.name.trim().toUpperCase() === cleanLedger || 
                            led.print_name.trim().toUpperCase() === cleanLedger ||
                            led.code.trim().toUpperCase() === cleanLedger
                        );
                    }
                }
                const isSuspense = cleanLedger === "SUSPENSE ACCOUNT" || row.group_hint === "Suspense Account";
                if (isSuspense) {
                    statusColor = 'text-amber-500 bg-amber-500/10 border-amber-500/20';
                    statusIcon = 'fa-triangle-exclamation';
                    statusText = 'Review';
                } else if (hasMappedMatch) {
                    statusColor = 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
                    statusIcon = 'fa-check-circle';
                    statusText = 'Mapped';
                } else {
                    statusColor = 'text-cyan-400 bg-cyan-400/10 border-cyan-400/20';
                    statusIcon = 'fa-circle-plus';
                    statusText = 'Auto-Create';
                }
            } else if (currentModule === 'Sales' || currentModule === 'Purchases') {
                if (row.autoCreateB2C) {
                    statusColor = 'text-purple-400 bg-purple-400/10 border-purple-400/20';
                    statusIcon = 'fa-user-plus';
                    statusText = 'Auto-Create (B2C)';
                } else if (row.autoCreateB2B) {
                    statusColor = 'text-cyan-400 bg-cyan-400/10 border-cyan-400/20';
                    statusIcon = 'fa-building-circle-check';
                    statusText = 'Auto-Create (B2B)';
                } else {
                    statusColor = 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
                    statusIcon = 'fa-check-circle';
                    statusText = 'Mapped';
                }
            }
        }

        let html = '';
        
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            let hasSuspense = false;
            let ledgerOptions = `<option value="">-- Select Ledger --</option><option value="CREATE_NEW_LEDGER" class="text-cyan-400 font-bold bg-slate-950">➕ + Create New Custom Miracle Ledger...</option>`;
            let hasMappedMatch = false;
            const aiLedger = (row.mapped_ledger || "Suspense Account").toUpperCase().trim();
            
            if (clientLedgers && clientLedgers.length > 0) {
                clientLedgers.forEach(l => {
                    if (l.name.toUpperCase().trim() === aiLedger) {
                        hasMappedMatch = true;
                    }
                });
            }

            const rawGroup = inferExpenseGroupHint(row.mapped_ledger, row.transaction_type, row.group_hint);
            const rowGroup = normalizeAccountingGroup(rawGroup);
            row.group_hint = rowGroup;
            
            if (globalAutoCreateLedgers && globalAutoCreateLedgers.length > 0) {
                globalAutoCreateLedgers.forEach(ul => {
                    const isSelected = (row.mapped_ledger || "").trim().toUpperCase() === ul.toUpperCase() && !hasMappedMatch ? "selected" : "";
                    const hint = (row.mapped_ledger || "").trim().toUpperCase() === ul.toUpperCase() && row.group_hint 
                        ? row.group_hint 
                        : inferExpenseGroupHint(ul, row.transaction_type, autoCreateLedgerHints[ul.toUpperCase()]);
                    ledgerOptions += `<option value="${ul}" data-hint="${hint}" ${isSelected}>${ul} (Auto-Create → ${hint})</option>`;
                });
            }

            if (!hasMappedMatch && row.mapped_ledger && row.mapped_ledger.toUpperCase().trim() !== "SUSPENSE ACCOUNT") {
                const unmappedName = row.mapped_ledger.trim();
                const alreadyInGlobal = globalAutoCreateLedgers && globalAutoCreateLedgers.some(g => g.toUpperCase().trim() === unmappedName.toUpperCase());
                if (!alreadyInGlobal) {
                    const hint = inferExpenseGroupHint(unmappedName, row.transaction_type, row.group_hint);
                    ledgerOptions += `<option value="${unmappedName}" data-hint="${hint}" selected>${unmappedName} (Auto-Create → ${hint})</option>`;
                }
            }

            if (clientLedgers && clientLedgers.length > 0) {
                clientLedgers.forEach(l => {
                    const rawName = l.name;
                    if (rawName.toUpperCase() === "SUSPENSE ACCOUNT") {
                        hasSuspense = true;
                    }
                    let displayName = rawName;
                    if (/@|OKAXIS|OKICICI|KHDFCBANK|OKHDFCBANK|OKSBI|PTYES|NAVIAXIS|SENT USING PAYTM|OKHD FCBANK|FCBANK|KAXIS/i.test(rawName)) {
                        let clean = rawName.replace(/@(okaxis|okicici|oka|waaxis|naviaxis|ptaxis|yescred|ptyes|axl|ybl|kotak|oksbi|okhdfcbank|hdfcbank)[A-Za-z0-9_.-]*/gi, '');
                        clean = clean.replace(/\b(SENT USING PAYTM|SENT USING PHONEPE|SENT USING GPAY|OKAXIS|OKICICI|KHDFCBANK|OKHDFCBANK|OKSBI|PTYES|NAVIAXIS|OKHD FCBANK|FCBANK|KAXIS)\b/gi, '');
                        clean = clean.replace(/^(UPI|IMPS|NEFT|RTGS|EFT)[-/_ \t]+/gi, '');
                        clean = clean.replace(/\b\d{5,}\b/g, '');
                        clean = clean.replace(/(?<=[A-Za-z])\d+/g, '');
                        clean = clean.replace(/\b\d+(?=[A-Za-z])/g, '');
                        clean = clean.replace(/\s+/g, ' ').trim();
                        if (clean.length >= 3) {
                            displayName = clean.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
                        }
                    }
                    const isSelected = (rawName.toUpperCase().trim() === aiLedger || displayName.toUpperCase().trim() === aiLedger) && hasMappedMatch ? "selected" : "";
                    ledgerOptions += `<option value="${rawName}" ${isSelected}>${displayName}</option>`;
                });
            }
            if (!hasSuspense) {
                const isSelected = (row.mapped_ledger || "Suspense Account").toUpperCase() === "SUSPENSE ACCOUNT" ? "selected" : "";
                ledgerOptions += `<option value="Suspense Account" ${isSelected}>Suspense Account (Auto-Create)</option>`;
            }

            const calculated_balance_formatted = row.calculated_balance !== undefined 
                ? (Math.abs(row.calculated_balance).toLocaleString('en-IN', {minimumFractionDigits: 2}) + (row.calculated_balance > 0 ? ' Cr' : (row.calculated_balance < 0 ? ' Dr' : '')))
                : '0.00';
            const balColor = row.calculated_balance > 0 ? 'text-emerald-400' : (row.calculated_balance < 0 ? 'text-red-400' : 'text-slate-400');


            html = `
                <td class="px-2 py-2 text-center border-r border-slate-800/30" style="width:40px;min-width:40px">
                    <input type="checkbox" class="row-select-checkbox cursor-pointer" data-idx="${index}" title="Select Row">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30" style="width:145px;min-width:145px">
                    <input type="date" class="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 focus:border-brand-500 w-full text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none transition date-input" value="${row.date || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30" style="width:145px;min-width:145px">
                    <input type="text" class="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 focus:border-brand-500 w-full text-slate-200 text-xs font-mono rounded-lg px-2.5 py-1.5 focus:outline-none transition ref-input" value="${row.reference_no || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30" style="min-width:260px">
                    <input type="text" class="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 focus:border-brand-500 w-full text-slate-200 text-xs font-semibold rounded-lg px-2.5 py-1.5 focus:outline-none transition narration-input" value="${row.narration || row.party_name || row.party || ''}" title="${row.narration || row.party_name || ''}">
                    <div class="text-xs text-slate-500 mt-1 bill-match-target hidden" data-party="${row.narration || row.party_name || row.party || ''}" data-amount="${row.amount || row.total || 0}"></div>
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30" style="min-width:240px">
                    <div class="flex items-center gap-1.5 w-full">
                        <input type="text" list="globalMiracleLedgersDatalist" class="bg-slate-900/80 hover:bg-slate-900 border border-slate-800 focus:border-brand-500 text-slate-200 text-xs font-medium rounded-lg block w-full px-2.5 py-1.5 focus:outline-none transition ledger-input cursor-pointer" value="${row.mapped_ledger && row.mapped_ledger.toUpperCase() !== 'SUSPENSE ACCOUNT' ? row.mapped_ledger : ''}" placeholder="🔍 Search or type Miracle ledger..." data-group-hint="${rowGroup}" autocomplete="off">
                        <button type="button" class="edit-ledger-btn text-slate-400 hover:text-cyan-400 p-1.5 rounded-lg hover:bg-slate-800/80 transition flex-shrink-0" data-idx="${index}" title="Edit & Rename Ledger in Miracle DBF">
                            <i class="fa-solid fa-pen-to-square text-xs"></i>
                        </button>
                    </div>
                    <div class="mt-1.5 flex items-center justify-between gap-1 group-hint-container ${!row.mapped_ledger || row.mapped_ledger.toUpperCase() === 'SUSPENSE ACCOUNT' ? 'hidden' : ''}" title="${rowGroup}">
                        <span class="text-[10px] text-cyan-400 font-bold uppercase tracking-tight whitespace-nowrap" title="${rowGroup}"><i class="fa-solid fa-layer-group text-cyan-400 mr-1"></i>GROUP:</span>
                        ${(() => {
                            const profileText = (businessProfileInput ? businessProfileInput.value : '').toUpperCase();
                            const isPersonal = profileText.includes('PERSON') || profileText.includes('INDIVIDUAL') || profileText.includes('PERSONAL');
                            const STD_OPTS = ['Sales Accounts', 'Direct Income', 'Purchase Accounts', 'Direct Expenses', 'Indirect Expenses', 'Indirect Income', 'Bank Charges', 'Fixed Assets', 'Investments', 'Sundry Debtors', 'Bank Accounts', 'Cash-in-Hand', 'Current Assets', 'Loans & Advances (Asset)', 'Capital Account', 'Capital Account / Drawings', 'Sundry Creditors', 'Duties & Taxes', 'Unsecured Loans', 'Secured Loans', 'Current Liabilities', 'Branch / Divisions', 'Suspense Account'];
                            const customOptionHtml = (rowGroup && !STD_OPTS.includes(rowGroup)) ? `<option value="${rowGroup}" selected>📂 ${rowGroup} (Custom Group)</option>` : '';

                            if (isPersonal) {
                                return `
                                <select class="bg-slate-950 border border-purple-500/40 text-purple-300 text-[11px] font-bold rounded-lg px-2 py-0.5 focus:outline-none transition group-hint-select cursor-pointer hover:border-purple-400 w-full" title="Select target personal accounting group for Miracle DBF">
                                    ${customOptionHtml}
                                    <optgroup label="🛍️ Personal Expenses & Outflows (P&L)">
                                        <option value="Indirect Expenses" ${rowGroup === 'Indirect Expenses' ? 'selected' : ''}>Indirect Expenses (Food / Rent / Petrol / Household Exp)</option>
                                        <option value="Bank Charges" ${rowGroup === 'Bank Charges' ? 'selected' : ''}>Bank Charges (Bank Fees / Debit Card Charges)</option>
                                    </optgroup>
                                    <optgroup label="💰 Personal Incomes & Earnings (P&L)">
                                        <option value="Indirect Income" ${rowGroup === 'Indirect Income' ? 'selected' : ''}>Indirect Income (Salary / Interest / Dividend / Cashback)</option>
                                    </optgroup>
                                    <optgroup label="💎 Personal Wealth & Investments (Assets)">
                                        <option value="Investments" ${rowGroup === 'Investments' ? 'selected' : ''}>Investments (Mutual Funds / Stocks / Groww / FD)</option>
                                        <option value="Fixed Assets" ${rowGroup === 'Fixed Assets' ? 'selected' : ''}>Fixed Assets (House / Property / Vehicles / Gold)</option>
                                        <option value="Bank Accounts" ${rowGroup === 'Bank Accounts' ? 'selected' : ''}>Bank Accounts (Bank A/c)</option>
                                        <option value="Cash-in-Hand" ${rowGroup === 'Cash-in-Hand' ? 'selected' : ''}>Cash-in-Hand (Pocket Money / Cash)</option>
                                        <option value="Current Assets" ${rowGroup === 'Current Assets' ? 'selected' : ''}>Current Assets (Prepaid / Deposits)</option>
                                        <option value="Loans & Advances (Asset)" ${rowGroup === 'Loans & Advances (Asset)' ? 'selected' : ''}>Loans &amp; Advances (Money Given to Friends)</option>
                                    </optgroup>
                                    <optgroup label="💳 Personal Liabilities & Taxes (Balance Sheet)">
                                        <option value="Capital Account / Drawings" ${rowGroup === 'Capital Account / Drawings' || rowGroup === 'Drawings' ? 'selected' : ''}>Drawings Account (Personal Spending / LIC)</option>
                                        <option value="Capital Account" ${rowGroup === 'Capital Account' ? 'selected' : ''}>Capital Account (Owner Equity Capital)</option>
                                        <option value="Duties & Taxes" ${rowGroup === 'Duties & Taxes' ? 'selected' : ''}>Duties &amp; Taxes (Income Tax / Advance Tax / TDS)</option>
                                        <option value="Unsecured Loans" ${rowGroup === 'Unsecured Loans' ? 'selected' : ''}>Unsecured Loans (Loans Taken from Friends)</option>
                                        <option value="Secured Loans" ${rowGroup === 'Secured Loans' ? 'selected' : ''}>Secured Loans (Home Loan / Car Loan / Mortgages)</option>
                                        <option value="Current Liabilities" ${rowGroup === 'Current Liabilities' ? 'selected' : ''}>Current Liabilities (Credit Card / Expenses Payable)</option>
                                        <option value="Sundry Creditors" ${rowGroup === 'Sundry Creditors' ? 'selected' : ''}>Sundry Creditors (Service Vendors / Bills)</option>
                                        <option value="Sundry Debtors" ${rowGroup === 'Sundry Debtors' ? 'selected' : ''}>Sundry Debtors (Receivables)</option>
                                    </optgroup>
                                    <optgroup label="⚠️ System & Review">
                                        <option value="Suspense Account" ${rowGroup === 'Suspense Account' ? 'selected' : ''}>Suspense Account (Review / Unmapped)</option>
                                    </optgroup>
                                </select>`;
                            } else {
                                return `
                                <select class="bg-slate-950 border border-cyan-500/30 text-cyan-300 text-[11px] font-bold rounded-lg px-2 py-0.5 focus:outline-none transition group-hint-select cursor-pointer hover:border-cyan-400 w-full" title="Select target commercial accounting group for Miracle DBF">
                                    ${customOptionHtml}
                                    <optgroup label="📈 Trading Account (Direct Sales, Purchases & Manufacturing)">
                                        <option value="Sales Accounts" ${rowGroup === 'Sales Accounts' ? 'selected' : ''}>Sales Accounts (Product Sales Revenue)</option>
                                        <option value="Direct Income" ${rowGroup === 'Direct Income' ? 'selected' : ''}>Direct Income (Jobwork / Service Revenue)</option>
                                        <option value="Purchase Accounts" ${rowGroup === 'Purchase Accounts' ? 'selected' : ''}>Purchase Accounts (Stock Purchases)</option>
                                        <option value="Direct Expenses" ${rowGroup === 'Direct Expenses' ? 'selected' : ''}>Direct Expenses (Freight / Wages / Factory Power)</option>
                                    </optgroup>
                                    <optgroup label="📊 Profit & Loss Account (Indirect Expenses & Operating Incomes)">
                                        <option value="Indirect Expenses" ${rowGroup === 'Indirect Expenses' ? 'selected' : ''}>Indirect Expenses (Rent / Salary / Petrol / Office Exp)</option>
                                        <option value="Indirect Income" ${rowGroup === 'Indirect Income' ? 'selected' : ''}>Indirect Income (Interest / Rent / Cashback)</option>
                                        <option value="Bank Charges" ${rowGroup === 'Bank Charges' ? 'selected' : ''}>Bank Charges (Bank Fees / Commission Expenses)</option>
                                    </optgroup>
                                    <optgroup label="🏢 Balance Sheet — Assets (Property, Investments & Debtors)">
                                        <option value="Fixed Assets" ${rowGroup === 'Fixed Assets' ? 'selected' : ''}>Fixed Assets (Machinery / Computers / Vehicles)</option>
                                        <option value="Investments" ${rowGroup === 'Investments' ? 'selected' : ''}>Investments (FD / Stocks / Mutual Funds / Groww)</option>
                                        <option value="Sundry Debtors" ${rowGroup === 'Sundry Debtors' ? 'selected' : ''}>Sundry Debtors (Trade Customers / Buyers)</option>
                                        <option value="Bank Accounts" ${rowGroup === 'Bank Accounts' ? 'selected' : ''}>Bank Accounts (Bank A/c)</option>
                                        <option value="Cash-in-Hand" ${/Cash-in-Hand/i.test(rowGroup) ? 'selected' : ''}>Cash-in-Hand (Petty Cash)</option>
                                        <option value="Current Assets" ${rowGroup === 'Current Assets' ? 'selected' : ''}>Current Assets (Prepaid / Security Deposits)</option>
                                        <option value="Loans & Advances (Asset)" ${rowGroup === 'Loans & Advances (Asset)' ? 'selected' : ''}>Loans &amp; Advances (Asset - Money Given)</option>
                                    </optgroup>
                                    <optgroup label="🏛️ Balance Sheet — Liabilities & Equity">
                                        <option value="Capital Account" ${rowGroup === 'Capital Account' ? 'selected' : ''}>Capital Account (Owner / Partner Equity)</option>
                                        <option value="Capital Account / Drawings" ${rowGroup === 'Capital Account / Drawings' || rowGroup === 'Drawings' ? 'selected' : ''}>Drawings Account (Owner Personal Spending / LIC)</option>
                                        <option value="Sundry Creditors" ${rowGroup === 'Sundry Creditors' ? 'selected' : ''}>Sundry Creditors (Trade Suppliers / Vendors)</option>
                                        <option value="Duties & Taxes" ${rowGroup === 'Duties & Taxes' ? 'selected' : ''}>Duties &amp; Taxes (GST / TDS / Tax Liabilities)</option>
                                        <option value="Unsecured Loans" ${rowGroup === 'Unsecured Loans' ? 'selected' : ''}>Unsecured Loans (Friends / Directors / Borrowings)</option>
                                        <option value="Secured Loans" ${rowGroup === 'Secured Loans' ? 'selected' : ''}>Secured Loans (Bank Term Loans / Mortgages)</option>
                                        <option value="Current Liabilities" ${rowGroup === 'Current Liabilities' ? 'selected' : ''}>Current Liabilities (Provisions / Expenses Payable)</option>
                                        <option value="Branch / Divisions" ${rowGroup === 'Branch / Divisions' ? 'selected' : ''}>Branch / Divisions</option>
                                    </optgroup>
                                    <optgroup label="⚠️ System & Review">
                                        <option value="Suspense Account" ${rowGroup === 'Suspense Account' ? 'selected' : ''}>Suspense Account (Review / Unmapped)</option>
                                    </optgroup>
                                </select>`;
                            }
                        })()}
                    </div>
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30 text-right" style="width:130px;min-width:130px">
                    <input type="text" class="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 focus:border-rose-500 w-full text-rose-400 text-xs font-bold rounded-lg px-2.5 py-1.5 focus:outline-none transition text-right withdrawal-input" value="${row.transaction_type === 'Payment' ? (row.amount || '') : ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30 text-right" style="width:130px;min-width:130px">
                    <input type="text" class="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 focus:border-emerald-500 w-full text-emerald-400 text-xs font-bold rounded-lg px-2.5 py-1.5 focus:outline-none transition text-right deposit-input" value="${row.transaction_type === 'Receipt' ? (row.amount || '') : ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/30 text-right font-black balance-cell whitespace-nowrap ${balColor}" style="width:145px;min-width:145px">
                    ${calculated_balance_formatted}
                </td>
                <td class="px-3 py-2 text-center" style="width:155px;min-width:155px">
                    <div class="flex flex-col items-center justify-center gap-1 status-container">
                        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${statusColor}">
                            <i class="fa-solid ${statusIcon}"></i> ${statusText === 'Auto-Create' ? `Auto-Create (${rowGroup})` : statusText}
                        </span>
                        <div class="flex items-center justify-center gap-1 mt-0.5">
                            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${confColorClass}" title="Confidence Score">
                                <i class="fa-solid fa-gauge mr-1"></i> ${cScore}%
                            </span>
                        </div>
                        ${flagsHtml}
                    </div>
                </td>
                <td class="px-2 py-2 text-center border-l border-slate-800/30 opacity-0 group-hover:opacity-100 transition" style="width:44px;min-width:44px">
                    <button class="delete-row-btn text-slate-500 hover:text-red-400 transition p-1.5 rounded-lg hover:bg-slate-800" data-idx="${index}" title="Delete Row"><i class="fa-solid fa-trash text-xs"></i></button>
                </td>
            `;
            tr.innerHTML = html;

            // Bind Event Listeners
            const dateInput = tr.querySelector('.date-input');
            const refInput = tr.querySelector('.ref-input');
            const narrationInput = tr.querySelector('.narration-input');
            const ledgerInput = tr.querySelector('.ledger-input');
            const withdrawalInput = tr.querySelector('.withdrawal-input');
            const depositInput = tr.querySelector('.deposit-input');

            if (dateInput) {
                dateInput.addEventListener('change', () => {
                    row.date = dateInput.value;
                    row.Date = dateInput.value;
                });
            }
            if (refInput) {
                refInput.addEventListener('input', () => {
                    row.reference_no = refInput.value;
                });
            }
            if (narrationInput) {
                narrationInput.addEventListener('input', () => {
                    const val = narrationInput.value;
                    row.narration = val;
                    if (!row.mapped_ledger || row.mapped_ledger === 'Suspense Account') {
                        row.party_name = val;
                        row.party = val;
                    }
                });
            }
            const editLedgerBtn = tr.querySelector('.edit-ledger-btn');
            if (editLedgerBtn) {
                editLedgerBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const rawTargetName = row.mapped_ledger || row.party_name || row.narration || '';
                    openEditLedgerModal(rawTargetName, index);
                });
            }

            const groupHintSelect = tr.querySelector('.group-hint-select');
            const groupHintContainer = tr.querySelector('.group-hint-container');

            if (groupHintSelect) {
                groupHintSelect.addEventListener('change', () => {
                    const newGroup = groupHintSelect.value;
                    row.group_hint = newGroup;
                    if (row.mapped_ledger) {
                        autoCreateLedgerHints[row.mapped_ledger.toUpperCase()] = newGroup;
                    }

                    // Propagate group_hint change across matching narrations
                    const currentNarr = (row.narration || "").trim().toUpperCase();
                    if (currentNarr) {
                        currentExtractedData.forEach(r => {
                            if ((r.narration || "").trim().toUpperCase() === currentNarr) {
                                r.group_hint = newGroup;
                            }
                        });
                    }

                    // Update status badge
                    const statusContainer = tr.querySelector('.status-container');
                    if (statusContainer) {
                        const badgeEl = statusContainer.querySelector('span');
                        if (badgeEl && !hasMappedMatch && row.mapped_ledger && row.mapped_ledger.toUpperCase() !== "SUSPENSE ACCOUNT") {
                            badgeEl.innerHTML = `<i class="fa-solid fa-circle-plus mr-1 text-cyan-400"></i> Auto-Create (${newGroup})`;
                        }
                    }
                    updateFilterCounts();
                });
            }

            if (ledgerInput) {
                const handleLedgerChange = () => {
                    const selectedVal = ledgerInput.value;
                    const cleanSelected = (selectedVal || "").trim();

                    row.mapped_ledger = cleanSelected || 'Suspense Account';
                    row.party_name = cleanSelected;
                    row.party = cleanSelected;
                    row.PartyName = cleanSelected;
                    row.Party_Name = cleanSelected;
                    row.status = 'Ready';

                    const newGroup = inferExpenseGroupHint(cleanSelected, row.transaction_type, row.group_hint);
                    row.group_hint = newGroup;

                    // Auto-propagate mapping across all rows with matching narration
                    const currentNarr = (row.narration || "").trim().toUpperCase();
                    let matchCount = 0;
                    if (currentNarr) {
                        currentExtractedData.forEach(r => {
                            if ((r.narration || "").trim().toUpperCase() === currentNarr) {
                                r.mapped_ledger = cleanSelected || 'Suspense Account';
                                r.party_name = cleanSelected;
                                r.party = cleanSelected;
                                r.PartyName = cleanSelected;
                                r.Party_Name = cleanSelected;
                                r.group_hint = newGroup;
                                r.status = 'Ready';
                                if (cleanSelected && cleanSelected.toUpperCase() !== "SUSPENSE ACCOUNT") {
                                    if (r.flags) r.flags = r.flags.filter(f => f !== "Suspense Mapping");
                                    r.confidence_score = Math.max(r.confidence_score || 95, 95);
                                } else {
                                    if (!r.flags) r.flags = [];
                                    if (!r.flags.includes("Suspense Mapping")) r.flags.push("Suspense Mapping");
                                    r.confidence_score = 75;
                                }
                                matchCount++;
                            }
                        });
                    }

                    if (matchCount > 1) {
                        showToast(`Auto-mapped '${cleanSelected}' to ${matchCount} matching transactions!`, "info");
                    }

                    populateGlobalLedgersDatalist();
                    updateFilterCounts();
                    recalcGrandTotals();
                    renderVirtualGridRows();
                };

                ledgerInput.addEventListener('change', handleLedgerChange);
            }
            if (withdrawalInput) {
                const updateW = () => {
                    if (withdrawalInput.value !== '' && depositInput) {
                        depositInput.value = '';
                    }
                    if (withdrawalInput.value !== '') row.transaction_type = 'Payment';
                    row.amount = parseCurrency(withdrawalInput.value) || 0;
                    recalcGrandTotals();
                    renderVirtualGridRows();
                };
                withdrawalInput.addEventListener('input', updateW);
                withdrawalInput.addEventListener('change', updateW);
            }
            if (depositInput) {
                const updateD = () => {
                    if (depositInput.value !== '' && withdrawalInput) {
                        withdrawalInput.value = '';
                    }
                    if (depositInput.value !== '') row.transaction_type = 'Receipt';
                    row.amount = parseCurrency(depositInput.value) || 0;
                    recalcGrandTotals();
                    renderVirtualGridRows();
                };
                depositInput.addEventListener('input', updateD);
                depositInput.addEventListener('change', updateD);
            }

        } else if (currentModule === 'Opening Balances') {
            const isDebit = row.dr_cr === 'D' || row.dr_cr === 'Dr';
            html = `
                <td class="px-3 py-2 border-r border-slate-800/50">
                    <input type="text" class="bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-full min-w-[200px] text-slate-200 text-sm font-semibold rounded-lg px-2.5 py-1.5 focus:outline-none transition ledger-name-input" value="${row.ledger_name || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-slate-350">
                    ${row.matched_code ? `<span class="text-emerald-400 text-sm font-bold"><i class="fa-solid fa-circle-check mr-1"></i> Mapped (${row.matched_code})</span>` : `<span class="text-amber-400 text-sm font-bold"><i class="fa-solid fa-circle-plus mr-1"></i> Auto-Create</span>`}
                    <input type="hidden" class="matched-code-input" value="${row.matched_code || ''}">
                    <input type="hidden" class="group-hint-input" value="${row.group_hint || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-center">
                    <select class="bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 text-slate-200 text-sm rounded-lg px-2.5 py-1.5 focus:outline-none transition dr-cr-select cursor-pointer">
                        <option value="D" ${isDebit ? 'selected' : ''}>Dr (Asset)</option>
                        <option value="C" ${!isDebit ? 'selected' : ''}>Cr (Liab)</option>
                    </select>
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="number" step="0.01" class="balance-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-28 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="${row.balance || 0}">
                </td>
                <td class="px-2 py-2 text-center border-r border-slate-800/50"></td>
                <td class="px-2 py-2 text-center border-r border-slate-800/50 opacity-0 group-hover:opacity-100 transition">
                    <button class="delete-row-btn text-slate-500 hover:text-red-500 transition px-2 py-1" data-idx="${index}" title="Delete Row"><i class="fa-solid fa-trash"></i></button>
                </td>
            `;
            tr.innerHTML = html;

            const nameInput = tr.querySelector('.ledger-name-input');
            const drCrSelect = tr.querySelector('.dr-cr-select');
            const balanceInput = tr.querySelector('.balance-input');

            if (nameInput) {
                nameInput.addEventListener('input', () => {
                    row.ledger_name = nameInput.value.trim();
                });
            }
            if (drCrSelect) {
                drCrSelect.addEventListener('change', () => {
                    row.dr_cr = drCrSelect.value;
                });
            }
            if (balanceInput) {
                balanceInput.addEventListener('input', () => {
                    row.balance = parseFloat(balanceInput.value) || 0;
                    recalcGrandTotals();
                });
            }

        } else {
            const hasDiscount = currentExtractedData.some(r => r.discount > 0);
            const hasFreight = currentExtractedData.some(r => r.freight > 0);
            const hasTcs = currentExtractedData.some(r => r.tcs > 0);
            const hasTds = currentExtractedData.some(r => r.tds > 0);

            const firstItemName = (row.items && row.items.length > 0 && row.items[0].name) ? row.items[0].name : "";
            const productOptions = generateProductOptions(firstItemName, row.gst_pct);

            html = `
                <td class="px-2 py-2 text-center border-r border-slate-800/50" style="width:40px;min-width:40px">
                    <input type="checkbox" class="row-select-checkbox cursor-pointer" data-idx="${index}" title="Select Row">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50">
                    <input type="date" class="bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-[135px] text-slate-200 text-sm rounded-lg px-2.5 py-1.5 focus:outline-none transition date-input" value="${row.date || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50">
                    <input type="text" class="bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-24 text-slate-200 text-sm rounded-lg px-2.5 py-1.5 focus:outline-none transition billno-input" value="${row.billNo || row.bill_no || row.invoice_no || ''}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50">
                    <div class="flex items-center gap-1.5 w-full">
                        <input type="text" class="bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-full min-w-[150px] text-slate-200 text-sm font-semibold rounded-lg px-2.5 py-1.5 focus:outline-none transition party-input" value="${row.party || row.party_name || ''}">
                        <button type="button" class="edit-ledger-btn text-slate-400 hover:text-cyan-400 p-1.5 rounded-lg hover:bg-slate-800/80 transition flex-shrink-0" data-idx="${index}" title="Edit & Rename Party Ledger in Miracle DBF">
                            <i class="fa-solid fa-pen-to-square text-xs"></i>
                        </button>
                    </div>
                    <div class="mt-1 flex items-center gap-1">
                        <span class="text-[10px] text-indigo-400 font-bold uppercase tracking-tight whitespace-nowrap"><i class="fa-solid fa-box text-indigo-400 mr-0.5"></i>Item:</span>
                        <select class="bg-slate-950 border border-indigo-500/30 text-indigo-300 text-[11px] font-bold rounded-lg px-2 py-0.5 focus:outline-none transition product-item-select cursor-pointer hover:border-indigo-400 w-full" title="Select product item from Miracle DBF">
                            ${productOptions}
                        </select>
                    </div>
                    ${row.party_gstin ? `<div class="text-xs text-slate-500 mt-1 flex items-center gap-1 gstin-verify" data-gstin="${row.party_gstin}"><i class="fa-solid fa-spinner fa-spin text-brand-500 mr-1"></i> Checking ${row.party_gstin}...</div>` : ''}
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="number" step="0.01" class="qty-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-16 text-slate-200 text-sm text-right font-semibold rounded-lg px-2 py-1.5 focus:outline-none transition" value="${row.qty || row.quantity || (row.items && row.items.length > 0 ? row.items.reduce((acc, it) => acc + (parseFloat(it.qty) || 0), 0) : 1) || 1}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="taxable-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-28 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${(row.taxable || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>
            `;

            if (hasDiscount) {
                const val = row.discount || 0;
                html += `
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="discount-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-20 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>`;
            }
            if (hasFreight) {
                const val = row.freight || 0;
                html += `
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="freight-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-20 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>`;
            }
            if (hasTcs) {
                const val = row.tcs || 0;
                html += `
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="tcs-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-20 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>`;
            }
            if (hasTds) {
                const val = row.tds || 0;
                html += `
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="tds-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-20 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>`;
            }

            let rawPct = row.gst_pct;
            if (rawPct === undefined || rawPct === null || isNaN(rawPct)) {
                const tx = parseFloat(row.taxable) || 0;
                const g = parseFloat(row.gst) || 0;
                if (tx > 0 && g > 0) {
                    const calcP = Math.round((g / tx) * 100 * 10) / 10;
                    const slabs = [0, 0.25, 1.5, 3, 5, 12, 18, 28];
                    rawPct = slabs.reduce((prev, curr) => Math.abs(curr - calcP) < Math.abs(prev - calcP) ? curr : prev);
                } else {
                    rawPct = 0;
                }
            }
            row.gst_pct = rawPct;

            html += `
                <td class="px-2 py-2 border-r border-slate-800/50 text-center">
                    <span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-extrabold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 gst-pct-badge" title="Effective GST Tax Rate">
                        ${rawPct}%
                    </span>
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-right">
                    <input type="text" class="gst-input bg-slate-900/40 hover:bg-slate-900 border border-slate-800/65 focus:border-brand-500 w-24 text-slate-200 text-sm text-right rounded-lg px-2.5 py-1.5 focus:outline-none transition" value="₹${(row.gst || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}">
                </td>
                <td class="px-3 py-2 border-r border-slate-800/50 text-right font-bold text-white total-cell">
                    ₹${(row.total || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
                </td>
                <td class="px-3 py-2 text-center">
                    <div class="flex flex-col items-center justify-center gap-1">
                        <span class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-base font-bold border ${statusColor}">
                            <i class="fa-solid ${statusIcon}"></i> ${statusText}
                        </span>
                        <div class="flex items-center justify-center gap-1 mt-1">
                            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${confColorClass}" title="Confidence Score">
                                <i class="fa-solid fa-gauge mr-1"></i> ${cScore}%
                            </span>
                        </div>
                        ${flagsHtml}
                    </div>
                </td>
                <td class="px-2 py-2 text-center opacity-0 group-hover:opacity-100 transition border-l border-slate-800/50 w-10">
                    <button class="delete-row-btn text-slate-500 hover:text-red-500 transition px-2 py-1" data-idx="${index}" title="Delete Row"><i class="fa-solid fa-trash"></i></button>
                </td>
            `;
            tr.innerHTML = html;

            const dateInput = tr.querySelector('.date-input');
            const billNoInput = tr.querySelector('.billno-input');
            const partyInput = tr.querySelector('.party-input');
            const qtyInput = tr.querySelector('.qty-input');
            const taxableInput = tr.querySelector('.taxable-input');
            const discountInput = tr.querySelector('.discount-input');
            const freightInput = tr.querySelector('.freight-input');
            const tcsInput = tr.querySelector('.tcs-input');
            const tdsInput = tr.querySelector('.tds-input');
            const gstInput = tr.querySelector('.gst-input');

            if (dateInput) {
                dateInput.addEventListener('change', () => {
                    row.date = dateInput.value;
                    row.Date = dateInput.value;
                });
            }
            if (billNoInput) {
                billNoInput.addEventListener('input', () => {
                    row.billNo = billNoInput.value;
                    row.bill_no = billNoInput.value;
                });
            }
            const productItemSelect = tr.querySelector('.product-item-select');
            if (productItemSelect) {
                productItemSelect.addEventListener('change', () => {
                    const newProd = productItemSelect.value;
                    if (row.items && row.items.length > 0) {
                        row.items[0].name = newProd;
                    } else {
                        row.items = [{ name: newProd, qty: row.qty || 1, rate: row.taxable || 0, amount: row.taxable || 0 }];
                    }
                    console.log(`Updated product item for bill ${row.billNo}: ${newProd}`);
                    renderGrid(currentExtractedData);
                });
            }
            if (partyInput) {
                partyInput.addEventListener('input', () => {
                    const val = partyInput.value;
                    row.party = val;
                    row.party_name = val;
                    row.mapped_ledger = val;
                    row.PartyName = val;
                });
            }
            if (qtyInput) {
                qtyInput.addEventListener('input', () => {
                    const parsedQty = parseFloat(qtyInput.value) || 1;
                    row.qty = parsedQty;
                    row.quantity = parsedQty;
                    if (row.items && row.items.length > 0) {
                        row.items[0].qty = parsedQty;
                    }
                });
            }

            const triggerRecalc = () => {
                row.taxable = taxableInput ? parseCurrency(taxableInput.value) : 0;
                row.gst = gstInput ? parseCurrency(gstInput.value) : 0;
                row.discount = discountInput ? parseCurrency(discountInput.value) : 0;
                row.freight = freightInput ? parseCurrency(freightInput.value) : 0;
                row.tcs = tcsInput ? parseCurrency(tcsInput.value) : 0;
                row.tds = tdsInput ? parseCurrency(tdsInput.value) : 0;
                
                const expNet = (row.taxable + row.freight) + row.gst + row.tcs - row.tds;
                const expGross = (row.taxable - row.discount + row.freight) + row.gst + row.tcs - row.tds;
                
                if (row.total > 0 && Math.abs(expNet - row.total) <= 2.00) {
                    row.total = expNet;
                } else if (row.total > 0 && Math.abs(expGross - row.total) <= 2.00) {
                    row.total = expGross;
                } else {
                    row.total = (row.discount > 0 && row.taxable > row.discount + 10) ? expGross : expNet;
                }

                const gstBadge = tr.querySelector('.gst-pct-badge');
                if (gstBadge) {
                    if (row.taxable > 0 && row.gst > 0) {
                        const calcP = Math.round((row.gst / row.taxable) * 100 * 10) / 10;
                        const slabs = [0, 0.25, 1.5, 3, 5, 12, 18, 28];
                        const updatedPct = slabs.reduce((prev, curr) => Math.abs(curr - calcP) < Math.abs(prev - calcP) ? curr : prev);
                        row.gst_pct = updatedPct;
                        gstBadge.innerText = `${updatedPct}%`;
                    }
                }

                const totalCell = tr.querySelector('.total-cell');
                if (totalCell) {
                    totalCell.innerText = `₹${row.total.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
                }
                recalcGrandTotals();
            };

            if (taxableInput) taxableInput.addEventListener('input', triggerRecalc);
            if (gstInput) gstInput.addEventListener('input', triggerRecalc);
            if (discountInput) discountInput.addEventListener('input', triggerRecalc);
            if (freightInput) freightInput.addEventListener('input', triggerRecalc);
            if (tcsInput) tcsInput.addEventListener('input', triggerRecalc);
            if (tdsInput) tdsInput.addEventListener('input', triggerRecalc);
        }

        const delBtn = tr.querySelector('.delete-row-btn');
        if (delBtn) {
            delBtn.addEventListener('click', () => {
                const actualIdx = currentExtractedData.indexOf(row);
                if (actualIdx !== -1) {
                    currentExtractedData.splice(actualIdx, 1);
                }
                renderGrid(currentExtractedData);
                recalcGrandTotals();
            });
        }

        return tr;
    }

    function calculateRollingBalances() {
        if (!currentExtractedData || !Array.isArray(currentExtractedData)) return;
        let currentBalance = 0;
        const opBalInput = document.getElementById('openingBalanceInput');
        if (opBalInput && opBalInput.value !== '' && !isNaN(parseFloat(opBalInput.value))) {
            currentBalance = parseFloat(opBalInput.value);
        }
        
        currentExtractedData.forEach(row => {
            const txType = (row.transaction_type || row.Transaction_Type || row.type || '').toString().trim().toLowerCase();
            let amt = parseCurrency(row.amount) || parseCurrency(row.deposit) || parseCurrency(row.withdrawal) || parseCurrency(row.Amount) || parseCurrency(row.Deposit) || parseCurrency(row.Withdrawal) || 0;
            row.amount = amt;

            if (txType === 'receipt' || txType === 'deposit' || txType === 'cr') {
                currentBalance += amt;
            } else if (txType === 'payment' || txType === 'withdrawal' || txType === 'dr') {
                currentBalance -= amt;
            } else if (row.running_balance !== undefined && row.running_balance !== null && row.running_balance !== '') {
                currentBalance = parseFloat(row.running_balance);
            }
            row.calculated_balance = Math.round(currentBalance * 100) / 100;
        });
    }

    function recalcGrandTotals() {
        const container = document.getElementById('grandTotalsContainer');
        if (!container) return;

        let sumTaxable = 0, sumGst = 0, sumTotal = 0;
        let sumDiscount = 0, sumFreight = 0, sumTcs = 0, sumTds = 0;
        let sumReceipts = 0, sumPayments = 0;
        
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            calculateRollingBalances();
        }
        updateFilterCounts();
        
        let count = 0;
        const dataToSum = getFilteredData();
        if (dataToSum && Array.isArray(dataToSum)) {
            count = dataToSum.length;
            dataToSum.forEach(row => {
                if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                    const amt = parseCurrency(row.amount) || parseCurrency(row.withdrawal_amt) || parseCurrency(row.deposit_amt) || parseCurrency(row.Amount) || parseCurrency(row.Withdrawal_Amount) || parseCurrency(row.Deposit_Amount) || parseCurrency(row.withdrawal) || parseCurrency(row.deposit) || 0;
                    const tType = String(row.transaction_type || row.Transaction_Type || row.type || row.Type || '').toLowerCase();
                    if (tType.includes('payment') || tType === 'dr' || tType === 'debit' || parseCurrency(row.withdrawal_amt || row.withdrawal || 0) > 0) sumPayments += amt;
                    else if (tType.includes('receipt') || tType === 'cr' || tType === 'credit' || parseCurrency(row.deposit_amt || row.deposit || 0) > 0) sumReceipts += amt;
                    else sumPayments += amt;
                } else if (currentModule === 'Opening Balances') {
                    // No totals needed for opening balances
                } else {
                    let rTaxable = parseCurrency(row.taxable || row.taxable_amount || row.Taxable || row['Taxable Amount'] || 0);
                    let rCgst = parseCurrency(row.cgst || row.CGST || 0);
                    let rSgst = parseCurrency(row.sgst || row.SGST || 0);
                    let rIgst = parseCurrency(row.igst || row.IGST || 0);
                    let rGst = parseCurrency(row.gst || row.GST || row.Total_GST || row['Total GST'] || 0);
                    if (rGst <= 0) rGst = rCgst + rSgst + rIgst;
                    
                    let rTotal = parseCurrency(row.total || row.Total || row.total_amount || row.Grand_Total || row['Grand Total'] || row.amount || 0);
                    if (rTotal <= 0 && (rTaxable > 0 || rGst > 0)) rTotal = rTaxable + rGst;
                    
                    // Fallback to item sums if row-level fields are missing
                    if (rTaxable <= 0 && Array.isArray(row.items) && row.items.length > 0) {
                        row.items.forEach(it => {
                            rTaxable += parseCurrency(it.taxable || it.amount || 0);
                            const itGst = parseCurrency(it.gst || it.tax || 0);
                            if (itGst > 0) rGst += itGst;
                            else rGst += (parseCurrency(it.cgst || 0) + parseCurrency(it.sgst || 0) + parseCurrency(it.igst || 0));
                        });
                        if (rTotal <= 0) rTotal = rTaxable + rGst;
                    }

                    sumTaxable += rTaxable;
                    sumGst += rGst;
                    sumDiscount += parseCurrency(row.discount || row.Discount || 0);
                    sumFreight += parseCurrency(row.freight || row.Freight || 0);
                    sumTcs += parseCurrency(row.tcs || row.TCS || 0);
                    sumTds += parseCurrency(row.tds || row.TDS || 0);
                    sumTotal += rTotal;
                }
            });
        }

        updateHeaderBadges();

        const mLower = String(currentModule || '').toLowerCase();
        const kpiEntries = document.getElementById('kpiTotalEntries');
        const kpiTaxable = document.getElementById('kpiTaxableTotal');
        const kpiGst = document.getElementById('kpiGstTotal');
        const kpiGrand = document.getElementById('kpiGrandTotal');

        const kpiLabel1 = document.getElementById('kpiLabel1');
        const kpiLabel2 = document.getElementById('kpiLabel2');
        const kpiLabel3 = document.getElementById('kpiLabel3');
        const kpiLabel4 = document.getElementById('kpiLabel4');

        const kpiIcon1 = document.getElementById('kpiIcon1');
        const kpiIcon2 = document.getElementById('kpiIcon2');
        const kpiIcon3 = document.getElementById('kpiIcon3');
        const kpiIcon4 = document.getElementById('kpiIcon4');

        if (mLower.includes('bank') || mLower.includes('cash')) {
            if (kpiLabel1) kpiLabel1.textContent = 'Total Entries';
            if (kpiLabel2) kpiLabel2.textContent = 'Total Receipts';
            if (kpiLabel3) kpiLabel3.textContent = 'Total Payments';
            if (kpiLabel4) kpiLabel4.textContent = 'Net Cash Flow';

            if (kpiIcon1) kpiIcon1.className = 'fa-solid fa-list-check text-sm';
            if (kpiIcon2) kpiIcon2.className = 'fa-solid fa-arrow-down-left text-sm text-emerald-400';
            if (kpiIcon3) kpiIcon3.className = 'fa-solid fa-arrow-up-right text-sm text-rose-400';
            if (kpiIcon4) kpiIcon4.className = 'fa-solid fa-scale-balanced text-sm text-cyan-400';

            if (kpiEntries) kpiEntries.textContent = `${count} Txns`;
            if (kpiTaxable) kpiTaxable.textContent = `₹${sumReceipts.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
            if (kpiGst) kpiGst.textContent = `₹${sumPayments.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
            
            const netBalance = sumReceipts - sumPayments;
            const netSign = netBalance > 0 ? '+' : (netBalance < 0 ? '-' : '');
            if (kpiGrand) kpiGrand.textContent = `${netSign}₹${Math.abs(netBalance).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        } else {
            if (kpiLabel1) kpiLabel1.textContent = 'Total Entries';
            if (kpiLabel2) kpiLabel2.textContent = 'Taxable Total';
            if (kpiLabel3) kpiLabel3.textContent = 'GST Output / Input';
            if (kpiLabel4) kpiLabel4.textContent = 'Grand Total';

            if (kpiIcon1) kpiIcon1.className = 'fa-solid fa-list-check text-sm';
            if (kpiIcon2) kpiIcon2.className = 'fa-solid fa-calculator text-sm text-blue-400';
            if (kpiIcon3) kpiIcon3.className = 'fa-solid fa-percent text-sm text-cyan-400';
            if (kpiIcon4) kpiIcon4.className = 'fa-solid fa-indian-rupee-sign text-sm text-emerald-400';

            if (kpiEntries) kpiEntries.textContent = `${count} Bills`;
            if (kpiTaxable) kpiTaxable.textContent = `₹${sumTaxable.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
            if (kpiGst) kpiGst.textContent = `₹${sumGst.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
            if (kpiGrand) kpiGrand.textContent = `₹${sumTotal.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        }

        if (container) {
            const unitStr = (mLower.includes('bank') || mLower.includes('cash')) ? 'Entries' : 'Invoices';
            container.innerHTML = `
                <div class="flex items-center gap-2">
                    <div class="bg-slate-900/90 px-3 py-1.5 border border-slate-800/80 rounded-xl flex items-center gap-2 shadow-sm text-xs">
                        <span class="h-2 w-2 rounded-full ${count > 0 ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}"></span>
                        <span class="font-extrabold text-white font-mono">${count}</span>
                        <span class="text-slate-400 font-bold uppercase tracking-wider text-[10px]">${unitStr} Ready</span>
                    </div>
                </div>
            `;
        }
    }

    function updateTotals(data) {
        // Obsolete, replaced by recalcGrandTotals
    }

    function parseCurrency(str) {
        if (!str) return 0;
        if (typeof str === 'number') return str;
        return parseFloat(str.replace(/[₹, \s]/g, '')) || 0;
    }

    const autoFillBtn = document.getElementById('autoFillDebtorsBtn');
    if (autoFillBtn) {
        autoFillBtn.addEventListener('click', async () => {
            if (!confirm('This will fetch all Sundry Debtors with an outstanding balance and automatically generate Cash Receipt entries for them in the grid. Existing grid data will be overwritten. Proceed?')) {
                return;
            }
            
            autoFillBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Loading...`;
            autoFillBtn.disabled = true;
            
            try {
                const response = await fetch(`${API_URL}/api/debtor-balances${activeYearFolder ? '?year=' + activeYearFolder : ''}`);
                if (!response.ok) throw new Error('Network response was not ok');
                
                const result = await response.json();
                if (result.status === 'success') {
                    if (!result.data || result.data.length === 0) {
                        alert("No Debtors found with an outstanding balance.");
                    } else {
                        currentExtractedData = result.data.map(debtor => ({
                            date: debtor.last_transaction_date || new Date().toISOString().split('T')[0],
                            narration: 'Cash Received',
                            mapped_ledger: debtor.name,
                            transaction_type: 'Receipt',
                            amount: debtor.balance,
                            reference_no: ''
                        }));
                        renderGrid(currentExtractedData);
                        recalcGrandTotals(currentExtractedData);
                        const btn = document.getElementById('pushBtn');
                        if (btn) {
                            btn.disabled = false;
                            btn.classList.remove('opacity-50', 'cursor-not-allowed');
                        }
                    }
                } else {
                    alert('Error: ' + result.detail);
                }
            } catch (error) {
                console.error('Error fetching debtor balances:', error);
                alert('Failed to fetch debtor balances.');
            } finally {
                autoFillBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles mr-1"></i> Auto-Fill Debtors`;
                autoFillBtn.disabled = false;
            }
        });
    }

    // Event listener for Pushing Staged Data to Miracle DBFs
    pushBtn.addEventListener('click', async () => {
        if (!currentExtractedData || currentExtractedData.length === 0) {
            alert("No vouchers available to push.");
            return;
        }

        // Check for any rows with a confidence score below 80%
        let lowConfidenceFound = false;
        if (Array.isArray(currentExtractedData)) {
            currentExtractedData.forEach(row => {
                if (row.confidence_score !== undefined && row.confidence_score < 80) {
                    lowConfidenceFound = true;
                }
            });
        }
        
        if (lowConfidenceFound) {
            const confirmed = confirm("⚠️ WARNING: Some staged transactions have a low confidence score (below 80%). Do you want to manually confirm and proceed to push them to Miracle?");
            if (!confirmed) {
                return;
            }
        }

        const vouchers = [];
        currentExtractedData.forEach((row) => {
            if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                const amount = row.amount || 0;
                vouchers.push({
                    date: (row.date || '').trim(),
                    reference_no: (row.reference_no || '').trim(),
                    narration: (row.narration || row.party_name || row.party || '').trim(),
                    party_name: (row.mapped_ledger && row.mapped_ledger.trim().toUpperCase() !== "SUSPENSE ACCOUNT") ? row.mapped_ledger.trim() : (row.party_name || row.party || "Suspense Account"),
                    transaction_type: row.transaction_type || 'Receipt',
                    amount: amount,
                    group_hint: row.group_hint || ''
                });
            } else if (currentModule === 'Opening Balances') {
                vouchers.push({
                    ledger_name: (row.ledger_name || '').trim(),
                    matched_code: (row.matched_code || '').trim(),
                    group_hint: (row.group_hint || '').trim(),
                    dr_cr: row.dr_cr || 'D',
                    balance: parseFloat(row.balance) || 0
                });
            } else { // Sales or Purchases
                const parsedQty = parseFloat(row.qty || row.quantity || 1) || 1;
                const taxable = parseFloat(row.taxable) || 0;
                const gst = parseFloat(row.gst) || 0;
                const discount = parseFloat(row.discount) || 0;
                const freight = parseFloat(row.freight) || 0;
                const tcs = parseFloat(row.tcs) || 0;
                const tds = parseFloat(row.tds) || 0;
                const total = parseFloat(row.total) || 0;
                
                const partyName = (row.party_name || row.party || row.mapped_ledger || row.PartyName || '').trim();
                const billNo = (row.bill_no || row.billNo || row.invoice_no || '').trim();
                const dateVal = (row.date || row.Date || '').trim();
                
                let originalItems = row.items || [];
                if (originalItems && originalItems.length > 0) {
                    originalItems.forEach(item => {
                        const existingQty = parseFloat(item.qty || item.quantity || 0);
                        if (!existingQty || existingQty <= 0) {
                            item.qty = parsedQty;
                            if (parsedQty > 0 && taxable > 0) item.rate = Math.round((taxable / parsedQty) * 100) / 100;
                        } else {
                            if (originalItems.length === 1 && taxable > 0) {
                                item.taxable = taxable;
                                item.amount = taxable;
                                if (existingQty > 0) item.rate = Math.round((taxable / existingQty) * 100) / 100;
                            }
                        }
                    });
                } else {
                    originalItems = [{
                        name: currentModule === "Sales" ? "SALES" : "PURCHASES",
                        qty: parsedQty,
                        rate: parsedQty > 0 ? Math.round((taxable / parsedQty) * 100) / 100 : taxable,
                        amount: taxable,
                        taxable: taxable,
                        gst_pct: gst > 0 && taxable > 0 ? (gst / taxable) * 100 : 18.0
                    }];
                }
                
                let cgst = 0, sgst = 0, igst = 0;
                if (row.igst > 0) {
                    igst = gst;
                } else if (row.cgst > 0 || row.sgst > 0) {
                    cgst = row.cgst || (gst / 2);
                    sgst = row.sgst || (gst / 2);
                } else {
                    cgst = gst / 2;
                    sgst = gst / 2;
                }
                
                vouchers.push({
                    date: dateVal,
                    bill_no: billNo,
                    billNo: billNo,
                    party_name: partyName,
                    party: partyName,
                    qty: parsedQty,
                    party_gstin: (row.party_gstin || '').trim(),
                    party_address: (row.party_address || '').trim(),
                    party_city: (row.party_city || '').trim(),
                    party_pincode: (row.party_pincode || '').trim(),
                    taxable: taxable,
                    cgst: cgst,
                    sgst: sgst,
                    igst: igst,
                    gst: gst,
                    discount: discount,
                    freight: freight,
                    tcs: tcs,
                    tds: tds,
                    total: total,
                    items: originalItems
                });
            }
        });

        if (vouchers.length === 0) {
            alert("No valid vouchers could be mapped from the grid.");
            return;
        }

        // FINAL CLIENT-SIDE DEDUP GUARD: Prevent sending exact-duplicate rows to the backend
        // This is the last line of defence against the duplicate journal entry bug.
        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
            const seenVouchers = new Set();
            const dedupedVouchers = [];
            for (const v of vouchers) {
                const key = `${v.date}|${v.amount}|${v.transaction_type}|${(v.reference_no||'').toLowerCase()}|${(v.narration||'').substring(0,40).toLowerCase()}`;
                if (!seenVouchers.has(key)) {
                    seenVouchers.add(key);
                    dedupedVouchers.push(v);
                } else {
                    console.warn('🚫 Blocked duplicate voucher before push:', v);
                }
            }
            if (dedupedVouchers.length < vouchers.length) {
                console.log(`🛡️ Dedup guard removed ${vouchers.length - dedupedVouchers.length} duplicate(s) before push.`);
            }
            vouchers.length = 0;
            dedupedVouchers.forEach(v => vouchers.push(v));
        }

        // Disable button and show spinner
        pushBtn.disabled = true;
        pushBtn.classList.add('cursor-not-allowed', 'opacity-50');
        const originalHtml = pushBtn.innerHTML;

        showToast(`🔒 Step 1/4: Checking Miracle DBF table locks & CDX context...`, "info");
        setTimeout(() => showToast(`📝 Step 2/4: Injecting ${vouchers.length} voucher headers (RKACCT41.DBF)...`, "info"), 600);
        setTimeout(() => showToast(`✍️ Step 3/4: Writing double entries & memo narrations (RKACCT01/40.DBF)...`, "info"), 1400);
        setTimeout(() => showToast(`🔄 Step 4/4: Cross-syncing multi-year ledger masters (YR25, YR26, YR27)...`, "info"), 2200);
        
        if (currentModule === 'Bank Statements') {
            const targetBank = window.currentBankName || "Bank Account";
            pushBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1"></i> Pushing ${vouchers.length} txns to ${targetBank}...`;
        } else if (currentModule === 'Cash Entries') {
            const targetCashDropdown = document.getElementById('targetCashAccount');
            const targetCash = targetCashDropdown ? (targetCashDropdown.options[targetCashDropdown.selectedIndex].text) : "Cash Account";
            pushBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1"></i> Pushing ${vouchers.length} txns to ${targetCash}...`;
        } else if (currentModule === 'Opening Balances') {
            pushBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1"></i> Pushing ${vouchers.length} Opening Balances...`;
            const payload = { 
                entries: vouchers,
                backup_path: inlineBackupPath ? inlineBackupPath.value.trim() : ""
            };
            try {
                const res = await fetch(`${API_URL}/api/opening-balances/push`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.detail || "Failed to push opening balances.");
                }
                
                const result = await res.json();
                alert(`Successfully processed ${result.processed} opening balances (Inserted: ${result.inserted}, Updated: ${result.updated}).`);
                renderEmptyState();
            } catch (err) {
                console.error("Push failed:", err);
                alert(`Push Failed: ${err.message}`);
            } finally {
                pushBtn.disabled = false;
                pushBtn.classList.remove('cursor-not-allowed', 'opacity-50');
                pushBtn.innerHTML = originalHtml;
            }
            return;
        }

        let activeSetupId = currentModule === 'Sales' 
            ? (document.getElementById('salesSetupId') ? document.getElementById('salesSetupId').value : 5)
            : (document.getElementById('purchaseSetupId') ? document.getElementById('purchaseSetupId').value : 3);
            
        pushBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1"></i> Pushing ${vouchers.length} ${currentModule} bills (Setup ID: ${activeSetupId})...`;

        let formatOverride = document.getElementById('formatOverrideSelect') ? document.getElementById('formatOverrideSelect').value : "";
        let pushPayload = {
            module: currentModule,
            vouchers: vouchers,
            year_folder: activeYearFolder || null,
            backup_path: inlineBackupPath ? inlineBackupPath.value.trim() : ""
        };
        if (currentModule === 'Bank Statements' && window.currentBankName) {
            pushPayload.target_bank_name = window.currentBankName;
        } else if (currentModule === 'Cash Entries') {
            const targetCashDropdown = document.getElementById('targetCashAccount');
            if (targetCashDropdown && targetCashDropdown.value) {
                pushPayload.target_cash_code = targetCashDropdown.value;
            } else {
                alert("Please select a Target Cash Account before pushing.");
                pushBtn.innerHTML = `<i class="fa-solid fa-check-double mr-1"></i> Push to Miracle`;
                pushBtn.disabled = false;
                return;
            }
        }
        if (formatOverride) {
            pushPayload.format_override = formatOverride;
        }

        let targetPushEndpoint = `${API_URL}/api/push`;
        let targetBody = JSON.stringify(pushPayload);

        // If running on Render Cloud and Local Miracle Bridge Agent is online, inject directly to client PC
        if ((window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') || isLocalBridgeOnline) {
            if (isLocalBridgeOnline) {
                targetPushEndpoint = `${LOCAL_BRIDGE_URL}/inject`;
                const miracleBasePathVal = (typeof miracleBasePathInput !== 'undefined' && miracleBasePathInput && miracleBasePathInput.value) 
                    ? miracleBasePathInput.value.trim() 
                    : "C:\\Miracle";
                const backupPathVal = (typeof inlineBackupPath !== 'undefined' && inlineBackupPath && inlineBackupPath.value)
                    ? inlineBackupPath.value.trim()
                    : "";
                const bridgePayload = {
                    miracle_base_path: miracleBasePathVal,
                    active_client_id: getActiveClientId(),
                    active_year_folder: activeYearFolder || "YR25",
                    module_type: (currentModule === 'Bank Statements') ? 'bank' 
                        : (currentModule === 'Sales') ? 'sales' 
                        : (currentModule === 'Purchases') ? 'purchase' 
                        : (currentModule === 'Cash Entries') ? 'cash' : 'opening_balance',
                    vouchers: vouchers,
                    backup_path: backupPathVal
                };
                targetBody = JSON.stringify(bridgePayload);
                console.log("⚡ Hybrid Mode active: Routing push directly to Local Miracle Bridge on port 9123");
            }
        }

        try {
            const res = await fetch(targetPushEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: targetBody
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Failed to push to Miracle.");
            }
            
            const result = await res.json();
            
            if (result.primary_year && result.primary_year !== activeYearFolder) {
                activeYearFolder = result.primary_year;
                if (yearSelect) {
                    yearSelect.value = activeYearFolder;
                }
                updateHeaderBadges();
                console.log(`Auto-synced active year folder to ${activeYearFolder}`);
            }

            if (result.audit_report) {
                const ar = result.audit_report;
                window.lastAuditReport = {
                    client_id: getActiveClientId(),
                    active_year: activeYearFolder || 'YR26',
                    timestamp: new Date().toLocaleString(),
                    ...ar,
                    primary_year: result.primary_year || activeYearFolder
                };

                document.getElementById('auditInjectedCount').innerText = ar.injected || result.count || 0;
                document.getElementById('auditDuplicateCount').innerText = ar.duplicates || 0;
                document.getElementById('auditMissingCount').innerText = ar.missing_parties || 0;
                document.getElementById('auditAnomalyCount').innerText = ar.anomalies || 0;
                
                // ── DUPLICATE DETAILS TABLE ──────────────────────────────────────
                const dupSection = document.getElementById('auditDupSection');
                const dupTableBody = document.getElementById('auditDupTableBody');
                const dupBadgeCount = document.getElementById('auditDupBadgeCount');
                dupTableBody.innerHTML = '';
                
                const dupDetails = ar.duplicate_details || [];
                if (dupBadgeCount) {
                    dupBadgeCount.innerText = `${dupDetails.length} items`;
                }

                if (dupDetails.length > 0) {
                    dupSection.classList.remove('hidden');
                    dupDetails.forEach(d => {
                        const reasonText = d.reason || '';
                        let reasonBadge = '';
                        if (reasonText.includes('Already in Miracle')) {
                            reasonBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 whitespace-nowrap"><i class="fa-solid fa-database text-[10px]"></i> Already in Miracle</span>`;
                        } else if (reasonText.includes('Exact Match')) {
                            const subText = reasonText.replace('Exact Match', '').replace(/[\(\)]/g, '').trim();
                            reasonBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20 whitespace-nowrap"><i class="fa-solid fa-copy text-[10px]"></i> Exact Match ${subText ? `(${subText})` : ''}</span>`;
                        } else {
                            reasonBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20 whitespace-nowrap"><i class="fa-solid fa-triangle-exclamation text-[10px]"></i> ${reasonText || 'Skipped'}</span>`;
                        }

                        const moduleText = d.module || '';
                        const moduleBadge = moduleText === 'Bank Statements'
                            ? `<span class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 whitespace-nowrap"><i class="fa-solid fa-building-columns text-[10px] mr-1"></i> Bank</span>`
                            : `<span class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/20 whitespace-nowrap"><i class="fa-solid fa-file-invoice text-[10px] mr-1"></i> ${moduleText || 'Vouchers'}</span>`;

                        const amtFmt = Number(d.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2});
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-800/50 transition-colors border-b border-slate-800/40';
                        tr.innerHTML = `
                            <td class="px-4 py-3 text-slate-300 font-mono text-xs whitespace-nowrap">${d.date || '-'}</td>
                            <td class="px-4 py-3 text-amber-300 font-mono text-xs font-semibold whitespace-nowrap">${d.bill_no || '—'}</td>
                            <td class="px-4 py-3 text-white font-medium max-w-[200px] truncate" title="${d.party || ''}">${d.party || 'Unknown'}</td>
                            <td class="px-4 py-3 text-right text-emerald-400 font-bold font-mono text-xs whitespace-nowrap">₹${amtFmt}</td>
                            <td class="px-4 py-3 whitespace-nowrap">${reasonBadge}</td>
                            <td class="px-4 py-3 whitespace-nowrap">${moduleBadge}</td>
                        `;
                        dupTableBody.appendChild(tr);
                    });
                } else {
                    dupSection.classList.add('hidden');
                }
                // ─────────────────────────────────────────────────────────────────

                // ── GENERAL AUDIT LOGS ────────────────────────────────────────────
                const logList = document.getElementById('auditLogList');
                logList.innerHTML = '';
                if (ar.messages && ar.messages.length > 0) {
                    ar.messages.forEach(msg => {
                        const li = document.createElement('li');
                        li.className = 'border-b border-slate-800/60 pb-1.5 mb-1.5 text-amber-300/90 text-xs flex items-center gap-2';
                        li.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-400 text-xs"></i> <span>${msg}</span>`;
                        logList.appendChild(li);
                    });
                } else {
                    logList.innerHTML = '<li class="text-emerald-400 italic text-xs flex items-center gap-2"><i class="fa-solid fa-circle-check text-emerald-400"></i> No anomalies or missing items. Clean sweep verification!</li>';
                }
                // ─────────────────────────────────────────────────────────────────
                
                if (result.year_counts && Object.keys(result.year_counts).length > 0) {
                    const yrParts = Object.entries(result.year_counts).map(([y, c]) => `• FY ${y}: ${c} vouchers`).join(' | ');
                    showToast(`🎉 Miracle DBF Push Success! ${yrParts}`, "success");
                } else {
                    showToast(`🎉 Miracle DBF Push Success! Injected ${result.count || 0} vouchers into Miracle DBF.`, "success");
                }

                document.getElementById('auditReportModal').classList.remove('hidden');
            } else {
                showToast(`🎉 Miracle DBF Push Success! ${result.message}`, "success");
            }
            
            // Clear staging area on success
            renderEmptyState();
        } catch (err) {
            console.error("Push failed:", err);
            alert(`Push Failed: ${err.message}`);
        } finally {
            // Reset button state
            pushBtn.disabled = false;
            pushBtn.classList.remove('cursor-not-allowed', 'opacity-50');
            pushBtn.innerHTML = originalHtml;
        }
    });

    const closeAuditReportBtn = document.getElementById('closeAuditReportBtn');
    if (closeAuditReportBtn) {
        closeAuditReportBtn.addEventListener('click', () => {
            document.getElementById('auditReportModal').classList.add('hidden');
        });
    }

    const downloadAuditPdfBtn = document.getElementById('downloadAuditPdfBtn');
    if (downloadAuditPdfBtn) {
        downloadAuditPdfBtn.addEventListener('click', () => {
            downloadAuditPdf();
        });
    }

// ── EXPORT AUDIT PDF FUNCTION ────────────────────────────────────────────────
function downloadAuditPdf() {
    if (!window.lastAuditReport) {
        showToast("No audit report data available to export.", "error");
        return;
    }

    const ar = window.lastAuditReport;
    const clientId = ar.client_id || getActiveClientId();
    const activeYr = ar.active_year || activeYearFolder || 'YR26';
    const timestamp = ar.timestamp || new Date().toLocaleString();
    const dupDetails = ar.duplicate_details || [];
    const messages = ar.messages || [];

    const injected = ar.injected || 0;
    const duplicates = ar.duplicates || 0;
    const anomalies = ar.anomalies || 0;
    const missing = ar.missing_parties || 0;

    const element = document.createElement('div');
    element.className = 'pdf-export-container';
    element.style.padding = '25px 30px';
    element.style.fontFamily = "'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif";
    element.style.color = '#0F172A';
    element.style.backgroundColor = '#FFFFFF';

    let dupTableRows = '';
    if (dupDetails.length > 0) {
        dupDetails.forEach((d, idx) => {
            const amt = Number(d.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2});
            dupTableRows += `
                <tr style="background-color: ${idx % 2 === 0 ? '#F8FAFC' : '#FFFFFF'}; border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 9px 12px; font-size: 11px; font-family: monospace;">${d.date || '-'}</td>
                    <td style="padding: 9px 12px; font-size: 11px; font-family: monospace; font-weight: 700; color: #B45309;">${d.bill_no || '—'}</td>
                    <td style="padding: 9px 12px; font-size: 11px; font-weight: 600; color: #1E293B;">${d.party || 'Unknown'}</td>
                    <td style="padding: 9px 12px; font-size: 11px; font-family: monospace; font-weight: 700; text-align: right; color: #047857;">₹${amt}</td>
                    <td style="padding: 9px 12px; font-size: 10px; color: #92400E;"><span style="background: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 12px; font-weight: 600;">${d.reason || 'Duplicate'}</span></td>
                    <td style="padding: 9px 12px; font-size: 10px; color: #4338CA;"><span style="background: #EEF2FF; color: #4338CA; padding: 4px 10px; border-radius: 12px; font-weight: 600;">${d.module || 'Vouchers'}</span></td>
                </tr>
            `;
        });
    } else {
        dupTableRows = `<tr><td colspan="6" style="padding: 16px; text-align: center; color: #047857; font-style: italic;">No skipped duplicates recorded in this injection batch.</td></tr>`;
    }

    let logItems = '';
    if (messages.length > 0) {
        messages.forEach(msg => {
            logItems += `<li style="margin-bottom: 6px; font-size: 11px; color: #B45309;">⚠️ ${msg}</li>`;
        });
    } else {
        logItems = `<li style="font-size: 11px; color: #047857; font-style: italic;">✅ No anomalies or missing items detected. Verification clean sweep!</li>`;
    }

    element.innerHTML = `
        <div style="border-bottom: 2px solid #4F46E5; padding-bottom: 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="font-size: 22px; font-weight: 800; color: #4F46E5; margin: 0 0 4px 0; tracking-tight: -0.5px;">Miracle AI Auto-Entry</h1>
                <h2 style="font-size: 13px; font-weight: 700; color: #1E293B; margin: 0; letter-spacing: 0.5px;">DATABASE INJECTION AUDIT REPORT & VERIFICATION CERTIFICATE</h2>
            </div>
            <div style="text-align: right; font-size: 10px; color: #64748B; line-height: 1.5;">
                <div><strong>Client ID:</strong> ${clientId}</div>
                <div><strong>Financial Year:</strong> ${activeYr}</div>
                <div><strong>Report Time:</strong> ${timestamp}</div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px;">
            <div style="background: #ECFDF5; border: 1px solid #A7F3D0; padding: 12px; border-radius: 10px; text-align: center;">
                <div style="font-size: 10px; font-weight: 700; color: #047857; text-transform: uppercase;">Injected Vouchers</div>
                <div style="font-size: 24px; font-weight: 900; color: #047857; margin-top: 2px;">${injected}</div>
            </div>
            <div style="background: #FEF3C7; border: 1px solid #FDE68A; padding: 12px; border-radius: 10px; text-align: center;">
                <div style="font-size: 10px; font-weight: 700; color: #B45309; text-transform: uppercase;">Duplicates Skipped</div>
                <div style="font-size: 24px; font-weight: 900; color: #B45309; margin-top: 2px;">${duplicates}</div>
            </div>
            <div style="background: #FEF2F2; border: 1px solid #FCA5A5; padding: 12px; border-radius: 10px; text-align: center;">
                <div style="font-size: 10px; font-weight: 700; color: #B91C1C; text-transform: uppercase;">Anomalies Flagged</div>
                <div style="font-size: 24px; font-weight: 900; color: #B91C1C; margin-top: 2px;">${anomalies}</div>
            </div>
            <div style="background: #EEF2FF; border: 1px solid #C7D2FE; padding: 12px; border-radius: 10px; text-align: center;">
                <div style="font-size: 10px; font-weight: 700; color: #4338CA; text-transform: uppercase;">Missing Parties</div>
                <div style="font-size: 24px; font-weight: 900; color: #4338CA; margin-top: 2px;">${missing}</div>
            </div>
        </div>

        <div style="margin-bottom: 24px;">
            <h3 style="font-size: 12px; font-weight: 700; color: #1E293B; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px;">
                📋 Skipped Duplicate Vouchers Summary (${dupDetails.length} items)
            </h3>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #CBD5E1; border-radius: 8px; overflow: hidden;">
                <thead>
                    <tr style="background: #0F172A; color: #FFFFFF; font-size: 10px; text-transform: uppercase; text-align: left;">
                        <th style="padding: 9px 12px;">Date</th>
                        <th style="padding: 9px 12px;">Bill No</th>
                        <th style="padding: 9px 12px;">Party Name</th>
                        <th style="padding: 9px 12px; text-align: right;">Amount</th>
                        <th style="padding: 9px 12px;">Reason</th>
                        <th style="padding: 9px 12px;">Module</th>
                    </tr>
                </thead>
                <tbody>
                    ${dupTableRows}
                </tbody>
            </table>
        </div>

        <div style="margin-bottom: 24px;">
            <h3 style="font-size: 12px; font-weight: 700; color: #1E293B; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px;">
                📝 Audit Log & System Messages
            </h3>
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 16px; border-radius: 8px;">
                <ul style="margin: 0; padding-left: 16px; font-family: monospace;">
                    ${logItems}
                </ul>
            </div>
        </div>

        <div style="margin-top: 36px; border-top: 1px solid #CBD5E1; padding-top: 14px; display: flex; justify-content: space-between; align-items: flex-end; font-size: 10px; color: #64748B;">
            <div>
                <div><strong>Verified By:</strong> Miracle DBF Injection Engine</div>
                <div><strong>Verification ID:</strong> AUDIT-VERIFIED-${Date.now().toString(16).toUpperCase()}</div>
            </div>
            <div style="text-align: right;">
                <div>_________________________________________</div>
                <div style="margin-top: 4px; font-weight: 600; color: #1E293B;">Authorized Signature</div>
            </div>
        </div>
    `;

    const opt = {
        margin:       [10, 10, 10, 10],
        filename:     `Miracle_Audit_Report_${clientId}_${new Date().toISOString().slice(0,10)}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, logging: false, useCORS: true },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    if (typeof html2pdf !== 'undefined') {
        showToast("📄 Generating PDF audit report...", "info");
        html2pdf().set(opt).from(element).save().then(() => {
            showToast("✅ Audit PDF downloaded successfully!", "success");
        }).catch(err => {
            console.error("html2pdf failed, fallback to print window:", err);
            printElementFallback(element);
        });
    } else {
        printElementFallback(element);
    }
}

function printElementFallback(element) {
    const printWin = window.open('', '_blank', 'width=900,height=800');
    if (!printWin) {
        showToast("Pop-up blocked. Please allow pop-ups to print PDF.", "error");
        return;
    }
    printWin.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Miracle Audit Report PDF</title>
            <style>
                body { margin: 0; padding: 20px; font-family: 'Segoe UI', Arial, sans-serif; }
                @media print {
                    body { padding: 0; }
                }
            </style>
        </head>
        <body>
            ${element.outerHTML}
            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        </body>
        </html>
    `);
    printWin.document.close();
}

    // --- DOCUMENT VIEWER RESIZER & TOGGLE LOGIC ---
    const docViewerPanel = document.getElementById('docViewerPanel');
    const panelResizer = document.getElementById('panelResizer');
    const toggleDocViewerBtn = document.getElementById('toggleDocViewerBtn');
    
    // --- SIDEBAR TOGGLE LOGIC ---
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const mainSidebar = document.getElementById('mainSidebar');
    if (toggleSidebarBtn && mainSidebar) {
        let isSidebarOpen = true;
        toggleSidebarBtn.addEventListener('click', () => {
            isSidebarOpen = !isSidebarOpen;
            if (isSidebarOpen) {
                mainSidebar.classList.remove('w-0', 'opacity-0', 'overflow-hidden');
                mainSidebar.classList.add('w-80');
                toggleSidebarBtn.innerHTML = '<i class="fa-solid fa-bars-staggered"></i>';
                toggleSidebarBtn.classList.remove('text-brand-500');
                toggleSidebarBtn.classList.add('text-slate-400');
            } else {
                mainSidebar.classList.remove('w-80');
                mainSidebar.classList.add('w-0', 'opacity-0', 'overflow-hidden');
                toggleSidebarBtn.innerHTML = '<i class="fa-solid fa-bars"></i>';
                toggleSidebarBtn.classList.add('text-brand-500');
                toggleSidebarBtn.classList.remove('text-slate-400');
            }
        });
    }
    
    // --- FORCE MATH RECALCULATION & DELEGATION ---
    const recalculateMathBtn = document.getElementById('recalculateMathBtn');
    if (recalculateMathBtn) {
        recalculateMathBtn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            recalcGrandTotals();
            renderVirtualGridRows();
            showToast("Recalculated Closing Balances & Math Totals!", "success");
            
            // Tiny visual feedback
            const icon = recalculateMathBtn.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-calculator');
                icon.classList.add('fa-check', 'text-emerald-400');
                setTimeout(() => {
                    icon.classList.remove('fa-check', 'text-emerald-400');
                    icon.classList.add('fa-calculator');
                }, 1200);
            }
        });
    }

    const autoResolveSuspenseBtn = document.getElementById('autoResolveSuspenseBtn');
    if (autoResolveSuspenseBtn) {
        autoResolveSuspenseBtn.addEventListener('click', async (e) => {
            if (e) e.preventDefault();
            if (!currentExtractedData || currentExtractedData.length === 0) {
                showToast("No staged data available to resolve.", "warning");
                return;
            }
            const originalHtml = autoResolveSuspenseBtn.innerHTML;
            autoResolveSuspenseBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> AI Resolving...`;
            autoResolveSuspenseBtn.disabled = true;
            try {
                const res = await fetch(`${API_URL}/api/resolve-suspense`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ vouchers: currentExtractedData, year_folder: activeYearFolder || "" })
                });
                if (!res.ok) throw new Error("Failed to resolve suspense entries.");
                const result = await res.json();
                if (result.vouchers) {
                    currentExtractedData = result.vouchers;
                    currentGridFilter = 'all';
                    gridBody.innerHTML = '';
                    delete gridBody.dataset.needsFullRender;
                    updateFilterCounts();
                    renderFilterBadgesForModule();
                    renderGrid(currentExtractedData);
                    recalcGrandTotals();
                    if (typeof saveGridSnapshotToLocalStorage === 'function') {
                        saveGridSnapshotToLocalStorage();
                    }
                    showToast("AI Suspense Resolution complete! All party ledgers mapped.", "success");
                }
            } catch (err) {
                console.error("Resolve suspense failed:", err);
                showToast(`Error: ${err.message}`, "error");
            } finally {
                autoResolveSuspenseBtn.innerHTML = originalHtml;
                autoResolveSuspenseBtn.disabled = false;
            }
        });
    }

    // Fail-safe event delegation to catch any stray keystrokes that bypassed the inline listeners
    const mainGridBody = document.getElementById('gridBody');
    if (mainGridBody) {
        const forceMathSync = (e) => {
            if (e.target.tagName === 'INPUT') {
                recalcGrandTotals();
            }
        };
        mainGridBody.addEventListener('input', forceMathSync);
        mainGridBody.addEventListener('keyup', forceMathSync);
        mainGridBody.addEventListener('change', forceMathSync);
    }
    // --- UPLOAD ZONE TOGGLE LOGIC ---
    const toggleUploadZoneBtn = document.getElementById('toggleUploadZoneBtn');
    const uploadZoneCard = document.getElementById('uploadZoneCard');
    // --- TOP BAR ACTION TOOLBAR SMOOTH HORIZONTAL WHEEL SCROLL ---
    const topBarActionsToolbar = document.getElementById('topBarActionsToolbar');
    if (topBarActionsToolbar) {
        topBarActionsToolbar.addEventListener('wheel', (e) => {
            if (e.deltaY !== 0) {
                e.preventDefault();
                topBarActionsToolbar.scrollLeft += e.deltaY;
            }
        }, { passive: false });
    }

    if (toggleUploadZoneBtn && uploadZoneCard) {
        let isUploadZoneOpen = true;
        toggleUploadZoneBtn.addEventListener('click', () => {
            isUploadZoneOpen = !isUploadZoneOpen;
            if (isUploadZoneOpen) {
                uploadZoneCard.style.display = 'flex';
                toggleUploadZoneBtn.innerHTML = '<i class="fa-solid fa-compress text-xs"></i> <span>Hide Tools</span>';
                toggleUploadZoneBtn.classList.remove('text-brand-500');
                toggleUploadZoneBtn.classList.add('text-slate-300');
            } else {
                uploadZoneCard.style.display = 'none';
                toggleUploadZoneBtn.innerHTML = '<i class="fa-solid fa-expand text-xs"></i> <span>Show Tools</span>';
                toggleUploadZoneBtn.classList.add('text-brand-500');
                toggleUploadZoneBtn.classList.remove('text-slate-300');
            }
        });

        // Drag & Drop Multi-File Upload Handling
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZoneCard.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZoneCard.addEventListener(eventName, () => {
                uploadZoneCard.classList.add('border-brand-500', 'bg-brand-500/10');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZoneCard.addEventListener(eventName, () => {
                uploadZoneCard.classList.remove('border-brand-500', 'bg-brand-500/10');
            }, false);
        });

        uploadZoneCard.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0 && fileInput) {
                fileInput.files = files;
                fileInput.dispatchEvent(new Event('change'));
            }
        });
    }

    if (toggleDocViewerBtn && docViewerPanel && panelResizer) {
        let isDocViewerOpen = false;
        docViewerPanel.style.display = 'none';
        panelResizer.style.display = 'none';
        
        toggleDocViewerBtn.addEventListener('click', () => {
            isDocViewerOpen = !isDocViewerOpen;
            if (isDocViewerOpen) {
                docViewerPanel.style.display = 'flex';
                panelResizer.style.display = 'flex';
                toggleDocViewerBtn.classList.add('text-brand-500');
                toggleDocViewerBtn.classList.remove('text-slate-400');
            } else {
                docViewerPanel.style.display = 'none';
                panelResizer.style.display = 'none';
                toggleDocViewerBtn.classList.add('text-slate-400');
                toggleDocViewerBtn.classList.remove('text-brand-500');
            }
        });

        let isResizing = false;
        panelResizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.classList.add('select-none'); // Prevent text selection during drag
        });

        window.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            // Calculate new width: viewport width - mouse X
            let newWidth = window.innerWidth - e.clientX;
            // Constraints to prevent panel from becoming too small or too large
            if (newWidth < 250) newWidth = 250;
            if (newWidth > 800) newWidth = 800;
            docViewerPanel.style.width = newWidth + 'px';
        });

        window.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = 'default';
                document.body.classList.remove('select-none');
            }
        });
    }

    const addEntryBtn = document.getElementById('addEntryBtn');
    if (addEntryBtn) {
        addEntryBtn.addEventListener('click', (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            console.log("Add Row clicked! currentModule:", currentModule, "currentExtractedData:", currentExtractedData);
            if (!currentExtractedData) currentExtractedData = [];
            
            const todayStr = new Date().toISOString().split('T')[0];
            const newRow = {
                id: ++globalIndexCounter,
                status: 'Ready',
                items: []
            };
            
            if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                newRow.date = todayStr;
                newRow.reference_no = '';
                newRow.narration = 'New Manual Entry';
                newRow.mapped_ledger = 'Suspense Account';
                newRow.transaction_type = 'Payment';
                newRow.amount = 0;
                newRow.party_name = 'Suspense Account';
                newRow.party = 'Suspense Account';
            } else if (currentModule === 'Opening Balances') {
                newRow.ledger_name = 'New Ledger';
                newRow.dr_cr = 'D';
                newRow.balance = 0;
            } else {
                newRow.date = todayStr;
                newRow.billNo = 'MANUAL-' + Math.floor(Math.random() * 10000);
                newRow.party = 'New Manual Party';
                newRow.taxable = 0;
                newRow.gst = 0;
                newRow.discount = 0;
                newRow.freight = 0;
                newRow.tcs = 0;
                newRow.tds = 0;
                newRow.total = 0;
            }
            
            currentExtractedData.push(newRow); // Add to the bottom
            renderGrid(currentExtractedData);
            
            // Scroll table container specifically to bottom & re-render virtual slice for bottom row
            const gridContainer = document.getElementById('gridTableContainer');
            if (gridContainer) {
                setTimeout(() => {
                    gridContainer.scrollTop = gridContainer.scrollHeight;
                    renderVirtualGridRows();
                    
                    // Auto-focus the narration / party input in the newly added row
                    const lastRow = gridBody.querySelector('tr:last-child');
                    if (lastRow) {
                        const targetInput = lastRow.querySelector('input.narration-input') || lastRow.querySelector('input[type="text"]') || lastRow.querySelector('input');
                        if (targetInput) {
                            targetInput.focus();
                            if (typeof targetInput.select === 'function') targetInput.select();
                        }
                    }
                }, 30);
            }
        });
    }

    // --- LIVE GRID SEARCH & FILTER EVENT LISTENERS ---
    const gridSearchInput = document.getElementById('gridSearchInput');
    if (gridSearchInput) {
        gridSearchInput.addEventListener('input', (e) => {
            currentGridSearch = e.target.value.trim();
            recalcGrandTotals();
            renderVirtualGridRows();
        });
    }

    // --- POWER-USER KEYBOARD SHORTCUTS ---
    document.addEventListener('keydown', (e) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const ctrlKey = isMac ? e.metaKey : e.ctrlKey;

        // Cmd/Ctrl + F: Focus Live Search Input
        if (ctrlKey && e.key.toLowerCase() === 'f') {
            const searchInput = document.getElementById('gridSearchInput');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        }
        // Cmd/Ctrl + U: Trigger File Upload
        else if (ctrlKey && e.key.toLowerCase() === 'u') {
            const fileInput = document.getElementById('fileInput');
            if (fileInput) {
                e.preventDefault();
                fileInput.click();
            }
        }
        // Cmd/Ctrl + S: Trigger Push to Miracle
        else if (ctrlKey && e.key.toLowerCase() === 's') {
            const pushBtn = document.getElementById('pushBtn');
            if (pushBtn && !pushBtn.disabled) {
                e.preventDefault();
                pushBtn.click();
            }
        }
        // Esc: Close Modals
        else if (e.key === 'Escape') {
            const settingsModal = document.getElementById('settingsModal');
            if (settingsModal && !settingsModal.classList.contains('hidden')) {
                settingsModal.classList.add('hidden');
            }
            const pdfPasswordModal = document.getElementById('pdfPasswordModal');
            if (pdfPasswordModal && !pdfPasswordModal.classList.contains('hidden')) {
                pdfPasswordModal.classList.add('hidden');
                pendingUploadContext = null;
                if (loadingState) loadingState.classList.add('hidden');
            }
        }
    });

    // --- ENCRYPTED PDF PASSWORD MODAL ---
    let pendingUploadContext = null;

    const pdfPasswordModal = document.getElementById('pdfPasswordModal');
    const pdfPasswordForm = document.getElementById('pdfPasswordForm');
    const pdfPasswordInput = document.getElementById('pdfPasswordInput');
    const pdfPasswordDesc = document.getElementById('pdfPasswordDesc');
    const pdfPasswordErrorAlert = document.getElementById('pdfPasswordErrorAlert');
    const pdfPasswordErrorMsg = document.getElementById('pdfPasswordErrorMsg');
    const closePdfPasswordModalBtn = document.getElementById('closePdfPasswordModalBtn');
    const cancelPdfPasswordBtn = document.getElementById('cancelPdfPasswordBtn');
    const togglePdfPasswordVisibilityBtn = document.getElementById('togglePdfPasswordVisibilityBtn');
    const togglePdfPasswordIcon = document.getElementById('togglePdfPasswordIcon');

    function showPdfPasswordModal(message, isIncorrect = false, filename = '') {
        if (!pdfPasswordModal) return;
        if (pdfPasswordDesc) {
            pdfPasswordDesc.innerText = filename 
                ? `The document '${filename}' is encrypted with a password. Please enter the password to process and extract data.`
                : "The document is encrypted with a password. Please enter the password to process and extract data.";
        }
        if (isIncorrect && pdfPasswordErrorAlert) {
            pdfPasswordErrorMsg.innerText = message || "Incorrect password. Please try again.";
            pdfPasswordErrorAlert.classList.remove('hidden');
        } else if (pdfPasswordErrorAlert) {
            pdfPasswordErrorAlert.classList.add('hidden');
        }
        if (pdfPasswordInput) {
            pdfPasswordInput.value = '';
        }
        pdfPasswordModal.classList.remove('hidden');
        setTimeout(() => { if (pdfPasswordInput) pdfPasswordInput.focus(); }, 100);
    }

    function hidePdfPasswordModal() {
        if (pdfPasswordModal) {
            pdfPasswordModal.classList.add('hidden');
        }
        if (pdfPasswordErrorAlert) {
            pdfPasswordErrorAlert.classList.add('hidden');
        }
    }

    if (closePdfPasswordModalBtn) {
        closePdfPasswordModalBtn.addEventListener('click', () => {
            hidePdfPasswordModal();
            pendingUploadContext = null;
            if (loadingState) loadingState.classList.add('hidden');
        });
    }

    if (cancelPdfPasswordBtn) {
        cancelPdfPasswordBtn.addEventListener('click', () => {
            hidePdfPasswordModal();
            pendingUploadContext = null;
            if (loadingState) loadingState.classList.add('hidden');
        });
    }

    if (togglePdfPasswordVisibilityBtn) {
        togglePdfPasswordVisibilityBtn.addEventListener('click', () => {
            if (pdfPasswordInput && pdfPasswordInput.type === 'password') {
                pdfPasswordInput.type = 'text';
                if (togglePdfPasswordIcon) {
                    togglePdfPasswordIcon.classList.remove('fa-eye');
                    togglePdfPasswordIcon.classList.add('fa-eye-slash');
                }
            } else if (pdfPasswordInput) {
                pdfPasswordInput.type = 'password';
                if (togglePdfPasswordIcon) {
                    togglePdfPasswordIcon.classList.remove('fa-eye-slash');
                    togglePdfPasswordIcon.classList.add('fa-eye');
                }
            }
        });
    }

    if (pdfPasswordForm) {
        pdfPasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const enteredPassword = pdfPasswordInput ? pdfPasswordInput.value.trim() : '';
            if (!enteredPassword || !pendingUploadContext) return;
            
            const ctx = pendingUploadContext;
            hidePdfPasswordModal();
            
            retryUploadWithPassword(ctx.file, ctx.module, ctx.instruction, enteredPassword);
        });
    }

    async function retryUploadWithPassword(file, module, instruction, password) {
        if (!loadingState) return;
        const loadingMsg = loadingState.querySelector('h3');
        const loadingSub = loadingState.querySelector('p');
        
        loadingMsg.innerText = `Decrypting & Extracting Data...`;
        loadingSub.innerText = `Unlocking ${file.name} with provided password.`;
        loadingState.classList.remove('hidden');

        const formData = new FormData();
        formData.append("file", file);
        formData.append("module", module);
        formData.append("instruction", instruction || "");
        formData.append("pdf_password", password);

        if ((module === 'Bank Statements' || module === 'Cash Entries') && clientLedgers.length > 0) {
            const ledgerNames = clientLedgers.map(l => l.name).join(", ");
            formData.append("ledgers_list", ledgerNames);
        }

        try {
            const res = await fetch(`${API_URL}/api/upload`, {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                if (errorData && errorData.requires_password) {
                    loadingState.classList.add('hidden');
                    showPdfPasswordModal(errorData.message, true, file.name);
                    return;
                }
                throw new Error(errorData.detail || `Failed to extract data from ${file.name}`);
            }

            const resData = await res.json();
            const data = resData.data || resData;
            window.currentBankName = data.bank_name || "Bank Account";
            window.lastProcessedData = data;

            if (data.opening_balance !== undefined) {
                const opBalInput = document.getElementById('openingBalanceInput');
                if (opBalInput) {
                    opBalInput.value = data.opening_balance;
                }
            }

            // Auto-detect year and client if detected
            if (resData.detected_year && resData.detected_year !== activeYearFolder) {
                activeYearFolder = resData.detected_year;
                if (yearSelect) yearSelect.value = activeYearFolder;
            }
            if (resData.detected_client && resData.detected_client !== clientSelect.value) {
                clientSelect.value = resData.detected_client;
                if (settingsActiveClient) settingsActiveClient.value = resData.detected_client;
            }

            // Refresh ledgers and render results into grid
            fetchLedgers().then(() => {
                let extractedArray = null;
                if (Array.isArray(data)) extractedArray = data;
                else if (data && typeof data === 'object') {
                    if (Array.isArray(data.extracted_data)) extractedArray = data.extracted_data;
                    else if (Array.isArray(data.data)) extractedArray = data.data;
                    else if (Array.isArray(data.invoices)) extractedArray = data.invoices;
                    else if (Array.isArray(data.results)) extractedArray = data.results;
                }

                if (extractedArray && Array.isArray(extractedArray)) {
                    let globalIndexCounter = 0;
                    const formattedData = extractedArray.map((row) => {
                        if (currentModule === 'Bank Statements' || currentModule === 'Cash Entries') {
                            const resolvedLedger = row.mapped_ledger || row.party_name || row.party || "Suspense Account";
                            const cleanLedger = resolvedLedger.trim().toUpperCase();
                            let status = (cleanLedger === "SUSPENSE ACCOUNT") ? 'Review' : 'Ready';
                            const amt = Number(row.amount || row.Amount || 0);
                            const txType = row.transaction_type || "Receipt";
                            return {
                                id: ++globalIndexCounter,
                                date: row.date || row.Date || "",
                                reference_no: row.reference_no || row.reference || "",
                                narration: row.narration || "",
                                party_name: resolvedLedger,
                                mapped_ledger: resolvedLedger,
                                party: resolvedLedger,
                                transaction_type: txType,
                                amount: amt,
                                withdrawal: txType === 'Payment' ? amt : Number(row.withdrawal || 0),
                                deposit: txType === 'Receipt' ? amt : Number(row.deposit || 0),
                                balance: Number(row.balance || 0),
                                status: status,
                                isB2C: false,
                                autoCreateB2B: false,
                                group_hint: row.group_hint || "",
                                confidence_score: row.confidence_score || 100,
                                flags: row.flags || []
                            };
                        } else {
                            const party = row.party_name || row.party || row.PartyName || "UNKNOWN_PARTY: Missing";
                            const billNo = row.bill_no || row.billNo || row.invoice_no || "";
                            const taxable = row.taxable_amount || row.taxable || 0;
                            const cgst = row.cgst || 0;
                            const sgst = row.sgst || 0;
                            const igst = row.igst || 0;
                            const gst = cgst + sgst + igst || row.gst || 0;
                            const discount = row.discount || 0;
                            const freight = row.freight || 0;
                            const tcs = row.tcs || 0;
                            const tds = row.tds || 0;
                            const total = row.total || row.total_amount || 0;
                            return {
                                id: ++globalIndexCounter,
                                date: row.date || row.Date || "",
                                billNo: String(billNo),
                                party: party,
                                party_gstin: row.party_gstin || row.gstin || "",
                                party_address: row.party_address || "",
                                taxable: Number(taxable),
                                cgst: Number(cgst),
                                sgst: Number(sgst),
                                igst: Number(igst),
                                gst: Number(gst),
                                discount: Number(discount),
                                freight: Number(freight),
                                tcs: Number(tcs),
                                tds: Number(tds),
                                total: Number(total),
                                status: 'Ready',
                                items: row.items || []
                            };
                        }
                    });

                    finalizeExtraction(formattedData);
                    showToast(`Successfully unlocked & extracted ${file.name}! (${formattedData.length} entries)`, "success");
                }
                loadingState.classList.add('hidden');
                pendingUploadContext = null;
            });

        } catch (err) {
            loadingState.classList.add('hidden');
            showToast(`Error: ${err.message}`, "error");
        }
    }

    // Synchronize default module immediately on load
    selectModule('Sales');
});
