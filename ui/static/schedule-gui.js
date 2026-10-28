// Schedule GUI - read-only view of schedule.json
//
// Renders one card per schedule pattern, mirroring the file's own structure.
// Each pattern is the fixed four-slot model - morning, day, evening, night -
// so a card is always four rows, and the slot names are positional.
//
// Tapping a row opens it for editing: start time, target temperature and
// offset, each on a stepper. The steppers cannot produce an invalid schedule -
// the start time is clamped to what the neighbouring slots allow - and the API
// re-checks the same rule on save, so this page is the convenient path to a
// valid schedule rather than the thing that guarantees one.
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

// The fixed slot model, mirroring schedule_api.py: every pattern is exactly
// these four slots in ascending time order, so there is no add, no remove and
// no undefined hour. Night is the slot that spans midnight.
const SLOT_NAMES = ['morning', 'day', 'evening', 'night'];
const BOUNDARY_STEP_MINUTES = 15;
const MIN_SLOT_MINUTES = 60;
const MINUTES_PER_DAY = 1440;

// Target temperatures are coloured across the same range the thermostat UI
// offers, so a given colour means the same thing on both pages.
const TEMP_MIN = CONFIG.THERMOSTAT_TEMP_MIN;
const TEMP_MAX = CONFIG.THERMOSTAT_TEMP_MAX;

// The steppers move in the same units as the control page, so a degree means
// the same thing whichever page you set it from.
const TEMP_STEP = CONFIG.THERMOSTAT_TEMP_STEP;
const OFFSET_MIN = -5;   // the API's own bounds for auto_offset
const OFFSET_MAX = 5;

const el = (id) => document.getElementById(id);

// The config as the API last gave it to us, and the row currently open for
// editing. While a row is open the 60s auto-refresh is skipped, so a reload
// cannot pull the ground out from under a half-finished edit.
let currentConfig = null;
let editing = null;   // { pattern, slot, draft } or null
let busy = false;     // a save is in flight

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

/**
 * How far one boundary may move, with the other three held where they are.
 *
 * Every slot has to keep MIN_SLOT_MINUTES, and night's length is the only one
 * set by two boundaries - (24:00 - night start) + morning start - so the first
 * and last slots constrain each other across midnight.
 */
function boundaryRange(starts, slotIdx) {
    const lastStep = MINUTES_PER_DAY - BOUNDARY_STEP_MINUTES;

    if (slotIdx === 0) {
        return [
            Math.max(0, starts[3] - (MINUTES_PER_DAY - MIN_SLOT_MINUTES)),
            starts[1] - MIN_SLOT_MINUTES
        ];
    }

    if (slotIdx === SLOT_NAMES.length - 1) {
        return [
            starts[2] + MIN_SLOT_MINUTES,
            Math.min(lastStep, starts[0] + MINUTES_PER_DAY - MIN_SLOT_MINUTES)
        ];
    }

    return [
        starts[slotIdx - 1] + MIN_SLOT_MINUTES,
        starts[slotIdx + 1] - MIN_SLOT_MINUTES
    ];
}

const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));

/** One labelled stepper line: label, minus, value, plus. */
function stepper(kind, label, value, canDec, canInc) {
    return `
        <div class="sg-step-row">
            <span class="sg-step-label">${label}</span>
            <button class="sg-step" data-act="dec" data-kind="${kind}"
                    ${canDec ? '' : 'disabled'} aria-label="decrease ${label}">&minus;</button>
            <span class="sg-step-value">${value}</span>
            <button class="sg-step" data-act="inc" data-kind="${kind}"
                    ${canInc ? '' : 'disabled'} aria-label="increase ${label}">+</button>
        </div>`;
}

