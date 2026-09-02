import { zodResolver } from "@hookform/resolvers/zod";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { z } from "zod";

import { Button } from "../../src/components/Button";
import { DeadlinePicker } from "../../src/components/DeadlinePicker";
import { LoadingState } from "../../src/components/LoadingState";
import { SelectField } from "../../src/components/SelectField";
import { TextField } from "../../src/components/TextField";
import { ApiError } from "../../src/api/client";
import { useCommitmentQuery, useCreateCommitment, useUpdateCommitment } from "../../src/hooks/useCommitments";
import { usePeopleQuery } from "../../src/hooks/usePeople";
import { useProjectsQuery } from "../../src/hooks/useProjects";
import { colors, radius, spacing, typography } from "../../src/theme";
import { DIRECTIONS, DIRECTION_LABELS } from "../../src/types/domain";

const schema = z
  .object({
    title: z.string().min(1, "Укажите задачу"),
    description: z.string().nullable(),
    direction: z.enum(["OWED_TO_ME", "I_OWE", "TEAM"]),
    personId: z.string().nullable(),
    counterpartyId: z.string().nullable(),
    projectId: z.string().nullable(),
    deadline: z.string().nullable(),
  })
  .refine((data) => data.direction === "I_OWE" || data.personId !== null, {
    message: "Укажите ответственного",
    path: ["personId"],
  });

type FormValues = z.infer<typeof schema>;

const LEAD_TIME_OPTIONS = [1, 2, 3, 7];

