/** Sprint 1 has no authentication, so the app is personalized for a single hardcoded user. */
export const CURRENT_USER_NAME = "Ернат";

export function getGreeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) return "Доброе утро";
  if (hour >= 12 && hour < 18) return "Добрый день";
  if (hour >= 18 && hour < 23) return "Добрый вечер";
  return "Доброй ночи";
}
