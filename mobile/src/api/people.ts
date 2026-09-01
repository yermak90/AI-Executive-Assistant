import { apiClient } from "./client";
import { Person } from "../types/domain";

export interface CreatePersonInput {
  name: string;
  notes?: string | null;
}

export interface UpdatePersonInput {
  name?: string;
  notes?: string | null;
}

export const peopleApi = {
  list: () => apiClient.get<Person[]>("/people"),
  get: (id: string) => apiClient.get<Person>(`/people/${id}`),
  create: (data: CreatePersonInput) => apiClient.post<Person>("/people", data),
  update: (id: string, data: UpdatePersonInput) => apiClient.patch<Person>(`/people/${id}`, data),
};
