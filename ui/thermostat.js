// Thermostat Control Module
import { CONFIG } from './config.js';
import { apiRequest } from './utils.js';

// State
let updateTimer = null;

// UI Elements - initialized after DOM loads
let elements = {};

/**
 * Initialize thermostat control
 */
export async function init() {
    // Initialize UI elements after DOM is ready
    elements = {
        modeButtons: document.querySelectorAll('.mode-btn'),
        tempDisplay: document.getElementById('thermostat-temp'),
        tempUpBtn: document.getElementById('temp-up'),
        tempDownBtn: document.getElementById('temp-down'),
        pumpStatusText: document.getElementById('pump-status-text'),
        pumpDot: document.querySelector('.pump-dot')
    };

    console.log('Thermostat elements initialized:', {
        modeButtonsCount: elements.modeButtons.length,
        tempDisplay: elements.tempDisplay,
        pumpDot: elements.pumpDot,
        pumpStatusText: elements.pumpStatusText
    });

    initEventListeners();
    await initializeDefaults();
    // Do immediate status update to show current state
    await updateStatus();
    startAutoUpdate();
}

/**
 * Set default thermostat configuration on startup
 */
async function initializeDefaults() {
    try {
        console.log('Setting thermostat default configuration...');

        // Get current config first
        const currentConfig = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`);

        // Merge with defaults, preserving target_temp, eco_temp, and mode
        const fullConfig = {
            target_temp: currentConfig.target_temp,
            eco_temp: currentConfig.eco_temp,
            mode: currentConfig.mode,
            ...CONFIG.THERMOSTAT_DEFAULTS
        };

        const result = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fullConfig)
        });
        console.log('Thermostat defaults applied:', result);
    } catch (error) {
        console.error('Failed to set thermostat defaults:', error);
        // Don't block initialization if this fails
    }
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
    // Mode buttons
    elements.modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            setMode(mode);
        });
    });

    // Temperature controls
    elements.tempUpBtn.addEventListener('click', () => {
        adjustTemperature(CONFIG.THERMOSTAT_TEMP_STEP);
    });

    elements.tempDownBtn.addEventListener('click', () => {
        adjustTemperature(-CONFIG.THERMOSTAT_TEMP_STEP);
    });
}

/**
 * Start automatic status updates
 */
function startAutoUpdate() {
    updateTimer = setInterval(updateStatus, CONFIG.THERMOSTAT_UPDATE_INTERVAL);
}

/**
 * Fetch and update thermostat status
 */
async function updateStatus() {
    try {
        const data = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/status`);
        updateUI(data);
        console.log('Thermostat status updated:', data);
        return data;
    } catch (error) {
        console.error('Failed to fetch thermostat status:', error);
        return null;
    }
}

/**
 * Update UI with thermostat data
 * @param {Object} data - Thermostat status data
 */
function updateUI(data) {
    console.log('updateUI called with data:', data);
    console.log('elements.modeButtons:', elements.modeButtons);

    // Update active mode button (mode is in data.config.mode) - only toggle if needed
    const currentMode = data.config?.mode || data.mode;
    console.log('currentMode extracted:', currentMode);

    elements.modeButtons.forEach(btn => {
        const shouldBeActive = btn.dataset.mode === currentMode;
        const isActive = btn.classList.contains('active');

        if (shouldBeActive && !isActive) {
            btn.classList.add('active');
            console.log(`Mode button ${currentMode} set to active`);
        } else if (!shouldBeActive && isActive) {
            btn.classList.remove('active');
        }
    });

    // Update target temperature display - only if changed
    const targetTemp = data.active_target || data.config?.target_temp || 0;
    const newTempText = `${targetTemp.toFixed(1)}°C`;
    if (elements.tempDisplay.textContent !== newTempText) {
        elements.tempDisplay.textContent = newTempText;
        console.log(`Target temp display updated to ${targetTemp}°C`);
    }

    // Update pump status - only toggle if changed to prevent flickering
    const pumpOn = data.switch_state === true;
    const pumpIsOn = elements.pumpDot.classList.contains('on');

    if (pumpOn && !pumpIsOn) {
        elements.pumpDot.classList.add('on');
        elements.pumpStatusText.textContent = 'ON';
        console.log('Pump turned ON');
    } else if (!pumpOn && pumpIsOn) {
        elements.pumpDot.classList.remove('on');
        elements.pumpStatusText.textContent = 'OFF';
        console.log('Pump turned OFF');
    }
}

/**
 * Set thermostat operating mode
 * @param {string} mode - Operating mode (AUTO, ECO, ON, OFF)
 */
async function setMode(mode) {
    try {
        // Get current config first
        const currentConfig = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`);

        // Build full config with new mode
        const fullConfig = {
            target_temp: currentConfig.target_temp,
            eco_temp: currentConfig.eco_temp,
            mode: mode,
            ...CONFIG.THERMOSTAT_DEFAULTS
        };

        const result = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fullConfig)
        });

        console.log('Thermostat mode set:', result);
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to set thermostat mode:', error);
        alert('Failed to set thermostat mode');
    }
}

/**
 * Adjust target temperature
 * @param {number} delta - Temperature change (+0.5 or -0.5)
 */
async function adjustTemperature(delta) {
    try {
        // Get current config
        const currentConfig = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`);

        // Calculate new temperature
        let newTemp = currentConfig.target_temp + delta;

        // Clamp to valid range
        newTemp = Math.max(CONFIG.THERMOSTAT_TEMP_MIN, Math.min(CONFIG.THERMOSTAT_TEMP_MAX, newTemp));
        newTemp = Math.round(newTemp * 2) / 2; // Round to nearest 0.5

        // Only update if changed
        if (newTemp === currentConfig.target_temp) {
            console.log('Temperature already at limit');
            return;
        }

        // Build full config with new target temperature
        const fullConfig = {
            target_temp: newTemp,
            eco_temp: currentConfig.eco_temp,
            mode: currentConfig.mode,
            ...CONFIG.THERMOSTAT_DEFAULTS
        };

        const result = await apiRequest(`${CONFIG.THERMOSTAT_API_URL}/api/v1/thermostat/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fullConfig)
        });

        console.log('Thermostat temperature adjusted:', result);
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to adjust thermostat temperature:', error);
        alert('Failed to adjust temperature');
    }
}
