/* Global "working..." feedback for every interactive control.

   Why this exists: a logout link, a submit button, or a plain <a> that POSTs
   gives the browser no signal that anything happened until the next page
   paints. On a slow network (or a remote database) that dead air makes the
   app feel broken -- so the user clicks again, firing a second logout or a
   duplicate order. This module makes the pending state visible on every page
   with zero markup changes:

     1. Logout links (any <a> whose href contains "logout") show a spinner +
        "Logging out..." before navigating.
     2. Every form submit spins the submit button (unless the page's own JS
        already took over via preventDefault, or the form opted into the
        dedicated auth-submit.js behaviour).
     3. Any button/anchor can opt in with data-loading="Verbing..." to get the
        same inline spinner treatment.

   Visual style matches auth-submit.js and the rest of the app: a FontAwesome
   spinner swapped into the control itself -- never a full-screen overlay.
   State is restored on pageshow so Back/Forward navigation (bfcache) can
   never leave a button permanently disabled. */
(function () {
    'use strict';

    var SPINNER = '<i class="fa-solid fa-spinner fa-spin"></i>';
    var DEFAULT_LABEL = 'Processing...';
    var LOGOUT_LABEL = 'Logging out...';
    // Short delay so the browser paints the spinner before the next
    // navigation freezes the page; long enough to be seen, short enough
    // that the logout still feels instant.
    var NAV_DELAY_MS = 180;

    function markBusy(el, label) {
        if (!el || el.dataset.uiBusy === '1') return;
        el.dataset.uiBusy = '1';
        if (el.dataset.idleHtml === undefined) {
            el.dataset.idleHtml = el.innerHTML;
        }
        el.setAttribute('aria-busy', 'true');
        el.style.pointerEvents = 'none';
        el.style.opacity = '0.75';
        if (el.tagName === 'BUTTON') {
            el.disabled = true;
        }
        el.innerHTML = SPINNER + ' <span>' + (label || DEFAULT_LABEL) + '</span>';
    }

    function markIdle(el) {
        if (!el || el.dataset.uiBusy !== '1') return;
        delete el.dataset.uiBusy;
        el.removeAttribute('aria-busy');
        el.style.pointerEvents = '';
        el.style.opacity = '';
        if (el.tagName === 'BUTTON') {
            el.disabled = false;
        }
        if (el.dataset.idleHtml !== undefined) {
            el.innerHTML = el.dataset.idleHtml;
            delete el.dataset.idleHtml;
        }
    }

    function onClick(event) {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;

        var el = event.target.closest('a, button, [data-loading]');
        if (!el) return;

        var isLogout = el.tagName === 'A' && /logout/i.test(el.getAttribute('href') || '');
        var hasLoadingAttr = el.hasAttribute('data-loading');
        if (!isLogout && !hasLoadingAttr) return;

        if (el.dataset.uiBusy === '1') {
            // Already working: swallow the impatient second click.
            event.preventDefault();
            return;
        }

        var label = isLogout
            ? LOGOUT_LABEL
            : (el.getAttribute('data-loading') || DEFAULT_LABEL);
        markBusy(el, label);

        // Plain navigating anchors: hold the door long enough for the
        // spinner to render, then follow the link like the browser would.
        if (el.tagName === 'A') {
            var href = el.getAttribute('href');
            if (href && href !== '#') {
                event.preventDefault();
                setTimeout(function () { window.location.assign(href); }, NAV_DELAY_MS);
            }
        }
    }

    function onSubmit(event) {
        var form = event.target;
        // The page's own JS took over the request (fetch/Alpine) -- it owns
        // the feedback and will restore its own button.
        if (event.defaultPrevented) return;
        // auth-submit.js already shows a spinner and blocks re-entry.
        if (form.hasAttribute('data-auth-submit')) return;
        // Submitting into a new tab leaves this page open; don't strand it.
        if (form.target === '_blank') return;

        if (form.dataset.uiPending === '1') {
            // A double click or an impatient Enter press must not fire a
            // second POST while the first one is still in flight.
            event.preventDefault();
            return;
        }
        form.dataset.uiPending = '1';

        var submitter = event.submitter
            || form.querySelector('[type="submit"]:not([disabled])');
        markBusy(submitter, form.getAttribute('data-loading-label') || DEFAULT_LABEL);
    }

    // Back/forward navigation restores the page from the bfcache with the
    // button still spinning and the pending flag set; reset both.
    function onPageShow() {
        document.querySelectorAll('[data-ui-busy]').forEach(markIdle);
        document.querySelectorAll('form[data-ui-pending]').forEach(function (form) {
            form.dataset.uiPending = '0';
        });
    }

    document.addEventListener('click', onClick, false);
    document.addEventListener('submit', onSubmit, false);
    window.addEventListener('pageshow', onPageShow);
})();
