import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Card } from "../../src/components/Card";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { usePeopleQuery } from "../../src/hooks/usePeople";
import { colors, spacing, typography } from "../../src/theme";
import { pluralizeActiveCommitments } from "../../src/utils/pluralize";

export default function ContactsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [refreshing, setRefreshing] = useState(false);
  const { data, isLoading, isError, refetch } = usePeopleQuery();

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
        <Text style={styles.title}>Контакты</Text>
        <Pressable style={styles.addButton} onPress={() => router.push("/person/new")}>
          <Feather name="plus" size={22} color={colors.textPrimary} />
        </Pressable>
      </View>

      {isLoading ? (
        <LoadingState />
      ) : isError || !data ? (
        <ErrorState onRetry={onRefresh} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        >
          {data.length === 0 ? (
            <EmptyState title="Контактов пока нет" />
          ) : (
            data.map((person) => (
              <Pressable key={person.id} onPress={() => router.push(`/person/${person.id}`)}>
                <Card style={styles.card}>
                  <Text style={styles.personName}>{person.name}</Text>
                  <Text style={styles.stats}>{pluralizeActiveCommitments(person.active_commitments_count)}</Text>
                </Card>
              </Pressable>
            ))
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    marginBottom: spacing.md,
  },
  title: {
    ...typography.h1,
  },
  addButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  personName: {
    ...typography.title,
    marginBottom: spacing.xs,
  },
  stats: {
    ...typography.caption,
  },
});
