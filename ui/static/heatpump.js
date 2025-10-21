// Heat Pump Control Module
import { CONFIG } from './config.js';
import { updateGauge, updateConnectionStatus, apiRequest } from './utils.js';

// State
let updateTimer = null;
let userInteractingWithSlider = false;
let pendingSliderValue = null;  // Track the temperature value we're setting
let pendingOffsetValue = null;  // Track the offset value we're setting

// UI Elements
const elements = {
    connectionStatusText: document.getElementById('connection-status-text'),
    connectionDot: document.getElementById('connection-dot'),
    powerStatus: document.getElementById('power-status'),
    powerDot: document.getElementById('power-dot'),
    compressorStatus: document.getElementById('compressor-status'),
    compressorDot: document.getElementById('compressor-dot'),
    flowTempValue: document.getElementById('flow-temp-value'),
    lastUpdateEl: document.getElementById('last-update'),
    tempSlider: document.getElementById('temp-slider'),
    tempSliderValue: document.getElementById('temp-slider-value'),
    powerSwitch: document.getElementById('power-switch'),
    lgModeSwitch: document.getElementById('lg-mode-switch'),
    lgModeStatusText: document.getElementById('lg-mode-status-text')
};

/**
 * Initialize heat pump control
 */
export function init() {
    initEventListeners();
    startAutoUpdate();
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

    // LG mode toggle
    elements.lgModeSwitch.addEventListener('change', async (e) => {
        const mode = e.target.checked ? 3 : 4; // 3=Auto, 4=Heating
        await setLGMode(mode);
    });

    // LG Auto mode offset buttons - delegate event listener
    // Using event delegation on the parent to avoid adding listeners to each button
    const offsetScale = document.querySelector('.offset-scale');
    if (offsetScale) {
        offsetScale.addEventListener('click', function(e) {
            // Check if clicked element is a span (offset button)
            if (e.target.tagName === 'SPAN') {
                const offsetValue = parseInt(e.target.textContent);
                if (!isNaN(offsetValue)) {
                    setAutoModeOffset(offsetValue);
                }
            }
        });
    }
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
        updateConnectionStatusBadge(true);
    } catch (error) {
        console.error('Failed to fetch heat pump status:', error);
        updateConnectionStatusBadge(false);
    }
}

/**
 * Update connection status badge (dot + text)
 * @param {boolean} connected - Connection state
 */
