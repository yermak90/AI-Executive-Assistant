import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";

interface DeadlinePickerProps {
  label: string;
  value: string | null;
  onChange: (isoValue: string | null) => void;
}

const DAY_OPTIONS = [
  { label: "Сегодня", offset: 0 },
  { label: "Завтра", offset: 1 },
  { label: "Через 3 дня", offset: 3 },
];

function toDateParts(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

export function DeadlinePicker({ label, value, onChange }: DeadlinePickerProps) {
  const initial = toDateParts(value);
  const [hasDeadline, setHasDeadline] = useState(!!initial);
  const [dayOffset, setDayOffset] = useState<number | null>(0);
  const [hours, setHours] = useState(initial ? String(initial.getHours()).padStart(2, "0") : "12");
  const [minutes, setMinutes] = useState(initial ? String(initial.getMinutes()).padStart(2, "0") : "00");

  const emit = (nextHasDeadline: boolean, nextOffset: number | null, nextHours: string, nextMinutes: string) => {
    if (!nextHasDeadline || nextOffset === null) {
      onChange(null);
      return;
    }
    const hourNum = Math.min(23, Math.max(0, Number(nextHours) || 0));
    const minuteNum = Math.min(59, Math.max(0, Number(nextMinutes) || 0));
    const date = new Date();
    date.setDate(date.getDate() + nextOffset);
    date.setHours(hourNum, minuteNum, 0, 0);
    onChange(date.toISOString());
  };

  const summary = useMemo(() => {
    if (!hasDeadline || dayOffset === null) return "Срок не определен";
    const chip = DAY_OPTIONS.find((o) => o.offset === dayOffset);
    return `${chip?.label ?? "Выбрано"} в ${hours}:${minutes}`;
  }, [hasDeadline, dayOffset, hours, minutes]);

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>

      <View style={styles.chips}>
        <Pressable
          style={[styles.chip, !hasDeadline && styles.chipActive]}
          onPress={() => {
            setHasDeadline(false);
            emit(false, dayOffset, hours, minutes);
          }}
        >
          <Text style={[styles.chipLabel, !hasDeadline && styles.chipLabelActive]}>Без срока</Text>
        </Pressable>
        {DAY_OPTIONS.map((option) => (
          <Pressable
            key={option.label}
            style={[styles.chip, hasDeadline && dayOffset === option.offset && styles.chipActive]}
            onPress={() => {
              setHasDeadline(true);
              setDayOffset(option.offset);
              emit(true, option.offset, hours, minutes);
            }}
          >
            <Text style={[styles.chipLabel, hasDeadline && dayOffset === option.offset && styles.chipLabelActive]}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {hasDeadline ? (
        <View style={styles.timeRow}>
          <TextInput
            style={styles.timeInput}
            keyboardType="number-pad"
            maxLength={2}
            value={hours}
            onChangeText={(text) => {
              setHours(text);
              emit(true, dayOffset, text, minutes);
            }}
          />
          <Text style={styles.colon}>:</Text>
          <TextInput
            style={styles.timeInput}
            keyboardType="number-pad"
            maxLength={2}
            value={minutes}
            onChangeText={(text) => {
              setMinutes(text);
              emit(true, dayOffset, hours, text);
            }}
          />
        </View>
      ) : null}

      <Text style={styles.summary}>{summary}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.lg,
  },
  label: {
    ...typography.caption,
    marginBottom: spacing.xs,
    fontWeight: "600",
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipLabel: {
    ...typography.caption,
    fontWeight: "600",
  },
  chipLabelActive: {
    color: "#fff",
  },
  timeRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  timeInput: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    width: 56,
    textAlign: "center",
    paddingVertical: spacing.sm,
    fontSize: 16,
  },
  colon: {
    ...typography.title,
    marginHorizontal: spacing.xs,
  },
  summary: {
    ...typography.caption,
  },
});
