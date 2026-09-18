import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { cleanSpeechText } from './cleanSpeechText.ts';

describe('cleanSpeechText', () => {
  it('should handle empty, null, or undefined input', () => {
    assert.equal(cleanSpeechText(''), '');
    assert.equal(cleanSpeechText(null), '');
    assert.equal(cleanSpeechText(undefined), '');
    assert.equal(cleanSpeechText('   '), '');
  });

  it('should remove source citations with URL and metadata', () => {
    const input = 'Messi sinh ngày 24/06/1987. (Nguồn: FIFA, https://fifa.com, cập nhật 2026-09-17)';
    const expected = 'Messi sinh ngày 24/06/1987.';
    assert.equal(cleanSpeechText(input), expected);
  });

  it('should remove multiple source citations and standalone Nguồn lines', () => {
    const input = 'Cristiano Ronaldo hiện đang thi đấu cho Al-Nassr.\n\nNguồn: VnExpress https://vnexpress.net';
    const output = cleanSpeechText(input);
    assert.ok(!output.includes('Nguồn:'));
    assert.ok(!output.includes('https://'));
    assert.ok(output.includes('Cristiano Ronaldo hiện đang thi đấu cho Al-Nassr'));
  });

  it('should strip markdown formatting while preserving natural text', () => {
    const input = `### Thông tin cầu thủ
**Lionel Messi** là *cầu thủ bóng đá* người Argentina.
- Vị trí: Tiền đạo
- Số áo: 10
Xem thêm tại [FIFA Profile](https://fifa.com/messi).`;

    const output = cleanSpeechText(input);
    assert.ok(!output.includes('###'));
    assert.ok(!output.includes('**'));
    assert.ok(!output.includes('*'));
    assert.ok(!output.includes('https://'));
    assert.ok(!output.includes('[FIFA Profile]'));
    assert.ok(output.includes('Lionel Messi là cầu thủ bóng đá người Argentina'));
    assert.ok(output.includes('Vị trí: Tiền đạo'));
    assert.ok(output.includes('Số áo: 10'));
    assert.ok(output.includes('Xem thêm tại FIFA Profile'));
  });

  it('should strip code blocks and disclaimers', () => {
    const input = `Kết quả tra cứu:
\`\`\`json
{"entity": "Messi"}
\`\`\`
(Lưu ý: Hiện tại SportHub AI chỉ hỗ trợ 6 môn thể thao).
Messi hiện đang chơi bóng tại Mỹ.`;

    const output = cleanSpeechText(input);
    assert.ok(!output.includes('```'));
    assert.ok(!output.includes('Lưu ý'));
    assert.ok(output.includes('Messi hiện đang chơi bóng tại Mỹ'));
  });

  it('should strip table syntax and format as sentences', () => {
    const input = `| Sân | Giá |
|---|---|
| Sân A | 300k |
| Sân B | 400k |`;

    const output = cleanSpeechText(input);
    assert.ok(!output.includes('|'));
    assert.ok(!output.includes('---'));
    assert.ok(output.includes('Sân A 300k'));
    assert.ok(output.includes('Sân B 400k'));
  });
});
