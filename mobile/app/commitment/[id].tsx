import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { AddCheckpointModal } from "../../src/components/AddCheckpointModal";
import { Button } from "../../src/components/Button";
import { Card } from "../../src/components/Card";
import { CheckpointAssessModal } from "../../src/components/CheckpointAssessModal";
import { CheckpointRow } from "../../src/components/CheckpointRow";
import { DeadlinePicker } from "../../src/components/DeadlinePicker";
import { ErrorState } from "../../src/components/ErrorState";
import { LoadingState } from "../../src/components/LoadingState";
import { ApiError } from "../../src/api/client";
import { ControlHealthBadge, DirectionBadge, StatusBadge } from "../../src/components/Badge";
import {
  useCancelCommitment,
  useCommitmentQuery,
  useCompleteCommitment,
  useRescheduleCommitment,
} from "../../src/hooks/useCommitments";
import { useAssessCheckpoint, useCreateCheckpoint, useSkipCheckpoint } from "../../src/hooks/useCheckpoints";
import { colors, radius, spacing, typography } from "../../src/theme";
import { formatDateTime, formatDeadline } from "../../src/utils/date";
import { Checkpoint, HistoryEventType } from "../../src/types/domain";

const HISTORY_LABELS: Record<HistoryEventType, string> = {
  CREATED: "Создано обязательство",
  UPDATED: "Обновлено",
  DEADLINE_CHANGED: "Изменен срок",
  COMPLETED: "Выполнено",
  CANCELLED: "Отменено",
  CHECKPOINT_CREATED: "Добавлена контрольная точка",
  CHECKPOINT_UPDATED: "Контрольная точка изменена",
  CHECKPOINT_RESCHEDULED: "Контрольная точка перенесена",
  CHECKPOINT_COMPLETED: "Контрольная точка завершена",
  CHECKPOINT_SKIPPED: "Контрольная точка пропущена",
  CHECKPOINT_ASSESSED_ON_TRACK: "Оценка: всё по плану",
  CHECKPOINT_ASSESSED_AT_RISK: "Оценка: есть риск",
  CHECKPOINT_ASSESSED_BLOCKED: "Оценка: заблокировано",
  CHECKPOINT_AUTO_RECALCULATED: "Контрольная точка пересчитана",
};

function formatHistoryDetail(oldValue: Record<string, unknown> | null, newValue: Record<string, unknown> | null): string | null {
  const value = newValue ?? oldValue;
  if (!value) return null;

  // `oldValue === null` means this is a creation snapshot, not an actual
  // transition — show the value on its own rather than "без срока → X".
  const isCreationSnapshot = oldValue === null;

  if (typeof value.deadline === "string" || (isCreationSnapshot && "deadline" in value)) {
    const newDeadline = newValue?.deadline;
    const newText = typeof newDeadline === "string" ? formatDateTime(newDeadline) : "без срока";
    if (isCreationSnapshot) return `Срок: ${newText}`;
    const oldDeadline = oldValue?.deadline;
    const oldText = typeof oldDeadline === "string" ? formatDateTime(oldDeadline) : "без срока";
    return `${oldText} → ${newText}`;
  }
  if (typeof value.scheduled_at === "string") {
    const oldAt = oldValue?.scheduled_at;
    const newAt = newValue?.scheduled_at;
    if (typeof oldAt === "string" && typeof newAt === "string") {
      return `${formatDateTime(oldAt)} → ${formatDateTime(newAt)}`;
    }
    if (isCreationSnapshot) return null; // just a "created" timestamp echo, redundant with the row's own date
    return formatDateTime(value.scheduled_at as string);
  }
  if (typeof value.title === "string" && Object.keys(value).length === 1) {
    return value.title as string;
  }
  if (typeof value.assessment_note === "string" && value.assessment_note) {
    return value.assessment_note as string;
  }
  return null;
}

