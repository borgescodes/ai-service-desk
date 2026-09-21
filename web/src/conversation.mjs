// Scroll is presentation state. It never changes conversation or operational data.
export function captureConversationScroll(thread) {
  if (!thread) return null;
  return { top: thread.scrollTop, atEnd: thread.scrollHeight - thread.clientHeight - thread.scrollTop < 96 };
}

export function createProgressiveScrollFollower(thread, following = true) {
  let follow = Boolean(thread && following);
  let lastScrollTop = thread?.scrollTop ?? 0;
  let automaticScrollTop = null;
  const isAtEnd = () => thread.scrollHeight - thread.clientHeight - thread.scrollTop < 96;
  const onScroll = () => {
    const current = thread.scrollTop;
    if (automaticScrollTop !== null && Math.abs(current - automaticScrollTop) <= 1) {
      automaticScrollTop = null;
      lastScrollTop = current;
      return;
    }
    follow = current >= lastScrollTop ? isAtEnd() : false;
    automaticScrollTop = null;
    lastScrollTop = current;
  };
  const onWheel = event => { if (event.deltaY < 0) follow = false; };
  thread?.addEventListener?.('scroll', onScroll, { passive: true });
  thread?.addEventListener?.('wheel', onWheel, { passive: true });
  return {
    update() {
      if (!follow || !thread) return;
      thread.scrollTop = thread.scrollHeight;
      automaticScrollTop = thread.scrollTop;
      lastScrollTop = thread.scrollTop;
    },
    stop() {
      thread?.removeEventListener?.('scroll', onScroll);
      thread?.removeEventListener?.('wheel', onWheel);
    },
  };
}

export function restoreConversationScroll(thread, button, previous, reducedMotion = false) {
  if (!thread || !button) return;
  thread.scrollTop = !previous || previous.atEnd ? thread.scrollHeight : previous.top;
  const update = () => { button.hidden = captureConversationScroll(thread).atEnd; };
  thread.addEventListener('scroll', update, { passive: true });
  thread.addEventListener('toggle', update, true);
  button.addEventListener('click', () => {
    thread.scrollTo({ top: thread.scrollHeight, behavior: reducedMotion ? 'auto' : 'smooth' });
  });
  update();
}
