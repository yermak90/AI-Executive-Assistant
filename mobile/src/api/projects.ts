import { apiClient } from "./client";
import { Project } from "../types/domain";

export interface CreateProjectInput {
  name: string;
  description?: string | null;
}

export interface UpdateProjectInput {
  name?: string;
  description?: string | null;
  is_active?: boolean;
}

export const projectsApi = {
  list: () => apiClient.get<Project[]>("/projects"),
  get: (id: string) => apiClient.get<Project>(`/projects/${id}`),
  create: (data: CreateProjectInput) => apiClient.post<Project>("/projects", data),
  update: (id: string, data: UpdateProjectInput) => apiClient.patch<Project>(`/projects/${id}`, data),
};
