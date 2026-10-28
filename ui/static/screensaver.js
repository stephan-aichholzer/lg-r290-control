/**
 * Screensaver module - Vanta.js WAVES effect with inactivity timeout
 * Kiosk mode: Starts with screensaver active, returns after 60s inactivity
 */

const INACTIVITY_TIMEOUT = 60 * 1000; // 60 seconds in milliseconds

class Screensaver {
    constructor() {
        this.overlay = document.getElementById('screensaver-overlay');
        this.timeElement = document.getElementById('screensaver-time');
        this.indoorTempElement = document.getElementById('screensaver-temp-indoor');
        this.outdoorTempElement = document.getElementById('screensaver-temp-outdoor');
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

        // Initialize Vanta.js WAVES effect.
        // Tuned dark and slow for the AMOLED kiosk panel: a deep colour keeps the
        // mean pixel luminance low, low shininess avoids bright fixed specular
        // highlights, and the slow speed cuts GPU load on an old phone. The
        // *Controls flags stay false so a touch wakes the screensaver instead of
        // being swallowed as a camera gesture.
        if (window.VANTA && window.THREE) {
            this.vantaEffect = window.VANTA.WAVES({
                el: '#screensaver-overlay',
                mouseControls: false,
                touchControls: false,
                gyroControls: false,
                minHeight: 200.00,
                minWidth: 200.00,
                scale: 1.00,
                scaleMobile: 1.00,
                color: 0x0a1a2a,
                shininess: 15.00,
                waveHeight: 18.00,
                waveSpeed: 0.55,
                zoom: 0.85
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
        // Get indoor temperature from main UI
        const indoorTempElement = document.getElementById('indoor-temp-value');
        if (indoorTempElement && this.indoorTempElement) {
            this.indoorTempElement.textContent = indoorTempElement.textContent;
        }

        // Get outdoor temperature from main UI
        const outdoorTempElement = document.getElementById('outdoor-temp-value');
        if (outdoorTempElement && this.outdoorTempElement) {
            this.outdoorTempElement.textContent = outdoorTempElement.textContent;
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
    console.log(`Screensaver initialized (activates after ${INACTIVITY_TIMEOUT / 1000}s of inactivity)`);

    // Expose for debugging
    window.screensaver = screensaver;
}

export default { initScreensaver };
