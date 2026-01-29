/**
 * Nostr Feedback Widget
 * 
 * A simple feedback widget that publishes Kind 1 events to Nostr relays.
 * Comments are tagged to a specific pubkey for private collection.
 */

// Configuration
const CONFIG = {
    targetPubkey: '87ad21b2fffac510fb01f631edc2b3c09c49297a4f65187656c72cf7da04d328',
    relays: [
        'wss://relay.damus.io',
        'wss://relay.primal.net',
        'wss://relay.bitcoindistrict.org',
        'wss://nos.lol',
        'wss://relay.nostr.band',
        'wss://nostr.wine',
        'wss://relay.snort.social',
        'wss://relay.current.fyi',
        'wss://nostr.fmt.wiz.biz',
        'wss://relay.nostr.bg'
    ],
    storageKey: 'fredco-feedback:user',
    clientTag: 'fredco-audit',
    connectionTimeout: 5000 // 5 second timeout for relay connections
};

// Topics for dropdown (shared across pages, page-specific ones added dynamically)
const TOPICS = {
    county: [
        { value: 'general', label: 'General Feedback' },
        { value: 'budget-growth', label: 'Budget Growth Analysis' },
        { value: 'department-spending', label: 'Department Spending' },
        { value: 'personnel', label: 'Personnel & Staffing' },
        { value: 'school-funding', label: 'School Funding' },
        { value: 'tax-rates', label: 'Tax Rates' },
        { value: 'data-accuracy', label: 'Data Accuracy Issue' },
        { value: 'feature-request', label: 'Feature Request' },
        { value: 'other', label: 'Other' }
    ],
    schools: [
        { value: 'general', label: 'General Feedback' },
        { value: 'admin-efficiency', label: 'Admin Efficiency' },
        { value: 'per-pupil-spending', label: 'Per-Pupil Spending' },
        { value: 'class-sizes', label: 'Class Sizes' },
        { value: 'peer-comparison', label: 'Peer Comparison' },
        { value: 'data-accuracy', label: 'Data Accuracy Issue' },
        { value: 'feature-request', label: 'Feature Request' },
        { value: 'other', label: 'Other' }
    ]
};

// State
let state = {
    secretKey: null,
    publicKey: null,
    name: '',
    rememberMe: false,
    isOpen: false,
    isAdvancedOpen: false,
    isSubmitting: false,
    connectedRelays: [],
    connectionStatus: 'disconnected' // 'disconnected', 'connecting', 'connected', 'error'
};

// Nostr-tools imports (loaded dynamically)
let nostrTools = null;
let pool = null;

/**
 * Load nostr-tools from CDN
 */
async function loadNostrTools() {
    if (nostrTools) return nostrTools;
    
    try {
        const [pure, poolModule, nip19] = await Promise.all([
            import('https://esm.sh/nostr-tools@2.10.0/pure'),
            import('https://esm.sh/nostr-tools@2.10.0/pool'),
            import('https://esm.sh/nostr-tools@2.10.0/nip19')
        ]);
        
        nostrTools = { ...pure, ...poolModule, ...nip19 };
        return nostrTools;
    } catch (error) {
        console.error('Failed to load nostr-tools:', error);
        throw new Error('Failed to load required libraries');
    }
}

/**
 * Connect to relays and track connection status
 */
async function connectToRelays(onStatusChange) {
    const tools = await loadNostrTools();
    
    state.connectionStatus = 'connecting';
    onStatusChange?.(state.connectionStatus, 0);
    
    pool = new tools.SimplePool();
    state.connectedRelays = [];
    
    // Try to connect to each relay
    const connectionPromises = CONFIG.relays.map(async (relayUrl) => {
        try {
            // SimplePool connects lazily, so we'll do a quick subscription to test
            const relay = await pool.ensureRelay(relayUrl);
            
            // Wait for connection with timeout
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error(`Timeout connecting to ${relayUrl}`));
                }, CONFIG.connectionTimeout);
                
                if (relay.status === 1) { // WebSocket.OPEN
                    clearTimeout(timeout);
                    resolve();
                } else {
                    relay.onconnect = () => {
                        clearTimeout(timeout);
                        resolve();
                    };
                    relay.ondisconnect = () => {
                        clearTimeout(timeout);
                        reject(new Error(`Disconnected from ${relayUrl}`));
                    };
                }
            });
            
            state.connectedRelays.push(relayUrl);
            onStatusChange?.(state.connectionStatus, state.connectedRelays.length);
            console.log(`Connected to ${relayUrl}`);
            return { relay: relayUrl, connected: true };
        } catch (err) {
            console.warn(`Failed to connect to ${relayUrl}:`, err.message);
            return { relay: relayUrl, connected: false, error: err.message };
        }
    });
    
    await Promise.allSettled(connectionPromises);
    
    if (state.connectedRelays.length > 0) {
        state.connectionStatus = 'connected';
        console.log(`Connected to ${state.connectedRelays.length}/${CONFIG.relays.length} relays`);
    } else {
        state.connectionStatus = 'error';
        console.error('Failed to connect to any relay');
    }
    
    onStatusChange?.(state.connectionStatus, state.connectedRelays.length);
    return state.connectedRelays.length;
}

