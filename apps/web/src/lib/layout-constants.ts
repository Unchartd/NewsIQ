/**
 * Shared layout constants.
 *
 * Most layout values (card min-height, card padding, card width, skeleton
 * height, empty-state min-height, feed gap) are now owned exclusively by
 * globals.css (.card, .feed-list, .em-state, .sk-bar) so that the browser
 * stylesheet is the single source of truth and CSS cascade prevents mismatches.
 *
 * These values are kept for any legacy callers during migration.
 */

/** @deprecated — use the .feed-list CSS class instead */
export const ARTICLE_LIST_GAP = "12px";

/** @deprecated — card sizing is now controlled by the .card CSS class */
export const CARD_MIN_HEIGHT = "184px";
/** @deprecated — card sizing is now controlled by the .card CSS class */
export const CARD_WIDTH = "100%";
/** @deprecated — card sizing is now controlled by the .card CSS class */
export const CARD_PADDING = "20px";
/** @deprecated — skeleton sizing mirrors the .card CSS class */
export const SKELETON_CARD_HEIGHT = "184px";
/** @deprecated — use the .em-state CSS class instead */
export const EMPTY_STATE_MIN_HEIGHT = "480px";
