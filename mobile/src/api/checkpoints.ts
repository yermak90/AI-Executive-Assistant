import { apiClient } from "./client";
import { Checkpoint, CheckpointAssessment } from "../types/domain";

export interface CreateCheckpointInput {
  title: string;
  question?: string | null;
  reason?: string | null;
  scheduled_at: string;
}

export interface UpdateCheckpointInput {
  title?: string;
  question?: string | null;
  reason?: string | null;
  scheduled_at?: string;
}

export interface AssessCheckpointInput {
  assessment: Extract<CheckpointAssessment, "ON_TRACK" | "AT_RISK" | "BLOCKED">;
  assessment_note?: string | null;
}

export interface GenerateCheckpointsResult {
  checkpoints: Checkpoint[];
  immediate_attention_required: boolean;
}

export const checkpointsApi = {
  list: (commitmentId: string) => apiClient.get<Checkpoint[]>(`/commitments/${commitmentId}/checkpoints`),
  create: (commitmentId: string, data: CreateCheckpointInput) =>
    apiClient.post<Checkpoint>(`/commitments/${commitmentId}/checkpoints`, data),
  generate: (
    commitmentId: string,
    leadTimeDays?: number | null,
    question?: string | null,
    reason?: string | null
  ) =>
    apiClient.post<GenerateCheckpointsResult>(`/commitments/${commitmentId}/checkpoints/generate`, {
      lead_time_days: leadTimeDays ?? null,
      question: question ?? null,
      reason: reason ?? null,
    }),
  update: (checkpointId: string, data: UpdateCheckpointInput) =>
    apiClient.patch<Checkpoint>(`/checkpoints/${checkpointId}`, data),
  delete: (checkpointId: string) => apiClient.delete<void>(`/checkpoints/${checkpointId}`),
  assess: (checkpointId: string, data: AssessCheckpointInput) =>
    apiClient.post<Checkpoint>(`/checkpoints/${checkpointId}/assess`, data),
  skip: (checkpointId: string) => apiClient.post<Checkpoint>(`/checkpoints/${checkpointId}/skip`),
};