/** The open row: three steppers, the legal window, and save/cancel. */
function renderEditor(patternIdx, slotIdx, starts) {
    const draft = editing.draft;
    const committed = currentConfig.schedules[patternIdx].periods[slotIdx];
    const [lo, hi] = boundaryRange(starts, slotIdx);
    const minutes = timeToMinutes(draft.time);

    const dirty = draft.time !== committed.time
        || draft.target_temp !== committed.target_temp
        || draft.auto_offset !== committed.auto_offset;

    return `
        <div class="sg-editor">
            <div class="sg-editor-head">
                <span class="sg-editor-slot" style="color:${tempColor(draft.target_temp)}">
                    ${SLOT_NAMES[slotIdx]}
                </span>
                <span class="sg-editor-hint">
                    may start ${minutesToTime(lo)}&ndash;${minutesToTime(hi)}
                </span>
            </div>
            ${stepper('time', 'start', draft.time,
                      minutes - BOUNDARY_STEP_MINUTES >= lo,
                      minutes + BOUNDARY_STEP_MINUTES <= hi)}
            ${stepper('temp', 'target', `${draft.target_temp.toFixed(1)}&deg;`,
                      draft.target_temp - TEMP_STEP >= TEMP_MIN - 0.001,
                      draft.target_temp + TEMP_STEP <= TEMP_MAX + 0.001)}
            ${stepper('offset', 'offset',
                      `${draft.auto_offset > 0 ? '+' : ''}${draft.auto_offset}`,
                      draft.auto_offset > OFFSET_MIN,
                      draft.auto_offset < OFFSET_MAX)}
            <div class="sg-editor-note">
                Applies when ${SLOT_NAMES[slotIdx]} next starts, at ${draft.time}.
            </div>
            <div class="sg-editor-actions">
                <button class="sg-btn" data-act="cancel" ${busy ? 'disabled' : ''}>Cancel</button>
                <button class="sg-btn primary" data-act="save"
                        ${dirty && !busy ? '' : 'disabled'}>${busy ? 'Saving...' : 'Save'}</button>
            </div>
        </div>`;
}

function renderDay(segments, sorted, isToday, patternIdx) {
    const active = isToday ? activeIndex(sorted) : -1;

    const starts = sorted.map((p) => timeToMinutes(p.time));

    const rows = segments.map((s) => {
        // A wrapped segment repeats the last period of the day, so it is the
        // active row only when the clock is actually inside it.
        const idx = sorted.indexOf(s.period);
        const isActive = isToday && idx === active
            && nowMinutes() >= s.start && nowMinutes() < s.end;

        // Night owns two rows - the collapsed carry-over at the top and its
        // own start at the bottom - so the editor opens on the real one.
        if (editing && editing.pattern === patternIdx && editing.slot === idx
                && !s.wrapped) {
            return renderEditor(patternIdx, idx, starts);
        }

        const rail =
            `<span class="sg-rail" style="background:${tempColor(s.period.target_temp)}"></span>`;

        if (s.wrapped) {
            // One collapsed line: what carried over, and until when.
            const sign = s.period.auto_offset > 0 ? '+' : '';
            const offset = s.period.auto_offset !== 0
                ? ` ${sign}${s.period.auto_offset}` : '';
            return `
            <div class="sg-row sg-row-cont ${isActive ? 'active' : ''}"
                 data-pattern="${patternIdx}" data-slot="${idx}"
                 style="height:${rowHeight(s)}px">
                ${rail}
                <span class="sg-cont-text">night &middot; until ${minutesToTime(s.end)}, carried from ${s.period.time}</span>
                <span class="sg-cont-temp">${s.period.target_temp.toFixed(1)}&deg;${offset}</span>
            </div>`;
        }

        return `
            <div class="sg-row ${isActive ? 'active' : ''}"
                 data-pattern="${patternIdx}" data-slot="${idx}"
                 style="height:${rowHeight(s)}px">
                ${rail}
                <span class="sg-row-time">${s.period.time}<em>${SLOT_NAMES[idx] || ''}</em></span>
                <span class="sg-row-temp">${s.period.target_temp.toFixed(1)}&deg;</span>
                ${offsetHtml(s.period.auto_offset)}
            </div>`;
    }).join('');

    // The open editor is taller than the row it replaced, so the marker can no
    // longer be placed from row heights. Hidden until the row closes.
    const marker = isToday && !(editing && editing.pattern === patternIdx)
        ? `<div class="sg-nowline" style="top:${nowOffsetPx(segments)}px">
               <span class="sg-nowtag">now</span>
           </div>`
        : '';

    return `<div class="sg-daycol">${rows}${marker}</div>`;
}

