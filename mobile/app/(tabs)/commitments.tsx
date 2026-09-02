import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { CommitmentListItem } from "../../src/components/CommitmentListItem";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { useCommitmentsQuery } from "../../src/hooks/useCommitments";
import { colors, radius, spacing, typography } from "../../src/theme";
import { BUCKET_LABELS, BUCKETS, Commitment, Direction, DIRECTION_LABELS, DIRECTIONS } from "../../src/types/domain";

export default function CommitmentsControlScreen() {
  const insets = useSafeAreaInsets();
  const [direction, setDirection] = useState<Direction>("OWED_TO_ME");
  const [showArchive, setShowArchive] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const query = useCommitmentsQuery(
    showArchive ? { direction, archive: true } : { direction, status: "ACTIVE" }
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await query.refetch();
    setRefreshing(false);
  };

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
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

      <View style={styles.segmented}>
        <Pressable
          style={[styles.segment, !showArchive && styles.segmentActive]}
          onPress={() => setShowArchive(false)}
        >
          <Text style={[styles.segmentLabel, !showArchive && styles.segmentLabelActive]}>Активные</Text>
        </Pressable>
        <Pressable
          style={[styles.segment, showArchive && styles.segmentActive]}
          onPress={() => setShowArchive(true)}
        >
          <Text style={[styles.segmentLabel, showArchive && styles.segmentLabelActive]}>Архив</Text>
        </Pressable>
      </View>

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError || !query.data ? (
        <ErrorState onRetry={onRefresh} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        >
          {query.data.length === 0 ? (
            <EmptyState
              title={showArchive ? "В архиве пока пусто" : "Пока нет обязательств"}
              description={showArchive ? undefined : "Добавьте первое обязательство,\nчтобы начать контроль."}
            />
          ) : showArchive ? (
            query.data.map((commitment) => <CommitmentListItem key={commitment.id} commitment={commitment} />)
          ) : (
            BUCKETS.map((bucket) => (
              <Section
                key={bucket}
                title={BUCKET_LABELS[bucket]}
                items={query.data!.filter((c) => c.bucket === bucket)}
              />
            ))
          )}
        </ScrollView>
      )}
    </View>
  );
}

function Section({ title, items }: { title: string; items: Commitment[] }) {
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
  segmented: {
    flexDirection: "row",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  segment: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
  },
  segmentActive: {
    backgroundColor: colors.surfaceElevated,
  },
  segmentLabel: {
    ...typography.caption,
    color: colors.textMuted,
  },
  segmentLabelActive: {
    color: colors.textPrimary,
    fontWeight: "600",
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