export default function CommitmentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [pendingDeadline, setPendingDeadline] = useState<string | null>(null);
  const [assessingCheckpoint, setAssessingCheckpoint] = useState<Checkpoint | null>(null);
  const [addCheckpointOpen, setAddCheckpointOpen] = useState(false);

  const { data: commitment, isLoading, isError, refetch } = useCommitmentQuery(id);
  const completeMutation = useCompleteCommitment(id);
  const cancelMutation = useCancelCommitment(id);
  const rescheduleMutation = useRescheduleCommitment(id);
  const createCheckpointMutation = useCreateCheckpoint(id);
  const assessMutation = useAssessCheckpoint(id);
  const skipMutation = useSkipCheckpoint(id);

  if (isLoading) return <LoadingState />;
  if (isError || !commitment) return <ErrorState onRetry={refetch} />;

  const isActive = commitment.status === "ACTIVE";
  const personName = commitment.person?.name ?? "Вы";

  const handleComplete = () => {
    Alert.alert("Выполнено?", `Отметить «${commitment.title}» как выполненное?`, [
      { text: "Отмена", style: "cancel" },
      {
        text: "Выполнено",
        onPress: () =>
          completeMutation.mutate(undefined, { onError: (e: any) => Alert.alert("Ошибка", e.message) }),
      },
    ]);
  };

  const handleCancel = () => {
    Alert.alert("Отменить обязательство?", `«${commitment.title}» будет отмечено как отмененное.`, [
      { text: "Назад", style: "cancel" },
      {
        text: "Отменить обязательство",
        style: "destructive",
        onPress: () => cancelMutation.mutate(undefined, { onError: (e: any) => Alert.alert("Ошибка", e.message) }),
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
      onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
    });
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{commitment.title}</Text>

      <Card style={styles.fieldsCard}>
        <Field label="Статус">
          <View style={styles.badgeRow}>
            <StatusBadge status={commitment.status} isOverdue={commitment.is_overdue} />
            <ControlHealthBadge health={commitment.control_health} />
          </View>
        </Field>
        <Field label="Ответственный">
          <Text style={styles.value}>{personName}</Text>
        </Field>
        {commitment.counterparty ? (
          <Field label="Контрагент">
            <Text style={styles.value}>{commitment.counterparty.name}</Text>
          </Field>
        ) : null}
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

      <View style={styles.timelineHeader}>
        <Text style={styles.sectionTitle}>Контрольные точки</Text>
        {isActive ? (
          <Pressable onPress={() => setAddCheckpointOpen(true)}>
            <Text style={styles.addLink}>+ Добавить</Text>
          </Pressable>
        ) : null}
      </View>
      <Card style={styles.historyCard}>
        {commitment.checkpoints.length === 0 ? (
          <Text style={styles.emptyText}>Контрольных точек пока нет</Text>
        ) : (
          commitment.checkpoints.map((cp) => (
            <CheckpointRow key={cp.id} checkpoint={cp} onPress={() => setAssessingCheckpoint(cp)} />
          ))
        )}
      </Card>

      <Text style={styles.sectionTitle}>История</Text>
      <Card style={styles.historyCard}>
        {commitment.history.map((entry, index) => {
          const detail = formatHistoryDetail(entry.old_value, entry.new_value);
          return (
            <View key={entry.id} style={[styles.historyRow, index === commitment.history.length - 1 && styles.last]}>
              <Text style={styles.historyLabel}>{HISTORY_LABELS[entry.event_type]}</Text>
              {detail ? <Text style={styles.historyDetail}>{detail}</Text> : null}
              <Text style={styles.historyDate}>{formatDateTime(entry.created_at)}</Text>
            </View>
          );
        })}
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
          <View style={styles.actionSpacer} />
          <Button label="Отменить обязательство" variant="danger" onPress={handleCancel} loading={cancelMutation.isPending} />
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

      <AddCheckpointModal
        visible={addCheckpointOpen}
        onClose={() => setAddCheckpointOpen(false)}
        loading={createCheckpointMutation.isPending}
        onCreate={(title, scheduledAt) =>
          createCheckpointMutation.mutate(
            { title, scheduled_at: scheduledAt },
            {
              onSuccess: () => setAddCheckpointOpen(false),
              onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
            }
          )
        }
      />

      <CheckpointAssessModal
        checkpoint={assessingCheckpoint}
        loading={assessMutation.isPending || skipMutation.isPending}
        onClose={() => setAssessingCheckpoint(null)}
        onAssess={(assessment, note) =>
          assessingCheckpoint &&
          assessMutation.mutate(
            { checkpointId: assessingCheckpoint.id, data: { assessment, assessment_note: note } },
            {
              onSuccess: () => setAssessingCheckpoint(null),
              onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
            }
          )
        }
        onSkip={() =>
          assessingCheckpoint &&
          skipMutation.mutate(assessingCheckpoint.id, {
            onSuccess: () => setAssessingCheckpoint(null),
            onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
          })
        }
      />
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
  badgeRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  value: {
    ...typography.body,
    fontWeight: "600",
  },
  overdue: {
    color: colors.danger,
  },
  timelineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.h2,
  },
  addLink: {
    ...typography.body,
    color: colors.primary,
    fontWeight: "600",
  },
  emptyText: {
    ...typography.caption,
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
  historyDetail: {
    ...typography.caption,
    marginTop: 2,
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
