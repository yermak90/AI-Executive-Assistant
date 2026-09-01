import { StyleSheet, Text, View } from "react-native";

import { colors, spacing, typography } from "../../src/theme";

export default function MoreScreen() {
  return (
    <View style={styles.screen}>
      <Text style={styles.title}>Еще</Text>
      <Text style={styles.description}>Настройки и дополнительные функции появятся в следующих обновлениях.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    paddingTop: spacing.xxl,
  },
  title: {
    ...typography.h1,
    marginBottom: spacing.sm,
  },
  description: {
    ...typography.caption,
  },
});
