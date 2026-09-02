import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Feather } from "@expo/vector-icons";

import { colors, radius, spacing, typography } from "../theme";
import { Commitment } from "../types/domain";
import { formatShortDeadline } from "../utils/date";
import { ControlHealthBadge, StatusBadge } from "./Badge";

interface CommitmentListItemProps {
  commitment: Commitment;
}

export function CommitmentListItem({ commitment }: CommitmentListItemProps) {
  const router = useRouter();
  const personName = commitment.person?.name ?? "Вы";

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={() => router.push(`/commitment/${commitment.id}`)}
    >
      <View style={styles.content}>
        <Text style={styles.person}>{personName}</Text>
        <Text style={styles.title} numberOfLines={2}>
          {commitment.title}
        </Text>
        <View style={styles.meta}>
          <Text style={[styles.deadline, commitment.is_overdue && styles.overdue]}>
            {formatShortDeadline(commitment.deadline)}
          </Text>
          {commitment.project ? <Text style={styles.project}>· {commitment.project.name}</Text> : null}
        </View>
      </View>
      <View style={styles.trailing}>
        <StatusBadge status={commitment.status} isOverdue={commitment.is_overdue} />
        <ControlHealthBadge health={commitment.control_health} />
        <Feather name="chevron-right" size={20} color={colors.textMuted} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  pressed: {
    opacity: 0.8,
  },
  content: {
    flex: 1,
    marginRight: spacing.sm,
  },
  person: {
    ...typography.caption,
    marginBottom: 2,
  },
  title: {
    ...typography.title,
    marginBottom: spacing.xs,
  },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
  },
  deadline: {
    ...typography.caption,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  overdue: {
    color: colors.danger,
  },
  project: {
    ...typography.caption,
    marginLeft: spacing.xs,
  },
  trailing: {
    alignItems: "flex-end",
    gap: spacing.sm,
  },
});
