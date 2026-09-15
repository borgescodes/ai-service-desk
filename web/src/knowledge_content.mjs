import { escapeHtml } from './render.mjs';

export const APPROVED_PROCEDURE_URL = 'https://mysignins.microsoft.com/security-info/password/change';

export function renderMessageBody(text) {
  return String(text ?? '').split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
    .map(p => `<p>${escapeHtml(p)}</p>`).join('');
}

export function renderApprovedKnowledgeBody({ text, procedureUrl = null, knowledgeId = null }) {
  const approvedUrl = procedureUrl === APPROVED_PROCEDURE_URL ? APPROVED_PROCEDURE_URL
    : knowledgeId === 'KB-SYN-FAQ-CDM-REQUEST-001' && procedureUrl === 'https://cdm.juparana.com.br/'
      ? 'https://cdm.juparana.com.br/' : null;
  const output = [], paragraph = [], steps = [];
  let linked = false;
  const flushParagraph = () => { if (paragraph.length) output.push(renderMessageBody(paragraph.splice(0).join('\n'))); };
  const flushSteps = () => {
    if (!steps.length) return;
    const start = steps[0].number;
    output.push(`<div class="approved-procedure"><ol class="procedure-steps"${start === 1 ? '' : ` start="${start}"`}>${steps.splice(0).map((step, index) => {
      let content = escapeHtml(step.text);
      if (!linked && approvedUrl) {
        content = `<a href="${approvedUrl}" target="_blank" rel="noopener noreferrer">${content}</a>`;
        linked = true;
      }
      return `<li${step.number === start + index ? '' : ` value="${step.number}"`}>${content}</li>`;
    }).join('')}</ol></div>`);
  };
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const match = line.match(/^\s*(\d+)\.\s+(.+?)\s*$/);
    if (match) { flushParagraph(); steps.push({ number: Number(match[1]), text: match[2] }); }
    else if (line.trim()) { flushSteps(); paragraph.push(line); }
    else { flushParagraph(); }
  }
  flushParagraph(); flushSteps();
  return output.join('');
}
