import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";

interface SummaryCardProps {
  label: string;
  count: number;
  color: string;
  onPress?: () => void;
}

export function SummaryCard({ label, count, color, onPress }: SummaryCardProps) {
  return (
    <Pressable style={styles.card} onPress={onPress} disabled={!onPress}>
      <Text style={[styles.count, { color }]}>{count}</Text>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexBasis: "48%",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  count: {
    fontSize: 30,
    fontWeight: "700",
    marginBottom: 2,
  },
  label: {
    ...typography.caption,
  },
});