/**
 * Generate a new keypair
 */
async function generateKeypair() {
    const tools = await loadNostrTools();
    const secretKey = tools.generateSecretKey();
    const publicKey = tools.getPublicKey(secretKey);
    return { secretKey, publicKey };
}

/**
 * Load saved user data from localStorage
 */
function loadSavedUser() {
    try {
        const saved = localStorage.getItem(CONFIG.storageKey);
        if (!saved) return null;
        
        const data = JSON.parse(saved);
        if (data.secretKey && data.name) {
            // Convert hex string back to Uint8Array
            const secretKey = new Uint8Array(
                data.secretKey.match(/.{1,2}/g).map(byte => parseInt(byte, 16))
            );
            return {
                secretKey,
                publicKey: data.publicKey,
                name: data.name
            };
        }
    } catch (e) {
        console.error('Failed to load saved user:', e);
    }
    return null;
}

/**
 * Save user data to localStorage
 */
function saveUser(secretKey, publicKey, name) {
    try {
        // Convert Uint8Array to hex string for storage
        const secretKeyHex = Array.from(secretKey)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
        
        localStorage.setItem(CONFIG.storageKey, JSON.stringify({
            secretKey: secretKeyHex,
            publicKey,
            name,
            savedAt: Date.now()
        }));
    } catch (e) {
        console.error('Failed to save user:', e);
    }
}

/**
 * Clear saved user data
 */
function clearSavedUser() {
    localStorage.removeItem(CONFIG.storageKey);
}

/**
 * Get npub from public key
 */
async function getNpub(publicKey) {
    const tools = await loadNostrTools();
    return tools.npubEncode(publicKey);
}

/**
 * Publish feedback to Nostr relays
 */
async function publishFeedback(name, comment, topic, pageType) {
    const tools = await loadNostrTools();
    
    if (state.connectedRelays.length === 0) {
        throw new Error('Not connected to any relays');
    }
    
    // Ensure we have a keypair
    if (!state.secretKey) {
        const keypair = await generateKeypair();
        state.secretKey = keypair.secretKey;
        state.publicKey = keypair.publicKey;
    }
    
    // Build event content
    const pageUrl = window.location.href;
    const content = `Feedback from: ${name}
Topic: ${topic}
Page: ${pageUrl}
---
${comment}`;
    
    // Create unsigned event
    const unsignedEvent = {
        kind: 1,
        created_at: Math.floor(Date.now() / 1000),
        tags: [
            ['p', CONFIG.targetPubkey],
            ['client', CONFIG.clientTag],
            ['t', `feedback-${pageType}`],
            ['t', `topic-${topic}`]
        ],
        content
    };
    
    // Sign the event
    const signedEvent = tools.finalizeEvent(unsignedEvent, state.secretKey);
    
    // Publish to connected relays
    try {
        const pubPromises = pool.publish(state.connectedRelays, signedEvent);
        
        // pubPromises is an array of promises, one per relay
        const results = await Promise.allSettled(pubPromises);
        
        const successful = results.filter(r => r.status === 'fulfilled');
        const failed = results.filter(r => r.status === 'rejected');
        
        if (failed.length > 0) {
            console.warn('Some relays failed to accept event:', failed.map(r => r.reason?.message || r.reason));
        }
        
        if (successful.length === 0) {
            throw new Error('Failed to publish to any relay');
        }
        
        console.log(`Published to ${successful.length}/${state.connectedRelays.length} relays`);
        
        // Save user if remember me is checked
        if (state.rememberMe) {
            saveUser(state.secretKey, state.publicKey, name);
        }
        
        return { success: true, relays: successful.length };
    } catch (error) {
        console.error('Publish error:', error);
        throw error;
    }
}

/**
 * Create the widget HTML
 */
