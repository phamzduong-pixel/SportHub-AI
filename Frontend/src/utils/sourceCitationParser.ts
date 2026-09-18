/**
 * Structure representing a parsed source or citation from AI responses.
 */
export interface SourceCitation {
  id: string;
  name: string;
  url?: string;
  domain?: string;
  collectedAt?: string;
  snippet?: string;
  isInternal?: boolean;
}

/**
 * Extract clean domain name from a URL string (e.g. "https://www.fifa.com/worldcup" -> "fifa.com")
 */
export function extractDomain(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl.startsWith('http') ? rawUrl : `https://${rawUrl}`);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    // Fallback regex if URL constructor fails
    const match = rawUrl.match(/(?:https?:\/\/)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+)/i);
    return match ? match[1] : rawUrl;
  }
}

/**
 * Parse citations and sources from an AI message text.
 * Handles formats:
 * - (Nguồn: FIFA, https://fifa.com, cập nhật 2026-09-17)
 * - (Nguồn: VnExpress, https://vnexpress.net; Nguồn: FIFA, https://fifa.com)
 * - (Nguồn: SportHub Knowledge)
 * - Markdown links: [FIFA Official](https://fifa.com)
 * - Standalone URLs: https://...
 */
export function parseCitationsFromText(text: string | null | undefined): {
  citations: SourceCitation[];
  bodyText: string;
} {
  if (!text || typeof text !== 'string') {
    return { citations: [], bodyText: '' };
  }

  const citations: SourceCitation[] = [];
  const seenUrls = new Set<string>();
  const seenNames = new Set<string>();

  // 1. Match bracketed citation blocks: (Nguồn: ... )
  const citationBlockRegex = /\(\s*Nguồn:\s*([\s\S]*?)\)/gi;
  let match: RegExpExecArray | null;

  while ((match = citationBlockRegex.exec(text)) !== null) {
    const rawContent = match[1];
    // A block might contain multiple items separated by semicolon: "FIFA, https://...; VnExpress, https://..."
    const items = rawContent.split(/;\s*(?:Nguồn:\s*)?/i);

    for (const item of items) {
      const trimmed = item.trim();
      if (!trimmed) continue;

      // Extract parts: "FIFA, https://fifa.com, cập nhật 2026-09-17"
      // URL matching
      const urlMatch = trimmed.match(/https?:\/\/[^\s,;)]+/i);
      const url = urlMatch ? urlMatch[0] : undefined;

      // Date matching
      const dateMatch = trimmed.match(/cập nhật\s+([0-9\-/]+)/i);
      const collectedAt = dateMatch ? dateMatch[1] : undefined;

      // Extract Name (everything before the URL or first comma/date)
      let name = trimmed;
      if (url) {
        name = name.replace(url, '');
      }
      if (dateMatch) {
        name = name.replace(dateMatch[0], '');
      }
      name = name
        .replace(/^Nguồn:\s*/i, '')
        .replace(/^[,\s-]+|[,\s-]+$/g, '')
        .trim();

      if (!name && url) {
        name = extractDomain(url);
      }
      if (!name) {
        name = 'Nguồn tham khảo';
      }

      const domain = url ? extractDomain(url) : undefined;
      const isInternal = !url || domain?.includes('sporthub');
      const uniqueKey = url ? url.toLowerCase() : name.toLowerCase();

      if (!seenUrls.has(uniqueKey) && !seenNames.has(name.toLowerCase())) {
        if (url) seenUrls.add(uniqueKey);
        seenNames.add(name.toLowerCase());

        citations.push({
          id: `cit-${citations.length + 1}-${Date.now()}`,
          name,
          url,
          domain,
          collectedAt,
          isInternal,
        });
      }
    }
  }

  // 2. Also check for Markdown links [Title](https://...) if not already captured
  const mdLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi;
  while ((match = mdLinkRegex.exec(text)) !== null) {
    const linkName = match[1].trim();
    const linkUrl = match[2].trim();
    const uniqueKey = linkUrl.toLowerCase();

    if (!seenUrls.has(uniqueKey)) {
      seenUrls.add(uniqueKey);
      citations.push({
        id: `cit-${citations.length + 1}-${Date.now()}`,
        name: linkName,
        url: linkUrl,
        domain: extractDomain(linkUrl),
        isInternal: false,
      });
    }
  }

  // 3. Remove raw citation blocks from the main body display so bodyText is clean
  let bodyText = text.replace(/\(\s*Nguồn:[\s\S]*?\)/gi, '').trim();
  bodyText = bodyText.replace(/(?:\r?\n|^)\s*Nguồn:\s*[\s\S]*$/gi, '').trim();

  return {
    citations,
    bodyText: bodyText || text.trim(),
  };
}
