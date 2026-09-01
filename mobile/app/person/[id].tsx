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
import { usePersonQuery, useUpdatePerson } from "../../src/hooks/usePeople";
import { colors, spacing, typography } from "../../src/theme";

export default function PersonDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: person, isLoading, isError, refetch } = usePersonQuery(id);
  const commitmentsQuery = useCommitmentsQuery({ person_id: id, status: "ACTIVE" });
  const updateMutation = useUpdatePerson(id);

  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (person) {
      setName(person.name);
      setNotes(person.notes ?? "");
    }
  }, [person]);

  if (isLoading) return <LoadingState />;
  if (isError || !person) return <ErrorState onRetry={refetch} />;

  const hasChanges = name !== person.name || notes !== (person.notes ?? "");

  const onSave = () => {
    updateMutation.mutate(
      { name, notes: notes || null },
      { onError: (e: unknown) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось сохранить") }
    );
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <TextField label="Имя" value={name} onChangeText={setName} />
      <TextField label="Заметки" value={notes} onChangeText={setNotes} multiline />
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
