// Heat Pump Control Module
import { CONFIG } from './config.js';
import { updateGauge, updateConnectionStatus, apiRequest } from './utils.js';

// State
let updateTimer = null;
let userInteractingWithSlider = false;

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
    powerSwitch: document.getElementById('power-switch')
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

    // Update slider to reflect actual target temperature from device
    if (data.target_temperature !== undefined && data.target_temperature !== null) {
        const currentSliderValue = parseFloat(elements.tempSlider.value);
        const deviceTargetTemp = parseFloat(data.target_temperature);

        if (!userInteractingWithSlider) {
            if (Math.abs(currentSliderValue - deviceTargetTemp) > 0.1) {
                elements.tempSlider.value = deviceTargetTemp;
                elements.tempSliderValue.textContent = deviceTargetTemp.toFixed(1);
                console.log(`Slider updated from ${currentSliderValue} to ${deviceTargetTemp}`);
            }
        } else {
            console.log(`Slider update blocked - user interacting (current: ${currentSliderValue}, device: ${deviceTargetTemp})`);
        }
    }

    // Temperature gauge - Flow only (updateGauge already optimized)
    updateGauge('gauge-flow', data.flow_temperature, CONFIG.GAUGE_MIN, CONFIG.GAUGE_MAX);

    // Only update text if value changed
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
 */
async function setTemperature() {
    const temperature = parseFloat(elements.tempSlider.value);

    try {
        const result = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/setpoint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ temperature })
        });

        console.log('Temperature set:', result);
        setTimeout(updateStatus, 500);
    } catch (error) {
        console.error('Failed to set temperature:', error);
        alert('Failed to set temperature');
    }
}
