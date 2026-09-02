import { apiClient } from "./client";
import {
  Bucket,
  Checkpoint,
  Commitment,
  CommitmentDetail,
  CommitmentHistoryEntry,
  ControlHealth,
  Direction,
  CommitmentStatus,
} from "../types/domain";

export interface CommitmentListFilters {
  direction?: Direction;
  status?: CommitmentStatus;
  project_id?: string;
  person_id?: string;
  bucket?: Bucket;
  control_health?: ControlHealth;
  archive?: boolean;
}

export interface CreateCommitmentInput {
  title: string;
  description?: string | null;
  owner_person_id?: string | null;
  counterparty_person_id?: string | null;
  project_id?: string | null;
  direction: Direction;
  deadline?: string | null;
  source_text?: string | null;
  enable_control?: boolean;
  lead_time_days?: number | null;
  control_question?: string | null;
  control_reason?: string | null;
}

export interface UpdateCommitmentInput {
  title?: string;
  description?: string | null;
  owner_person_id?: string | null;
  counterparty_person_id?: string | null;
  project_id?: string | null;
  direction?: Direction;
  deadline?: string | null;
  source_text?: string | null;
  lead_time_days?: number | null;
}

export interface RescheduleResult {
  commitment: CommitmentDetail;
  immediate_attention_required: boolean;
  manual_checkpoints_after_deadline: Checkpoint[];
}

function buildQuery(filters: CommitmentListFilters): string {
  const params = new URLSearchParams();
  if (filters.direction) params.set("direction", filters.direction);
  if (filters.status) params.set("status", filters.status);
  if (filters.project_id) params.set("project_id", filters.project_id);
  if (filters.person_id) params.set("person_id", filters.person_id);
  if (filters.bucket) params.set("bucket", filters.bucket);
  if (filters.control_health) params.set("control_health", filters.control_health);
  if (filters.archive) params.set("archive", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const commitmentsApi = {
  list: (filters: CommitmentListFilters = {}) => apiClient.get<Commitment[]>(`/commitments${buildQuery(filters)}`),
  get: (id: string) => apiClient.get<CommitmentDetail>(`/commitments/${id}`),
  create: (data: CreateCommitmentInput) => apiClient.post<CommitmentDetail>("/commitments", data),
  update: (id: string, data: UpdateCommitmentInput) =>
    apiClient.patch<CommitmentDetail>(`/commitments/${id}`, data),
  complete: (id: string) => apiClient.post<CommitmentDetail>(`/commitments/${id}/complete`),
  reschedule: (id: string, deadline: string | null) =>
    apiClient.post<RescheduleResult>(`/commitments/${id}/reschedule`, { deadline }),
  cancel: (id: string) => apiClient.post<CommitmentDetail>(`/commitments/${id}/cancel`),
  history: (id: string) => apiClient.get<CommitmentHistoryEntry[]>(`/commitments/${id}/history`),
};
