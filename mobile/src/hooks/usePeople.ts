import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { peopleApi, CreatePersonInput, UpdatePersonInput } from "../api/people";

export function usePeopleQuery() {
  return useQuery({ queryKey: ["people"], queryFn: peopleApi.list });
}

export function usePersonQuery(id: string) {
  return useQuery({ queryKey: ["person", id], queryFn: () => peopleApi.get(id), enabled: !!id });
}

export function useCreatePerson() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePersonInput) => peopleApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["people"] }),
  });
}

export function useUpdatePerson(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdatePersonInput) => peopleApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["people"] });
      queryClient.invalidateQueries({ queryKey: ["person", id] });
    },
  });
}
