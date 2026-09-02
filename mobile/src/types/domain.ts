export type Direction = "OWED_TO_ME" | "I_OWE" | "TEAM";
export type CommitmentStatus = "ACTIVE" | "COMPLETED" | "CANCELLED";
export type SourceType = "MANUAL" | "MEETING" | "VOICE_NOTE" | "EMAIL" | "CHAT";
export type HistoryEventType =
  | "CREATED"
  | "UPDATED"
  | "DEADLINE_CHANGED"
  | "COMPLETED"
  | "CANCELLED"
  | "CHECKPOINT_CREATED"
  | "CHECKPOINT_UPDATED"
  | "CHECKPOINT_RESCHEDULED"
  | "CHECKPOINT_COMPLETED"
  | "CHECKPOINT_SKIPPED"
  | "CHECKPOINT_ASSESSED_ON_TRACK"
  | "CHECKPOINT_ASSESSED_AT_RISK"
  | "CHECKPOINT_ASSESSED_BLOCKED"
  | "CHECKPOINT_AUTO_RECALCULATED";

export type Bucket = "overdue" | "today" | "tomorrow" | "later" | "no_deadline";
export type ControlHealth = "ON_TRACK" | "CHECK_DUE" | "AT_RISK" | "BLOCKED";

export type CheckpointStatus = "PENDING" | "COMPLETED" | "SKIPPED";
export type CheckpointAssessment = "UNKNOWN" | "ON_TRACK" | "AT_RISK" | "BLOCKED";
export type CheckpointSourceType = "MANUAL" | "AUTO_RULE" | "AI_SUGGESTED";

export const DIRECTION_LABELS: Record<Direction, string> = {
  OWED_TO_ME: "Мне должны",
  I_OWE: "Я должен",
  TEAM: "Команда",
};

export const DIRECTIONS: Direction[] = ["OWED_TO_ME", "I_OWE", "TEAM"];

export const BUCKET_LABELS: Record<Bucket, string> = {
  overdue: "Просрочено",
  today: "Сегодня",
  tomorrow: "Завтра",
  later: "Позже",
  no_deadline: "Без срока",
};

export const BUCKETS: Bucket[] = ["overdue", "today", "tomorrow", "later", "no_deadline"];

export interface PersonSummary {
  id: string;
  name: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
}

export interface Person {
  id: string;
  name: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  active_commitments_count: number;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  active_commitments_count: number;
  overdue_commitments_count: number;
}

export interface CommitmentHistoryEntry {
  id: string;
  event_type: HistoryEventType;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}

export interface Checkpoint {
  id: string;
  commitment_id: string;
  title: string;
  question: string | null;
  reason: string | null;
  scheduled_at: string;
  status: CheckpointStatus;
  assessment: CheckpointAssessment;
  source_type: CheckpointSourceType;
  action_note: string | null;
  assessment_note: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  skipped_at: string | null;
  assessed_at: string | null;
}

export interface Commitment {
  id: string;
  title: string;
  description: string | null;
  direction: Direction;
  status: CommitmentStatus;
  source_type: SourceType;
  source_text: string | null;
  deadline: string | null;
  lead_time_days: number | null;
  is_overdue: boolean;
  bucket: Bucket | null;
  control_health: ControlHealth;
  person: PersonSummary | null;
  counterparty: PersonSummary | null;
  project: ProjectSummary | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
}

export interface CommitmentDetail extends Commitment {
  history: CommitmentHistoryEntry[];
  checkpoints: Checkpoint[];
}
