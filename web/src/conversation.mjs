// Scroll is presentation state. It never changes conversation or operational data.
export function captureConversationScroll(thread) {
  if (!thread) return null;
  return { top: thread.scrollTop, atEnd: thread.scrollHeight - thread.clientHeight - thread.scrollTop < 96 };
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
