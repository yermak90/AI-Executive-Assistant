import { Direction } from "../types/domain";

/**
 * Pure payload-building logic for the commitment create/edit form. Extracted
 * and unit-tested because of a specific bug class (P0 review): a PATCH must
 * never carry `deadline` — POST /commitments/{id}/reschedule is the only
 * path that changes it (it's the only one that validates the AUTO_RULE plan
 * and returns immediate_attention_required / manual_checkpoints_after_deadline),
 * and the backend now rejects a PATCH containing `deadline` outright. Since
 * the create and edit forms share this one screen, that guarantee has to
 * live in one place the payload is actually built, not be re-derived at
 * each call site.
 */

export interface CommitmentFormValues {
  title: string;
  description: string | null;
  direction: Direction;
  personId: string | null;
  counterpartyId: string | null;
  projectId: string | null;
  deadline: string | null;
}

export interface ControlOptions {
  enableControl: boolean;
  leadTimeDays: number | null;
  controlQuestion: string;
  controlReason: string;
}

export function buildCommitmentPayload(
  values: CommitmentFormValues,
  mode: "create" | "edit",
  control?: ControlOptions
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: values.title,
    description: values.description || null,
    direction: values.direction,
    project_id: values.projectId,
  };

  if (values.direction === "I_OWE") {
    payload.owner_person_id = null;
    payload.counterparty_person_id = values.counterpartyId;
  } else {
    payload.owner_person_id = values.personId;
  }

  if (mode === "create") {
    payload.deadline = values.deadline;
    if (control) {
      payload.enable_control = control.enableControl;
      payload.lead_time_days = control.enableControl ? control.leadTimeDays : null;
      payload.control_question = control.enableControl ? control.controlQuestion.trim() || null : null;
      payload.control_reason = control.enableControl ? control.controlReason.trim() || null : null;
    }
  }

  return payload;
}
