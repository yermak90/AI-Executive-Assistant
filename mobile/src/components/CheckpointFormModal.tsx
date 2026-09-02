import DateTimePicker from "@react-native-community/datetimepicker";
import { useEffect, useState } from "react";
import { Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";
import { Checkpoint } from "../types/domain";
import { formatDateTime } from "../utils/date";
import { Button } from "./Button";
import { TextField } from "./TextField";

export interface CheckpointFormValues {
  title: string;
  question: string | null;
  reason: string | null;
  scheduled_at: string;
}

interface CheckpointFormModalProps {
  visible: boolean;
  mode: "create" | "edit";
  initial?: Checkpoint | null;
  onClose: () => void;
  onSubmit: (values: CheckpointFormValues) => void;
  loading?: boolean;
}

/** P1-05: shared create/edit form for checkpoints — title, question, reason,
 * and scheduled_at, matching the fields CheckpointCreate/CheckpointUpdate
 * accept on the backend. */
export function CheckpointFormModal({ visible, mode, initial, onClose, onSubmit, loading }: CheckpointFormModalProps) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(() => new Date(Date.now() + 24 * 60 * 60 * 1000));
  const [activePicker, setActivePicker] = useState<"date" | "time" | "datetime" | null>(null);

  useEffect(() => {
    if (!visible) return;
    setTitle(initial?.title ?? "");
    setQuestion(initial?.question ?? "");
    setReason(initial?.reason ?? "");
    setDate(initial ? new Date(initial.scheduled_at) : new Date(Date.now() + 24 * 60 * 60 * 1000));
  }, [visible, initial]);

  const close = () => {
    onClose();
  };

  const submit = () => {
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      question: question.trim() || null,
      reason: reason.trim() || null,
      scheduled_at: date.toISOString(),
    });
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>
            {mode === "edit" ? "Редактировать контрольную точку" : "Новая контрольная точка"}
          </Text>
          <TextField label="Что проверить" value={title} onChangeText={setTitle} placeholder="Например, заказ материалов" />
          <TextField
            label="Вопрос для проверки (необязательно)"
            value={question}
            onChangeText={setQuestion}
            placeholder="Например, материалы заказаны?"
          />
          <TextField
            label="Почему важно проверить (необязательно)"
            value={reason}
            onChangeText={setReason}
            placeholder="Например, влияет на сроки поставки"
          />

          <Text style={styles.label}>Когда проверить</Text>
          <Pressable
            style={styles.dateButton}
            onPress={() => setActivePicker(Platform.OS === "ios" ? "datetime" : "date")}
          >
            <Text style={styles.dateLabel}>{formatDateTime(date.toISOString())}</Text>
          </Pressable>

          {activePicker ? (
            <DateTimePicker
              value={date}
              mode={activePicker === "time" ? "time" : activePicker === "date" ? "date" : "datetime"}
              is24Hour
              onChange={(event, selected) => {
                if (Platform.OS === "android") {
                  const wasDateStep = activePicker === "date";
                  setActivePicker(null);
                  if (event.type === "dismissed" || !selected) return;
                  setDate(selected);
                  if (wasDateStep) setActivePicker("time");
                  return;
                }
                if (event.type === "dismissed" || !selected) {
                  setActivePicker(null);
                  return;
                }
                setDate(selected);
              }}
            />
          ) : null}

          <View style={styles.submitSpacer} />
          <Button label={mode === "edit" ? "Сохранить" : "Добавить"} onPress={submit} disabled={!title.trim()} loading={loading} />
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
    marginBottom: spacing.md,
  },
  label: {
    ...typography.caption,
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  dateButton: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  dateLabel: {
    ...typography.body,
  },
  submitSpacer: {
    height: spacing.xs,
  },
});
