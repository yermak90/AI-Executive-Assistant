import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";
import { Checkpoint } from "../types/domain";
import { Button } from "./Button";

interface CheckpointAssessModalProps {
  checkpoint: Checkpoint | null;
  onClose: () => void;
  onAssess: (assessment: "ON_TRACK" | "AT_RISK" | "BLOCKED", note: string | null) => void;
  onSkip: () => void;
  loading?: boolean;
}

const OPTIONS: { value: "ON_TRACK" | "AT_RISK" | "BLOCKED"; label: string; color: string }[] = [
  { value: "ON_TRACK", label: "Всё по плану", color: colors.success },
  { value: "AT_RISK", label: "Есть риск", color: colors.warning },
  { value: "BLOCKED", label: "Заблокировано", color: colors.danger },
];

export function CheckpointAssessModal({ checkpoint, onClose, onAssess, onSkip, loading }: CheckpointAssessModalProps) {
  const [selected, setSelected] = useState<"ON_TRACK" | "AT_RISK" | "BLOCKED" | null>(null);
  const [note, setNote] = useState("");

  const close = () => {
    setSelected(null);
    setNote("");
    onClose();
  };

  return (
    <Modal visible={checkpoint !== null} transparent animationType="slide" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>{checkpoint?.title}</Text>
          <Text style={styles.question}>{checkpoint?.question ?? "Оцените состояние обязательства"}</Text>

          <View style={styles.options}>
            {OPTIONS.map((option) => (
              <Pressable
                key={option.value}
                style={[styles.option, selected === option.value && { borderColor: option.color }]}
                onPress={() => setSelected(option.value)}
              >
                <Text style={[styles.optionLabel, { color: option.color }]}>{option.label}</Text>
              </Pressable>
            ))}
          </View>

          {selected === "AT_RISK" || selected === "BLOCKED" ? (
            <TextInput
              style={styles.noteInput}
              placeholder="Что происходит? (необязательно)"
              placeholderTextColor={colors.textMuted}
              value={note}
              onChangeText={setNote}
              multiline
            />
          ) : null}

          <Button
            label="Сохранить оценку"
            onPress={() => selected && onAssess(selected, note || null)}
            disabled={!selected}
            loading={loading}
          />
          <View style={styles.skipSpacer} />
          <Button label="Пропустить контрольную точку" variant="secondary" onPress={onSkip} />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
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
  title: {
    ...typography.title,
    marginBottom: spacing.xs,
  },
  question: {
    ...typography.caption,
    marginBottom: spacing.lg,
  },
  options: {
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  option: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  optionLabel: {
    fontWeight: "600",
    fontSize: 15,
  },
  noteInput: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    padding: spacing.md,
    minHeight: 70,
    marginBottom: spacing.md,
    textAlignVertical: "top",
  },
  skipSpacer: {
    height: spacing.sm,
  },
});
