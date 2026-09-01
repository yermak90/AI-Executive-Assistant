import { PropsWithChildren } from "react";
import { StyleSheet, View, ViewStyle } from "react-native";

import { colors, radius, spacing } from "../theme";

interface CardProps extends PropsWithChildren {
  style?: ViewStyle;
  elevated?: boolean;
}

export function Card({ children, style, elevated }: CardProps) {
  return <View style={[styles.card, elevated && styles.elevated, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  elevated: {
    backgroundColor: colors.surfaceElevated,
  },
});
