/**
 * Screensaver module - Vanta.js HALO effect with inactivity timeout
 * Kiosk mode: Starts with screensaver active, returns after 60s inactivity
 */

const INACTIVITY_TIMEOUT = 60 * 1000; // 60 seconds in milliseconds

class Screensaver {
    constructor() {
        this.overlay = document.getElementById('screensaver-overlay');
        this.timeElement = document.getElementById('screensaver-time');
        this.tempElement = document.getElementById('screensaver-temp');
        this.inactivityTimer = null;
        this.clockTimer = null;
        this.tempTimer = null;
        this.vantaEffect = null;
        this.isActive = false;

        this.init();
    }

    init() {
        // Listen for user activity
        this.setupActivityListeners();

        // Click to wake
        this.overlay.addEventListener('click', () => this.deactivate());

        // Kiosk mode: Start with screensaver active on page load
        // This prevents flashing/flipping on auto-reload or view switching
        this.activate();
    }

    setupActivityListeners() {
        const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];

        events.forEach(event => {
            document.addEventListener(event, () => {
                if (!this.isActive) {
                    this.resetInactivityTimer();
                }
            }, true);
        });
    }

    resetInactivityTimer() {
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
        }

        this.inactivityTimer = setTimeout(() => {
            this.activate();
        }, INACTIVITY_TIMEOUT);
    }

    activate() {
        if (this.isActive) return;

        console.log('Activating screensaver...');
        this.isActive = true;
        this.overlay.classList.add('active');

        // Initialize Vanta.js HALO effect
        if (window.VANTA && window.THREE) {
            this.vantaEffect = window.VANTA.HALO({
                el: '#screensaver-overlay',
                mouseControls: false,
                touchControls: false,
                gyroControls: false,
                minHeight: 200.00,
                minWidth: 200.00,
                baseColor: 0x0,
                backgroundColor: 0x0,
                amplitudeFactor: 1.0,
                xOffset: 0.0,
                yOffset: 0.0,
                size: 1.5
            });
        }

        // Start clock
        this.updateClock();
        this.clockTimer = setInterval(() => this.updateClock(), 1000);

        // Update temperature from current display (initial + every 10 seconds)
        this.updateTemperature();
        this.tempTimer = setInterval(() => this.updateTemperature(), 10000);
    }

    deactivate() {
        if (!this.isActive) return;

        console.log('Deactivating screensaver...');
        this.isActive = false;
        this.overlay.classList.remove('active');

        // Destroy Vanta effect
        if (this.vantaEffect) {
            this.vantaEffect.destroy();
            this.vantaEffect = null;
        }

        // Stop clock
        if (this.clockTimer) {
            clearInterval(this.clockTimer);
            this.clockTimer = null;
        }

        // Stop temperature updates
        if (this.tempTimer) {
            clearInterval(this.tempTimer);
            this.tempTimer = null;
        }

        // Reset inactivity timer
        this.resetInactivityTimer();
    }

    updateClock() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        this.timeElement.textContent = `${hours}:${minutes}`;
    }

    updateTemperature() {
        // Get indoor/room temperature from main UI
        const indoorTempElement = document.getElementById('indoor-temp-value');
        if (indoorTempElement) {
            this.tempElement.textContent = indoorTempElement.textContent;
        }
    }

    // Public method to manually trigger screensaver (for testing)
    trigger() {
        this.activate();
    }
}

// Initialize screensaver when DOM is ready
let screensaver;

export function initScreensaver() {
    screensaver = new Screensaver();
    console.log('Screensaver initialized (activates after 2 minutes of inactivity)');

    // Expose for debugging
    window.screensaver = screensaver;
}

export default { initScreensaver };
