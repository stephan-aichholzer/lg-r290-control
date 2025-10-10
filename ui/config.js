// Configuration and Constants
export const CONFIG = {
    HEATPUMP_API_URL: `http://${window.location.hostname}:8002`,
    THERMOSTAT_API_URL: `http://192.168.2.11:8001`,
    HEATPUMP_UPDATE_INTERVAL: 10000, // 10 seconds (reduced from 2s to minimize Modbus traffic)
    THERMOSTAT_UPDATE_INTERVAL: 60000, // 60 seconds
    GAUGE_MIN: 0,
    GAUGE_MAX: 80,
    THERMOSTAT_TEMP_MIN: 18.0,
    THERMOSTAT_TEMP_MAX: 24.0,
    THERMOSTAT_TEMP_STEP: 0.5,

    // Thermostat default configuration
    THERMOSTAT_DEFAULTS: {
        hysteresis: 0.1,
        min_on_time: 40,
        min_off_time: 10,
        temp_sample_count: 4,
        control_interval: 60
    }
};
