import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { parseAssistantMarkdown } from './assistantMarkdown.ts';

describe('parseAssistantMarkdown', () => {
  it('parses bold years and preserves the surrounding Vietnamese text', () => {
    const blocks = parseAssistantMarkdown('**2022**: Argentina vô địch, Pháp á quân.');
    assert.equal(blocks[0].type, 'paragraph');
    if (blocks[0].type !== 'paragraph') return;
    assert.deepEqual(blocks[0].children.slice(0, 2), [
      { type: 'strong', children: [{ type: 'text', value: '2022' }] },
      { type: 'text', value: ': Argentina vô địch, Pháp á quân.' },
    ]);
  });

  it('parses emoji list items and bold titles without changing their descriptions', () => {
    const blocks = parseAssistantMarkdown(
      '- 🏟️ **Tìm và gợi ý sân**: Tìm sân bóng đá, cầu lông, pickleball...\n' +
      '- ⏱️ **Kiểm tra lịch trống & đặt sân**: Tra cứu khung giờ còn trống...',
    );
    assert.equal(blocks.length, 1);
    assert.equal(blocks[0].type, 'list');
    if (blocks[0].type !== 'list') return;
    assert.equal(blocks[0].ordered, false);
    assert.equal(blocks[0].items.length, 2);
    assert.deepEqual(blocks[0].items[0].slice(0, 3), [
      { type: 'text', value: '🏟️ ' },
      { type: 'strong', children: [{ type: 'text', value: 'Tìm và gợi ý sân' }] },
      { type: 'text', value: ': Tìm sân bóng đá, cầu lông, pickleball...' },
    ]);
  });

  it('keeps paragraph breaks and renders single line breaks distinctly', () => {
    const blocks = parseAssistantMarkdown('Đoạn một\ndòng tiếp theo.\n\nĐoạn hai.');
    assert.equal(blocks.length, 2);
    assert.equal(blocks[0].type, 'paragraph');
    if (blocks[0].type !== 'paragraph') return;
    assert.deepEqual(blocks[0].children, [
      { type: 'text', value: 'Đoạn một' },
      { type: 'break' },
      { type: 'text', value: 'dòng tiếp theo.' },
    ]);
  });

  it('supports headings and ordered lists', () => {
    const blocks = parseAssistantMarkdown('## Hướng dẫn\n\n1. Bước một\n2) Bước hai');
    assert.deepEqual(blocks.map((block) => block.type), ['heading', 'list']);
    assert.equal(blocks[0].type === 'heading' ? blocks[0].level : 0, 2);
    assert.equal(blocks[1].type === 'list' ? blocks[1].ordered : false, true);
  });

  it('does not show unfinished bold markers while streaming and preserves malformed final text', () => {
    assert.deepEqual(parseAssistantMarkdown('**2022', { streaming: true })[0], {
      type: 'paragraph',
      children: [{ type: 'text', value: '2022' }],
    });
    assert.deepEqual(parseAssistantMarkdown('5 * 4 and **literal')[0], {
      type: 'paragraph',
      children: [{ type: 'text', value: '5 * 4 and **literal' }],
    });
  });

  it('keeps untrusted HTML as text and accepts only safe Markdown links', () => {
    const blocks = parseAssistantMarkdown('<img src=x onerror=alert(1)> [FIFA](https://www.fifa.com) [bad](javascript:alert(1))');
    assert.equal(blocks[0].type, 'paragraph');
    if (blocks[0].type !== 'paragraph') return;
    assert.deepEqual(blocks[0].children, [
      { type: 'text', value: '<img src=x onerror=alert(1)> ' },
      { type: 'link', href: 'https://www.fifa.com', children: [{ type: 'text', value: 'FIFA' }] },
      { type: 'text', value: ' [bad](javascript:alert(1))' },
    ]);
  });
});
