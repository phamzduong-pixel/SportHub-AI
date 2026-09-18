import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { extractDomain, parseCitationsFromText } from './sourceCitationParser.ts';

describe('sourceCitationParser', () => {
  describe('extractDomain', () => {
    it('should extract domain correctly from various URL formats', () => {
      assert.equal(extractDomain('https://www.fifa.com/worldcup'), 'fifa.com');
      assert.equal(extractDomain('https://vnexpress.net/the-thao'), 'vnexpress.net');
      assert.equal(extractDomain('http://tuoitre.vn'), 'tuoitre.vn');
      assert.equal(extractDomain('vff.org.vn/news'), 'vff.org.vn');
    });
  });

  describe('parseCitationsFromText', () => {
    it('should handle empty or undefined input', () => {
      assert.deepEqual(parseCitationsFromText(''), { citations: [], bodyText: '' });
      assert.deepEqual(parseCitationsFromText(null), { citations: [], bodyText: '' });
    });

    it('should parse single citation with source name, URL and date', () => {
      const text = 'Lionel Messi sinh ngày 24/06/1987.\n\n(Nguồn: FIFA, https://fifa.com, cập nhật 2026-09-17)';
      const { citations } = parseCitationsFromText(text);

      assert.equal(citations.length, 1);
      assert.equal(citations[0].name, 'FIFA');
      assert.equal(citations[0].url, 'https://fifa.com');
      assert.equal(citations[0].domain, 'fifa.com');
      assert.equal(citations[0].collectedAt, '2026-09-17');
      assert.equal(citations[0].isInternal, false);
    });

    it('should parse multiple citations separated by semicolons', () => {
      const text = 'Thông tin về Ronaldo.\n\n(Nguồn: VnExpress, https://vnexpress.net/the-thao; Nguồn: FIFA, https://fifa.com/ronaldo, cập nhật 2026-09-15)';
      const { citations } = parseCitationsFromText(text);

      assert.equal(citations.length, 2);
      assert.equal(citations[0].name, 'VnExpress');
      assert.equal(citations[0].domain, 'vnexpress.net');
      assert.equal(citations[1].name, 'FIFA');
      assert.equal(citations[1].domain, 'fifa.com');
      assert.equal(citations[1].collectedAt, '2026-09-15');
    });

    it('should handle internal sources without URLs', () => {
      const text = 'Đây là quy định đặt sân SportHub.\n\n(Nguồn: SportHub Knowledge)';
      const { citations } = parseCitationsFromText(text);

      assert.equal(citations.length, 1);
      assert.equal(citations[0].name, 'SportHub Knowledge');
      assert.equal(citations[0].url, undefined);
      assert.equal(citations[0].isInternal, true);
    });

    it('should parse markdown links', () => {
      const text = 'Xem thêm chi tiết tại [Liên đoàn Thể thao](https://vff.org.vn/news).';
      const { citations } = parseCitationsFromText(text);

      assert.equal(citations.length, 1);
      assert.equal(citations[0].name, 'Liên đoàn Thể thao');
      assert.equal(citations[0].url, 'https://vff.org.vn/news');
      assert.equal(citations[0].domain, 'vff.org.vn');
    });
  });
});
