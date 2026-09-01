import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { Button } from "../../src/components/Button";
import { CommitmentListItem } from "../../src/components/CommitmentListItem";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { SummaryCard } from "../../src/components/SummaryCard";
import { useCommitmentsQuery } from "../../src/hooks/useCommitments";
import { colors, spacing, typography } from "../../src/theme";
import { formatHeaderDate } from "../../src/utils/date";
import { getGreeting, CURRENT_USER_NAME } from "../../src/utils/user";

export default function TodayScreen() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);

  const activeQuery = useCommitmentsQuery({ status: "ACTIVE" });
  const todayQuery = useCommitmentsQuery({ due: "today" });
  const overdueQuery = useCommitmentsQuery({ overdue: true });

  const isLoading = activeQuery.isLoading || todayQuery.isLoading || overdueQuery.isLoading;
  const isError = activeQuery.isError || todayQuery.isError || overdueQuery.isError;

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([activeQuery.refetch(), todayQuery.refetch(), overdueQuery.refetch()]);
    setRefreshing(false);
  };

  if (isLoading) return <LoadingState />;
  if (isError || !activeQuery.data || !todayQuery.data || !overdueQuery.data) {
    return <ErrorState onRetry={onRefresh} />;
  }

  const owedToMeCount = activeQuery.data.filter((c) => c.direction === "OWED_TO_ME").length;
  const iOweCount = activeQuery.data.filter((c) => c.direction === "I_OWE").length;

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <View style={styles.header}>
        <Text style={styles.greeting}>
          {getGreeting()}, {CURRENT_USER_NAME}
        </Text>
        <Text style={styles.date}>{formatHeaderDate(new Date())}</Text>
      </View>

      <View style={styles.summaryGrid}>
        <SummaryCard
          label="Сегодня"
          count={todayQuery.data.length}
          color={colors.primary}
          onPress={() => router.push("/(tabs)/commitments")}
        />
        <SummaryCard
          label="Просрочено"
          count={overdueQuery.data.length}
          color={colors.danger}
          onPress={() => router.push("/(tabs)/commitments")}
        />
        <SummaryCard label="Мне должны" count={owedToMeCount} color={colors.success} />
        <SummaryCard label="Я должен" count={iOweCount} color={colors.warning} />
      </View>

      <Pressable
        style={styles.recordButton}
        onPress={() => Alert.alert("Скоро", "Запись встречи появится в следующем обновлении.")}
      >
        <Feather name="mic" size={18} color={colors.textMuted} />
        <Text style={styles.recordLabel}>Записать встречу</Text>
        <Text style={styles.soonBadge}>Скоро</Text>
      </Pressable>

      <Text style={styles.sectionTitle}>На контроле сегодня</Text>

      {todayQuery.data.length === 0 ? (
        <EmptyState
          title="Пока нет обязательств"
          description={"Добавьте первое обязательство,\nчтобы начать контроль."}
        />
      ) : (
        todayQuery.data.map((commitment) => <CommitmentListItem key={commitment.id} commitment={commitment} />)
      )}

      <View style={styles.createButton}>
        <Button label="Добавить в контроль" onPress={() => router.push("/commitment/new")} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  header: {
    marginBottom: spacing.lg,
  },
  greeting: {
    ...typography.h1,
  },
  date: {
    ...typography.caption,
    marginTop: spacing.xs,
    textTransform: "capitalize",
  },
  summaryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },
  recordButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.lg,
    opacity: 0.7,
  },
  recordLabel: {
    ...typography.body,
    marginLeft: spacing.sm,
    flex: 1,
  },
  soonBadge: {
    ...typography.small,
    color: colors.textMuted,
  },
  sectionTitle: {
    ...typography.h2,
    marginBottom: spacing.md,
  },
  createButton: {
    marginTop: spacing.md,
  },
});
