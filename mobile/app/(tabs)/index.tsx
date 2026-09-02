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
import { Commitment } from "../../src/types/domain";
import { formatHeaderDate } from "../../src/utils/date";
import { getGreeting, CURRENT_USER_NAME } from "../../src/utils/user";

export default function TodayScreen() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);

  // A single ACTIVE query carries backend-computed `bucket` and
  // `control_health` per item — grouping below only reads those values,
  // it never re-derives overdue/today/risk logic on the client (4.2).
  const activeQuery = useCommitmentsQuery({ status: "ACTIVE" });

  const onRefresh = async () => {
    setRefreshing(true);
    await activeQuery.refetch();
    setRefreshing(false);
  };

  if (activeQuery.isLoading) return <LoadingState />;
  if (activeQuery.isError || !activeQuery.data) return <ErrorState onRetry={onRefresh} />;

  const active = activeQuery.data;
  const owedToMeCount = active.filter((c) => c.direction === "OWED_TO_ME").length;
  const iOweCount = active.filter((c) => c.direction === "I_OWE").length;
  const todayCount = active.filter((c) => c.bucket === "today").length;
  const overdueCount = active.filter((c) => c.bucket === "overdue").length;

  const shown = new Set<string>();
  const takeUnshown = (items: Commitment[]) => {
    const result = items.filter((c) => !shown.has(c.id));
    result.forEach((c) => shown.add(c.id));
    return result;
  };

  const blocked = takeUnshown(active.filter((c) => c.control_health === "BLOCKED"));
  const atRisk = takeUnshown(active.filter((c) => c.control_health === "AT_RISK"));
  const checkDue = takeUnshown(active.filter((c) => c.control_health === "CHECK_DUE"));
  const dueToday = takeUnshown(active.filter((c) => c.bucket === "today" || c.bucket === "overdue"));

  const hasAnything = blocked.length + atRisk.length + checkDue.length + dueToday.length > 0;

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
          count={todayCount}
          color={colors.primary}
          onPress={() => router.push("/(tabs)/commitments")}
        />
        <SummaryCard
          label="Просрочено"
          count={overdueCount}
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

      {!hasAnything ? (
        <EmptyState
          title="Пока нет обязательств"
          description={"Добавьте первое обязательство,\nчтобы начать контроль."}
        />
      ) : (
        <>
          <AttentionSection title="Заблокировано" items={blocked} />
          <AttentionSection title="Есть риск" items={atRisk} />
          <AttentionSection title="Требуют проверки" items={checkDue} />
          <AttentionSection title="На контроле сегодня" items={dueToday} />
        </>
      )}

      <View style={styles.createButton}>
        <Button label="Добавить в контроль" onPress={() => router.push("/commitment/new")} />
      </View>
    </ScrollView>
  );
}

function AttentionSection({ title, items }: { title: string; items: Commitment[] }) {
  if (items.length === 0) return null;
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
  section: {
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    ...typography.h2,
    marginBottom: spacing.md,
  },
  createButton: {
    marginTop: spacing.md,
  },
});
