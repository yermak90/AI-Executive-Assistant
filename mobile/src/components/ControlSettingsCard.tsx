import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useUpdateCommitment } from "../hooks/useCommitments";
import { useGenerateCheckpoints } from "../hooks/useCheckpoints";
import { ApiError } from "../api/client";
import { colors, radius, spacing, typography } from "../theme";
import { Button } from "./Button";

const LEAD_TIME_PRESETS = [1, 2, 3, 7];

interface ControlSettingsCardProps {
  commitmentId: string;
  leadTimeDays: number | null;
  hasDeadline: boolean;
}

/** PRD FR-015/FR-016 "Настроить контроль" block, editable after creation
 * (P1-06): pick a lead time (or a custom value), save it on the commitment,
 * and (re)generate the AUTO_RULE checkpoint from it. Surfaces
 * immediate_attention_required (P0-04) rather than letting it disappear
 * into an ignored response field. */
export function ControlSettingsCard({ commitmentId, leadTimeDays, hasDeadline }: ControlSettingsCardProps) {
  const [selected, setSelected] = useState<number | null>(leadTimeDays);
  const [customText, setCustomText] = useState(
    leadTimeDays && !LEAD_TIME_PRESETS.includes(leadTimeDays) ? String(leadTimeDays) : ""
  );
  const [customMode, setCustomMode] = useState(!!customText);

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

  const handleSave = () => {
    if (!effectiveDays || effectiveDays <= 0) {
      Alert.alert("Укажите срок", "Введите количество дней больше нуля.");
      return;
    }
    updateMutation.mutate(
      { lead_time_days: effectiveDays },
      {
        onSuccess: () => {
          generateMutation.mutate(effectiveDays, {
            onSuccess: (result) => {
              if (result.immediate_attention_required) {
                Alert.alert(
                  "Требуется внимание сейчас",
                  "Рекомендованная дата проверки уже наступила — вмешайтесь как можно скорее."
                );
              }
            },
            onError: (e: unknown) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось создать контрольную точку"),
          });
        },
        onError: (e: unknown) => Alert.alert("Ошибка", e instanceof ApiError ? e.detail : "Не удалось сохранить настройки"),
      }
    );
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

      <Button label="Сохранить и пересчитать" onPress={handleSave} loading={isSaving} disabled={!effectiveDays} />
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
});
