/**
 * Utility to clean AI markdown and metadata text into natural, speakable text
 * suitable for Web Speech API (Text-to-Speech / SpeechSynthesis).
 */
export function cleanSpeechText(rawText: string | null | undefined): string {
  if (!rawText || typeof rawText !== 'string') {
    return '';
  }

  let text = rawText;

  // 1. Remove source & citation blocks in parentheses, e.g. "(Nguồn: FIFA, https://..., cập nhật 2026-09-17)"
  text = text.replace(/\(\s*Nguồn:[\s\S]*?\)/gi, '');

  // 2. Remove standalone "Nguồn: ..." lines or trailers at the end of text
  text = text.replace(/(?:\r?\n|^)\s*Nguồn:\s*[\s\S]*$/gi, '');

  // 3. Remove disclaimer notes if any, e.g. "(Lưu ý: Hiện tại SportHub AI chưa có...)"
  text = text.replace(/\(\s*Lưu ý:[\s\S]*?\)/gi, '');

  // 4. Remove code blocks ```code``` and inline code `code`
  text = text.replace(/```[\s\S]*?```/g, '');
  text = text.replace(/`([^`]+)`/g, '$1');

  // 5. Remove images ![alt](url)
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, '');

  // 6. Convert markdown links [text](url) -> text
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');

  // 7. Remove raw standalone URLs (http://, https://, www.)
  text = text.replace(/https?:\/\/\S+/gi, '');
  text = text.replace(/www\.\S+/gi, '');

  // 8. Remove markdown headers (# Title -> Title)
  text = text.replace(/^\s*#{1,6}\s+/gm, '');

  // 9. Remove blockquote markers (> Quote -> Quote)
  text = text.replace(/^\s*>\s*/gm, '');

  // 10. Remove bold, italic, strikethrough markers (**bold**, *italic*, __bold__, _italic_, ~~strike~~)
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
  text = text.replace(/\*([^*]+)\*/g, '$1');
  text = text.replace(/__([^_]+)__/g, '$1');
  text = text.replace(/_([^_]+)_/g, '$1');
  text = text.replace(/~~([^~]+)~~/g, '$1');

  // 11. Remove table borders and separators (| Col 1 | Col 2 |)
  text = text.replace(/\|/g, ' ');
  text = text.replace(/[-:]{3,}/g, '');

  // 12. Convert bullet points / numbered lists into natural sentence breaks
  // e.g. "\n- Item 1\n- Item 2" -> ". Item 1. Item 2"
  text = text.replace(/^\s*[\*\-\+•]\s+/gm, '');
  text = text.replace(/^\s*\d+[\.\)]\s+/gm, '');

  // 13. Remove leftover empty parentheses or brackets () [] {}
  text = text.replace(/\(\s*\)/g, '');
  text = text.replace(/\[\s*\]/g, '');

  // 14. Normalize whitespace, newlines and multiple punctuation marks
  const lines = text
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  let cleaned = lines.join('. ');

  // Collapse multiple dots/spaces
  cleaned = cleaned.replace(/\s+/g, ' ');
  cleaned = cleaned.replace(/\.{2,}/g, '.');
  cleaned = cleaned.replace(/\s+([.,!?:;])/g, '$1');
  cleaned = cleaned.replace(/([.,!?:;])\1+/g, '$1');

  return cleaned.trim();
}
