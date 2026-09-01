import { StyleSheet, Text, View } from "react-native";

import { colors, spacing, typography } from "../theme";

interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {description ? <Text style={styles.description}>{description}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
  },
  title: {
    ...typography.title,
    color: colors.textSecondary,
    textAlign: "center",
    marginBottom: spacing.xs,
  },
  description: {
    ...typography.caption,
    textAlign: "center",
  },
});
