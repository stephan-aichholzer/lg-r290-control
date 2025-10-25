// LG R290 Heat Pump & Thermostat Control
// Main application entry point

import * as HeatPump from './heatpump.js';
import * as Thermostat from './thermostat.js';
import { initScreensaver } from './screensaver.js';

// Initialize application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing LG R290 Control System...');

    // Initialize heat pump control
    HeatPump.init();
    console.log('Heat pump module initialized');

    // Initialize thermostat control (async - sets defaults)
    await Thermostat.init();
    console.log('Thermostat module initialized');

    // Initialize screensaver
    initScreensaver();
    console.log('Screensaver module initialized');

    console.log('System ready');
});
