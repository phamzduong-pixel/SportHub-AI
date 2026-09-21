import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  extractDomain,
  parseCitationsFromText,
  isValidHttpUrl,
  openSafeExternalUrl,
  getInitialEmbedStatus,
  type SourceCitation,
} from './sourceCitationParser.ts';

describe('sourceCitationParser', () => {
  describe('getInitialEmbedStatus', () => {
    it('should return LOADING and embed tab for valid http/https source', () => {
      const validSource: SourceCitation = {
        id: '1',
        name: 'MLS Soccer',
        url: 'https://www.mlssoccer.com',
        domain: 'mlssoccer.com',
        isInternal: false,
      };
      const result = getInitialEmbedStatus(validSource);
      assert.deepEqual(result, {
        status: 'LOADING',
        initialTab: 'embed',
        hasValidUrl: true,
      });
    });

    it('should return INVALID_SOURCE and info tab for internal sources without URL', () => {
      const internalSource: SourceCitation = {
        id: '2',
        name: 'SportHub Knowledge',
        isInternal: true,
      };
      const result = getInitialEmbedStatus(internalSource);
      assert.deepEqual(result, {
        status: 'INVALID_SOURCE',
        initialTab: 'info',
        hasValidUrl: false,
      });
    });

    it('should return INVALID_SOURCE and info tab for dangerous or malformed URL', () => {
      const dangerousSource: SourceCitation = {
        id: '3',
        name: 'Malicious Site',
        url: 'javascript:alert(1)',
        isInternal: false,
      };
      const result = getInitialEmbedStatus(dangerousSource);
      assert.deepEqual(result, {
        status: 'INVALID_SOURCE',
        initialTab: 'info',
        hasValidUrl: false,
      });
    });

    it('should return INVALID_SOURCE for null source', () => {
      const result = getInitialEmbedStatus(null);
      assert.deepEqual(result, {
        status: 'INVALID_SOURCE',
        initialTab: 'info',
        hasValidUrl: false,
      });
    });
  });

  describe('isValidHttpUrl & openSafeExternalUrl', () => {
    it('should validate legitimate http and https URLs', () => {
      assert.equal(isValidHttpUrl('https://fifa.com'), true);
      assert.equal(isValidHttpUrl('http://tuoitre.vn/the-thao'), true);
      assert.equal(isValidHttpUrl('www.mlssoccer.com'), true);
      assert.equal(isValidHttpUrl('https://www.vff.org.vn/article/123?ref=test#section'), true);
    });

    it('should reject dangerous, empty or malformed URLs', () => {
      assert.equal(isValidHttpUrl(''), false);
      assert.equal(isValidHttpUrl(null), false);
      assert.equal(isValidHttpUrl(undefined), false);
      assert.equal(isValidHttpUrl('javascript:alert(1)'), false);
      assert.equal(isValidHttpUrl('data:text/html,<script>alert(1)</script>'), false);
      assert.equal(isValidHttpUrl('file:///etc/passwd'), false);
      assert.equal(isValidHttpUrl('vbscript:msgbox(1)'), false);
      assert.equal(isValidHttpUrl('about:blank'), false);
    });

    it('should reject openSafeExternalUrl when URL is invalid or dangerous', () => {
      assert.equal(openSafeExternalUrl(''), false);
      assert.equal(openSafeExternalUrl('javascript:alert(1)'), false);
      assert.equal(openSafeExternalUrl('data:text/html;base64,123'), false);
      assert.equal(openSafeExternalUrl(null), false);
    });
  });

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

    it('should parse MLS Soccer source and format domain and clean bodyText properly', () => {
      const text = 'Lionel Messi đang thi đấu cho CLB Inter Miami CF tại giải bóng đá Nhà nghề Mỹ (MLS).\n\n(Nguồn: MLS Soccer, https://www.mlssoccer.com, cập nhật 2026-09-17)';
      const { citations, bodyText } = parseCitationsFromText(text);

      assert.equal(citations.length, 1);
      assert.equal(citations[0].name, 'MLS Soccer');
      assert.equal(citations[0].url, 'https://www.mlssoccer.com');
      assert.equal(citations[0].domain, 'mlssoccer.com');
      assert.equal(citations[0].collectedAt, '2026-09-17');
      assert.equal(citations[0].isInternal, false);
      assert.equal(bodyText, 'Lionel Messi đang thi đấu cho CLB Inter Miami CF tại giải bóng đá Nhà nghề Mỹ (MLS).');
    });

    it('should normalize www. URLs without explicit protocol to https://', () => {
      const text = 'Thông tin giải đấu VBA.\n\n(Nguồn: VBA Official, www.vba.vn, cập nhật 2026-09-10)';
      const { citations } = parseCitationsFromText(text);

      assert.equal(citations.length, 1);
      assert.equal(citations[0].name, 'VBA Official');
      assert.equal(citations[0].url, 'https://www.vba.vn');
      assert.equal(citations[0].domain, 'vba.vn');
    });
  });
});
