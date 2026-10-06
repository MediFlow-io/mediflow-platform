/**
 * Assumptions:
 * - DOMPurify runs in a browser-supported environment with DOM APIs available.
 * - Only explicitly allowlisted HTML is intended for rendering.
 * - URLs must be absolute HTTP(S) or mailto URLs; data URLs are not accepted because
 *   images are not included in the HTML allowlist.
 *
 * Only use when you MUST render HTML. Prefer plain text.
 * React auto-escapes by default - do not use dangerouslySetInnerHTML casually.
 */

import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "u",
  "ul",
  "ol",
  "li",
  "a",
  "code",
  "pre",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
];
const ALLOWED_ATTR = ["href", "rel", "target"];
const ALLOWED_URI_REGEXP = /^(?:https?:|mailto:)/i;

/**
 * Validate a URL against the application's safe navigation protocols.
 *
 * @param {*} url - Candidate URL.
 * @returns {string} The original URL when valid, otherwise "#".
 */
export function sanitizeUrl(url) {
  if (typeof url !== "string" || !url.trim()) {
    return "#";
  }

  const candidate = url.trim();
  try {
    const parsed = new URL(candidate);
    if (["http:", "https:", "mailto:"].includes(parsed.protocol.toLowerCase())) {
      return candidate;
    }
  } catch {
    return "#";
  }

  return "#";
}

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.nodeName?.toLowerCase() !== "a") {
    return;
  }

  const href = node.getAttribute("href");
  if (href) {
    node.setAttribute("href", sanitizeUrl(href));
  }
  node.setAttribute("rel", "noopener noreferrer");
  node.setAttribute("target", "_blank");
});

/**
 * Sanitize a limited subset of HTML for the rare cases where HTML rendering is required.
 * Event handlers and style attributes are excluded by the explicit allowlists.
 *
 * @param {*} dirty - Untrusted HTML string.
 * @returns {string} Sanitized HTML.
 */
export function sanitizeHtml(dirty) {
  if (typeof dirty !== "string") {
    return "";
  }

  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP,
    FORBID_ATTR: ["style"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Strip all HTML and return plain text.
 *
 * @param {*} dirty - Untrusted text or HTML string.
 * @returns {string} Plain text with all HTML removed.
 */
export function sanitizeText(dirty) {
  if (typeof dirty !== "string") {
    return "";
  }

  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
    FORBID_ATTR: ["style"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Usage example:
 *
 * import { sanitizeHtml, sanitizeText, sanitizeUrl } from "./sanitizeHtml";
 *
 * const safeMarkup = sanitizeHtml(untrustedDescription);
 * const plainLabel = sanitizeText(untrustedLabel);
 * const safeHref = sanitizeUrl(untrustedHref);
 *
 * // Only use sanitized markup with dangerouslySetInnerHTML when unavoidable.
 * <article dangerouslySetInnerHTML={{ __html: safeMarkup }} />;
 */