function createWidgetHTML(pageType) {
    const topics = TOPICS[pageType] || TOPICS.county;
    const topicOptions = topics
        .map(t => `<option value="${t.value}">${t.label}</option>`)
        .join('');
    
    return `
        <button class="feedback-toggle" aria-label="Leave Feedback" disabled>
            <span class="feedback-toggle-text">Connecting...</span>
            <span class="feedback-connection-indicator"></span>
        </button>
        
        <div class="feedback-form">
            <div class="feedback-header">
                <span class="feedback-header-title">Feedback</span>
                <div class="feedback-header-actions">
                    <span class="feedback-relay-count" title="Connected relays"></span>
                    <button class="feedback-gear" aria-label="Advanced options" title="Advanced options">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                        </svg>
                    </button>
                    <button class="feedback-close" aria-label="Close">&times;</button>
                </div>
            </div>
            
            <div class="feedback-logged-in" style="display: none;">
                Welcome back, <span class="feedback-logged-in-name"></span>
            </div>
            
            <div class="feedback-body">
                <div class="feedback-field">
                    <label for="feedback-name">Your Name</label>
                    <input type="text" id="feedback-name" placeholder="Enter your name" required>
                </div>
                
                <div class="feedback-field">
                    <label for="feedback-topic">Topic</label>
                    <select id="feedback-topic">
                        ${topicOptions}
                    </select>
                </div>
                
                <div class="feedback-field">
                    <label for="feedback-comment">Your Feedback</label>
                    <textarea id="feedback-comment" placeholder="Share your thoughts, suggestions, or report issues..." required></textarea>
                </div>
                
                <button class="feedback-submit" type="button">Send Feedback</button>
                
                <div class="feedback-status"></div>
            </div>
            
            <div class="feedback-advanced">
                <div class="feedback-advanced-title">Advanced Options</div>
                
                <label class="feedback-checkbox">
                    <input type="checkbox" id="feedback-remember">
                    <div>
                        <div class="feedback-checkbox-label">Remember me on this device</div>
                        <div class="feedback-checkbox-hint">Use the same identity for future feedback</div>
                    </div>
                </label>
                
                <div class="feedback-npub">
                    <div class="feedback-npub-label">Your Nostr identity:</div>
                    <div class="feedback-npub-value" id="feedback-npub-display">Generating...</div>
                </div>
                
                <button class="feedback-clear" type="button">Clear saved data</button>
            </div>
            
            <div class="feedback-thanks">
                <div class="feedback-thanks-icon">&#10003;</div>
                <div class="feedback-thanks-text">Thanks for your feedback!</div>
            </div>
        </div>
    `;
}

/**
 * Initialize the feedback widget
 */
