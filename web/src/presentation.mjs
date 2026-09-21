import { createProgressiveScrollFollower } from './conversation.mjs';

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

export function responseRevealDuration(wordCount) {
  const words = Math.max(0, Number(wordCount) || 0);
  if (words <= 24) return Math.min(1200, Math.max(700, 700 + words * 20));
  if (words <= 120) return Math.min(2000, Math.max(1200, 1000 + words * 12));
  return Math.min(3000, Math.max(2200, 2000 + (words - 120) * 2.1));
}

function exposeResponse(message) {
  message.querySelector?.('[data-progressive-response]')?.removeAttribute?.('aria-hidden');
  message.querySelectorAll?.('[data-response-followup]')?.forEach?.(item => item.removeAttribute?.('aria-hidden'));
  message.querySelector?.('.response-announcement')?.remove?.();
}

function chunkResponse(primary) {
  const doc = primary?.ownerDocument;
  if (!doc?.createTreeWalker || !doc.createElement || !doc.createDocumentFragment) return [];
  const filter = doc.defaultView?.NodeFilter ?? globalThis.NodeFilter;
  if (!filter) return [];
  const walker = doc.createTreeWalker(primary, filter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.data.trim() && !node.parentElement?.closest?.('.sr-only')) textNodes.push(node);
  }
  const chunks = [];
  textNodes.forEach(node => {
    const tokens = node.data.match(/\S+\s*/g) || [];
    if (!tokens.length) return;
    const fragment = doc.createDocumentFragment();
    for (let index = 0; index < tokens.length; index += 2) {
      const text = tokens.slice(index, index + 2).join('');
      const span = doc.createElement('span');
      span.className = 'response-reveal-chunk';
      span.textContent = text;
      if (/[.!?;:]\s*$/.test(text)) span.dataset.revealPause = 'punctuation';
      fragment.append(span);
      chunks.push(span);
    }
    const last = chunks.at(-1);
    if (last && node.parentElement?.matches?.('p, li, h1, h2, h3, h4')) last.dataset.revealPause = 'block';
    const link = node.parentElement?.closest?.('a');
    if (link && !link.getAttribute('aria-label')) link.setAttribute('aria-label', link.textContent.trim());
    node.replaceWith(fragment);
  });
  return chunks;
}

function animateWelcome(root, gsap, enabled) {
  if (!enabled) return null;
  const welcome = root.querySelector?.('.chat-welcome:not(.chat-welcome--leaving)');
  if (!welcome) return null;
  const avatar = welcome.querySelector?.('.chat-welcome-avatar-stack');
  const lines = welcome.querySelectorAll?.('[data-welcome-line]') || [];
  const timeline = gsap.timeline();
  if (avatar) timeline.fromTo(avatar, { autoAlpha: 0, scale: 0.94 }, { autoAlpha: 1, scale: 1, duration: 0.42, ease: 'power3.out' });
  lines.forEach((line, index) => timeline.fromTo(line, { clipPath: 'inset(0 100% 0 0)', autoAlpha: 0.45 }, { clipPath: 'inset(0 0% 0 0)', autoAlpha: 1, duration: 0.48, ease: 'power3.out' }, 0.22 + index * 0.34));
  return timeline;
}

export function presentChat(root, { welcome = false, followConversation = true, reducedMotion = false } = {}) {
  const { gsap } = motion();
  const fresh = [...root.querySelectorAll('.conversation-message.is-new:not(.conversation-message--thinking)')];
  if (!gsap || reducedMotion) {
    fresh.forEach(exposeResponse);
    return () => {};
  }

  const timelines = [];
  const progressiveFollowers = [];
  const welcomeTimeline = animateWelcome(root, gsap, welcome);
  if (welcomeTimeline) timelines.push(welcomeTimeline);

  fresh.forEach(message => {
    const primary = message.querySelector?.('[data-progressive-response]');
    if (!primary) return;
    const chunks = chunkResponse(primary);
    const followups = [...(message.querySelectorAll?.('[data-response-followup]') || [])];
    if (!chunks.length) {
      exposeResponse(message);
      return;
    }
    primary.removeAttribute('aria-hidden');
    const wordCount = primary.textContent.trim().split(/\s+/).filter(Boolean).length;
    const duration = responseRevealDuration(wordCount) / 1000;
    const weights = chunks.map(chunk => chunk.dataset.revealPause === 'block' ? 2.1 : chunk.dataset.revealPause === 'punctuation' ? 1.55 : 1);
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
    const thread = message.closest?.('.conversation-thread');
    const follower = createProgressiveScrollFollower(thread, followConversation);
    progressiveFollowers.push(follower);
    const timeline = gsap.timeline({
      onUpdate() { follower.update(); },
      onComplete() {
        followups.forEach(item => item.removeAttribute('aria-hidden'));
        message.querySelector?.('.response-announcement')?.remove?.();
        follower.stop();
      },
    });
    gsap.set(chunks, { autoAlpha: 0 });
    let cursor = 0;
    chunks.forEach((chunk, index) => {
      timeline.to(chunk, { autoAlpha: 1, duration: 0.07, ease: 'power2.out' }, cursor / totalWeight * Math.max(0.1, duration - 0.07));
      cursor += weights[index];
    });
    if (followups.length) {
      timeline.call(() => followups.forEach(item => item.removeAttribute('aria-hidden')), [], duration)
        .fromTo(followups, { autoAlpha: 0, y: 3 }, { autoAlpha: 1, y: 0, duration: 0.16, stagger: 0.04, ease: 'power3.out' }, duration);
    }
    timelines.push(timeline);
  });

  return () => {
    timelines.forEach(timeline => timeline.kill());
    progressiveFollowers.forEach(follower => follower.stop());
    fresh.forEach(exposeResponse);
  };
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
