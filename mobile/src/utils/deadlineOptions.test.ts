import { computeQuickOptionDate } from "./deadlineOptions";

describe("computeQuickOptionDate", () => {
  const now = new Date(2026, 8, 2, 10, 0, 0); // 2 Sep 2026, 10:00 local

  it("computes 'Сегодня' relative to now, not a stale value", () => {
    // Regression for P0-02: previously the offset was applied to whatever
    // the picker's existing value was, so repeated taps compounded.
    const staleValue = new Date(2026, 8, 20, 9, 0, 0); // 20 Sep, far in the future
    const result = computeQuickOptionDate(0, now, staleValue);
    expect(result.getFullYear()).toBe(2026);
    expect(result.getMonth()).toBe(8);
    expect(result.getDate()).toBe(2); // must be "today" (2 Sep), not 20 Sep + 0
  });

  it("'Завтра' after 'Через 3 дня' lands on tomorrow, not +4 days", () => {
    // Simulates: user taps "+3 days" first (producing 5 Sep), then "Завтра".
    const afterPlusThree = computeQuickOptionDate(3, now, null);
    expect(afterPlusThree.getDate()).toBe(5);

    const afterTomorrow = computeQuickOptionDate(1, now, afterPlusThree);
    expect(afterTomorrow.getDate()).toBe(3); // 3 Sep, i.e. tomorrow from `now` — not 6 Sep
  });

  it("+3 days computes from now", () => {
    const result = computeQuickOptionDate(3, now, null);
    expect(result.getDate()).toBe(5);
    expect(result.getMonth()).toBe(8);
  });

  it("preserves the previously chosen time of day", () => {
    const previousSelection = new Date(2026, 8, 1, 18, 30, 0);
    const result = computeQuickOptionDate(1, now, previousSelection);
    expect(result.getHours()).toBe(18);
    expect(result.getMinutes()).toBe(30);
  });

  it("defaults to one hour from now when there is no previous time", () => {
    const result = computeQuickOptionDate(0, now, null);
    expect(result.getHours()).toBe(11);
    expect(result.getMinutes()).toBe(0);
  });

  it("'Сегодня' never lands in the past relative to now", () => {
    const earlierTimeToday = new Date(2026, 8, 2, 8, 0, 0); // 08:00, before `now` (10:00)
    const result = computeQuickOptionDate(0, now, earlierTimeToday);
    expect(result.getTime()).toBeGreaterThan(now.getTime());
  });
});
