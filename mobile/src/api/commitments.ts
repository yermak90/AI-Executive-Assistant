import { apiClient } from "./client";
import { Commitment, CommitmentDetail, CommitmentHistoryEntry, Direction, CommitmentStatus } from "../types/domain";

export interface CommitmentListFilters {
  direction?: Direction;
  status?: CommitmentStatus;
  project_id?: string;
  person_id?: string;
  due?: "today" | "tomorrow";
  overdue?: boolean;
}

export interface CreateCommitmentInput {
  title: string;
  description?: string | null;
  owner_person_id?: string | null;
  project_id?: string | null;
  direction: Direction;
  deadline?: string | null;
}

export interface UpdateCommitmentInput {
  title?: string;
  description?: string | null;
  owner_person_id?: string | null;
  project_id?: string | null;
  direction?: Direction;
  deadline?: string | null;
}

function buildQuery(filters: CommitmentListFilters): string {
  const params = new URLSearchParams();
  if (filters.direction) params.set("direction", filters.direction);
  if (filters.status) params.set("status", filters.status);
  if (filters.project_id) params.set("project_id", filters.project_id);
  if (filters.person_id) params.set("person_id", filters.person_id);
  if (filters.due) params.set("due", filters.due);
  if (filters.overdue) params.set("overdue", "true");
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
    apiClient.post<CommitmentDetail>(`/commitments/${id}/reschedule`, { deadline }),
  cancel: (id: string) => apiClient.post<CommitmentDetail>(`/commitments/${id}/cancel`),
  history: (id: string) => apiClient.get<CommitmentHistoryEntry[]>(`/commitments/${id}/history`),
};
