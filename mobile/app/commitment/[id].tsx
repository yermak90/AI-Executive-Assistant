import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Button } from "../../src/components/Button";
import { Card } from "../../src/components/Card";
import { DeadlinePicker } from "../../src/components/DeadlinePicker";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { DirectionBadge, StatusBadge } from "../../src/components/Badge";
import {
  useCommitmentQuery,
  useCompleteCommitment,
  useRescheduleCommitment,
} from "../../src/hooks/useCommitments";
import { colors, radius, spacing, typography } from "../../src/theme";
import { formatDateTime, formatDeadline } from "../../src/utils/date";
import { HistoryEventType } from "../../src/types/domain";

const HISTORY_LABELS: Record<HistoryEventType, string> = {
  CREATED: "Создано обязательство",
  DEADLINE_CHANGED: "Изменен срок",
  COMPLETED: "Выполнено",
  CANCELLED: "Отменено",
  UPDATED: "Обновлено",
};

export default function CommitmentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [pendingDeadline, setPendingDeadline] = useState<string | null>(null);

  const { data: commitment, isLoading, isError, refetch } = useCommitmentQuery(id);
  const completeMutation = useCompleteCommitment(id);
  const rescheduleMutation = useRescheduleCommitment(id);

  if (isLoading) return <LoadingState />;
  if (isError || !commitment) return <ErrorState onRetry={refetch} />;

  const isActive = commitment.status === "ACTIVE";
  const personName = commitment.person?.name ?? "Вы";

  const handleComplete = () => {
    Alert.alert("Выполнено?", `Отметить «${commitment.title}» как выполненное?`, [
      { text: "Отмена", style: "cancel" },
      {
        text: "Выполнено",
        onPress: () => completeMutation.mutate(undefined, { onError: (e: any) => Alert.alert("Ошибка", e.message) }),
      },
    ]);
  };

  const openReschedule = () => {
    setPendingDeadline(commitment.deadline);
    setRescheduleOpen(true);
  };

  const confirmReschedule = () => {
    rescheduleMutation.mutate(pendingDeadline, {
      onSuccess: () => setRescheduleOpen(false),
      onError: (e: any) => Alert.alert("Ошибка", e.message),
    });
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{commitment.title}</Text>

      <Card style={styles.fieldsCard}>
        <Field label="Статус">
          <StatusBadge status={commitment.status} isOverdue={commitment.is_overdue} />
        </Field>
        <Field label="Ответственный">
          <Text style={styles.value}>{personName}</Text>
        </Field>
        <Field label="Срок">
          <Text style={[styles.value, commitment.is_overdue && styles.overdue]}>
            {formatDeadline(commitment.deadline)}
          </Text>
        </Field>
        <Field label="Проект">
          <Text style={styles.value}>{commitment.project?.name ?? "Без проекта"}</Text>
        </Field>
        <Field label="Направление" last>
          <DirectionBadge direction={commitment.direction} />
        </Field>
      </Card>

      <Text style={styles.sectionTitle}>История</Text>
      <Card style={styles.historyCard}>
        {commitment.history.map((entry, index) => (
          <View key={entry.id} style={[styles.historyRow, index === commitment.history.length - 1 && styles.last]}>
            <Text style={styles.historyLabel}>{HISTORY_LABELS[entry.event_type]}</Text>
            <Text style={styles.historyDate}>{formatDateTime(entry.created_at)}</Text>
          </View>
        ))}
      </Card>

      {isActive ? (
        <View style={styles.actions}>
          <Button label="Выполнено" onPress={handleComplete} loading={completeMutation.isPending} />
          <View style={styles.actionSpacer} />
          <Button label="Перенести" variant="secondary" onPress={openReschedule} />
          <View style={styles.actionSpacer} />
          <Button
            label="Редактировать"
            variant="secondary"
            onPress={() => router.push({ pathname: "/commitment/new", params: { editId: commitment.id } })}
          />
        </View>
      ) : null}

      <Modal visible={rescheduleOpen} transparent animationType="slide" onRequestClose={() => setRescheduleOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setRescheduleOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Перенести срок</Text>
            <DeadlinePicker label="Новый срок" value={pendingDeadline} onChange={setPendingDeadline} />
            <Button label="Сохранить" onPress={confirmReschedule} loading={rescheduleMutation.isPending} />
          </Pressable>
        </Pressable>
      </Modal>
    </ScrollView>
  );
}

function Field({ label, children, last }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <View style={[styles.field, last && styles.last]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
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
  title: {
    ...typography.h1,
    marginBottom: spacing.lg,
  },
  fieldsCard: {
    marginBottom: spacing.lg,
  },
  field: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  last: {
    borderBottomWidth: 0,
  },
  fieldLabel: {
    ...typography.caption,
  },
  value: {
    ...typography.body,
    fontWeight: "600",
  },
  overdue: {
    color: colors.danger,
  },
  sectionTitle: {
    ...typography.h2,
    marginBottom: spacing.md,
  },
  historyCard: {
    marginBottom: spacing.xl,
  },
  historyRow: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  historyLabel: {
    ...typography.body,
    fontWeight: "600",
  },
  historyDate: {
    ...typography.small,
    marginTop: 2,
  },
  actions: {
    marginTop: spacing.md,
  },
  actionSpacer: {
    height: spacing.sm,
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surfaceElevated,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
  },
  sheetTitle: {
    ...typography.title,
    marginBottom: spacing.md,
  },
});
