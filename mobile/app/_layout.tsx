import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { colors } from "../src/theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: colors.background },
            headerTintColor: colors.textPrimary,
            headerShadowVisible: false,
            contentStyle: { backgroundColor: colors.background },
          }}
        >
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="commitment/[id]" options={{ title: "Обязательство" }} />
          <Stack.Screen name="commitment/new" options={{ title: "Новое обязательство", presentation: "modal" }} />
          <Stack.Screen name="project/[id]" options={{ title: "Проект" }} />
          <Stack.Screen name="project/new" options={{ title: "Новый проект", presentation: "modal" }} />
          <Stack.Screen name="person/[id]" options={{ title: "Контакт" }} />
          <Stack.Screen name="person/new" options={{ title: "Новый контакт", presentation: "modal" }} />
        </Stack>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
