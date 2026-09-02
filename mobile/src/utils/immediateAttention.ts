export interface ImmediateAttentionAlert {
  title: string;
  message: string;
}

/** Review follow-up (P0-04 on create): a commitment created with
 * enable_control and a deadline close enough to trigger the backend's
 * immediate-attention clamp must surface an explicit alert before the
 * caller navigates away — this decides what that alert says, kept as a
 * pure function so the decision is testable without mounting the screen. */
export function resolveImmediateAttentionAlert(immediateAttentionRequired: boolean): ImmediateAttentionAlert | null {
  if (!immediateAttentionRequired) return null;
  return {
    title: "Требуется внимание сейчас",
    message: "Рекомендованная дата проверки уже наступила — вмешайтесь как можно скорее.",
  };
}
