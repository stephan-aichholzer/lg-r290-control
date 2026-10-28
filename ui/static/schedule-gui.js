// Schedule GUI - read-only view of schedule.json
//
// Renders one card per schedule pattern, mirroring the file's own structure.
// Deliberately read-only: it only issues GET /schedule/config, so this page
// cannot alter the heating schedule.
//
// Note: the screensaver is NOT loaded here. It activates on load and after
// 60s idle, which would black out a page meant to be read.

import { CONFIG } from './config.js';
import { apiRequest } from './utils.js';

const REFRESH_INTERVAL = 60000; // 60s - enough to move the "now" marker

// Portrait layout: the day runs vertically, so a period's height encodes its
// duration. MIN_ROW_PX keeps a short period tall enough to read and to tap;
// because that floor distorts the scale, the "now" marker is positioned from
// the accumulated row heights rather than from the clock alone.
const PX_PER_MINUTE = 0.30;   // 1440 min -> ~432px for a full day
const MIN_ROW_PX = 52;

// The stretch from midnight to the first period of the day only repeats what
// the evening left in force, so it is collapsed to one line instead of being
// drawn to scale - it would otherwise be the tallest row on the card.
const CONT_ROW_PX = 34;

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday',
              'friday', 'saturday', 'sunday'];

// Target temperatures are coloured across the same range the thermostat UI
// offers, so a given colour means the same thing on both pages.
const TEMP_MIN = CONFIG.THERMOSTAT_TEMP_MIN;
const TEMP_MAX = CONFIG.THERMOSTAT_TEMP_MAX;

const el = (id) => document.getElementById(id);

function timeToMinutes(hhmm) {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
}

function minutesToTime(mins) {
    const h = String(Math.floor(mins / 60) % 24).padStart(2, '0');
    const m = String(mins % 60).padStart(2, '0');
    return `${h}:${m}`;
}

function todayName() {
    return DAYS[(new Date().getDay() + 6) % 7]; // JS: 0=Sunday
}

function nowMinutes() {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
}

