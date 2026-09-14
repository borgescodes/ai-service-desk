function syncWelcomeListening(value) {
  const welcome = document.querySelector('.chat-welcome');
  if (!welcome) return;
  const listening = Boolean(String(value ?? '').trim());
  welcome.dataset.listening = String(listening);
  welcome.querySelector('[data-welcome-state="idle"]')?.setAttribute('aria-hidden', String(listening));
  welcome.querySelector('[data-welcome-state="listening"]')?.setAttribute('aria-hidden', String(!listening));
}

document.addEventListener('input', event => {
  if (event.target?.id === 'jup-message') syncWelcomeListening(event.target.value);
});

// The `name` attribute provides native exclusivity in current browsers; this keeps
// the same one-open contract in engines that do not implement grouped details yet.
document.addEventListener('toggle', event => {
  const current = event.target;
  if (!(current instanceof HTMLDetailsElement) || !current.matches('.faq-category[name="support-faq"]') || !current.open) return;
  document.querySelectorAll('.faq-category[name="support-faq"][open]').forEach(item => {
    if (item !== current) item.open = false;
  });
}, true);
