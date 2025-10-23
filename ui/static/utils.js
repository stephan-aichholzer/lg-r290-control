// Shared utility functions

/**
 * Update gauge visualization
 * @param {string} gaugeId - The ID of the gauge element
 * @param {number} value - Current value
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 */
export function updateGauge(gaugeId, value, min, max) {
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

/**
 * Update connection status badge
 * @param {HTMLElement} element - The status badge element
 * @param {boolean} connected - Connection state
 */
export function updateConnectionStatus(element, connected) {
    if (connected) {
        element.textContent = 'Connected';
        element.classList.remove('disconnected');
        element.classList.add('connected');
    } else {
        element.textContent = 'Disconnected';
        element.classList.remove('connected');
        element.classList.add('disconnected');
    }
}

/**
 * Perform async HTTP request with error handling
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */
export async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API request failed: ${url}`, error);
        throw error;
    }
}

/**
 * Show modern confirmation modal dialog
 * @param {string} title - Dialog title
 * @param {string} message - Dialog message
 * @returns {Promise<boolean>} True if confirmed, false if cancelled
 */
export function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('modal-overlay');
        const titleEl = document.getElementById('modal-title');
        const messageEl = document.getElementById('modal-message');
        const confirmBtn = document.getElementById('modal-confirm');
        const cancelBtn = document.getElementById('modal-cancel');

        // Set content
        titleEl.textContent = title;
        messageEl.textContent = message;

        // Show modal
        overlay.classList.add('active');

        // Handle confirm
        const handleConfirm = () => {
            cleanup();
            resolve(true);
        };

        // Handle cancel
        const handleCancel = () => {
            cleanup();
            resolve(false);
        };

        // Handle click outside
        const handleOverlayClick = (e) => {
            if (e.target === overlay) {
                handleCancel();
            }
        };

        // Cleanup function
        const cleanup = () => {
            overlay.classList.remove('active');
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
            overlay.removeEventListener('click', handleOverlayClick);
        };

        // Attach event listeners
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        overlay.addEventListener('click', handleOverlayClick);
    });
}
