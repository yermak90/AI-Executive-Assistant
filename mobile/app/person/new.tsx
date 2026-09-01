import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "expo-router";
import { Controller, useForm } from "react-hook-form";
import { Alert, ScrollView, StyleSheet, View } from "react-native";
import { z } from "zod";

import { ApiError } from "../../src/api/client";
import { Button } from "../../src/components/Button";
import { TextField } from "../../src/components/TextField";
import { useCreatePerson } from "../../src/hooks/usePeople";
import { colors, spacing } from "../../src/theme";

const schema = z.object({
  name: z.string().min(1, "Укажите имя"),
  notes: z.string().nullable(),
});

type FormValues = z.infer<typeof schema>;

export default function NewPersonScreen() {
  const router = useRouter();
  const createMutation = useCreatePerson();
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { name: "", notes: null } });

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values, {
      onSuccess: () => router.back(),
      onError: (error: unknown) => {
        const message = error instanceof ApiError ? error.detail : "Не удалось добавить контакт";
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
            label="Имя *"
            placeholder="Например, Аян"
            value={field.value}
            onChangeText={field.onChange}
            error={errors.name?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="notes"
        render={({ field }) => (
          <TextField
            label="Заметки"
            placeholder="Необязательно"
            value={field.value ?? ""}
            onChangeText={field.onChange}
            multiline
          />
        )}
      />
      <View style={styles.submit}>
        <Button label="Добавить контакт" onPress={handleSubmit(onSubmit)} loading={createMutation.isPending} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg },
  submit: { marginTop: spacing.md },
});
