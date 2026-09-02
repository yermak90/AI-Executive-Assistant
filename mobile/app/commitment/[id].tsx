import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Button } from "../../src/components/Button";
import { Card } from "../../src/components/Card";
import { CheckpointAssessModal } from "../../src/components/CheckpointAssessModal";
import { CheckpointFormModal, CheckpointFormValues } from "../../src/components/CheckpointFormModal";
import { CheckpointRow } from "../../src/components/CheckpointRow";
import { ControlSettingsCard } from "../../src/components/ControlSettingsCard";
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
import {
  useAssessCheckpoint,
  useCreateCheckpoint,
  useDeleteCheckpoint,
  useSkipCheckpoint,
  useUpdateCheckpoint,
} from "../../src/hooks/useCheckpoints";
import { colors, radius, spacing, typography } from "../../src/theme";
import { formatDateTime, formatDeadline } from "../../src/utils/date";
import { Checkpoint, CommitmentHistoryEntry, Direction, DIRECTION_LABELS, HistoryEventType } from "../../src/types/domain";

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

const FIELD_LABELS: Record<string, string> = {
  title: "Задача",
  description: "Описание",
  direction: "Направление",
  owner_person_id: "Ответственный",
  counterparty_person_id: "Контрагент",
  project_id: "Проект",
  lead_time_days: "Контроль (дней до срока)",
  deadline: "Срок",
};

const CHECKPOINT_FIELD_LABELS: Record<string, string> = {
  title: "Название",
  question: "Вопрос",
  reason: "Причина",
};

function formatFieldValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (field === "direction" && typeof value === "string") {
    return DIRECTION_LABELS[value as Direction] ?? value;
  }
  return String(value);
}

/** P1-9: every field an UPDATED event can carry gets its own readable
 * "Label: old → new" line (or just "Label: value" for the CREATED
 * snapshot, which has no real "old"). Person/project fields already arrive
 * as resolved names from the backend, not raw IDs. */
function formatHistoryDetailLines(entry: CommitmentHistoryEntry): string[] {
  const { event_type, old_value, new_value } = entry;
  const isCreationSnapshot = old_value === null;

  if (event_type === "DEADLINE_CHANGED") {
    const newDeadline = new_value?.deadline;
    const newText = typeof newDeadline === "string" ? formatDateTime(newDeadline) : "без срока";
    const oldDeadline = old_value?.deadline;
    const oldText = typeof oldDeadline === "string" ? formatDateTime(oldDeadline) : "без срока";
    return [`${oldText} → ${newText}`];
  }

  if (event_type.startsWith("CHECKPOINT_")) {
    const value = new_value ?? old_value;
    if (!value) return [];
    if (typeof value.scheduled_at === "string") {
      const oldAt = old_value?.scheduled_at;
      const newAt = new_value?.scheduled_at;
      if (typeof oldAt === "string" && typeof newAt === "string") {
        return [`${formatDateTime(oldAt)} → ${formatDateTime(newAt)}`];
      }
      return isCreationSnapshot ? [] : [formatDateTime(value.scheduled_at as string)];
    }
    if (typeof value.assessment_note === "string" && value.assessment_note) {
      return [value.assessment_note as string];
    }
    if (event_type === "CHECKPOINT_UPDATED") {
      // title/question/reason old->new — old_value/new_value carry only
      // the fields that actually changed (see backend update_checkpoint).
      return Object.keys(value).map((field) => {
        const label = CHECKPOINT_FIELD_LABELS[field] ?? field;
        const oldText = formatFieldValue(field, old_value?.[field]);
        const newText = formatFieldValue(field, new_value?.[field]);
        return `${label}: ${oldText} → ${newText}`;
      });
    }
    return [];
  }

  if (event_type === "CREATED" || event_type === "UPDATED") {
    // Both are per-field snapshots/diffs (CREATED just has no "old" side —
    // every field it carries is rendered as "Label: value" instead of a
    // transition). This is also where title/direction/deadline for a brand
    // new commitment get spelled out, not just a bare "Создано обязательство".
    const value = new_value ?? old_value;
    if (!value) return [];
    return Object.keys(value).map((field) => {
      const label = FIELD_LABELS[field] ?? field;
      const rawNew = new_value?.[field];
      const newText =
        field === "deadline"
          ? typeof rawNew === "string"
            ? formatDateTime(rawNew)
            : "без срока"
          : formatFieldValue(field, rawNew);
      if (isCreationSnapshot) return `${label}: ${newText}`;
      const oldText = formatFieldValue(field, old_value?.[field]);
      return `${label}: ${oldText} → ${newText}`;
    });
  }

  return [];
}

