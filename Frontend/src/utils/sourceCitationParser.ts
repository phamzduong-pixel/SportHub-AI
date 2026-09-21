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

export type EmbedStatus = 'LOADING' | 'EMBED_SUCCESS' | 'EMBED_BLOCKED' | 'EMBED_TIMEOUT' | 'INVALID_SOURCE';

/**
 * Determines the initial embed state and tab for a given source citation.
 */
export function getInitialEmbedStatus(source: SourceCitation | null): {
  status: EmbedStatus;
  initialTab: 'embed' | 'info';
  hasValidUrl: boolean;
} {
  if (!source) {
    return { status: 'INVALID_SOURCE', initialTab: 'info', hasValidUrl: false };
  }
  if (source.isInternal || !source.url) {
    return { status: 'INVALID_SOURCE', initialTab: 'info', hasValidUrl: false };
  }
  if (!isValidHttpUrl(source.url)) {
    return { status: 'INVALID_SOURCE', initialTab: 'info', hasValidUrl: false };
  }
  return { status: 'LOADING', initialTab: 'embed', hasValidUrl: true };
}

/**
 * Validates whether a given string is a valid http(s) URL.
 * Strictly disallows dangerous protocols (e.g. javascript:, data:, file:).
 */
export function isValidHttpUrl(rawUrl?: string | null): boolean {
  if (!rawUrl || typeof rawUrl !== 'string') return false;
  const trimmed = rawUrl.trim();
  if (!trimmed) return false;
  // Disallow javascript:, data:, vbscript: or other dangerous pseudo-protocols before parsing
  if (/^(?:javascript|data|vbscript|file|about):/i.test(trimmed)) {
    return false;
  }
  try {
    const parsed = new URL(
      trimmed.startsWith('http://') || trimmed.startsWith('https://') ? trimmed : `https://${trimmed}`
    );
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Safely opens an external URL in a new browser tab with strict security flags.
 * Returns true if opened successfully, false otherwise.
 */
export function openSafeExternalUrl(rawUrl?: string | null): boolean {
  if (!rawUrl || !isValidHttpUrl(rawUrl)) return false;
  const trimmed = rawUrl.trim();
  const safeUrl = trimmed.startsWith('http://') || trimmed.startsWith('https://') ? trimmed : `https://${trimmed}`;
  if (typeof window === 'undefined') return false;
  try {
    const newWindow = window.open(safeUrl, '_blank', 'noopener,noreferrer');
    if (newWindow) {
      newWindow.opener = null;
    }
    return true;
  } catch {
    return false;
  }
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

      // URL matching (supports https://, http://, www.)
      const urlMatch = trimmed.match(/(?:https?:\/\/|www\.)[^\s,;)]+/i);
      let url = urlMatch ? urlMatch[0] : undefined;
      if (url && url.toLowerCase().startsWith('www.')) {
        url = `https://${url}`;
      }

      // Date matching
      const dateMatch = trimmed.match(/cập nhật\s+([0-9\-/]+)/i);
      const collectedAt = dateMatch ? dateMatch[1] : undefined;

      // Extract Name (everything before the URL or first comma/date)
      let name = trimmed;
      if (urlMatch) {
        name = name.replace(urlMatch[0], '');
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
