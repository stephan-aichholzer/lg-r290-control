// LG R290 Heat Pump Control UI
// Use window.location.hostname to work with any IP address or hostname
const API_URL = `http://${window.location.hostname}:8002`;
const UPDATE_INTERVAL = 2000; // 2 seconds

let updateTimer = null;
let userInteractingWithSlider = false;

// UI Elements
const connectionStatus = document.getElementById('connection-status');
const powerStatus = document.getElementById('power-status');
const compressorStatus = document.getElementById('compressor-status');
const flowTempValue = document.getElementById('flow-temp-value');
const returnTempValue = document.getElementById('return-temp-value');
const flowRateEl = document.getElementById('flow-rate');
const waterPressureEl = document.getElementById('water-pressure');
const operatingModeEl = document.getElementById('operating-mode');
const lastUpdateEl = document.getElementById('last-update');
const errorSection = document.getElementById('error-section');
const errorMessage = document.getElementById('error-message');
const tempSlider = document.getElementById('temp-slider');
const tempSliderValue = document.getElementById('temp-slider-value');
const powerSwitch = document.getElementById('power-switch');

// Gauge configuration
const GAUGE_MIN = 0;
const GAUGE_MAX = 80;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    startAutoUpdate();
});

function initEventListeners() {
    // Power switch toggle
    powerSwitch.addEventListener('change', (e) => {
        setPower(e.target.checked);
    });

    // Temperature slider - track when user starts interacting
    tempSlider.addEventListener('mousedown', () => {
        console.log('mousedown - setting userInteractingWithSlider = true');
        userInteractingWithSlider = true;
    });

    tempSlider.addEventListener('touchstart', () => {
        console.log('touchstart - setting userInteractingWithSlider = true');
        userInteractingWithSlider = true;
    });

    // Temperature slider - update display on input
    tempSlider.addEventListener('input', (e) => {
        tempSliderValue.textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Temperature slider - set value when released
    tempSlider.addEventListener('change', (e) => {
        console.log('change event - calling setTemperature');
        setTemperature();
        // Allow automatic updates again after a short delay
        setTimeout(() => {
            console.log('change timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });

    // Also reset flag on mouseup/touchend (in case change event doesn't fire)
    tempSlider.addEventListener('mouseup', () => {
        setTimeout(() => {
            console.log('mouseup timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });

    tempSlider.addEventListener('touchend', () => {
        setTimeout(() => {
            console.log('touchend timeout - setting userInteractingWithSlider = false');
            userInteractingWithSlider = false;
        }, 100);
    });
}

function startAutoUpdate() {
    updateStatus();
    updateTimer = setInterval(updateStatus, UPDATE_INTERVAL);
}

function stopAutoUpdate() {
    if (updateTimer) {
        clearInterval(updateTimer);
        updateTimer = null;
    }
}

async function updateStatus() {
    try {
        const response = await fetch(`${API_URL}/status`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        updateUI(data);
        updateConnectionStatus(true);

    } catch (error) {
        console.error('Failed to fetch status:', error);
        updateConnectionStatus(false);
    }
}

function updateUI(data) {
    // Debug logging
    console.log('updateUI called, userInteracting:', userInteractingWithSlider, 'target_temp:', data.target_temperature);

    // Power status - update switch state
    powerSwitch.checked = data.is_on;
    powerStatus.textContent = data.is_on ? 'ON' : 'OFF';
    powerStatus.style.color = data.is_on ? '#10b981' : '#ef4444';

    // Compressor status
    compressorStatus.textContent = `Compressor: ${data.compressor_running ? 'ON' : 'OFF'}`;
    compressorStatus.style.background = data.compressor_running ? '#d1fae5' : '#374151';
    compressorStatus.style.color = data.compressor_running ? '#065f46' : '#9ca3af';

    // Update slider to reflect actual target temperature from device
    // Only update if user is not currently interacting with the slider
    if (data.target_temperature !== undefined && data.target_temperature !== null) {
        const currentSliderValue = parseFloat(tempSlider.value);
        const deviceTargetTemp = parseFloat(data.target_temperature);

        if (!userInteractingWithSlider) {
            // Always update slider if device temperature differs from current slider value
            if (Math.abs(currentSliderValue - deviceTargetTemp) > 0.1) {
                tempSlider.value = deviceTargetTemp;
                tempSliderValue.textContent = deviceTargetTemp.toFixed(1);
                console.log(`Slider updated from ${currentSliderValue} to ${deviceTargetTemp}`);
            }
        } else {
            console.log(`Slider update blocked - user interacting (current: ${currentSliderValue}, device: ${deviceTargetTemp})`);
        }
    }

    // Temperature gauges - Flow (red) and Return (blue)
    updateGauge('gauge-flow', data.flow_temperature, GAUGE_MIN, GAUGE_MAX);
    flowTempValue.textContent = `${data.flow_temperature.toFixed(1)}°C`;

    updateGauge('gauge-return', data.return_temperature, GAUGE_MIN, GAUGE_MAX);
    returnTempValue.textContent = `${data.return_temperature.toFixed(1)}°C`;

    // Metrics
    flowRateEl.textContent = `${data.flow_rate.toFixed(1)} L/min`;
    waterPressureEl.textContent = `${data.water_pressure.toFixed(1)} bar`;
    operatingModeEl.textContent = data.operating_mode;

    // Error status
    if (data.has_error) {
        errorSection.style.display = 'block';
        errorMessage.textContent = `Error Code: ${data.error_code}`;
    } else {
        errorSection.style.display = 'none';
    }

    // Last update time
    lastUpdateEl.textContent = new Date().toLocaleTimeString();
}

function updateGauge(gaugeId, value, min, max) {
    const gauge = document.getElementById(gaugeId);
    if (!gauge) return;

    // Clamp value
    value = Math.max(min, Math.min(max, value));

    // Calculate percentage (0-100)
    const percentage = ((value - min) / (max - min)) * 100;

    // Arc length calculation for semi-circle gauge
    const arcLength = 251.2; // Approximate arc length for the gauge path
    const offset = arcLength - (arcLength * percentage / 100);

    gauge.style.strokeDasharray = arcLength;
    gauge.style.strokeDashoffset = offset;

    // Color coding - skip for flow gauge (already red via CSS)
    if (gaugeId !== 'gauge-flow') {
        if (percentage > 80) {
            gauge.style.stroke = '#ef4444'; // Red
        } else if (percentage > 60) {
            gauge.style.stroke = '#f59e0b'; // Orange
        } else {
            gauge.style.stroke = '#667eea'; // Blue
        }
    }
}

function updateConnectionStatus(connected) {
    if (connected) {
        connectionStatus.textContent = 'Connected';
        connectionStatus.classList.remove('disconnected');
        connectionStatus.classList.add('connected');
    } else {
        connectionStatus.textContent = 'Disconnected';
        connectionStatus.classList.remove('connected');
        connectionStatus.classList.add('disconnected');
    }
}

async function setPower(powerOn) {
    try {
        const response = await fetch(`${API_URL}/power`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ power_on: powerOn })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        console.log('Power set:', result);

        // Immediate update
        setTimeout(updateStatus, 500);

    } catch (error) {
        console.error('Failed to set power:', error);
        alert('Failed to set power state');
    }
}

async function setTemperature() {
    const temperature = parseFloat(tempSlider.value);

    try {
        const response = await fetch(`${API_URL}/setpoint`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ temperature })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        console.log('Temperature set:', result);

        // Immediate update to reflect change
        setTimeout(updateStatus, 500);

    } catch (error) {
        console.error('Failed to set temperature:', error);
        alert('Failed to set temperature');
    }
}