export default function CommitmentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [pendingDeadline, setPendingDeadline] = useState<string | null>(null);
  const [assessingCheckpoint, setAssessingCheckpoint] = useState<Checkpoint | null>(null);
  const [addCheckpointOpen, setAddCheckpointOpen] = useState(false);
  const [editingCheckpoint, setEditingCheckpoint] = useState<Checkpoint | null>(null);

  const { data: commitment, isLoading, isError, refetch } = useCommitmentQuery(id);
  const completeMutation = useCompleteCommitment(id);
  const cancelMutation = useCancelCommitment(id);
  const rescheduleMutation = useRescheduleCommitment(id);
  const createCheckpointMutation = useCreateCheckpoint(id);
  const updateCheckpointMutation = useUpdateCheckpoint(id);
  const deleteCheckpointMutation = useDeleteCheckpoint(id);
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
      onSuccess: (result) => {
        setRescheduleOpen(false);
        if (result.manual_checkpoints_after_deadline.length > 0) {
          const titles = result.manual_checkpoints_after_deadline.map((cp) => `• ${cp.title}`).join("\n");
          Alert.alert(
            "Контрольные точки после нового срока",
            `Эти контрольные точки не были перенесены и теперь позже нового срока:\n${titles}`
          );
        } else if (result.immediate_attention_required) {
          Alert.alert(
            "Требуется внимание сейчас",
            "Пересчитанная контрольная точка попадает на момент создания обязательства — вмешайтесь как можно скорее."
          );
        }
      },
      onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
    });
  };

  const handleDeleteCheckpoint = (checkpoint: Checkpoint) => {
    Alert.alert("Удалить контрольную точку?", checkpoint.title, [
      { text: "Отмена", style: "cancel" },
      {
        text: "Удалить",
        style: "destructive",
        onPress: () =>
          deleteCheckpointMutation.mutate(checkpoint.id, {
            onSuccess: () => setAssessingCheckpoint(null),
            onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
          }),
      },
    ]);
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

      {isActive ? (
        <>
          <Text style={styles.sectionTitle}>Настроить контроль</Text>
          <ControlSettingsCard
            commitmentId={commitment.id}
            leadTimeDays={commitment.lead_time_days}
            hasDeadline={commitment.deadline !== null}
            autoCheckpoint={
              commitment.checkpoints.find((cp) => cp.status === "PENDING" && cp.source_type === "AUTO_RULE") ?? null
            }
          />
        </>
      ) : null}

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
          const detailLines = formatHistoryDetailLines(entry);
          return (
            <View key={entry.id} style={[styles.historyRow, index === commitment.history.length - 1 && styles.last]}>
              <Text style={styles.historyLabel}>{HISTORY_LABELS[entry.event_type]}</Text>
              {detailLines.map((line, lineIndex) => (
                <Text key={lineIndex} style={styles.historyDetail}>
                  {line}
                </Text>
              ))}
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

      <CheckpointFormModal
        visible={addCheckpointOpen}
        mode="create"
        onClose={() => setAddCheckpointOpen(false)}
        loading={createCheckpointMutation.isPending}
        onSubmit={(values: CheckpointFormValues) =>
          createCheckpointMutation.mutate(values, {
            onSuccess: () => setAddCheckpointOpen(false),
            onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
          })
        }
      />

      <CheckpointFormModal
        visible={editingCheckpoint !== null}
        mode="edit"
        initial={editingCheckpoint}
        onClose={() => setEditingCheckpoint(null)}
        loading={updateCheckpointMutation.isPending}
        onSubmit={(values: CheckpointFormValues) =>
          editingCheckpoint &&
          updateCheckpointMutation.mutate(
            { checkpointId: editingCheckpoint.id, data: values },
            {
              onSuccess: () => setEditingCheckpoint(null),
              onError: (e: any) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : e.message),
            }
          )
        }
      />

      <CheckpointAssessModal
        checkpoint={assessingCheckpoint}
        loading={assessMutation.isPending || skipMutation.isPending || deleteCheckpointMutation.isPending}
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
        onEdit={() => {
          if (!assessingCheckpoint) return;
          setEditingCheckpoint(assessingCheckpoint);
          setAssessingCheckpoint(null);
        }}
        onDelete={() => assessingCheckpoint && handleDeleteCheckpoint(assessingCheckpoint)}
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