function updateConnectionStatusBadge(connected) {
    if (connected) {
        elements.connectionStatusText.textContent = 'Connected';
        elements.connectionDot.classList.add('on');
    } else {
        elements.connectionStatusText.textContent = 'Disconnected';
        elements.connectionDot.classList.remove('on');
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

    // Toggle Manual/Auto mode sections based on op_mode (register 40001)
    // IMPORTANT: The heat pump has two different temperature control mechanisms:
    //
    // 1. HEATING MODE (Manual) - Register 40001 = 4
    //    - User sets explicit target flow temperature via register 40003 (33-50°C)
    //    - Display: Temperature slider for direct control
    //    - Register 40005 (auto offset) is ignored
    //
    // 2. AUTO MODE - Register 40001 = 3
    //    - LG's internal heating curve calculates optimal flow temperature
    //    - Based on outdoor temp (INPUT 30013) + heating curve + offset (HOLDING 40005)
    //    - Register 40003 (target temperature) is IGNORED in this mode!
    //    - Display: Auto offset adjustment (±5K)
    //
    const opMode = data.op_mode; // Register 40001: 3=Auto, 4=Heating
    const manualSection = document.getElementById('manual-setpoint-section');
    const lgAutoSection = document.getElementById('lg-auto-offset-section');

    // Update LG mode toggle to match current mode
    updateLGModeUI(opMode);

    if (opMode === 3) {
        // LG Auto mode - hide manual slider (register 40003 unused), show offset (register 40005 active)
        if (manualSection) manualSection.style.display = 'none';
        if (lgAutoSection) lgAutoSection.style.display = 'block';

        // Update offset value (register 40005: -5 to +5°C)
        const deviceOffsetValue = data.auto_mode_offset || 0;

        // If we have a pending value, check if device has caught up
        if (pendingOffsetValue !== null) {
            if (deviceOffsetValue === pendingOffsetValue) {
                // Device has caught up to our requested value
                console.log('Device caught up to pending offset value ' + pendingOffsetValue + '°C');
                pendingOffsetValue = null;
            } else {
                // Still waiting for device to catch up
                console.log('Waiting for device to catch up (pending: ' + pendingOffsetValue + '°C, device: ' + deviceOffsetValue + '°C)');
            }
        }

        // Use pending value if set, otherwise use device value
        const displayOffsetValue = pendingOffsetValue !== null ? pendingOffsetValue : deviceOffsetValue;

        const offsetElement = document.getElementById('lg-offset-value');
        if (offsetElement) {
            offsetElement.textContent = displayOffsetValue >= 0 ? '+' + displayOffsetValue + '°C' : displayOffsetValue + '°C';
            // Add 'negative' class for blue color if value is negative
            if (displayOffsetValue < 0) {
                offsetElement.classList.add('negative');
            } else {
                offsetElement.classList.remove('negative');
            }
        }

        // Highlight the active offset button based on display value (pending or actual)
        const offsetButtons = document.querySelectorAll('.offset-scale span');
        // Convert NodeList to Array for older browser compatibility
        const buttonsArray = Array.prototype.slice.call(offsetButtons);
        for (let i = 0; i < buttonsArray.length; i++) {
            const button = buttonsArray[i];
            const buttonValue = parseInt(button.textContent);
            if (buttonValue === displayOffsetValue) {
                button.classList.add('active');
                // Add 'negative' class for blue color if value is negative
                if (buttonValue < 0) {
                    button.classList.add('negative');
                } else {
                    button.classList.remove('negative');
                }
            } else {
                button.classList.remove('active');
                button.classList.remove('negative');
            }
        }

        console.log('LG Auto mode active, offset: ' + displayOffsetValue + '°C (register 40003 ignored)');
    } else {
        // Heating mode (manual) - show manual slider (register 40003 active), hide offset (register 40005 unused)
        if (manualSection) manualSection.style.display = 'block';
        if (lgAutoSection) lgAutoSection.style.display = 'none';
        console.log('Manual Heating mode active (mode=' + opMode + '), using target temperature from register 40003');
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
 * Set LG Auto mode offset adjustment
 * Fire-and-forget to keep UI responsive, using pending value pattern
 * @param {number} offset - Offset value in °C (-5 to +5)
 */
function setAutoModeOffset(offset) {
    // Validate range
    if (offset < -5 || offset > 5) {
        console.error('Invalid offset value:', offset);
        alert('Offset must be between -5 and +5°C');
        return;
    }

    // Mark this value as pending so updateUI won't override it
    pendingOffsetValue = offset;
    console.log('Setting LG Auto mode offset to ' + offset + '°C (marked as pending)');

    // Fire request in background without blocking UI
    apiRequest(CONFIG.HEATPUMP_API_URL + '/auto-mode-offset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offset: offset })
    })
    .then(function(result) {
        console.log('Auto mode offset set:', result);
        // Quick status update after a short delay to check if device caught up
        setTimeout(updateStatus, 500);
    })
    .catch(function(error) {
        console.error('Failed to set auto mode offset:', error);
        alert('Failed to set auto mode offset');
        // Clear pending value on error and revert to actual device value
        pendingOffsetValue = null;
        setTimeout(updateStatus, 100);
    });
}

/**
 * Set LG heat pump operating mode
 * @param {number} mode - Operating mode (3=Auto, 4=Heating)
 */
async function setLGMode(mode) {
    try {
        const result = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/lg-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });

        console.log('LG mode set:', result);

        // Update UI state immediately (no waiting for poll)
        updateLGModeUI(mode);

        // If switching to Heating mode and API returned default temperature, update slider
        if (mode === 4 && result.default_temperature) {
            elements.tempSlider.value = result.default_temperature;
            elements.tempSliderValue.textContent = result.default_temperature.toFixed(1);
            console.log(`Slider updated to default temperature: ${result.default_temperature}°C`);
        }

        // Refresh status after a short delay to confirm
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to set LG mode:', error);
        alert('Failed to set LG mode');
        // Revert switch state on error
        elements.lgModeSwitch.checked = (mode === 4 ? true : false);
    }
}

/**
 * Update LG mode UI state
 * @param {number} mode - Operating mode (3=Auto, 4=Heating)
 */
function updateLGModeUI(mode) {
    const isAuto = (mode === 3);

    // Update toggle (checked = Auto mode)
    if (elements.lgModeSwitch.checked !== isAuto) {
        elements.lgModeSwitch.checked = isAuto;
    }

    // Update status text
    elements.lgModeStatusText.textContent = isAuto ? 'LG Auto Mode' : 'Manual Heating';

    // Show/hide appropriate sections
    const manualSection = document.getElementById('manual-setpoint-section');
    const autoSection = document.getElementById('lg-auto-offset-section');

    if (isAuto) {
        if (manualSection) manualSection.style.display = 'none';
        if (autoSection) autoSection.style.display = 'block';
    } else {
        if (manualSection) manualSection.style.display = 'block';
        if (autoSection) autoSection.style.display = 'none';
    }
}
