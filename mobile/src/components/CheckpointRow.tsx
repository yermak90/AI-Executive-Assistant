import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";
import { Checkpoint } from "../types/domain";
import { formatDateTime } from "../utils/date";

interface CheckpointRowProps {
  checkpoint: Checkpoint;
  onPress?: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  PENDING: "Ожидает",
  COMPLETED: "Оценено",
  SKIPPED: "Пропущено",
};

const ASSESSMENT_LABEL: Record<string, string> = {
  ON_TRACK: "Всё по плану",
  AT_RISK: "Есть риск",
  BLOCKED: "Заблокировано",
  UNKNOWN: "",
};

const ASSESSMENT_COLOR: Record<string, string> = {
  ON_TRACK: colors.success,
  AT_RISK: colors.warning,
  BLOCKED: colors.danger,
  UNKNOWN: colors.textMuted,
};

export function CheckpointRow({ checkpoint, onPress }: CheckpointRowProps) {
  const isPending = checkpoint.status === "PENDING";
  const markerColor = isPending
    ? colors.primary
    : checkpoint.status === "SKIPPED"
      ? colors.textMuted
      : ASSESSMENT_COLOR[checkpoint.assessment];

  return (
    <Pressable style={styles.row} onPress={onPress} disabled={!isPending}>
      <View style={[styles.marker, { backgroundColor: markerColor }]} />
      <View style={styles.content}>
        <Text style={styles.title}>{checkpoint.title}</Text>
        <Text style={styles.date}>{formatDateTime(checkpoint.scheduled_at)}</Text>
        <Text style={[styles.status, { color: markerColor }]}>
          {checkpoint.status === "COMPLETED"
            ? ASSESSMENT_LABEL[checkpoint.assessment]
            : STATUS_LABEL[checkpoint.status]}
          {checkpoint.source_type === "MANUAL" ? " · вручную" : ""}
        </Text>
        {checkpoint.assessment_note ? <Text style={styles.note}>{checkpoint.assessment_note}</Text> : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  marker: {
    width: 10,
    height: 10,
    borderRadius: radius.pill,
    marginTop: 6,
    marginRight: spacing.sm,
  },
  content: {
    flex: 1,
  },
  title: {
    ...typography.body,
    fontWeight: "600",
  },
  date: {
    ...typography.small,
    marginTop: 2,
  },
  status: {
    ...typography.caption,
    fontWeight: "600",
    marginTop: 2,
  },
  note: {
    ...typography.caption,
    marginTop: 2,
    fontStyle: "italic",
  },
});
