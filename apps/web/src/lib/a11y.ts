import type { KeyboardEvent, SyntheticEvent } from "react";

/**
 * Make a non-button element activatable by keyboard.
 *
 * 46 `<div>`/`<span>`/`<li>` elements in this app carried `onClick` with no
 * role, tabIndex or key handler — reachable by mouse only (WCAG 2.1.1). They are
 * selection chips and toggles whose styling depends on not being a `<button>`,
 * so they keep their element and gain keyboard semantics instead.
 *
 * The single cast below exists because click handlers in this codebase vary:
 * some take a mouse event and call `stopPropagation`, some take no argument,
 * some are plain function references, and some are optional props. A keyboard
 * event is not assignable to a `MouseEventHandler`, so without this the
 * alternative is ~50 casts at the call sites. Keeping it here means one audited
 * place instead of fifty unaudited ones.
 */
export function activateOnKey(
  handler: ((event: SyntheticEvent) => void) | (() => void) | undefined,
) {
  return (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    // Space would scroll the page; Enter would submit an enclosing form.
    event.preventDefault();
    event.stopPropagation();
    (handler as ((event: SyntheticEvent) => void) | undefined)?.(event);
  };
}
