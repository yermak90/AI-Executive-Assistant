import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "expo-router";
import { Controller, useForm } from "react-hook-form";
import { Alert, ScrollView, StyleSheet, View } from "react-native";
import { z } from "zod";

import { ApiError } from "../../src/api/client";
import { Button } from "../../src/components/Button";
import { TextField } from "../../src/components/TextField";
import { useCreateProject } from "../../src/hooks/useProjects";
import { colors, spacing } from "../../src/theme";

const schema = z.object({
  name: z.string().min(1, "Укажите название"),
  description: z.string().nullable(),
});

type FormValues = z.infer<typeof schema>;

export default function NewProjectScreen() {
  const router = useRouter();
  const createMutation = useCreateProject();
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { name: "", description: null } });

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values, {
      onSuccess: () => router.back(),
      onError: (error: unknown) => {
        const message = error instanceof ApiError ? error.detail : "Не удалось создать проект";
        Alert.alert("Ошибка", message);
      },
    });
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Controller
        control={control}
        name="name"
        render={({ field }) => (
          <TextField
            label="Название *"
            placeholder="Например, Astana Plaza"
            value={field.value}
            onChangeText={field.onChange}
            error={errors.name?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="description"
        render={({ field }) => (
          <TextField
            label="Описание"
            placeholder="Необязательно"
            value={field.value ?? ""}
            onChangeText={field.onChange}
            multiline
          />
        )}
      />
      <View style={styles.submit}>
        <Button label="Создать проект" onPress={handleSubmit(onSubmit)} loading={createMutation.isPending} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg },
  submit: { marginTop: spacing.md },
});
