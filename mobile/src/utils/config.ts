import { Platform } from "react-native";

/**
 * Resolves the backend base URL.
 *
 * Priority:
 * 1. EXPO_PUBLIC_API_URL from the environment (see README for how to set this
 *    for a physical device, where localhost does not point at the dev machine).
 * 2. Platform-specific default for the local dev backend:
 *    - Android emulator maps host loopback to 10.0.2.2.
 *    - iOS simulator and web can use localhost directly.
 */
function resolveApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv;

  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000/api/v1";
  }
  return "http://localhost:8000/api/v1";
}

export const API_BASE_URL = resolveApiBaseUrl();
