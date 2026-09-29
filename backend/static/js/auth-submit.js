/* Shared submit-feedback for the plain-server-rendered auth forms
   (staff login, rider login, generic login, admin PIN verify).

   Why this exists: those forms POST normally, so the browser gives no signal
   that a click did anything until the next page paints. A user who clicks
   twice -- or clicks and waits with no feedback -- assumes the app is broken.
   This module makes the pending state visible and blocks the double submit.

   Markup contract: add data-auth-submit="Verbing..." to the <form> and
   data-auth-submit-btn to the submit button. Both are optional; the script
   degrades to plain form behaviour if neither is present. */
(function () {
    'use strict';

    var SPINNER = '<i class="fa-solid fa-spinner fa-spin"></i> ';

    function busyLabel(form) {
        return form.getAttribute('data-auth-submit') || 'Please wait...';
    }

    function setButtonBusy(form, button, isBusy) {
        if (!button) return;

        if (isBusy) {
            if (button.dataset.idleHtml === undefined) {
                button.dataset.idleHtml = button.innerHTML;
            }
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            button.innerHTML = SPINNER + '<span>' + busyLabel(form) + '</span>';
        } else {
            button.disabled = false;
            button.removeAttribute('aria-busy');
            if (button.dataset.idleHtml !== undefined) {
                button.innerHTML = button.dataset.idleHtml;
            }
        }
    }

    function setStatus(form, message, isError) {
        var status = form.querySelector('[data-auth-status]');
        if (!status) return;
        status.textContent = message || '';
        status.classList.toggle('hidden', !message);
        status.classList.toggle('text-red-400', !!isError);
        status.classList.toggle('text-brand-orange', !isError);
    }

    function onSubmit(event) {
        var form = event.currentTarget;

        // Let the browser show its own validation bubbles; report only the
        // fields that are actually invalid so the user knows what to fix.
        if (!form.checkValidity()) {
            form.reportValidity();
            setStatus(form, 'Please correct the highlighted fields.', true);
            return;
        }

        // Guard re-entry: once a submit is in flight the button is disabled,
        // but a keyboard Enter or a programmatic requestSubmit can still fire.
        if (form.dataset.authPending === '1') {
            event.preventDefault();
            return;
        }
        form.dataset.authPending = '1';

        setStatus(form, busyLabel(form), false);
        setButtonBusy(form, form.querySelector('[data-auth-submit-btn]'), true);
    }

    // Back/forward navigation restores the form from the bfcache with the
    // button still disabled, which would leave the page permanently unusable.
    function onPageShow() {
        document.querySelectorAll('form[data-auth-submit], form[data-auth-submit-btn]').forEach(function (form) {
            form.dataset.authPending = '0';
            setButtonBusy(form, form.querySelector('[data-auth-submit-btn]'), false);
            var status = form.querySelector('[data-auth-status]');
            if (status) status.textContent = '';
        });
    }

    function init() {
        document.querySelectorAll('form[data-auth-submit], form[data-auth-submit-btn]').forEach(function (form) {
            if (form.dataset.authBound === '1') return;
            form.dataset.authBound = '1';
            form.addEventListener('submit', onSubmit);
        });
        window.addEventListener('pageshow', onPageShow);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
