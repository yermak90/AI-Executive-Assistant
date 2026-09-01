import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { commitmentsApi, CommitmentListFilters, CreateCommitmentInput, UpdateCommitmentInput } from "../api/commitments";

const commitmentsKey = (filters: CommitmentListFilters = {}) => ["commitments", filters] as const;
const commitmentKey = (id: string) => ["commitment", id] as const;

export function useCommitmentsQuery(filters: CommitmentListFilters = {}) {
  return useQuery({
    queryKey: commitmentsKey(filters),
    queryFn: () => commitmentsApi.list(filters),
  });
}

export function useCommitmentQuery(id: string) {
  return useQuery({
    queryKey: commitmentKey(id),
    queryFn: () => commitmentsApi.get(id),
    enabled: !!id,
  });
}

function useInvalidateCommitments() {
  const queryClient = useQueryClient();
  return (id?: string) => {
    queryClient.invalidateQueries({ queryKey: ["commitments"] });
    if (id) queryClient.invalidateQueries({ queryKey: commitmentKey(id) });
  };
}

export function useCreateCommitment() {
  const invalidate = useInvalidateCommitments();
  return useMutation({
    mutationFn: (data: CreateCommitmentInput) => commitmentsApi.create(data),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateCommitment(id: string) {
  const invalidate = useInvalidateCommitments();
  return useMutation({
    mutationFn: (data: UpdateCommitmentInput) => commitmentsApi.update(id, data),
    onSuccess: () => invalidate(id),
  });
}

export function useCompleteCommitment(id: string) {
  const invalidate = useInvalidateCommitments();
  return useMutation({
    mutationFn: () => commitmentsApi.complete(id),
    onSuccess: () => invalidate(id),
  });
}

export function useRescheduleCommitment(id: string) {
  const invalidate = useInvalidateCommitments();
  return useMutation({
    mutationFn: (deadline: string | null) => commitmentsApi.reschedule(id, deadline),
    onSuccess: () => invalidate(id),
  });
}
