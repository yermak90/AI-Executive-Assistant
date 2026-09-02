import DateTimePicker from "@react-native-community/datetimepicker";
import { useState } from "react";
import { Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "../theme";
import { formatDateTime } from "../utils/date";
import { Button } from "./Button";
import { TextField } from "./TextField";

interface AddCheckpointModalProps {
  visible: boolean;
  onClose: () => void;
  onCreate: (title: string, scheduledAt: string) => void;
  loading?: boolean;
}

export function AddCheckpointModal({ visible, onClose, onCreate, loading }: AddCheckpointModalProps) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(() => new Date(Date.now() + 24 * 60 * 60 * 1000));
  const [activePicker, setActivePicker] = useState<"date" | "time" | "datetime" | null>(null);

  const close = () => {
    setTitle("");
    onClose();
  };

  const submit = () => {
    if (!title.trim()) return;
    onCreate(title.trim(), date.toISOString());
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>Новая контрольная точка</Text>
          <TextField label="Что проверить" value={title} onChangeText={setTitle} placeholder="Например, заказ материалов" />

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
          <Button label="Добавить" onPress={submit} disabled={!title.trim()} loading={loading} />
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
