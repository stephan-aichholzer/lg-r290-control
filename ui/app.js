// LG R290 Heat Pump Control UI
const API_URL = 'http://localhost:8002';
const UPDATE_INTERVAL = 2000; // 2 seconds

let updateTimer = null;

// UI Elements
const connectionStatus = document.getElementById('connection-status');
const powerStatus = document.getElementById('power-status');
const compressorStatus = document.getElementById('compressor-status');
const flowTempValue = document.getElementById('flow-temp-value');
const returnTempValue = document.getElementById('return-temp-value');
const outdoorTempValue = document.getElementById('outdoor-temp-value');
const flowRateEl = document.getElementById('flow-rate');
const waterPressureEl = document.getElementById('water-pressure');
const operatingModeEl = document.getElementById('operating-mode');
const lastUpdateEl = document.getElementById('last-update');
const errorSection = document.getElementById('error-section');
const errorMessage = document.getElementById('error-message');
const tempSlider = document.getElementById('temp-slider');
const tempSliderValue = document.getElementById('temp-slider-value');

// Buttons
const btnPowerOn = document.getElementById('btn-power-on');
const btnPowerOff = document.getElementById('btn-power-off');
const btnSetTemp = document.getElementById('btn-set-temp');

// Gauge configuration
const GAUGE_MIN = 0;
const GAUGE_MAX = 80;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    startAutoUpdate();
});

function initEventListeners() {
    btnPowerOn.addEventListener('click', () => setPower(true));
    btnPowerOff.addEventListener('click', () => setPower(false));
    btnSetTemp.addEventListener('click', setTemperature);
    tempSlider.addEventListener('input', (e) => {
        tempSliderValue.textContent = parseFloat(e.target.value).toFixed(1);
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
    // Power status
    powerStatus.textContent = data.is_on ? 'ON' : 'OFF';
    powerStatus.style.color = data.is_on ? '#10b981' : '#ef4444';

    // Compressor status
    compressorStatus.textContent = `Compressor: ${data.compressor_running ? 'ON' : 'OFF'}`;
    compressorStatus.style.background = data.compressor_running ? '#d1fae5' : '#e5e7eb';
    compressorStatus.style.color = data.compressor_running ? '#065f46' : '#6b7280';

    // Temperature gauges
    updateGauge('gauge-flow', data.flow_temperature, GAUGE_MIN, GAUGE_MAX);
    flowTempValue.textContent = `${data.flow_temperature.toFixed(1)}°C`;

    updateGauge('gauge-return', data.return_temperature, GAUGE_MIN, GAUGE_MAX);
    returnTempValue.textContent = `${data.return_temperature.toFixed(1)}°C`;

    updateGauge('gauge-outdoor', data.outdoor_temperature, -20, 40);
    outdoorTempValue.textContent = `${data.outdoor_temperature.toFixed(1)}°C`;

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

    // Color coding
    if (percentage > 80) {
        gauge.style.stroke = '#ef4444'; // Red
    } else if (percentage > 60) {
        gauge.style.stroke = '#f59e0b'; // Orange
    } else {
        gauge.style.stroke = '#667eea'; // Blue
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

        // Show confirmation
        btnSetTemp.textContent = '✓ Set';
        setTimeout(() => {
            btnSetTemp.textContent = 'Set Temperature';
        }, 2000);

    } catch (error) {
        console.error('Failed to set temperature:', error);
        alert('Failed to set temperature');
    }
}
