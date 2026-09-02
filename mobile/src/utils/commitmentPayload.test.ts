import { buildCommitmentPayload, CommitmentFormValues } from "./commitmentPayload";

const baseValues: CommitmentFormValues = {
  title: "Купить материалы",
  description: null,
  direction: "OWED_TO_ME",
  personId: "person-1",
  counterpartyId: null,
  projectId: null,
  deadline: "2026-09-10T12:00:00.000Z",
};

describe("buildCommitmentPayload", () => {
  it("does not include deadline in an edit payload", () => {
    const payload = buildCommitmentPayload(baseValues, "edit");
    expect(payload).not.toHaveProperty("deadline");
  });

  it("does not include deadline in an edit payload even when the form still holds one", () => {
    const payload = buildCommitmentPayload({ ...baseValues, deadline: "2026-12-01T00:00:00.000Z" }, "edit");
    expect(payload).not.toHaveProperty("deadline");
  });

  it("includes deadline in a create payload", () => {
    const payload = buildCommitmentPayload(baseValues, "create");
    expect(payload).toHaveProperty("deadline", baseValues.deadline);
  });

  it("includes control fields only on create, and only when enabled", () => {
    const payload = buildCommitmentPayload(baseValues, "create", {
      enableControl: true,
      leadTimeDays: 3,
      controlQuestion: "Готово?",
      controlReason: "Иначе сорвём срок",
    });
    expect(payload.enable_control).toBe(true);
    expect(payload.lead_time_days).toBe(3);
    expect(payload.control_question).toBe("Готово?");
    expect(payload.control_reason).toBe("Иначе сорвём срок");
  });

  it("does not include control fields on edit even when control options are passed", () => {
    const payload = buildCommitmentPayload(baseValues, "edit", {
      enableControl: true,
      leadTimeDays: 3,
      controlQuestion: "Готово?",
      controlReason: "Иначе сорвём срок",
    });
    expect(payload).not.toHaveProperty("enable_control");
    expect(payload).not.toHaveProperty("lead_time_days");
    expect(payload).not.toHaveProperty("control_question");
    expect(payload).not.toHaveProperty("control_reason");
    expect(payload).not.toHaveProperty("deadline");
  });

  it("sets owner_person_id to null and uses counterpartyId for I_OWE", () => {
    const payload = buildCommitmentPayload(
      { ...baseValues, direction: "I_OWE", counterpartyId: "counterparty-1" },
      "edit"
    );
    expect(payload.owner_person_id).toBeNull();
    expect(payload.counterparty_person_id).toBe("counterparty-1");
  });

  it("uses personId as owner_person_id for non-I_OWE directions", () => {
    const payload = buildCommitmentPayload({ ...baseValues, direction: "TEAM" }, "edit");
    expect(payload.owner_person_id).toBe("person-1");
    expect(payload).not.toHaveProperty("counterparty_person_id");
  });
});
