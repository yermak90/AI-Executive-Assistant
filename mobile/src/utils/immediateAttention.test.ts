import { resolveImmediateAttentionAlert } from "./immediateAttention";

describe("resolveImmediateAttentionAlert", () => {
  it("returns an alert when a commitment due in 1 hour comes back immediate_attention_required", () => {
    // Mirrors the backend scenario: enable_control=true + deadline in 1
    // hour falls under the "<24h -> 2h lead" default rule, so the computed
    // checkpoint is already in the past and the create response flags it.
    const createResponse = {
      commitment: {
        id: "c1",
        deadline: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      },
      immediate_attention_required: true,
    };

    const alert = resolveImmediateAttentionAlert(createResponse.immediate_attention_required);

    expect(alert).not.toBeNull();
    expect(alert?.title).toBe("Требуется внимание сейчас");
  });

  it("returns null when the backend does not flag immediate attention", () => {
    expect(resolveImmediateAttentionAlert(false)).toBeNull();
  });
});
