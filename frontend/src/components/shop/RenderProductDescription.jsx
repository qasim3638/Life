import React from 'react';

/**
 * Tiny, safe renderer for product descriptions that may contain markdown
 * links (`[text](/path)`) produced by the bulk AI description generator.
 *
 * Why not a general markdown lib?
 *   - The AI prompt only ever emits plain prose + 0-1 markdown link.
 *   - A 300-byte helper is safer (no library-wide XSS surface) and avoids
 *     adding react-markdown (~45 KB) just for this one thing.
 *
 * Security rules:
 *   1. All text is escaped via React's default textContent (we pass plain
 *      strings, not `dangerouslySetInnerHTML`).
 *   2. `href` is only rendered when it starts with `/` (internal) or
 *      `https://` — javascript:, mailto:, tel:, etc are dropped.
 *   3. No HTML is ever parsed — we use a single regex to split the string.
 */
const LINK_RE = /\[([^\]]+)\]\(([^)\s]+)\)/g;

function _isSafeHref(href) {
  if (!href) return false;
  if (href.startsWith('/')) return true;
  if (href.startsWith('https://')) return true;
  return false;
}

export function RenderProductDescription({ text, className, linkClassName }) {
  if (!text) return null;

  const nodes = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  LINK_RE.lastIndex = 0;
  while ((match = LINK_RE.exec(text)) !== null) {
    const [full, label, href] = match;
    if (match.index > lastIndex) {
      nodes.push(
        <React.Fragment key={`t-${key++}`}>{text.slice(lastIndex, match.index)}</React.Fragment>
      );
    }
    if (_isSafeHref(href)) {
      const isExternal = href.startsWith('https://');
      nodes.push(
        <a
          key={`a-${key++}`}
          href={href}
          className={linkClassName || 'underline text-amber-700 hover:text-amber-900'}
          {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
        >
          {label}
        </a>
      );
    } else {
      // Unsafe href → render the label as plain text, drop the link
      nodes.push(<React.Fragment key={`t-${key++}`}>{label}</React.Fragment>);
    }
    lastIndex = match.index + full.length;
  }
  if (lastIndex < text.length) {
    nodes.push(
      <React.Fragment key={`t-${key++}`}>{text.slice(lastIndex)}</React.Fragment>
    );
  }

  return <p className={className}>{nodes}</p>;
}

export default RenderProductDescription;
