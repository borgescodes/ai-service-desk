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

function scrollOpenFaqIntoView(current) {
  const viewport = current.closest('.faq-directory-scroll');
  if (!viewport || !current.open) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  requestAnimationFrame(() => {
    const viewportRect = viewport.getBoundingClientRect();
    const categoryRect = current.getBoundingClientRect();
    const targetTop = viewport.scrollTop + categoryRect.top - viewportRect.top - 8;
    viewport.scrollTo({
      top: Math.max(0, targetTop),
      behavior: reducedMotion ? 'auto' : 'smooth',
    });
  });
}

document.addEventListener('toggle', event => {
  const current = event.target;
  if (!(current instanceof HTMLDetailsElement) || !current.matches('.faq-category') || !current.open) return;
  scrollOpenFaqIntoView(current);
}, true);