/** Blue (cool) to orange (warm), matching --blue-color and --accent-color. */
function tempColor(temp) {
    const t = Math.max(0, Math.min(1, (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)));
    const from = [59, 130, 246];
    const to = [249, 115, 22];
    const mix = from.map((c, i) => Math.round(c + (to[i] - c) * t));
    return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

/**
 * Expand a pattern's periods into 24h segments.
 *
 * Mirrors scheduler.py: periods are sorted by time, and the stretch before the
 * first period belongs to the LAST period of the day - the scheduler wraps
 * around rather than leaving the early hours undefined.
 */
function buildSegments(periods) {
    const sorted = [...periods].sort(
        (a, b) => timeToMinutes(a.time) - timeToMinutes(b.time));

    const segments = [];
    const first = timeToMinutes(sorted[0].time);

    if (first > 0) {
        segments.push({
            period: sorted[sorted.length - 1],
            start: 0,
            end: first,
            wrapped: true
        });
    }

    sorted.forEach((period, i) => {
        const start = timeToMinutes(period.time);
        const end = (i + 1 < sorted.length)
            ? timeToMinutes(sorted[i + 1].time)
            : 1440;
        segments.push({ period, start, end, wrapped: false });
    });

    return { sorted, segments };
}

function offsetHtml(offset) {
    const cls = offset > 0 ? 'pos' : offset < 0 ? 'neg' : '';
    const sign = offset > 0 ? '+' : '';
    return `<span class="sg-offset ${cls}">${sign}${offset}</span>`;
}

/** Row height in px for a segment, floored so short periods stay legible. */
function rowHeight(segment) {
    if (segment.wrapped) return CONT_ROW_PX;
    return Math.max(MIN_ROW_PX, (segment.end - segment.start) * PX_PER_MINUTE);
}

/** Index of the period in force right now, following the same wrap rule. */
function activeIndex(sorted) {
    const mins = nowMinutes();
    let idx = -1;
    sorted.forEach((p, i) => {
        if (timeToMinutes(p.time) <= mins) idx = i;
    });
    return idx === -1 ? sorted.length - 1 : idx;
}

/**
 * Offset of the "now" marker in px, measured through the rendered rows so it
 * stays aligned with what is actually on screen even where MIN_ROW_PX has
 * stretched a short period.
 */
function nowOffsetPx(segments) {
    const mins = nowMinutes();
    let top = 0;

    for (const segment of segments) {
        const height = rowHeight(segment);
        if (mins < segment.end) {
            const into = (mins - segment.start) / (segment.end - segment.start);
            return top + Math.max(0, Math.min(1, into)) * height;
        }
        top += height;
    }
    return top;
}

function renderDay(segments, sorted, isToday) {
    const active = isToday ? activeIndex(sorted) : -1;

    const rows = segments.map((s) => {
        // A wrapped segment repeats the last period of the day, so it is the
        // active row only when the clock is actually inside it.
        const idx = sorted.indexOf(s.period);
        const isActive = isToday && idx === active
            && nowMinutes() >= s.start && nowMinutes() < s.end;
        const rail =
            `<span class="sg-rail" style="background:${tempColor(s.period.target_temp)}"></span>`;

        if (s.wrapped) {
            // One collapsed line: what carried over, and until when.
            const sign = s.period.auto_offset > 0 ? '+' : '';
            const offset = s.period.auto_offset !== 0
                ? ` ${sign}${s.period.auto_offset}` : '';
            return `
            <div class="sg-row sg-row-cont ${isActive ? 'active' : ''}"
                 style="height:${rowHeight(s)}px">
                ${rail}
                <span class="sg-cont-text">00:00&ndash;${minutesToTime(s.end)} &middot; carried from ${s.period.time}</span>
                <span class="sg-cont-temp">${s.period.target_temp.toFixed(1)}&deg;${offset}</span>
            </div>`;
        }

        return `
            <div class="sg-row ${isActive ? 'active' : ''}"
                 style="height:${rowHeight(s)}px">
                ${rail}
                <span class="sg-row-time">${s.period.time}</span>
                <span class="sg-row-temp">${s.period.target_temp.toFixed(1)}&deg;</span>
                ${offsetHtml(s.period.auto_offset)}
            </div>`;
    }).join('');

    const marker = isToday
        ? `<div class="sg-nowline" style="top:${nowOffsetPx(segments)}px">
               <span class="sg-nowtag">now</span>
           </div>`
        : '';

    return `<div class="sg-daycol">${rows}${marker}</div>`;
}

function renderPattern(pattern) {
    const today = todayName();
    const isToday = pattern.days.map((d) => d.toLowerCase()).includes(today);
    const { sorted, segments } = buildSegments(pattern.periods);

    const days = pattern.days.map((d) => {
        const cls = d.toLowerCase() === today ? 'sg-day is-today' : 'sg-day';
        return `<span class="${cls}">${d.slice(0, 3)}</span>`;
    }).join('');

    return `
        <section class="sg-card ${isToday ? 'today' : ''}">
            <div class="sg-card-head">
                <div class="sg-days">${days}</div>
                <span class="sg-card-tag">
                    ${sorted.length} periods${isToday ? ' &middot; today' : ''}
                </span>
            </div>
            ${renderDay(segments, sorted, isToday)}
        </section>`;
}

/**
 * Problems the API's own validation does not catch, because it checks each
 * period in isolation. Both of these are silent failures at runtime.
 */
function runChecks(config) {
    const checks = [];

    if (!config.enabled) {
        checks.push({
            level: 'warn',
            text: '<strong>Scheduler is disabled.</strong> These periods are '
                + 'stored but not applied - AUTO mode will not follow them.'
        });
    }

    const coverage = {};
    DAYS.forEach((d) => { coverage[d] = 0; });
    config.schedules.forEach((s) => {
        s.days.forEach((d) => {
            const key = d.toLowerCase();
            if (key in coverage) coverage[key] += 1;
        });
    });

    const missing = DAYS.filter((d) => coverage[d] === 0);
    const doubled = DAYS.filter((d) => coverage[d] > 1);

    if (missing.length) {
        checks.push({
            level: 'err',
            text: `<strong>No schedule for ${missing.join(', ')}.</strong> `
                + 'On those days the scheduler finds no match and AUTO holds '
                + 'the last target indefinitely.'
        });
    }

    if (doubled.length) {
        checks.push({
            level: 'warn',
            text: `<strong>${doubled.join(', ')} appears in more than one `
                + 'pattern.</strong> The first matching pattern silently wins.'
        });
    }

    config.schedules.forEach((s, i) => {
        const times = s.periods.map((p) => p.time);
        const dupes = times.filter((t, k) => times.indexOf(t) !== k);
        if (dupes.length) {
            checks.push({
                level: 'warn',
                text: `<strong>Pattern ${i + 1} repeats ${[...new Set(dupes)].join(', ')}.</strong> `
                    + 'Only one of the duplicates will take effect.'
            });
        }
    });

    if (!checks.length) {
        checks.push({
            level: 'ok',
            text: 'All seven days covered exactly once, no duplicate times.'
        });
    }

    return checks;
}

function renderChecks(checks) {
    const box = el('sg-checks');
    box.innerHTML = checks
        .map((c) => `<div class="sg-check ${c.level}">${c.text}</div>`)
        .join('');
    box.hidden = false;
}

function renderHeader(config) {
    const badge = el('sg-enabled');
    badge.textContent = config.enabled ? 'Enabled' : 'Disabled';
    badge.className = `sg-badge ${config.enabled ? 'on' : 'off'}`;

    const now = new Date();
    const day = now.toLocaleDateString(undefined, { weekday: 'long' });
    const time = now.toLocaleTimeString(undefined,
        { hour: '2-digit', minute: '2-digit' });
    el('sg-now').textContent = `${day} ${time}`;
}

function showError(message) {
    const box = el('sg-error');
    box.textContent = message;
    box.hidden = false;
}

async function load() {
    try {
        const config = await apiRequest(
            `${CONFIG.HEATPUMP_API_URL}/schedule/config`);

        el('sg-error').hidden = true;
        renderHeader(config);
        renderChecks(runChecks(config));

        el('sg-patterns').innerHTML =
            config.schedules.map(renderPattern).join('');

        el('sg-updated').textContent =
            `Loaded ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        showError(`Could not load the schedule from `
            + `${CONFIG.HEATPUMP_API_URL}/schedule/config - ${error.message}`);
        el('sg-patterns').innerHTML = '';
        el('sg-updated').textContent = 'Load failed';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    load();
    el('sg-refresh').addEventListener('click', load);
    setInterval(load, REFRESH_INTERVAL);
});
