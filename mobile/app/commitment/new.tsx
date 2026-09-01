import { zodResolver } from "@hookform/resolvers/zod";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { Alert, ScrollView, StyleSheet, View } from "react-native";
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
import { colors, spacing } from "../../src/theme";
import { DIRECTIONS, DIRECTION_LABELS } from "../../src/types/domain";

const schema = z.object({
  title: z.string().min(1, "Укажите задачу"),
  direction: z.enum(["OWED_TO_ME", "I_OWE", "TEAM"]),
  personId: z.string().nullable(),
  projectId: z.string().nullable(),
  deadline: z.string().nullable(),
});

type FormValues = z.infer<typeof schema>;

export default function CommitmentFormScreen() {
  const router = useRouter();
  const { editId } = useLocalSearchParams<{ editId?: string }>();
  const isEdit = !!editId;

  const peopleQuery = usePeopleQuery();
  const projectsQuery = useProjectsQuery();
  const existingQuery = useCommitmentQuery(editId ?? "");
  const createMutation = useCreateCommitment();
  const updateMutation = useUpdateCommitment(editId ?? "");

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", direction: "OWED_TO_ME", personId: null, projectId: null, deadline: null },
  });

  useEffect(() => {
    if (isEdit && existingQuery.data) {
      reset({
        title: existingQuery.data.title,
        direction: existingQuery.data.direction,
        personId: existingQuery.data.person?.id ?? null,
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
    const payload = {
      title: values.title,
      direction: values.direction,
      owner_person_id: values.personId,
      project_id: values.projectId,
      deadline: values.deadline,
    };

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

      <Controller
        control={control}
        name="personId"
        render={({ field }) => (
          <SelectField label="Ответственный" value={field.value} options={personOptions} onChange={field.onChange} />
        )}
      />

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
  submit: {
    marginTop: spacing.md,
  },
});
