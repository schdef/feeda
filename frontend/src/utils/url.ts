// Tracking parameters to strip during URL normalization for deduplication
const TRACKING_PARAMS = new Set([
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'utm_id',
  'utm_reader',
  'utm_name',
  'utm_cid',
  'utm_pubreferrer',
  'fbclid',
  'gclid',
  'gclsrc',
  'dclid',
  'msclkid',
  'twclid',
  '_ga',
  '_gl',
  '_hsenc',
  '_hsmi',
  'mkt_tok',
  'oly_anon_id',
  'oly_enc_id',
  'vero_id',
  's_cid',
  'icid',
  'igshid',
  'mc_cid',
  'mc_eid',
]);

function isTrackingParam(key: string): boolean {
  const lower = key.toLowerCase();
  return lower.startsWith('utm_') || TRACKING_PARAMS.has(lower);
}

/**
 * Normalizes a URL for deterministic article deduplication.
 * - Preserves non-standard host and port (e.g. http://example.com:8080)
 * - Cleans trailing slashes from pathname
 * - Strips marketing / analytics tracking query parameters (utm_*, fbclid, etc.)
 * - Preserves and sorts meaningful query parameters (e.g. episodeId, v, id, p)
 * - Returns clean lowercased trimmed string on invalid URL
 */
export function normalizeUrl(url?: string): string {
  if (!url) return '';
  const trimmed = url.trim();
  if (!trimmed) return '';

  try {
    const u = new URL(trimmed);
    const host = u.host.toLowerCase();
    const pathname = u.pathname.toLowerCase().replace(/\/+$/, '');

    const filteredParams: [string, string][] = [];
    u.searchParams.forEach((val, key) => {
      if (!isTrackingParam(key)) {
        filteredParams.push([key, val]);
      }
    });

    filteredParams.sort(([k1, v1], [k2, v2]) => {
      if (k1 !== k2) return k1 < k2 ? -1 : 1;
      return v1 < v2 ? -1 : v1 > v2 ? 1 : 0;
    });

    const searchParams = new URLSearchParams();
    for (const [key, val] of filteredParams) {
      searchParams.append(key, val);
    }

    const query = searchParams.toString();
    const searchPart = query ? `?${query}` : '';

    return `${host}${pathname}${searchPart}`;
  } catch {
    return trimmed.toLowerCase();
  }
}
