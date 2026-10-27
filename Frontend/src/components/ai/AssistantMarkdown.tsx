import type { ReactNode } from 'react';
import { isValidHttpUrl } from '@/utils/sourceCitationParser';
import { parseAssistantMarkdown, type AssistantInlineNode, type AssistantMarkdownBlock } from '@/utils/assistantMarkdown';

type HeadingTag = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

function renderInline(nodes: AssistantInlineNode[], keyPrefix: string): ReactNode[] {
  return nodes.map((node, index) => {
    const key = `${keyPrefix}-${index}`;
    if (node.type === 'text') return node.value;
    if (node.type === 'break') return <br key={key} />;
    if (node.type === 'strong') {
      return <strong key={key} className="font-semibold text-slate-900">{renderInline(node.children, key)}</strong>;
    }

    if (!isValidHttpUrl(node.href)) return renderInline(node.children, key);
    return (
      <a key={key} href={node.href} target="_blank" rel="noopener noreferrer" className="text-brand-700 underline underline-offset-2">
        {renderInline(node.children, key)}
      </a>
    );
  });
}

function renderBlock(block: AssistantMarkdownBlock, index: number): ReactNode {
  const key = `assistant-markdown-${index}`;
  if (block.type === 'paragraph') {
    return <p key={key} className="leading-6">{renderInline(block.children, key)}</p>;
  }

  if (block.type === 'heading') {
    const Heading = `h${block.level}` as HeadingTag;
    return <Heading key={key} className="font-bold leading-6 text-slate-900">{renderInline(block.children, key)}</Heading>;
  }

  const List = block.ordered ? 'ol' : 'ul';
  return (
    <List key={key} className={`space-y-1.5 pl-5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>
      {block.items.map((item, itemIndex) => (
        <li key={`${key}-item-${itemIndex}`} className="ps-0.5 leading-6">
          {renderInline(item, `${key}-item-${itemIndex}`)}
        </li>
      ))}
    </List>
  );
}

export function AssistantMarkdown({
  content,
  streaming = false,
}: {
  content: string;
  streaming?: boolean;
}) {
  const blocks = parseAssistantMarkdown(content, { streaming });
  return <div className="space-y-3">{blocks.map(renderBlock)}</div>;
}
