/* Navigation bar injected into every protected window.
 *
 * Runs inside the page, so back/forward/reload are plain history and location
 * calls. Only "new window" and "close" need to reach Python, via the bridge that
 * pywebview installs on each navigation.
 */
(function () {
  'use strict';

  if (document.getElementById('__cbs_toolbar')) return;

  var HEIGHT = 38;
  var BG = '#161b22';
  var LINE = '#30363d';
  var TEXT = '#e6edf3';
  var MUTED = '#8b949e';
  var OK = '#3fb950';

  function makeButton(label, title, onClick) {
    var button = document.createElement('button');
    button.textContent = label;
    button.title = title;
    button.setAttribute(
      'style',
      'all:unset;box-sizing:border-box;min-width:30px;height:26px;padding:0 8px;' +
        'border:1px solid ' + LINE + ';border-radius:6px;background:#1c2230;color:' + TEXT + ';' +
        'font:14px/1 "Segoe UI Symbol","Segoe UI",system-ui,sans-serif;text-align:center;' +
        'cursor:pointer;user-select:none;'
    );
    button.addEventListener('mouseenter', function () { button.style.background = '#232b39'; });
    button.addEventListener('mouseleave', function () { button.style.background = '#1c2230'; });
    button.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();
      onClick();
    });
    return button;
  }

  function navigate(raw) {
    var value = (raw || '').trim();
    if (!value) return;
    if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) {
      var looksLikeHost = value.indexOf('.') !== -1 && value.indexOf(' ') === -1;
      value = looksLikeHost
        ? 'https://' + value
        : 'https://www.google.com/search?q=' + encodeURIComponent(value);
    }
    window.location.href = value;
  }

  function callApi(name, argument) {
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api[name]) {
        window.pywebview.api[name](argument);
        return;
      }
    } catch (error) { /* bridge not ready yet */ }
  }

  var bar = document.createElement('div');
  bar.id = '__cbs_toolbar';
  bar.setAttribute(
    'style',
    'position:fixed;top:0;left:0;right:0;height:' + HEIGHT + 'px;box-sizing:border-box;' +
      'display:flex;align-items:center;gap:6px;padding:0 8px;background:' + BG + ';' +
      'border-bottom:1px solid ' + LINE + ';color:' + TEXT + ';z-index:2147483647;' +
      'font:13px "Segoe UI",system-ui,sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.45);'
  );

  var badge = document.createElement('span');
  badge.textContent = 'protected';
  badge.title = 'This window is excluded from screen capture';
  badge.setAttribute(
    'style',
    'color:' + OK + ';border:1px solid ' + OK + ';border-radius:999px;' +
      'padding:1px 8px;font-size:10.5px;font-weight:600;white-space:nowrap;'
  );

  var address = document.createElement('input');
  address.type = 'text';
  address.spellcheck = false;
  address.value = window.location.href;
  address.setAttribute(
    'style',
    'flex:1;min-width:60px;height:26px;box-sizing:border-box;padding:0 10px;' +
      'border:1px solid ' + LINE + ';border-radius:6px;background:#0b0f14;color:' + TEXT + ';' +
      'font:12px "Segoe UI",system-ui,sans-serif;outline:none;'
  );
  address.addEventListener('keydown', function (event) {
    event.stopPropagation();
    if (event.key === 'Enter') navigate(address.value);
    if (event.key === 'Escape') address.value = window.location.href;
  });
  address.addEventListener('focus', function () { address.select(); });

  bar.appendChild(makeButton('←', 'Back (Alt+Left)', function () { window.history.back(); }));
  bar.appendChild(makeButton('→', 'Forward (Alt+Right)', function () { window.history.forward(); }));
  bar.appendChild(makeButton('⟳', 'Reload (F5)', function () { window.location.reload(); }));
  bar.appendChild(address);
  bar.appendChild(badge);
  bar.appendChild(makeButton('＋', 'New protected window', function () { callApi('new_window', ''); }));
  bar.appendChild(makeButton('✕', 'Close this window', function () { callApi('close_window', ''); }));

  function attach() {
    if (!document.body) return false;
    document.body.appendChild(bar);
    return true;
  }

  if (!attach()) {
    document.addEventListener('DOMContentLoaded', attach);
  }

  window.addEventListener('popstate', function () { address.value = window.location.href; });
  window.addEventListener('hashchange', function () { address.value = window.location.href; });

  window.addEventListener('keydown', function (event) {
    var target = event.target;
    var typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
    if (event.altKey && event.key === 'ArrowLeft') { event.preventDefault(); window.history.back(); }
    else if (event.altKey && event.key === 'ArrowRight') { event.preventDefault(); window.history.forward(); }
    else if (event.key === 'F5' || (event.ctrlKey && event.key.toLowerCase() === 'r')) {
      event.preventDefault(); window.location.reload();
    } else if (event.ctrlKey && event.key.toLowerCase() === 'l') {
      event.preventDefault(); address.focus();
    } else if (event.ctrlKey && !event.shiftKey && !typing && event.key.toLowerCase() === 'w') {
      event.preventDefault(); callApi('close_window', '');
    }
  }, true);
})();