export default function CommitmentFormScreen() {
  const router = useRouter();
  const { editId } = useLocalSearchParams<{ editId?: string }>();
  const isEdit = !!editId;

  const peopleQuery = usePeopleQuery();
  const projectsQuery = useProjectsQuery();
  const existingQuery = useCommitmentQuery(editId ?? "");
  const createMutation = useCreateCommitment();
  const updateMutation = useUpdateCommitment(editId ?? "");

  const [enableControl, setEnableControl] = useState(false);
  const [leadTimeDays, setLeadTimeDays] = useState<number | null>(2);
  const [customLeadTime, setCustomLeadTime] = useState(false);
  const [customLeadTimeText, setCustomLeadTimeText] = useState("");
  const [controlQuestion, setControlQuestion] = useState("");
  const [controlReason, setControlReason] = useState("");

  const {
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      description: null,
      direction: "OWED_TO_ME",
      personId: null,
      counterpartyId: null,
      projectId: null,
      deadline: null,
    },
  });

  const direction = watch("direction");
  const deadline = watch("deadline");

  useEffect(() => {
    if (isEdit && existingQuery.data) {
      reset({
        title: existingQuery.data.title,
        description: existingQuery.data.description,
        direction: existingQuery.data.direction,
        personId: existingQuery.data.person?.id ?? null,
        counterpartyId: existingQuery.data.counterparty?.id ?? null,
        projectId: existingQuery.data.project?.id ?? null,
        deadline: existingQuery.data.deadline,
      });
    }
  }, [isEdit, existingQuery.data, reset]);

  if (isEdit && existingQuery.isLoading) return <LoadingState />;

  const personOptions = [
    { label: "Не выбрано", value: null },
    ...(peopleQuery.data ?? []).map((p) => ({ label: p.name, value: p.id })),
  ];
  const projectOptions = [
    { label: "Без проекта", value: null },
    ...(projectsQuery.data ?? []).map((p) => ({ label: p.name, value: p.id })),
  ];
  const directionOptions = DIRECTIONS.map((d) => ({ label: DIRECTION_LABELS[d], value: d }));

  const onSubmit = (values: FormValues) => {
    const payload: Record<string, unknown> = {
      title: values.title,
      description: values.description || null,
      direction: values.direction,
      project_id: values.projectId,
      deadline: values.deadline,
    };

    if (values.direction === "I_OWE") {
      payload.owner_person_id = null;
      payload.counterparty_person_id = values.counterpartyId;
    } else {
      payload.owner_person_id = values.personId;
    }

    if (!isEdit) {
      const effectiveLeadTime = customLeadTime ? Number(customLeadTimeText) || null : leadTimeDays;
      payload.enable_control = enableControl;
      payload.lead_time_days = enableControl ? effectiveLeadTime : null;
      payload.control_question = enableControl ? controlQuestion.trim() || null : null;
      payload.control_reason = enableControl ? controlReason.trim() || null : null;
    }

    const mutation = isEdit ? updateMutation : createMutation;
    mutation.mutate(payload as any, {
      onSuccess: () => router.back(),
      onError: (error: unknown) => {
        const message = error instanceof ApiError ? error.detail : "Не удалось сохранить обязательство";
        Alert.alert("Ошибка", message);
      },
    });
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Controller
        control={control}
        name="title"
        render={({ field }) => (
          <TextField
            label="Задача *"
            placeholder="Что нужно сделать"
            value={field.value}
            onChangeText={field.onChange}
            error={errors.title?.message}
          />
        )}
      />

      <Controller
        control={control}
        name="description"
        render={({ field }) => (
          <TextField
            label="Описание"
            placeholder="Дополнительные детали (необязательно)"
            value={field.value ?? ""}
            onChangeText={field.onChange}
            multiline
          />
        )}
      />

      <Controller
        control={control}
        name="direction"
        render={({ field }) => (
          <SelectField
            label="Направление *"
            value={field.value}
            options={directionOptions}
            onChange={(v) => field.onChange(v ?? "OWED_TO_ME")}
          />
        )}
      />

      {direction === "I_OWE" ? (
        <Controller
          control={control}
          name="counterpartyId"
          render={({ field }) => (
            <SelectField label="Контрагент" value={field.value} options={personOptions} onChange={field.onChange} />
          )}
        />
      ) : (
        <Controller
          control={control}
          name="personId"
          render={({ field }) => (
            <SelectField
              label="Ответственный *"
              value={field.value}
              options={personOptions}
              onChange={field.onChange}
            />
          )}
        />
      )}
      {errors.personId ? <Text style={styles.errorText}>{errors.personId.message}</Text> : null}

      <Controller
        control={control}
        name="projectId"
        render={({ field }) => (
          <SelectField label="Проект" value={field.value} options={projectOptions} onChange={field.onChange} />
        )}
      />

      <Controller
        control={control}
        name="deadline"
        render={({ field }) => <DeadlinePicker label="Срок" value={field.value} onChange={field.onChange} />}
      />

      {!isEdit && deadline ? (
        <View style={styles.controlBlock}>
          <Pressable style={styles.controlToggle} onPress={() => setEnableControl((v) => !v)}>
            <Text style={styles.controlToggleLabel}>Настроить контроль</Text>
            <View style={[styles.switch, enableControl && styles.switchOn]}>
              <View style={[styles.switchDot, enableControl && styles.switchDotOn]} />
            </View>
          </Pressable>

          {enableControl ? (
            <View style={styles.leadTimeRow}>
              <Text style={styles.leadTimeLabel}>Проверить заранее (дней):</Text>
              <View style={styles.leadTimeChips}>
                {LEAD_TIME_OPTIONS.map((days) => (
                  <Pressable
                    key={days}
                    style={[styles.leadChip, !customLeadTime && leadTimeDays === days && styles.leadChipActive]}
                    onPress={() => {
                      setCustomLeadTime(false);
                      setLeadTimeDays(days);
                    }}
                  >
                    <Text
                      style={[
                        styles.leadChipLabel,
                        !customLeadTime && leadTimeDays === days && styles.leadChipLabelActive,
                      ]}
                    >
                      {days}
                    </Text>
                  </Pressable>
                ))}
                <Pressable
                  style={[styles.leadChip, styles.leadChipCustom, customLeadTime && styles.leadChipActive]}
                  onPress={() => setCustomLeadTime(true)}
                >
                  <Text style={[styles.leadChipLabel, customLeadTime && styles.leadChipLabelActive]}>Свое</Text>
                </Pressable>
              </View>

              {customLeadTime ? (
                <TextField
                  label="Дней до срока"
                  keyboardType="number-pad"
                  placeholder="Например, 5"
                  value={customLeadTimeText}
                  onChangeText={setCustomLeadTimeText}
                />
              ) : null}

              <TextField
                label="Контрольный вопрос (необязательно)"
                placeholder="Что проверить?"
                value={controlQuestion}
                onChangeText={setControlQuestion}
              />
              <TextField
                label="Почему важно (необязательно)"
                placeholder="Причина контроля"
                value={controlReason}
                onChangeText={setControlReason}
              />
            </View>
          ) : null}
        </View>
      ) : null}

      <View style={styles.submit}>
        <Button
          label="Добавить в контроль"
          onPress={handleSubmit(onSubmit)}
          loading={createMutation.isPending || updateMutation.isPending}
        />
      </View>
    </ScrollView>
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
  errorText: {
    ...typography.small,
    color: colors.danger,
    marginTop: -spacing.md,
    marginBottom: spacing.md,
  },
  controlBlock: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  controlToggle: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  controlToggleLabel: {
    ...typography.body,
    fontWeight: "600",
  },
  switch: {
    width: 44,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: colors.border,
    padding: 3,
  },
  switchOn: {
    backgroundColor: colors.primary,
  },
  switchDot: {
    width: 20,
    height: 20,
    borderRadius: radius.pill,
    backgroundColor: "#fff",
  },
  switchDotOn: {
    transform: [{ translateX: 18 }],
  },
  leadTimeRow: {
    marginTop: spacing.md,
  },
  leadTimeLabel: {
    ...typography.caption,
    marginBottom: spacing.sm,
  },
  leadTimeChips: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  leadChip: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  leadChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  leadChipCustom: {
    width: 56,
  },
  leadChipLabel: {
    ...typography.body,
    fontWeight: "600",
  },
  leadChipLabelActive: {
    color: "#fff",
  },
  submit: {
    marginTop: spacing.md,
  },
});
