/**
 * Autonomous AI Data Analyst - Client-Side Instant Interaction Engine
 * Exposes zero-latency client triggers for theme, layout, and keyboard interactions.
 */
(function() {
  // 1. Instant Theme Switcher without server roundtrip lag or CSS transition thrash
  window.__toggleThemeInstant = function() {
    try {
      var html = document.documentElement;
      var body = document.body;
      var current = html.getAttribute('data-theme') || 
                    (body.classList.contains('theme-dark') ? 'dark' : 'light');
      var next = current === 'dark' ? 'light' : 'dark';

      html.classList.add('no-transition');
      body.classList.add('no-transition');
      html.setAttribute('data-theme', next);
      body.setAttribute('data-theme', next);

      if (next === 'light') {
        body.classList.remove('theme-dark');
        body.classList.add('theme-light');
      } else {
        body.classList.remove('theme-light');
        body.classList.add('theme-dark');
      }

      try {
        localStorage.setItem('aa_theme_mode', next);
      } catch(e) {}

      requestAnimationFrame(function() {
        requestAnimationFrame(function() {
          html.classList.remove('no-transition');
          body.classList.remove('no-transition');
        });
      });
    } catch(err) {
      console.warn('Instant theme toggle error:', err);
    }
  };

  // 2. Instant Sidebar Collapse/Expand trigger
  window.__toggleSidebarInstant = function() {
    try {
      var sb = document.querySelector('.app-sidebar');
      if (sb) {
        sb.classList.toggle('collapsed');
      }
    } catch(err) {
      console.warn('Instant sidebar toggle error:', err);
    }
  };

  // 3. Client-side Enter key handler for chat without per-keystroke server roundtrips
  document.addEventListener('keydown', function(e) {
    if (e.target && e.target.id === 'chat-input-textarea') {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        var btn = document.getElementById('chat-send-btn') || e.target.closest('div')?.querySelector('button');
        if (btn && !btn.disabled) {
          btn.click();
        }
      }
    }
  });
})();
