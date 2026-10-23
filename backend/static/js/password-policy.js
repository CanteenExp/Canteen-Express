/* Live password policy for every "new password" field.

   Mirrors accounts/validators.py so the browser and the server never disagree:
   at least 8 characters with an uppercase letter, a lowercase letter, a number
   and a special character. Requirements are shown as a live checklist while
   the user types, the confirm field is checked as it is typed, and weak
   submissions are stopped before the request leaves the page.

   Paste and drag-and-drop are disabled on password inputs: the policy only
   helps if the value was actually typed by the person who will use it.

   Usage (no markup beyond these attributes):
       <input type="password" data-password-policy>
       <input type="password" data-password-confirm>            // same form
       <input type="password" data-password-confirm="primary-id"> // explicit

   The module is intentionally dependency-free and injects its own small
   stylesheet, so it works on the dark auth screens and the light dashboards
   without a Tailwind rebuild. */
(function () {
    'use strict';

    var MIN_LENGTH = 8;
    var PASTE_NOTE = 'For your security, please type your password instead of pasting it.';

    var RULES = [
        { id: 'length', label: 'At least ' + MIN_LENGTH + ' characters', test: function (value) {
            return value.length >= MIN_LENGTH;
        } },
        { id: 'lower', label: 'A lowercase letter (a-z)', test: function (value) {
            return /[a-z]/.test(value);
        } },
        { id: 'upper', label: 'An uppercase letter (A-Z)', test: function (value) {
            return /[A-Z]/.test(value);
        } },
        { id: 'digit', label: 'A number (0-9)', test: function (value) {
            return /[0-9]/.test(value);
        } },
        { id: 'special', label: 'A special character (!@#$%^&*)', test: function (value) {
            return /[^A-Za-z0-9]/.test(value);
        } }
    ];

    function evaluate(value) {
        value = value || '';
        var checks = {};
        var met = 0;
        RULES.forEach(function (rule) {
            var passed = rule.test(value);
            checks[rule.id] = passed;
            if (passed) met += 1;
        });
        var valid = met === RULES.length;
        return {
            value: value,
            checks: checks,
            met: met,
            total: RULES.length,
            valid: valid,
            // Same three labels the old faculty meter used, so existing
            // colour bindings keep working.
            level: valid ? 'Strong' : (met >= 3 ? 'Medium' : 'Weak')
        };
    }

    var STYLES = [
        '.pw-policy{margin-top:6px;font-size:11px;line-height:1.5;color:#94a3b8;text-align:left}',
        '.pw-policy[hidden]{display:none}',
        '.pw-policy__head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}',
        '.pw-policy__label{font-weight:700;letter-spacing:.02em}',
        '.pw-policy__level{font-weight:800;text-transform:uppercase;letter-spacing:.05em;font-size:10px;padding:1px 7px;border-radius:999px;border:1px solid transparent}',
        '.pw-policy__level.is-weak{color:#f87171;background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.35)}',
        '.pw-policy__level.is-medium{color:#fbbf24;background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.35)}',
        '.pw-policy__level.is-strong{color:#34d399;background:rgba(16,185,129,.12);border-color:rgba(16,185,129,.35)}',
        '.pw-policy__meter{height:4px;border-radius:999px;background:rgba(148,163,184,.28);overflow:hidden;margin-bottom:6px}',
        '.pw-policy__bar{display:block;height:100%;width:0;border-radius:999px;transition:width .18s ease,background-color .18s ease}',
        '.pw-policy__bar.is-weak{background:#ef4444}',
        '.pw-policy__bar.is-medium{background:#f59e0b}',
        '.pw-policy__bar.is-strong{background:#10b981}',
        '.pw-policy__rules{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:1px 10px}',
        '@media (max-width:420px){.pw-policy__rules{grid-template-columns:1fr}}',
        '.pw-policy__rule{display:flex;align-items:flex-start;gap:5px;opacity:.8;transition:color .15s ease,opacity .15s ease}',
        '.pw-policy__rule.is-met{color:#10b981;opacity:1}',
        '.pw-policy__mark{width:12px;flex:0 0 12px;text-align:center;font-weight:900}',
        '.pw-policy__note{margin:4px 0 0;font-size:10px;font-weight:700;color:#fb7185}',
        '.pw-policy__note[hidden]{display:none}',
        '@media (prefers-reduced-motion:reduce){.pw-policy__bar{transition:none}}'
    ].join('');

    function ensureStyles() {
        if (document.getElementById('pw-policy-styles')) return;
        var style = document.createElement('style');
        style.id = 'pw-policy-styles';
        style.textContent = STYLES;
        document.head.appendChild(style);
    }

    function fieldAnchor(input) {
        return input.closest('.relative') || input.parentElement || input;
    }

    function buildPanel() {
        var panel = document.createElement('div');
        panel.className = 'pw-policy';
        panel.hidden = true;
        panel.setAttribute('aria-live', 'polite');

        var head = document.createElement('div');
        head.className = 'pw-policy__head';
        var label = document.createElement('span');
        label.className = 'pw-policy__label';
        label.textContent = 'Password strength';
        var level = document.createElement('span');
        level.className = 'pw-policy__level is-weak';
        level.textContent = 'Weak';
        head.appendChild(label);
        head.appendChild(level);

        var meter = document.createElement('div');
        meter.className = 'pw-policy__meter';
        var bar = document.createElement('span');
        bar.className = 'pw-policy__bar is-weak';
        meter.appendChild(bar);

        var list = document.createElement('ul');
        list.className = 'pw-policy__rules';
        var rows = {};
        RULES.forEach(function (rule) {
            var row = document.createElement('li');
            row.className = 'pw-policy__rule';
            row.setAttribute('data-rule', rule.id);
            var mark = document.createElement('span');
            mark.className = 'pw-policy__mark';
            mark.setAttribute('aria-hidden', 'true');
            mark.textContent = '\u25CB'; // hollow circle until met
            var text = document.createElement('span');
            text.textContent = rule.label;
            row.appendChild(mark);
            row.appendChild(text);
            list.appendChild(row);
            rows[rule.id] = row;
        });

        panel.appendChild(head);
        panel.appendChild(meter);
        panel.appendChild(list);
        return { panel: panel, level: level, bar: bar, rows: rows };
    }

    function render(ui, result) {
        var tone = result.level.toLowerCase();
        ui.level.textContent = result.level;
        ui.level.className = 'pw-policy__level is-' + tone;
        ui.bar.style.width = Math.round((result.met / result.total) * 100) + '%';
        ui.bar.className = 'pw-policy__bar is-' + tone;

        RULES.forEach(function (rule) {
            var row = ui.rows[rule.id];
            var passed = !!result.checks[rule.id];
            row.classList.toggle('is-met', passed);
            var mark = row.querySelector('.pw-policy__mark');
            if (mark) mark.textContent = passed ? '\u2713' : '\u25CB';
        });
    }

    function note(anchor) {
        var el = anchor.querySelector('.pw-policy__note');
        if (el) return el;
        el = document.createElement('p');
        el.className = 'pw-policy__note';
        el.hidden = true;
        anchor.appendChild(el);
        return el;
    }

    function flash(input, message) {
        var anchor = fieldAnchor(input);
        var el = note(anchor);
        el.textContent = message;
        el.hidden = false;
        clearTimeout(el._timer);
        el._timer = setTimeout(function () {
            el.hidden = true;
        }, 5000);
    }

    var enhanced = [];   // { input, ui }
    var confirms = [];   // { input, primary, note }

    function enhancePolicy(input) {
        if (input._pwPolicy) return;
        var ui = buildPanel();
        fieldAnchor(input).insertAdjacentElement('afterend', ui.panel);
        input._pwPolicy = ui;

        function sync() {
            var result = evaluate(input.value);
            render(ui, result);
            if (document.activeElement === input || input.value) {
                ui.panel.hidden = false;
            } else {
                ui.panel.hidden = true;
            }
            if (input.hasAttribute('required')) {
                input.setCustomValidity(result.valid || !input.value
                    ? ''
                    : 'Use at least 8 characters with uppercase, lowercase, a number and a special character.');
            }
            syncConfirms();
        }

        input.addEventListener('input', sync);
        input.addEventListener('focus', sync);
        input.addEventListener('blur', function () {
            if (!input.value) ui.panel.hidden = true;
        });
        enhanced.push({ input: input, ui: ui });
        sync();
    }

    function primaryFor(confirmInput) {
        var explicit = confirmInput.getAttribute('data-password-confirm');
        if (explicit) {
            var byId = document.getElementById(explicit);
            if (byId) return byId;
        }
        var form = confirmInput.form;
        return form ? form.querySelector('[data-password-policy]') : null;
    }

    function syncConfirms() {
        confirms.forEach(function (entry) {
            var primary = entry.primary;
            var confirm = entry.input;
            if (!primary) return;
            var mismatch = !!confirm.value && confirm.value !== primary.value;
            entry.note.hidden = !mismatch;
            confirm.setCustomValidity(mismatch ? 'Passwords do not match.' : '');
        });
    }

    function enhanceConfirm(input) {
        if (input._pwConfirm) return;
        var anchor = fieldAnchor(input);
        var el = note(anchor);
        el.textContent = 'Passwords do not match.';
        var entry = { input: input, primary: primaryFor(input), note: el };
        input._pwConfirm = entry;
        input.addEventListener('input', syncConfirms);
        confirms.push(entry);
        syncConfirms();
    }

    function isProtectedField(input) {
        if (!input || input.tagName !== 'INPUT') return false;
        // Stay protected even after the "show password" eye toggles the input
        // to type="text", otherwise that button would re-enable pasting.
        return input.type === 'password'
            || input.hasAttribute('data-password-policy')
            || input.hasAttribute('data-password-confirm');
    }

    function stopPaste(event) {
        var input = event.target;
        if (!isProtectedField(input)) return;
        if (input.hasAttribute('data-allow-paste')) return;
        event.preventDefault();
        flash(input, PASTE_NOTE);
    }

    // Form-level guard: works for plain POST forms, Alpine @submit.prevent
    // handlers and inline onsubmit handlers alike because it runs during the
    // capture phase and stops the event before it reaches the form.
    function guardSubmit(event) {
        var form = event.target;
        if (!form || form.nodeType !== 1) return;

        var policyInput = form.querySelector('[data-password-policy]');
        if (!policyInput) return;

        if (!evaluate(policyInput.value).valid) {
            event.preventDefault();
            event.stopPropagation();
            policyInput.focus();
            flash(policyInput, 'Use at least 8 characters with an uppercase letter, a lowercase letter, a number and a special character.');
            return;
        }

        var confirmInput = form.querySelector('[data-password-confirm]');
        if (confirmInput && confirmInput.value !== policyInput.value) {
            event.preventDefault();
            event.stopPropagation();
            confirmInput.focus();
            confirmInput.setCustomValidity('Passwords do not match.');
            var anchor = fieldAnchor(confirmInput);
            var el = note(anchor);
            el.textContent = 'Passwords do not match.';
            el.hidden = false;
        }
    }

    function init() {
        ensureStyles();
        var policyInputs = document.querySelectorAll('[data-password-policy]');
        Array.prototype.forEach.call(policyInputs, enhancePolicy);
        var confirmInputs = document.querySelectorAll('[data-password-confirm]');
        Array.prototype.forEach.call(confirmInputs, enhanceConfirm);

        document.addEventListener('paste', stopPaste, true);
        document.addEventListener('drop', stopPaste, true);
        document.addEventListener('submit', guardSubmit, true);
    }

    // Called when a form clears its own values programmatically (e.g. the
    // forgot-password modal), where no input event fires to refresh the meter.
    function reset(input) {
        if (!input) return;
        var policy = enhanced.filter(function (entry) { return entry.input === input; })[0];
        if (policy) {
            render(policy.ui, evaluate(''));
            policy.ui.panel.hidden = true;
        }
        input.setCustomValidity('');
        confirms.forEach(function (entry) {
            if (entry.input === input || entry.primary === input) {
                entry.input.setCustomValidity('');
                entry.note.hidden = true;
            }
        });
    }

    window.PasswordPolicy = {
        rules: RULES,
        evaluate: evaluate,
        reset: reset,
        minLength: MIN_LENGTH,
        flash: flash
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
