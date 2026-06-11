export type LifecycleState =
  | "queued"
  | "sent"
  | "delivered"
  | "opened"
  | "read"
  | "clicked"
  | "failed";

export const FUNNEL_ORDER: LifecycleState[] = [
  "sent",
  "delivered",
  "opened",
  "read",
  "clicked",
];

export interface CustomerStats {
  total: number;
  by_stage: Record<string, number>;
  by_channel: Record<string, number>;
}

export interface PreviewSample {
  name: string;
  email: string;
  city: string;
  lifecycle_stage: string;
}

export interface SegmentPreview {
  count: number;
  total: number;
  sample: PreviewSample[];
}

export interface Proposal {
  goal: string;
  segment: Record<string, unknown>;
  segment_human: string;
  channel: string;
  message: string;
  reasoning: string;
  source: string;
  warnings: string[];
  preview: SegmentPreview;
}

export interface Campaign {
  id: string;
  name: string;
  channel: string;
  message: string;
  status: string;
  recipient_count: number;
  segment: Record<string, unknown>;
}

export interface Funnel {
  queued: number;
  sent: number;
  delivered: number;
  opened: number;
  read: number;
  clicked: number;
  failed: number;
  total: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  failure_rate: number;
}

export interface CampaignStats {
  campaign_id: string;
  status: string;
  recipient_count: number;
  funnel: Funnel;
  attributed_orders: number;
}

export interface Communication {
  id: string;
  recipient: string;
  channel: string;
  state: LifecycleState;
  failed: boolean;
  failure_reason: string | null;
  updated_at: string | null;
}

export interface FeedEvent {
  type: string;
  communication_id: string;
  campaign_id: string;
  channel: string;
  state: LifecycleState;
  failed: boolean;
  failure_reason: string | null;
  at: string;
}

export interface DeadLetter {
  id: number;
  kind: string;
  error: string;
  attempts: number;
  created_at: string | null;
  payload: Record<string, unknown>;
}
