import { format, isToday, isTomorrow, isYesterday } from "date-fns";
import { ru } from "date-fns/locale";

export function formatDeadline(deadline: string | null): string {
  if (!deadline) return "Срок не определен";

  const date = new Date(deadline);
  const time = format(date, "HH:mm");

  if (isToday(date)) return `Сегодня до ${time}`;
  if (isTomorrow(date)) return `Завтра до ${time}`;
  if (isYesterday(date)) return `Вчера, ${time}`;

  return `${format(date, "d MMMM", { locale: ru })} до ${time}`;
}

export function formatShortDeadline(deadline: string | null): string {
  if (!deadline) return "Срок не определен";

  const date = new Date(deadline);
  const time = format(date, "HH:mm");

  if (isToday(date) || isTomorrow(date) || isYesterday(date)) return `до ${time}`;
  return `${format(date, "d MMMM", { locale: ru })}`;
}

export function formatDateTime(value: string): string {
  return format(new Date(value), "d MMMM, HH:mm", { locale: ru });
}

export function formatHeaderDate(date: Date): string {
  return format(date, "d MMMM, EEEE", { locale: ru });
}
