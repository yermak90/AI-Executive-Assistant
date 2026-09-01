import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";

import { CommitmentListItem } from "../../src/components/CommitmentListItem";
import { EmptyState } from "../../src/components/EmptyState";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { TextField } from "../../src/components/TextField";
import { Button } from "../../src/components/Button";
import { ApiError } from "../../src/api/client";
import { useCommitmentsQuery } from "../../src/hooks/useCommitments";
import { useProjectQuery, useUpdateProject } from "../../src/hooks/useProjects";
import { colors, spacing, typography } from "../../src/theme";

export default function ProjectDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: project, isLoading, isError, refetch } = useProjectQuery(id);
  const commitmentsQuery = useCommitmentsQuery({ project_id: id, status: "ACTIVE" });
  const updateMutation = useUpdateProject(id);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (project) {
      setName(project.name);
      setDescription(project.description ?? "");
    }
  }, [project]);

  if (isLoading) return <LoadingState />;
  if (isError || !project) return <ErrorState onRetry={refetch} />;

  const hasChanges = name !== project.name || description !== (project.description ?? "");

  const onSave = () => {
    updateMutation.mutate(
      { name, description: description || null },
      { onError: (e: unknown) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось сохранить") }
    );
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <TextField label="Название" value={name} onChangeText={setName} />
      <TextField label="Описание" value={description} onChangeText={setDescription} multiline />
      {hasChanges ? (
        <View style={styles.saveButton}>
          <Button label="Сохранить" onPress={onSave} loading={updateMutation.isPending} />
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>Активные обязательства</Text>
      {commitmentsQuery.isLoading ? (
        <LoadingState />
      ) : !commitmentsQuery.data || commitmentsQuery.data.length === 0 ? (
        <EmptyState title="Пока нет обязательств" />
      ) : (
        commitmentsQuery.data.map((c) => <CommitmentListItem key={c.id} commitment={c} />)
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  saveButton: { marginBottom: spacing.lg },
  sectionTitle: { ...typography.h2, marginTop: spacing.md, marginBottom: spacing.md },
});