function renderPattern(pattern, patternIdx) {
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
            ${renderDay(segments, sorted, isToday, patternIdx)}
        </section>`;
}

/**
 * Check one pattern against the fixed slot model, the same way the API does
 * on write. Reads are deliberately tolerant, so a hand-edited file still
 * renders - this is what reports it instead.
 */
function slotModelErrors(periods) {
    if (periods.length !== SLOT_NAMES.length) {
        return [`has ${periods.length} `
                + `slot${periods.length === 1 ? '' : 's'}; the model is exactly `
                + `${SLOT_NAMES.length} (${SLOT_NAMES.join(', ')})`];
    }

    // Sorted first, because this page judges the schedule, not the order the
    // file happens to list it in - the API is the one that insists on
    // ascending order on write.
    const starts = [...periods]
        .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time))
        .map((p) => timeToMinutes(p.time));

    const errors = [];

    starts.forEach((start, i) => {
        if (start % BOUNDARY_STEP_MINUTES !== 0) {
            errors.push(`${SLOT_NAMES[i]} starts at ${minutesToTime(start)}, `
                + `not on a ${BOUNDARY_STEP_MINUTES}-minute step`);
        }
        if (i > 0 && start === starts[i - 1]) {
            errors.push(`${SLOT_NAMES[i]} and ${SLOT_NAMES[i - 1]} both start `
                + `at ${minutesToTime(start)}`);
        }
    });

    // Night wraps midnight, so its length is the only one set by two boundaries.
    const durations = [
        starts[1] - starts[0],
        starts[2] - starts[1],
        starts[3] - starts[2],
        (MINUTES_PER_DAY - starts[3]) + starts[0]
    ];

    durations.forEach((duration, i) => {
        if (duration < MIN_SLOT_MINUTES) {
            errors.push(`${SLOT_NAMES[i]} lasts ${duration} min, `
                + `under the ${MIN_SLOT_MINUTES} min minimum`);
        }
    });

    return errors;
}

/**
 * Problems the API's per-period validation does not catch, because it checks
 * each period in isolation: day coverage, and the slot model above. All of
 * these are silent failures at runtime.
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
        const errors = slotModelErrors(s.periods);
        if (errors.length) {
            checks.push({
                level: 'err',
                text: `<strong>Pattern ${i + 1} (${s.days.join(', ')}) `
                    + `breaks the slot model:</strong> ${errors.join('; ')}. `
                    + 'Saving it from this page would be refused.'
            });
        }
    });

    if (!checks.length) {
        checks.push({
            level: 'ok',
            text: 'All seven days covered exactly once, four valid slots each.'
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

/** Open a row for editing, holding the edit in a draft until Save. */
function openRow(patternIdx, slotIdx) {
    if (busy || !currentConfig) return;

    const periods = currentConfig.schedules[patternIdx].periods;
    const sorted = [...periods].sort(
        (a, b) => timeToMinutes(a.time) - timeToMinutes(b.time));
    const target = sorted[slotIdx];

    editing = {
        pattern: patternIdx,
        slot: slotIdx,
        // Index in the file's own order, which is what a save has to write
        // back - it is not necessarily the sorted position.
        raw: periods.indexOf(target),
        draft: Object.assign({}, target)
    };

    renderAll();
}

/** Move one value by one step, clamped so the result is always valid. */
function adjustDraft(kind, direction) {
    if (!editing) return;

    const periods = currentConfig.schedules[editing.pattern].periods;
    const starts = [...periods]
        .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time))
        .map((p) => timeToMinutes(p.time));
    const draft = editing.draft;

    if (kind === 'time') {
        const [lo, hi] = boundaryRange(starts, editing.slot);
        const moved = timeToMinutes(draft.time)
            + direction * BOUNDARY_STEP_MINUTES;
        draft.time = minutesToTime(clamp(moved, lo, hi));
    } else if (kind === 'temp') {
        const moved = draft.target_temp + direction * TEMP_STEP;
        // Back to one decimal: repeated 0.1 steps drift in binary floats.
        draft.target_temp =
            Math.round(clamp(moved, TEMP_MIN, TEMP_MAX) * 10) / 10;
    } else if (kind === 'offset') {
        draft.auto_offset =
            clamp(draft.auto_offset + direction, OFFSET_MIN, OFFSET_MAX);
    }

    renderAll();
}

/** POST the whole configuration, surfacing the API's own refusal text. */
async function postConfig(config) {
    const response = await fetch(`${CONFIG.HEATPUMP_API_URL}/schedule/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });

    const body = await response.json().catch(() => null);

    if (!response.ok) {
        const detail = body && body.detail ? body.detail : `HTTP ${response.status}`;
        throw new Error(
            typeof detail === 'string' ? detail : JSON.stringify(detail));
    }

    return body;
}

