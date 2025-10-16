// Heat Pump Control Module
import { CONFIG } from './config.js';
import { updateGauge, updateConnectionStatus, apiRequest } from './utils.js';

// State
let updateTimer = null;
let userInteractingWithSlider = false;
let pendingSliderValue = null;  // Track the value we're setting

// UI Elements
const elements = {
    connectionStatus: document.getElementById('connection-status'),
    powerStatus: document.getElementById('power-status'),
    powerDot: document.getElementById('power-dot'),
    compressorStatus: document.getElementById('compressor-status'),
    compressorDot: document.getElementById('compressor-dot'),
    flowTempValue: document.getElementById('flow-temp-value'),
    lastUpdateEl: document.getElementById('last-update'),
    tempSlider: document.getElementById('temp-slider'),
    tempSliderValue: document.getElementById('temp-slider-value'),
    powerSwitch: document.getElementById('power-switch'),
    aiModeSwitch: document.getElementById('ai-mode-switch'),
    aiStatusText: document.getElementById('ai-status-text'),
    heatpumpLogo: document.getElementById('heatpump-logo')
};

/**
 * Initialize heat pump control
 */
export function init() {
    initEventListeners();
    startAutoUpdate();
    // Fetch initial AI mode status
    fetchAIModeStatus();
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
    // Power switch toggle
    elements.powerSwitch.addEventListener('change', (e) => {
        setPower(e.target.checked);
    });

    // Temperature slider - track when user starts interacting
    elements.tempSlider.addEventListener('mousedown', () => {
        console.log('mousedown - setting userInteractingWithSlider = true');
        userInteractingWithSlider = true;
    });

    elements.tempSlider.addEventListener('touchstart', () => {
        console.log('touchstart - setting userInteractingWithSlider = true');
        userInteractingWithSlider = true;
    });

    // Temperature slider - update display on input
    elements.tempSlider.addEventListener('input', (e) => {
        elements.tempSliderValue.textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Temperature slider - set value when released
    elements.tempSlider.addEventListener('change', (e) => {
        console.log('change event - calling setTemperature');
        setTemperature();
        setTimeout(() => {
            console.log('change timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });

    // Reset flag on mouseup/touchend
    elements.tempSlider.addEventListener('mouseup', () => {
        setTimeout(() => {
            console.log('mouseup timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });

    elements.tempSlider.addEventListener('touchend', () => {
        setTimeout(() => {
            console.log('touchend timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });

    // AI mode toggle
    elements.aiModeSwitch.addEventListener('change', async (e) => {
        await setAIMode(e.target.checked);
    });
}

/**
 * Start automatic status updates
 */
function startAutoUpdate() {
    updateStatus();
    updateTimer = setInterval(updateStatus, CONFIG.HEATPUMP_UPDATE_INTERVAL);
}

/**
 * Fetch and update heat pump status
 */
async function updateStatus() {
    try {
        const data = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/status`);
        updateUI(data);
        updateConnectionStatus(elements.connectionStatus, true);

        // Also fetch AI mode status periodically
        await fetchAIModeStatus();
    } catch (error) {
        console.error('Failed to fetch heat pump status:', error);
        updateConnectionStatus(elements.connectionStatus, false);
    }
}

/**
 * Update UI with heat pump data
 * @param {Object} data - Heat pump status data
 */
function updateUI(data) {
    console.log('updateUI called, userInteracting:', userInteractingWithSlider, 'target_temp:', data.target_temperature);

    // Power status - only update if changed to prevent flickering
    if (elements.powerSwitch.checked !== data.is_on) {
        elements.powerSwitch.checked = data.is_on;
    }
    const newPowerText = data.is_on ? 'ON' : 'OFF';
    if (elements.powerStatus.textContent !== newPowerText) {
        elements.powerStatus.textContent = newPowerText;
    }
    // Toggle class only if needed
    if (data.is_on && !elements.powerDot.classList.contains('on')) {
        elements.powerDot.classList.add('on');
    } else if (!data.is_on && elements.powerDot.classList.contains('on')) {
        elements.powerDot.classList.remove('on');
    }

    // Compressor status - only update if changed to prevent flickering
    const newCompressorText = data.compressor_running ? 'ON' : 'OFF';
    if (elements.compressorStatus.textContent !== newCompressorText) {
        elements.compressorStatus.textContent = newCompressorText;
    }
    // Toggle class only if needed
    if (data.compressor_running && !elements.compressorDot.classList.contains('on')) {
        elements.compressorDot.classList.add('on');
    } else if (!data.compressor_running && elements.compressorDot.classList.contains('on')) {
        elements.compressorDot.classList.remove('on');
    }

    // Rotate heat pump logo when compressor is running
    if (data.compressor_running && !elements.heatpumpLogo.classList.contains('running')) {
        elements.heatpumpLogo.classList.add('running');
    } else if (!data.compressor_running && elements.heatpumpLogo.classList.contains('running')) {
        elements.heatpumpLogo.classList.remove('running');
    }

    // Update slider to reflect actual target temperature from device
    if (data.target_temperature !== undefined && data.target_temperature !== null) {
        const currentSliderValue = parseFloat(elements.tempSlider.value);
        const deviceTargetTemp = parseFloat(data.target_temperature);

        // If we have a pending value, check if device has caught up
        if (pendingSliderValue !== null) {
            if (Math.abs(deviceTargetTemp - pendingSliderValue) < 0.1) {
                // Device has caught up to our requested value
                console.log(`Device caught up to pending value ${pendingSliderValue}°C`);
                pendingSliderValue = null;
                userInteractingWithSlider = false;
            } else {
                // Still waiting for device to catch up
                console.log(`Waiting for device to catch up (pending: ${pendingSliderValue}°C, device: ${deviceTargetTemp}°C)`);
            }
        }

        // Only update slider if user is not interacting and no pending value
        if (!userInteractingWithSlider && pendingSliderValue === null) {
            if (Math.abs(currentSliderValue - deviceTargetTemp) > 0.1) {
                elements.tempSlider.value = deviceTargetTemp;
                elements.tempSliderValue.textContent = deviceTargetTemp.toFixed(1);
                console.log(`Slider updated from ${currentSliderValue} to ${deviceTargetTemp}`);
            }
        } else {
            console.log(`Slider update blocked - userInteracting: ${userInteractingWithSlider}, pending: ${pendingSliderValue}`);
        }
    }

    // Flow temperature - update badge display only if value changed
    const newFlowTemp = `${data.flow_temperature.toFixed(1)}°C`;
    if (elements.flowTempValue.textContent !== newFlowTemp) {
        elements.flowTempValue.textContent = newFlowTemp;
    }

    // Last update time (always update to show it's alive)
    elements.lastUpdateEl.textContent = new Date().toLocaleTimeString();
}

/**
 * Set heat pump power state
 * @param {boolean} powerOn - Desired power state
 */
async function setPower(powerOn) {
    try {
        const result = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/power`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ power_on: powerOn })
        });

        console.log('Power set:', result);
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to set power:', error);
        alert('Failed to set power state');
    }
}

/**
 * Set heat pump target temperature
 * Fire-and-forget to keep UI responsive
 */
function setTemperature() {
    const temperature = parseFloat(elements.tempSlider.value);

    // Mark this value as pending so updateUI won't override it
    pendingSliderValue = temperature;
    console.log(`Setting temperature to ${temperature}°C (marked as pending)`);

    // Fire request in background without blocking UI
    apiRequest(`${CONFIG.HEATPUMP_API_URL}/setpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temperature })
    })
    .then(result => {
        console.log('Temperature set:', result);
        // Quick status update after a short delay to check if device caught up
        setTimeout(updateStatus, 500);
    })
    .catch(error => {
        console.error('Failed to set temperature:', error);
        alert('Failed to set temperature');
        // Clear pending value on error and revert slider
        pendingSliderValue = null;
        userInteractingWithSlider = false;
        setTimeout(updateStatus, 100);
    });
}

/**
 * Set AI mode (adaptive heating curve control)
 * @param {boolean} enabled - Enable or disable AI mode
 */
async function setAIMode(enabled) {
    try {
        const result = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/ai-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        console.log('AI Mode set:', result);

        // Update UI state
        updateAIModeUI(enabled);

        // Refresh status after a short delay
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to set AI mode:', error);
        alert('Failed to set AI mode');
        // Revert switch state on error
        elements.aiModeSwitch.checked = !enabled;
    }
}

/**
 * Update AI mode UI state
 * @param {boolean} enabled - AI mode enabled state
 */
function updateAIModeUI(enabled) {
    // Update status text
    if (enabled) {
        elements.aiStatusText.textContent = 'AI Mode Active';
        elements.aiStatusText.classList.add('active');

        // Disable temperature slider
        elements.tempSlider.disabled = true;
        elements.tempSlider.classList.add('ai-disabled');
    } else {
        elements.aiStatusText.textContent = 'Manual Control';
        elements.aiStatusText.classList.remove('active');

        // Enable temperature slider
        elements.tempSlider.disabled = false;
        elements.tempSlider.classList.remove('ai-disabled');
    }
}

/**
 * Fetch AI mode status
 */
async function fetchAIModeStatus() {
    try {
        const data = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/ai-mode`);

        // Update switch state without triggering change event
        if (elements.aiModeSwitch.checked !== data.enabled) {
            elements.aiModeSwitch.checked = data.enabled;
        }

        // Update UI
        updateAIModeUI(data.enabled);

        return data;
    } catch (error) {
        console.error('Failed to fetch AI mode status:', error);
        return null;
    }
}
