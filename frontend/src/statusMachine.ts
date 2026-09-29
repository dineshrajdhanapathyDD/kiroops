/**
 * Client-side mirror of the backend status state machine (design.md "Status
 * State Machine"). Used by the detail page to only offer valid next states.
 *
 * This is a UI convenience only; the backend remains the sole authority and
 * still rejects invalid transitions with 409. Keeping the allow-list here in
 * one place mirrors the backend's single `is_valid_transition` function.
 */

import type { IncidentStatus } from "./types";

const NEXT_STATES: Record<IncidentStatus, IncidentStatus[]> = {
  OPEN: ["INVESTIGATING"],
  INVESTIGATING: ["RESOLVED"],
  RESOLVED: [],
};

/** Return the valid forward transitions from `current` (may be empty). */
export function nextStates(current: IncidentStatus): IncidentStatus[] {
  return NEXT_STATES[current];
}

/** Whether `target` is a valid forward transition from `current`. */
export function isValidTransition(
  current: IncidentStatus,
  target: IncidentStatus,
): boolean {
  return NEXT_STATES[current].includes(target);
}
