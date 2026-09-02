import DateTimePicker, { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useEffect, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";
import { formatDateTime } from "../utils/date";

interface DeadlinePickerProps {
  label: string;
  value: string | null;
  onChange: (isoValue: string | null) => void;
}

const QUICK_OPTIONS = [
  { label: "Сегодня", offset: 0 },
  { label: "Завтра", offset: 1 },
  { label: "Через 3 дня", offset: 3 },
];

function parseValue(value: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * FR-008: a controlled date/time picker. `value` can change asynchronously
 * (e.g. once a commitment finishes loading for the reschedule/edit flow) —
 * internal state is re-derived from `value` on every change via the effect
 * below, rather than only read once at mount, which was the bug that made
 * edit/reschedule show "no deadline" for an existing deadline.
 */
export function DeadlinePicker({ label, value, onChange }: DeadlinePickerProps) {
  const [hasDeadline, setHasDeadline] = useState(() => parseValue(value) !== null);
  const [date, setDate] = useState<Date>(() => parseValue(value) ?? new Date());
  const [activePicker, setActivePicker] = useState<"date" | "time" | "datetime" | null>(null);

  useEffect(() => {
    const parsed = parseValue(value);
    setHasDeadline(parsed !== null);
    if (parsed !== null) setDate(parsed);
  }, [value]);

  const applyDate = (next: Date) => {
    setDate(next);
    onChange(next.toISOString());
  };

  const handleNoDeadline = () => {
    setHasDeadline(false);
    onChange(null);
  };

  const handleQuickOption = (offsetDays: number) => {
    const base = hasDeadline ? date : new Date();
    const next = new Date(base);
    next.setDate(next.getDate() + offsetDays);
    if (offsetDays === 0 && next < new Date()) {
      // "Today" from a fresh pick should still land later today, not in the past.
      next.setHours(new Date().getHours() + 1, 0, 0, 0);
    }
    setHasDeadline(true);
    applyDate(next);
  };

  const openPicker = () => {
    setHasDeadline(true);
    setActivePicker(Platform.OS === "ios" ? "datetime" : "date");
  };

  const handlePickerChange = (event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS === "android") {
      const wasDateStep = activePicker === "date";
      setActivePicker(null);
      if (event.type === "dismissed" || !selected) return;
      if (wasDateStep) {
        // Android shows date and time as two separate native dialogs.
        setDate(selected);
        setActivePicker("time");
        return;
      }
      applyDate(selected);
      return;
    }

    if (event.type === "dismissed" || !selected) {
      setActivePicker(null);
      return;
    }
    applyDate(selected);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>

      <View style={styles.chips}>
        <Chip label="Без срока" active={!hasDeadline} onPress={handleNoDeadline} />
        {QUICK_OPTIONS.map((option) => (
          <Chip key={option.label} label={option.label} active={false} onPress={() => handleQuickOption(option.offset)} />
        ))}
      </View>

      <Pressable style={styles.customButton} onPress={openPicker}>
        <Text style={styles.customButtonLabel}>
          {hasDeadline ? formatDateTime(date.toISOString()) : "Выбрать дату и время"}
        </Text>
      </Pressable>

      {activePicker !== null ? (
        <DateTimePicker
          value={date}
          mode={activePicker === "time" ? "time" : activePicker === "date" ? "date" : "datetime"}
          is24Hour
          onChange={handlePickerChange}
        />
      ) : null}
    </View>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipLabel, active && styles.chipLabelActive]}>{label}</Text>
    </Pressable>
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
  customButton: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  customButtonLabel: {
    ...typography.body,
  },
});
