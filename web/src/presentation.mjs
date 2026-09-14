export function pageScrollTarget(rect, height, scrollY) {
  if (rect.top >= 96 && rect.bottom <= height - 24) return null;
  return Math.max(0, scrollY + rect.top - 116);
}

export function revealTextNodes(nodes, { characters = false, reducedMotion = false, schedule = setTimeout, cancel = clearTimeout, onProgress = () => {}, onFinish = () => {} } = {}) {
  const originals = nodes.map(node => node.data);
  if (reducedMotion) { onFinish(); return () => {}; }
  const units = originals.flatMap((text, index) => (characters ? Array.from(text) : text.match(/\s+|\S+\s*/g) || []).map(text => ({ index, text })));
  const batch = characters ? 1 : Math.max(1, Math.ceil(units.length / 100));
  let cursor = 0, timer, finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    cancel(timer);
    nodes.forEach((node, i) => { node.data = originals[i]; });
    onFinish();
  };
  nodes.forEach(node => { node.data = ''; });
  const tick = () => {
    if (finished) return;
    for (let i = 0; i < batch && cursor < units.length; i += 1) {
      const unit = units[cursor++];
      nodes[unit.index].data += unit.text;
    }
    onProgress();
    if (cursor >= units.length) finish();
    else timer = schedule(tick, characters ? 28 : 30);
  };
  timer = schedule(tick, characters ? 260 : 90);
  return finish;
}

function textNodes(element) {
  const walker = element.ownerDocument.createTreeWalker(element, 4);
  const nodes = [];
  while (walker.nextNode()) {
    if (walker.currentNode.data.trim() && !walker.currentNode.parentElement.closest('svg, .sr-only, .support-handoff, .request-context')) nodes.push(walker.currentNode);
  }
  return nodes;
}

export function presentChat(root, { welcome = false, reducedMotion = false, followConversation = true } = {}) {
  const finishers = [];
  const tagline = welcome ? root.querySelector('.chat-welcome:not(.chat-welcome--leaving) .chat-welcome-tagline') : null;
  if (tagline) {
    tagline.setAttribute('aria-label', tagline.textContent);
    finishers.push(revealTextNodes(textNodes(tagline), { characters: true, reducedMotion }));
  }
  root.querySelectorAll('[data-reveal-response]').forEach(bubble => {
    const thread = bubble.closest('.conversation-thread');
    let follow = followConversation;
    const onScroll = () => { follow = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80; };
    thread?.addEventListener('scroll', onScroll, { passive: true });
    bubble.setAttribute('aria-busy', 'true');
    finishers.push(revealTextNodes(textNodes(bubble), {
      reducedMotion,
      onProgress() { if (follow && thread) thread.scrollTop = thread.scrollHeight; },
      onFinish() { bubble.removeAttribute('aria-busy'); bubble.removeAttribute('data-reveal-response'); thread?.removeEventListener('scroll', onScroll); },
    }));
  });
  return () => finishers.forEach(finish => finish());
}

export async function dismissThinking(root, reducedMotion = false) {
  const element = root.querySelector('.conversation-message--thinking');
  if (!element?.animate || reducedMotion) return;
  await element.animate([{ opacity: 1 }, { opacity: 0, transform: 'translateY(-4px)' }], { duration: 160, fill: 'forwards', easing: 'ease-out' }).finished.catch(() => {});
}
