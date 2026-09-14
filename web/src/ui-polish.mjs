import { pageScrollTarget } from './presentation.mjs';
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
  if (!current.open) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(() => {
    if (!current.open || !current.isConnected) return;
    const footerHeight = document.querySelector('.faq-help-strip')?.getBoundingClientRect().height || 0;
    const target = pageScrollTarget(current.getBoundingClientRect(), window.innerHeight - footerHeight, window.scrollY);
    if (target !== null) window.scrollTo({ top: target, behavior: reducedMotion ? 'auto' : 'smooth' });
  }, reducedMotion ? 0 : 240);
}

const toggledByUser = new WeakSet();
document.addEventListener('click', event => {
  const category = event.target.closest?.('.faq-category > summary')?.parentElement;
  if (category) toggledByUser.add(category);
});

document.addEventListener('toggle', event => {
  const current = event.target;
  if (!(current instanceof HTMLDetailsElement) || !current.matches('.faq-category') || !current.open) return;
  if (!toggledByUser.has(current)) return;
  toggledByUser.delete(current);
  scrollOpenFaqIntoView(current);
}, true);
