/**
 * Pure date math for the DeadlinePicker's quick options ("Сегодня",
 * "Завтра", "Через 3 дня"). Extracted from the component and unit-tested
 * because the original bug (P0-02) was exactly here: the day offset was
 * applied to whatever the picker's *current* value already was, so tapping
 * "Завтра" after "Через 3 дня" landed 4 days out instead of 1. The day
 * component must always be computed from `now`, never from the previous
 * selection — only the time-of-day is carried over, so re-tapping a quick
 * option after dialing in a custom time doesn't reset it.
 */
export function computeQuickOptionDate(
  offsetDays: number,
  now: Date,
  preserveTimeFrom: Date | null,
): Date {
  const result = new Date(now);
  result.setDate(result.getDate() + offsetDays);

  if (preserveTimeFrom) {
    result.setHours(preserveTimeFrom.getHours(), preserveTimeFrom.getMinutes(), 0, 0);
  } else {
    result.setHours(now.getHours() + 1, 0, 0, 0);
  }

  // "Сегодня" must land later today, not in the past relative to `now`.
  if (offsetDays === 0 && result <= now) {
    result.setHours(now.getHours() + 1, 0, 0, 0);
  }

  return result;
}
