import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme";
import { CommitmentStatus, ControlHealth, Direction } from "../types/domain";

interface StatusBadgeProps {
  status: CommitmentStatus;
  isOverdue: boolean;
}

export function StatusBadge({ status, isOverdue }: StatusBadgeProps) {
  if (status === "COMPLETED") return <Badge label="Выполнено" color={colors.success} />;
  if (status === "CANCELLED") return <Badge label="Отменено" color={colors.textMuted} />;
  if (isOverdue) return <Badge label="Просрочено" color={colors.danger} />;
  return <Badge label="Активно" color={colors.primary} />;
}

export function ControlHealthBadge({ health }: { health: ControlHealth }) {
  if (health === "BLOCKED") return <Badge label="Заблокировано" color={colors.danger} />;
  if (health === "AT_RISK") return <Badge label="Есть риск" color={colors.warning} />;
  if (health === "CHECK_DUE") return <Badge label="Нужна проверка" color={colors.primary} />;
  return null;
}

export function DirectionBadge({ direction }: { direction: Direction }) {
  if (direction === "OWED_TO_ME") return <Badge label="Мне должны" color={colors.success} />;
  if (direction === "I_OWE") return <Badge label="Я должен" color={colors.warning} />;
  return <Badge label="Команда" color={colors.primary} />;
}

export function Badge({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: `${color}26`, borderColor: `${color}55` }]}>
      <Text style={[styles.label, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignSelf: "flex-start",
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
  },
});
