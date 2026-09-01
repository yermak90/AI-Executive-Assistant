import { colors } from "./colors";

export const typography = {
  h1: { fontSize: 28, fontWeight: "700" as const, color: colors.textPrimary },
  h2: { fontSize: 20, fontWeight: "700" as const, color: colors.textPrimary },
  title: { fontSize: 17, fontWeight: "600" as const, color: colors.textPrimary },
  body: { fontSize: 15, fontWeight: "400" as const, color: colors.textPrimary },
  caption: { fontSize: 13, fontWeight: "400" as const, color: colors.textSecondary },
  small: { fontSize: 12, fontWeight: "500" as const, color: colors.textMuted },
};
