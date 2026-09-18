/* CardaLink — project.js
   Global JS: password show/hide toggle + dark mode switch
   ============================================================ */

window.addEventListener('DOMContentLoaded', function () {

  /* ------------------------------------------------------------------
     1. PASSWORD SHOW / HIDE TOGGLE
     Works for any button with class .password-toggle-btn that has a
     data-target="<input-id>" attribute.
  ------------------------------------------------------------------ */
  document.querySelectorAll('.password-toggle-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var targetId = btn.getAttribute('data-target');
      var input = targetId
        ? document.getElementById(targetId)
        : btn.closest('.password-input-group')?.querySelector('input');

      if (!input) return;

      var isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';

      var icon = btn.querySelector('i');
      if (icon) {
        icon.classList.toggle('bi-eye', !isPassword);
        icon.classList.toggle('bi-eye-slash', isPassword);
      }

      btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    });
  });

  /* ------------------------------------------------------------------
     2. DARK MODE TOGGLE
     Only present on portal/dashboard pages (dashboard_base.html injects
     the #themeToggleBtn). The landing page never has this button.
  ------------------------------------------------------------------ */
  var toggleBtn = document.getElementById('themeToggleBtn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      var current = document.documentElement.getAttribute('data-theme');
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('cl-theme', next); } catch (e) {}
    });
  }

});
