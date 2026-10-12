/**
 * Assumptions:
 * - html is intended for trusted rich text, such as CMS content or formatted clinical notes.
 * - sanitizeHtml is the single sanitization boundary before HTML reaches the DOM.
 * - as is a valid React intrinsic element name supplied by the application.
 *
 * DO NOT use this for user-generated content unless absolutely necessary.
 * React escapes by default. This exists for trusted HTML (e.g., rich-text
 * from a CMS or a doctor's formatted notes).
 */

import { sanitizeHtml } from "./sanitizeHtml";

/**
 * Render allowlisted HTML after sanitizing it with DOMPurify.
 *
 * @param {{html: string, className?: string, as?: keyof JSX.IntrinsicElements}} props - Component props.
 * @returns {JSX.Element} Element containing sanitized HTML.
 *
 * @example
 * import { SafeHtml } from "./SafeHtml";
 *
 * <SafeHtml
 *   as="article"
 *   className="prose"
 *   html={doctorFormattedNotes}
 * />;
 */
export function SafeHtml({ html, className, as: Element = "div" }) {
  const sanitizedHtml = sanitizeHtml(html);

  return (
    <Element
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
    />
  );
}
