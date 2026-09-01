import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { CommitmentListItem } from "../../src/components/CommitmentListItem";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { useCommitmentsQuery } from "../../src/hooks/useCommitments";
import { colors, radius, spacing, typography } from "../../src/theme";
import { Direction, DIRECTION_LABELS, DIRECTIONS } from "../../src/types/domain";

export default function CommitmentsControlScreen() {
  const router = useRouter();
  const [direction, setDirection] = useState<Direction>("OWED_TO_ME");
  const [refreshing, setRefreshing] = useState(false);

  const filters = { direction, status: "ACTIVE" as const };
  const todayQuery = useCommitmentsQuery({ ...filters, due: "today" });
  const overdueQuery = useCommitmentsQuery({ ...filters, overdue: true });
  const tomorrowQuery = useCommitmentsQuery({ ...filters, due: "tomorrow" });

  const isLoading = todayQuery.isLoading || overdueQuery.isLoading || tomorrowQuery.isLoading;
  const isError = todayQuery.isError || overdueQuery.isError || tomorrowQuery.isError;

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([todayQuery.refetch(), overdueQuery.refetch(), tomorrowQuery.refetch()]);
    setRefreshing(false);
  };

  const todayItems = (todayQuery.data ?? []).filter((c) => !c.is_overdue);
  const overdueItems = overdueQuery.data ?? [];
  const tomorrowItems = tomorrowQuery.data ?? [];
  const isEmpty = todayItems.length === 0 && overdueItems.length === 0 && tomorrowItems.length === 0;

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Контроль обязательств</Text>
      </View>

      <View style={styles.tabs}>
        {DIRECTIONS.map((option) => (
          <Pressable
            key={option}
            style={[styles.tab, direction === option && styles.tabActive]}
            onPress={() => setDirection(option)}
          >
            <Text style={[styles.tabLabel, direction === option && styles.tabLabelActive]}>
              {DIRECTION_LABELS[option]}
            </Text>
          </Pressable>
        ))}
      </View>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState onRetry={onRefresh} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        >
          {isEmpty ? (
            <EmptyState
              title="Пока нет обязательств"
              description={"Добавьте первое обязательство,\nчтобы начать контроль."}
            />
          ) : (
            <>
              <Section title="Просрочено" items={overdueItems} />
              <Section title="Сегодня" items={todayItems} />
              <Section title="Завтра" items={tomorrowItems} />
            </>
          )}
        </ScrollView>
      )}
    </View>
  );
}

function Section({ title, items }: { title: string; items: ReturnType<typeof useCommitmentsQuery>["data"] }) {
  if (!items || items.length === 0) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {items.map((commitment) => (
        <CommitmentListItem key={commitment.id} commitment={commitment} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
  },
  title: {
    ...typography.h1,
    marginBottom: spacing.md,
  },
  tabs: {
    flexDirection: "row",
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  tab: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  tabActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  tabLabel: {
    ...typography.caption,
    fontWeight: "600",
  },
  tabLabelActive: {
    color: "#fff",
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  section: {
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    ...typography.h2,
    marginBottom: spacing.md,
  },
});