export async function initFeedbackWidget(options = {}) {
    const pageType = options.pageType || 'county';
    
    // Create container
    const container = document.createElement('div');
    container.id = 'nostr-feedback';
    container.className = `feedback-widget${pageType === 'schools' ? ' schools' : ''}`;
    container.innerHTML = createWidgetHTML(pageType);
    document.body.appendChild(container);
    
    // Get elements
    const toggle = container.querySelector('.feedback-toggle');
    const toggleText = container.querySelector('.feedback-toggle-text');
    const connectionIndicator = container.querySelector('.feedback-connection-indicator');
    const form = container.querySelector('.feedback-form');
    const closeBtn = container.querySelector('.feedback-close');
    const gearBtn = container.querySelector('.feedback-gear');
    const advancedPanel = container.querySelector('.feedback-advanced');
    const submitBtn = container.querySelector('.feedback-submit');
    const nameInput = container.querySelector('#feedback-name');
    const topicSelect = container.querySelector('#feedback-topic');
    const commentInput = container.querySelector('#feedback-comment');
    const rememberCheckbox = container.querySelector('#feedback-remember');
    const clearBtn = container.querySelector('.feedback-clear');
    const statusDiv = container.querySelector('.feedback-status');
    const thanksDiv = container.querySelector('.feedback-thanks');
    const bodyDiv = container.querySelector('.feedback-body');
    const loggedInDiv = container.querySelector('.feedback-logged-in');
    const loggedInName = container.querySelector('.feedback-logged-in-name');
    const npubDisplay = container.querySelector('#feedback-npub-display');
    const relayCount = container.querySelector('.feedback-relay-count');
    
    // Update connection status UI
    function updateConnectionUI(status, connectedCount) {
        connectionIndicator.className = 'feedback-connection-indicator ' + status;
        
        switch (status) {
            case 'connecting':
                toggleText.textContent = 'Connecting...';
                toggle.disabled = true;
                relayCount.textContent = '';
                break;
            case 'connected':
                toggleText.textContent = 'Leave Feedback';
                toggle.disabled = false;
                relayCount.textContent = `${connectedCount} relays`;
                relayCount.title = `Connected to ${connectedCount} of ${CONFIG.relays.length} relays`;
                break;
            case 'error':
                toggleText.textContent = 'Offline';
                toggle.disabled = true;
                relayCount.textContent = 'No relays';
                break;
        }
    }
    
    // Load saved user
    const savedUser = loadSavedUser();
    if (savedUser) {
        state.secretKey = savedUser.secretKey;
        state.publicKey = savedUser.publicKey;
        state.name = savedUser.name;
        state.rememberMe = true;
        
        nameInput.value = savedUser.name;
        rememberCheckbox.checked = true;
        loggedInName.textContent = savedUser.name;
        loggedInDiv.style.display = 'block';
    }
    
    // Connect to relays early
    connectToRelays(updateConnectionUI).then(async (connectedCount) => {
        if (connectedCount > 0) {
            // Generate keypair and display npub
            if (!state.secretKey) {
                const keypair = await generateKeypair();
                state.secretKey = keypair.secretKey;
                state.publicKey = keypair.publicKey;
            }
            const npub = await getNpub(state.publicKey);
            npubDisplay.textContent = npub;
        } else {
            npubDisplay.textContent = 'Not connected';
        }
    }).catch(err => {
        console.error('Failed to initialize nostr:', err);
        npubDisplay.textContent = 'Error loading';
        updateConnectionUI('error', 0);
    });
    
    // Toggle form visibility
    function openForm() {
        if (state.connectionStatus !== 'connected') {
            return; // Don't open if not connected
        }
        state.isOpen = true;
        toggle.classList.add('hidden');
        form.classList.add('visible');
        nameInput.focus();
    }
    
    function closeForm() {
        state.isOpen = false;
        toggle.classList.remove('hidden');
        form.classList.remove('visible');
        advancedPanel.classList.remove('visible');
        thanksDiv.classList.remove('visible');
        bodyDiv.style.display = 'block';
        statusDiv.classList.remove('visible', 'success', 'error');
    }
    
    // Event listeners
    toggle.addEventListener('click', openForm);
    closeBtn.addEventListener('click', closeForm);
    
    gearBtn.addEventListener('click', () => {
        advancedPanel.classList.toggle('visible');
    });
    
    rememberCheckbox.addEventListener('change', (e) => {
        state.rememberMe = e.target.checked;
    });
    
    clearBtn.addEventListener('click', async () => {
        clearSavedUser();
        state.rememberMe = false;
        rememberCheckbox.checked = false;
        loggedInDiv.style.display = 'none';
        nameInput.value = '';
        
        // Generate new keypair
        const keypair = await generateKeypair();
        state.secretKey = keypair.secretKey;
        state.publicKey = keypair.publicKey;
        const npub = await getNpub(state.publicKey);
        npubDisplay.textContent = npub;
    });
    
    submitBtn.addEventListener('click', async () => {
        const name = nameInput.value.trim();
        const topic = topicSelect.value;
        const comment = commentInput.value.trim();
        
        // Validate
        if (!name) {
            statusDiv.textContent = 'Please enter your name';
            statusDiv.className = 'feedback-status visible error';
            nameInput.focus();
            return;
        }
        
        if (!comment) {
            statusDiv.textContent = 'Please enter your feedback';
            statusDiv.className = 'feedback-status visible error';
            commentInput.focus();
            return;
        }
        
        // Check connection
        if (state.connectedRelays.length === 0) {
            statusDiv.textContent = 'Not connected to any relays. Please refresh and try again.';
            statusDiv.className = 'feedback-status visible error';
            return;
        }
        
        // Submit
        state.isSubmitting = true;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';
        statusDiv.classList.remove('visible');
        
        try {
            await publishFeedback(name, comment, topic, pageType);
            
            // Show thanks
            bodyDiv.style.display = 'none';
            advancedPanel.classList.remove('visible');
            thanksDiv.classList.add('visible');
            
            // Update logged in indicator for next time
            if (state.rememberMe) {
                loggedInName.textContent = name;
                loggedInDiv.style.display = 'block';
            }
            
            // Clear form
            commentInput.value = '';
            topicSelect.value = 'general';
            
            // Auto-close after 2 seconds
            setTimeout(() => {
                closeForm();
            }, 2000);
            
        } catch (error) {
            console.error('Failed to submit feedback:', error);
            statusDiv.textContent = 'Failed to send. Please try again.';
            statusDiv.className = 'feedback-status visible error';
        } finally {
            state.isSubmitting = false;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Send Feedback';
        }
    });
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && state.isOpen) {
            closeForm();
        }
    });
}

// Auto-initialize if data attribute is present
document.addEventListener('DOMContentLoaded', () => {
    const widget = document.querySelector('[data-feedback-widget]');
    if (widget) {
        const pageType = widget.dataset.feedbackWidget || 'county';
        initFeedbackWidget({ pageType });
    }
});
