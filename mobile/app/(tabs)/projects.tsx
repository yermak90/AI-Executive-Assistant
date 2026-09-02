import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Card } from "../../src/components/Card";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { useProjectsQuery } from "../../src/hooks/useProjects";
import { colors, spacing, typography } from "../../src/theme";
import { pluralizeActiveCommitments } from "../../src/utils/pluralize";

export default function ProjectsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [refreshing, setRefreshing] = useState(false);
  const { data, isLoading, isError, refetch } = useProjectsQuery();

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
        <Text style={styles.title}>Проекты</Text>
        <Pressable style={styles.addButton} onPress={() => router.push("/project/new")}>
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
            <EmptyState title="Проектов пока нет" />
          ) : (
            data.map((project) => (
              <Pressable key={project.id} onPress={() => router.push(`/project/${project.id}`)}>
                <Card style={styles.card}>
                  <Text style={styles.projectName}>{project.name}</Text>
                  <Text style={styles.stats}>
                    {pluralizeActiveCommitments(project.active_commitments_count)}
                    {project.overdue_commitments_count > 0
                      ? ` · ${project.overdue_commitments_count} просрочено`
                      : ""}
                  </Text>
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
  projectName: {
    ...typography.title,
    marginBottom: spacing.xs,
  },
  stats: {
    ...typography.caption,
  },
});
