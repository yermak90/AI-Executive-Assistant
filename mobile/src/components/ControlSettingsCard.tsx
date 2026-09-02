import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useUpdateCommitment } from "../hooks/useCommitments";
import { useGenerateCheckpoints } from "../hooks/useCheckpoints";
import { ApiError } from "../api/client";
import { colors, radius, spacing, typography } from "../theme";
import { Checkpoint } from "../types/domain";
import { resolveImmediateAttentionAlert } from "../utils/immediateAttention";
import { Button } from "./Button";
import { TextField } from "./TextField";

const LEAD_TIME_PRESETS = [1, 2, 3, 7];

interface ControlSettingsCardProps {
  commitmentId: string;
  leadTimeDays: number | null;
  hasDeadline: boolean;
  /** The commitment's current PENDING AUTO_RULE checkpoint, if any — its
   * question/reason prefill the edit fields below. */
  autoCheckpoint: Checkpoint | null;
}

/** PRD FR-015/FR-016 "Настроить контроль" block, editable after creation
 * (P1-06): pick a lead time (or a custom value), edit the control
 * question/reason, save it on the commitment, and (re)generate the
 * AUTO_RULE checkpoint from it — which replaces the existing PENDING
 * AUTO_RULE checkpoint in place rather than piling a new one on top.
 * Surfaces immediate_attention_required (P0-04) rather than letting it
 * disappear into an ignored response field, and offers turning control off
 * entirely. */
export function ControlSettingsCard({ commitmentId, leadTimeDays, hasDeadline, autoCheckpoint }: ControlSettingsCardProps) {
  const [selected, setSelected] = useState<number | null>(leadTimeDays);
  const [customText, setCustomText] = useState(
    leadTimeDays && !LEAD_TIME_PRESETS.includes(leadTimeDays) ? String(leadTimeDays) : ""
  );
  const [customMode, setCustomMode] = useState(!!(leadTimeDays && !LEAD_TIME_PRESETS.includes(leadTimeDays)));
  const [question, setQuestion] = useState(autoCheckpoint?.question ?? "");
  const [reason, setReason] = useState(autoCheckpoint?.reason ?? "");

  const updateMutation = useUpdateCommitment(commitmentId);
  const generateMutation = useGenerateCheckpoints(commitmentId);

  if (!hasDeadline) {
    return (
      <View style={styles.card}>
        <Text style={styles.hint}>Укажите срок обязательства, чтобы настроить контроль.</Text>
      </View>
    );
  }

  const effectiveDays = customMode ? Number(customText) || null : selected;
  const isSaving = updateMutation.isPending || generateMutation.isPending;
  const isEnabled = leadTimeDays !== null;

  const handleSave = () => {
    if (!effectiveDays || effectiveDays <= 0) {
      Alert.alert("Укажите срок", "Введите количество дней больше нуля.");
      return;
    }
    updateMutation.mutate(
      { lead_time_days: effectiveDays },
      {
        onSuccess: () => {
          generateMutation.mutate(
            { leadTimeDays: effectiveDays, question: question.trim() || null, reason: reason.trim() || null },
            {
              onSuccess: (result) => {
                const alert = resolveImmediateAttentionAlert(result.immediate_attention_required);
                if (alert) Alert.alert(alert.title, alert.message);
              },
              onError: (e: unknown) =>
                Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось создать контрольную точку"),
            }
          );
        },
        onError: (e: unknown) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось сохранить настройки"),
      }
    );
  };

  const handleDisable = () => {
    Alert.alert("Отключить контроль?", "Запланированная проверка будет отменена.", [
      { text: "Отмена", style: "cancel" },
      {
        text: "Отключить",
        style: "destructive",
        onPress: () =>
          updateMutation.mutate(
            { lead_time_days: null },
            {
              onError: (e: unknown) =>
                Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось отключить контроль"),
            }
          ),
      },
    ]);
  };

  return (
    <View style={styles.card}>
      <Text style={styles.label}>Проверить заранее (дней до срока)</Text>
      <View style={styles.chips}>
        {LEAD_TIME_PRESETS.map((days) => (
          <Pressable
            key={days}
            style={[styles.chip, !customMode && selected === days && styles.chipActive]}
            onPress={() => {
              setCustomMode(false);
              setSelected(days);
            }}
          >
            <Text style={[styles.chipLabel, !customMode && selected === days && styles.chipLabelActive]}>{days}</Text>
          </Pressable>
        ))}
        <Pressable style={[styles.chip, customMode && styles.chipActive]} onPress={() => setCustomMode(true)}>
          <Text style={[styles.chipLabel, customMode && styles.chipLabelActive]}>Свое</Text>
        </Pressable>
      </View>

      {customMode ? (
        <TextInput
          style={styles.customInput}
          keyboardType="number-pad"
          placeholder="Дней до срока"
          placeholderTextColor={colors.textMuted}
          value={customText}
          onChangeText={setCustomText}
        />
      ) : null}

      <TextField
        label="Контрольный вопрос (необязательно)"
        placeholder="Что проверить?"
        value={question}
        onChangeText={setQuestion}
      />
      <TextField
        label="Почему важно (необязательно)"
        placeholder="Причина контроля"
        value={reason}
        onChangeText={setReason}
      />

      <Button label="Сохранить и пересчитать" onPress={handleSave} loading={isSaving} disabled={!effectiveDays} />

      {isEnabled ? (
        <View style={styles.disableSpacer}>
          <Button label="Отключить контроль" variant="secondary" onPress={handleDisable} loading={isSaving} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.xl,
  },
  hint: {
    ...typography.caption,
  },
  label: {
    ...typography.caption,
    fontWeight: "600",
    marginBottom: spacing.sm,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  chip: {
    width: 48,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipLabel: {
    ...typography.body,
    fontWeight: "600",
  },
  chipLabelActive: {
    color: "#fff",
  },
  customInput: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  disableSpacer: {
    marginTop: spacing.sm,
  },
});
