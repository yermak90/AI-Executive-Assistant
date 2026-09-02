/** Russian plural rules for "N активных обязательств(о/а/)" style counters. */
export function pluralizeActiveCommitments(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) return `${count} активное обязательство`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} активных обязательства`;
  return `${count} активных обязательств`;
}
