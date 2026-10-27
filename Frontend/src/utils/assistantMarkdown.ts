import { isValidHttpUrl } from './sourceCitationParser.ts';

export type AssistantInlineNode =
  | { type: 'text'; value: string }
  | { type: 'strong'; children: AssistantInlineNode[] }
  | { type: 'link'; href: string; children: AssistantInlineNode[] }
  | { type: 'break' };

export type AssistantMarkdownBlock =
  | { type: 'paragraph'; children: AssistantInlineNode[] }
  | { type: 'heading'; level: 1 | 2 | 3 | 4 | 5 | 6; children: AssistantInlineNode[] }
  | { type: 'list'; ordered: boolean; items: AssistantInlineNode[][] };

export interface AssistantMarkdownOptions {
  /** Hide unfinished bold delimiters while a partial response is being received. */
  streaming?: boolean;
}

function parseInline(source: string, streaming: boolean): AssistantInlineNode[] {
  const nodes: AssistantInlineNode[] = [];
  let text = '';
  let index = 0;

  const flushText = () => {
    if (text) nodes.push({ type: 'text', value: text });
    text = '';
  };

  while (index < source.length) {
    if (source[index] === '\n') {
      flushText();
      nodes.push({ type: 'break' });
      index += 1;
      continue;
    }

    const linkMatch = source.slice(index).match(/^\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/i);
    if (linkMatch && isValidHttpUrl(linkMatch[2])) {
      flushText();
      nodes.push({
        type: 'link',
        href: linkMatch[2],
        children: parseInline(linkMatch[1], false),
      });
      index += linkMatch[0].length;
      continue;
    }

    const marker = source.startsWith('**', index)
      ? '**'
      : source.startsWith('__', index)
        ? '__'
        : undefined;
    if (marker) {
      const closingIndex = source.indexOf(marker, index + marker.length);
      if (closingIndex > index + marker.length) {
        flushText();
        nodes.push({
          type: 'strong',
          children: parseInline(source.slice(index + marker.length, closingIndex), false),
        });
        index = closingIndex + marker.length;
        continue;
      }

      // A chunk can end between the opening and closing marker. Hide only that
      // unfinished syntax while streaming; final malformed text remains literal.
      if (!streaming) text += marker;
      index += marker.length;
      continue;
    }

    text += source[index];
    index += 1;
  }

  flushText();
  return nodes;
}

type ListLine = { ordered: boolean; text: string };

function getListLine(line: string): ListLine | undefined {
  const unordered = line.match(/^\s{0,3}[-+*]\s+(.*)$/);
  if (unordered) return { ordered: false, text: unordered[1] };

  const ordered = line.match(/^\s{0,3}\d+[.)]\s+(.*)$/);
  if (ordered) return { ordered: true, text: ordered[1] };

  return undefined;
}

function getHeadingLine(line: string): { level: number; text: string } | undefined {
  const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
  if (!heading) return undefined;
  return { level: heading[1].length, text: heading[2] };
}

function isBlockStart(line: string): boolean {
  return Boolean(getListLine(line) || getHeadingLine(line));
}

/** Parse the small Markdown subset used in assistant replies without creating HTML. */
export function parseAssistantMarkdown(
  source: string | null | undefined,
  options: AssistantMarkdownOptions = {},
): AssistantMarkdownBlock[] {
  if (typeof source !== 'string' || source.length === 0) return [];

  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  const blocks: AssistantMarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    if (!lines[index].trim()) {
      index += 1;
      continue;
    }

    const heading = getHeadingLine(lines[index]);
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading.level as 1 | 2 | 3 | 4 | 5 | 6,
        children: parseInline(heading.text, Boolean(options.streaming)),
      });
      index += 1;
      continue;
    }

    const firstListLine = getListLine(lines[index]);
    if (firstListLine) {
      const items: AssistantInlineNode[][] = [];
      const ordered = firstListLine.ordered;

      while (index < lines.length) {
        const current = getListLine(lines[index]);
        if (current?.ordered === ordered) {
          items.push(parseInline(current.text, Boolean(options.streaming)));
          index += 1;
          continue;
        }

        if (!lines[index].trim()) {
          let next = index;
          while (next < lines.length && !lines[next].trim()) next += 1;
          const nextList = next < lines.length ? getListLine(lines[next]) : undefined;
          if (nextList?.ordered === ordered) {
            index = next;
            continue;
          }
        }
        break;
      }

      blocks.push({ type: 'list', ordered, items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push({
      type: 'paragraph',
      children: parseInline(paragraphLines.join('\n'), Boolean(options.streaming)),
    });
  }

  return blocks;
}
