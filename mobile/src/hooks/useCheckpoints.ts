import { useMutation, useQueryClient } from "@tanstack/react-query";

import { checkpointsApi, AssessCheckpointInput, CreateCheckpointInput, UpdateCheckpointInput } from "../api/checkpoints";

function useInvalidateCommitment(commitmentId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["commitment", commitmentId] });
    queryClient.invalidateQueries({ queryKey: ["commitments"] });
  };
}

export function useCreateCheckpoint(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: (data: CreateCheckpointInput) => checkpointsApi.create(commitmentId, data),
    onSuccess: invalidate,
  });
}

export interface GenerateCheckpointsInput {
  leadTimeDays?: number | null;
  question?: string | null;
  reason?: string | null;
}

export function useGenerateCheckpoints(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: ({ leadTimeDays, question, reason }: GenerateCheckpointsInput) =>
      checkpointsApi.generate(commitmentId, leadTimeDays, question, reason),
    onSuccess: invalidate,
  });
}

export function useUpdateCheckpoint(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: ({ checkpointId, data }: { checkpointId: string; data: UpdateCheckpointInput }) =>
      checkpointsApi.update(checkpointId, data),
    onSuccess: invalidate,
  });
}

export function useDeleteCheckpoint(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: (checkpointId: string) => checkpointsApi.delete(checkpointId),
    onSuccess: invalidate,
  });
}

export function useAssessCheckpoint(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: ({ checkpointId, data }: { checkpointId: string; data: AssessCheckpointInput }) =>
      checkpointsApi.assess(checkpointId, data),
    onSuccess: invalidate,
  });
}

export function useSkipCheckpoint(commitmentId: string) {
  const invalidate = useInvalidateCommitment(commitmentId);
  return useMutation({
    mutationFn: (checkpointId: string) => checkpointsApi.skip(checkpointId),
    onSuccess: invalidate,
  });
}
