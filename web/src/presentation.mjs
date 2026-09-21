const motion = () => ({ gsap: globalThis.gsap, Flip: globalThis.Flip });

export function createWelcomeEntry() {
  let wasVisible = false;
  return {
    update(visible) { const entering = visible && !wasVisible; wasVisible = visible; return entering; },
    reset() { wasVisible = false; },
  };
}

export function pageScrollTarget(rect, height, scrollY) {
  if (rect.top >= 96 && rect.bottom <= height - 24) return null;
  return Math.max(0, scrollY + rect.top - 116);
}

export function captureJupFlip(root, reducedMotion = false) {
  const { Flip } = motion();
  const avatar = root.querySelector('[data-flip-id="jup-avatar"]');
  if (reducedMotion || !Flip || !avatar) return null;
  return Flip.getState(avatar, { props: 'borderRadius' });
}

export function animateJupFlip(root, state, reducedMotion = false) {
  const { Flip } = motion();
  const avatar = root.querySelector('[data-flip-id="jup-avatar"]');
  if (!state || reducedMotion || !Flip || !avatar) return;
  Flip.from(state, {
    targets: avatar,
    duration: 0.46,
    ease: 'power3.out',
    absolute: true,
    scale: true,
    prune: true,
  });
}

export function presentChat(root, { reducedMotion = false } = {}) {
  const { gsap } = motion();
  const fresh = root.querySelectorAll('.conversation-message.is-new:not(.conversation-message--thinking)');
  if (!gsap || reducedMotion || !fresh.length) return () => {};
  const timeline = gsap.timeline();
  fresh.forEach(message => {
    const paragraphs = message.querySelectorAll('.message-bubble > p, .message-source-card, .support-handoff');
    timeline.fromTo(message, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.18, ease: 'power3.out' }, 0);
    if (paragraphs.length) timeline.fromTo(paragraphs, { autoAlpha: 0, y: 6 }, { autoAlpha: 1, y: 0, duration: 0.22, stagger: 0.035, ease: 'power3.out' }, 0.04);
  });
  return () => timeline.kill();
}

export async function dismissThinking(root, reducedMotion = false) {
  const element = root.querySelector('.conversation-message--thinking');
  if (!element) return;
  const { gsap } = motion();
  if (!gsap || reducedMotion) {
    element.style.opacity = '0';
    return;
  }
  await new Promise(resolve => {
    gsap.timeline({ onComplete: resolve })
      .to(element.querySelector('.processing-activity'), { autoAlpha: 0, y: -3, duration: 0.1, ease: 'power2.out' })
      .to(element, { height: 34, autoAlpha: 0, marginBlock: 0, duration: 0.2, ease: 'power3.inOut' }, '<0.03');
  });
}

export function animatePersonaPopover(menu, reducedMotion = false) {
  if (!menu?.open) return;
  const panel = menu.querySelector('.persona-options');
  const { gsap } = motion();
  if (!panel || !gsap || reducedMotion) return;
  gsap.fromTo(panel, { autoAlpha: 0, y: -6, scale: 0.985 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.2, ease: 'power3.out', clearProps: 'transform' });
}

export function presentQueueChanges(root, previousIds = new Set(), reducedMotion = false) {
  const rows = [...root.querySelectorAll('[data-request-id], [data-request-select], [data-handoff-id]')];
  const ids = new Set(rows.map(row => row.dataset.requestId || row.dataset.requestSelect || row.dataset.handoffId).filter(Boolean));
  const { gsap } = motion();
  if (!gsap || reducedMotion || !previousIds.size) return { ids, finish: () => {} };
  const fresh = rows.filter(row => !previousIds.has(row.dataset.requestId || row.dataset.requestSelect || row.dataset.handoffId));
  const selected = rows.find(row => row.getAttribute('aria-current') === 'true');
  const timeline = gsap.timeline();
  if (fresh.length) timeline.fromTo(fresh, { autoAlpha: 0, y: -9, backgroundColor: '#fff4cf' }, { autoAlpha: 1, y: 0, backgroundColor: 'transparent', duration: 0.42, ease: 'power3.out', clearProps: 'backgroundColor' });
  if (selected) timeline.fromTo(selected, { x: -3 }, { x: 0, duration: 0.18, ease: 'power3.out', clearProps: 'transform' }, fresh.length ? 0.12 : 0);
  return { ids, finish: () => timeline.kill() };
}
