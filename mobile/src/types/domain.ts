export type Direction = "OWED_TO_ME" | "I_OWE" | "TEAM";
export type CommitmentStatus = "ACTIVE" | "COMPLETED" | "CANCELLED";
export type SourceType = "MANUAL" | "MEETING" | "VOICE_NOTE" | "EMAIL" | "CHAT";
export type HistoryEventType = "CREATED" | "DEADLINE_CHANGED" | "COMPLETED" | "CANCELLED" | "UPDATED";

export const DIRECTION_LABELS: Record<Direction, string> = {
  OWED_TO_ME: "Мне должны",
  I_OWE: "Я должен",
  TEAM: "Команда",
};

export const DIRECTIONS: Direction[] = ["OWED_TO_ME", "I_OWE", "TEAM"];

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

export interface Commitment {
  id: string;
  title: string;
  description: string | null;
  direction: Direction;
  status: CommitmentStatus;
  source_type: SourceType;
  deadline: string | null;
  is_overdue: boolean;
  person: PersonSummary | null;
  project: ProjectSummary | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
}

export interface CommitmentDetail extends Commitment {
  history: CommitmentHistoryEntry[];
}
