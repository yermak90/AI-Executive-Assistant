import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { projectsApi, CreateProjectInput, UpdateProjectInput } from "../api/projects";

export function useProjectsQuery() {
  return useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
}

export function useProjectQuery(id: string) {
  return useQuery({ queryKey: ["project", id], queryFn: () => projectsApi.get(id), enabled: !!id });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProjectInput) => projectsApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateProjectInput) => projectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["project", id] });
    },
  });
}
