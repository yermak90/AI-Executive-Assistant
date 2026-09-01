import { Feather } from "@expo/vector-icons";
import { Tabs } from "expo-router";

import { colors } from "../../src/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          backgroundColor: colors.background,
          borderTopColor: colors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Сегодня",
          tabBarIcon: ({ color, size }) => <Feather name="sun" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="projects"
        options={{
          title: "Проекты",
          tabBarIcon: ({ color, size }) => <Feather name="folder" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="commitments"
        options={{
          title: "Задачи",
          tabBarIcon: ({ color, size }) => <Feather name="check-square" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="contacts"
        options={{
          title: "Контакты",
          tabBarIcon: ({ color, size }) => <Feather name="users" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: "Еще",
          tabBarIcon: ({ color, size }) => <Feather name="more-horizontal" color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