/**
 * Send the draft. The endpoint takes the whole configuration, so the draft is
 * applied to a copy and the copy is posted - a failed save leaves both the
 * file and what is on screen exactly as they were.
 */
async function saveDraft() {
    if (busy || !editing) return;

    const next = JSON.parse(JSON.stringify(currentConfig));
    next.schedules[editing.pattern].periods[editing.raw] = {
        time: editing.draft.time,
        target_temp: editing.draft.target_temp,
        auto_offset: editing.draft.auto_offset
    };

    busy = true;
    renderAll();

    try {
        const saved = await postConfig(next);
        currentConfig = saved;
        editing = null;
        busy = false;
        el('sg-error').hidden = true;
        renderAll();
        el('sg-updated').textContent =
            `Saved ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        busy = false;
        renderAll();
        showError(`Save refused: ${error.message}`);
    }
}

/** One delegated listener for the whole card stack. */
function onPatternsClick(event) {
    const control = event.target.closest('[data-act]');

    if (control) {
        const act = control.dataset.act;
        if (act === 'dec') adjustDraft(control.dataset.kind, -1);
        else if (act === 'inc') adjustDraft(control.dataset.kind, 1);
        else if (act === 'cancel') { editing = null; renderAll(); }
        else if (act === 'save') saveDraft();
        return;
    }

    const row = event.target.closest('.sg-row[data-pattern]');
    if (row) {
        openRow(Number(row.dataset.pattern), Number(row.dataset.slot));
    }
}

function renderAll() {
    renderHeader(currentConfig);
    renderChecks(runChecks(currentConfig));
    el('sg-patterns').innerHTML =
        currentConfig.schedules.map(renderPattern).join('');
}

function showError(message) {
    const box = el('sg-error');
    box.textContent = message;
    box.hidden = false;
}

async function load() {
    // A reload mid-edit would discard the draft and close the row underneath
    // the finger that is still on it.
    if (editing || busy) return;

    try {
        currentConfig = await apiRequest(
            `${CONFIG.HEATPUMP_API_URL}/schedule/config`);

        el('sg-error').hidden = true;
        renderAll();

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
    el('sg-patterns').addEventListener('click', onPatternsClick);
    // An explicit refresh is allowed to drop an open draft; the automatic one
    // is not, and load() guards itself.
    el('sg-refresh').addEventListener('click', () => {
        editing = null;
        load();
    });
    setInterval(load, REFRESH_INTERVAL);
});
