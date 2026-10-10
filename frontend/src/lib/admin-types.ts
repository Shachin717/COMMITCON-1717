export type UserRole = "ADMIN" | "HOD" | "COORDINATOR" | "FACULTY";
export type RoomType = "CLASSROOM" | "LAB" | "EXAM_HALL" | "SEMINAR_HALL";
export type RoomStatus = "ACTIVE" | "MAINTENANCE";
export type BookingStatus =
  | "PENDING"
  | "COORDINATOR_APPROVED"
  | "APPROVED"
  | "REJECTED"
  | "CANCELLED"
  | "RELOCATED";
export type RequesterType = "STUDENT" | "FACULTY";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  department_id?: number | null;
  phone?: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export interface Department {
  id: number;
  name: string;
  code: string;
  hod_approval_required: boolean;
  created_at?: string;
}

export interface Block {
  id: number;
  name: string;
  description?: string | null;
  coordinators: User[];
}

export interface Facility {
  id: number;
  name: string;
}

export interface Room {
  id: number;
  name: string;
  block_id: number;
  block?: string;
  block_name?: string;
  floor: number;
  room_type: RoomType;
  capacity: number;
  department_id?: number | null;
  status: RoomStatus;
  maintenance_note?: string | null;
  facilities: Facility[];
}

export interface CoordinatorRoom {
  id: number;
  name: string;
  block: string;
  block_id: number;
  floor: number;
  room_type: RoomType;
  capacity: number;
  status: RoomStatus;
  maintenance_note?: string | null;
}

export interface CoordinatorBlock {
  id: number;
  name: string;
  description?: string | null;
}

export interface TimeSlot {
  id: number;
  label: string;
  start_time: string;
  end_time: string;
  order: number;
}

export interface TimetableEntry {
  id: number;
  room_id: number;
  day_of_week: number;
  slot_id: number;
  department_id: number;
  subject: string;
  faculty_name: string;
}

export interface Booking {
  id: number;
  reference: string;
  room_id: number;
  date: string;
  slot_id: number;
  purpose: string;
  expected_strength: number;
  required_facilities: string[];
  status: BookingStatus;
  requires_hod_approval: boolean;
  requester_type: RequesterType;
  roll_no?: string | null;
  name: string;
  department_id: number;
  class_name?: string | null;
  phone: string;
  email: string;
  created_at: string;
  decided_by?: number | null;
  decision_note?: string | null;
  room?: any;
  slot?: any;
  department?: any;
}

export interface AuditLog {
  id: number;
  actor_id?: number | null;
  action: string;
  entity: string;
  entity_id?: string | null;
  meta: Record<string, any>;
  created_at: string;
}

export interface DailyBookingStats {
  date: string;
  day: string;
  total: number;
  confirmed: number;
  pending: number;
  rejected: number;
}

export interface RoomTypeUsageStats {
  room_type: string;
  label: string;
  room_count: number;
  booking_count: number;
}

export interface AdminOverview {
  total_rooms: number;
  in_maintenance: number;
  bookings_today: number;
  pending_bookings: number;
  utilization_rate: number;
  bookings_per_day: DailyBookingStats[];
  room_type_usage: RoomTypeUsageStats[];
  recent_activity: AuditLog[];
}

export interface BlockOverviewRoom {
  room_id: number;
  room_name: string;
  block_id: number;
  block_name: string;
  capacity: number;
  room_type: RoomType;
  is_booked: boolean;
  status: string; // FREE, BOOKED, MAINTENANCE, EXAM, CLASS
  booking_reference?: string | null;
  purpose?: string | null;
  is_my_block: boolean;
}

export interface BlockOverviewResponse {
  date: string;
  slot_id?: number | null;
  total_rooms: number;
  booked_rooms_count: number;
  free_rooms_count: number;
  other_rooms_count: number;
  rooms: BlockOverviewRoom[];
}

export interface AffectedBookingItem {
  booking_id: number;
  reference: string;
  requester_name: string;
  requester_email: string;
  date: string;
  slot_id: number;
  slot_label: string;
  purpose: string;
  expected_strength: number;
  current_room_id: number;
  current_room_name: string;
  suggested_room_id?: number | null;
  suggested_room_name?: string | null;
  suggested_block_name?: string | null;
  suggested_capacity?: number | null;
  can_relocate: boolean;
}

export interface RoomBlockPreviewResponse {
  room_id: number;
  room_name: string;
  total_affected: number;
  can_relocate_count: number;
  cannot_relocate_count: number;
  affected_bookings: AffectedBookingItem[];
}

export interface HodUpcomingBooking {
  id: number;
  reference: string;
  date: string;
  slot_label: string;
  start_time: string;
  end_time: string;
  purpose: string;
  requester_name: string;
  roll_no?: string | null;
  expected_strength: number;
  status: string;
}

export interface HodLab {
  id: number;
  name: string;
  block_name: string;
  floor: number;
  capacity: number;
  status: RoomStatus;
  maintenance_note?: string | null;
  facilities: string[];
  total_bookings: number;
  upcoming_bookings: HodUpcomingBooking[];
  today_bookings_count: number;
  utilization_rate: number;
}

export interface HodRoomOption {
  id: number;
  name: string;
  room_type: string;
  block_name: string;
  capacity: number;
}

export interface HodSummary {
  department_id: number;
  department_name: string;
  department_code: string;
  hod_approval_required: boolean;
  total_rooms: number;
  total_labs: number;
  bookings_today: number;
  pending_approvals_count: number;
  utilization_rate: number;
  bookings_per_day: DailyBookingStats[];
  room_type_usage: RoomTypeUsageStats[];
  recent_bookings: Booking[];
}

// -------------------------------------------------------------
// ALLOCATION INSIGHTS & OPTIMIZATION TYPES
// -------------------------------------------------------------

export interface AllocationWeightsConfig {
  wastage_weight?: number;
  dept_ownership_weight?: number;
  block_match_weight?: number;
  distance_weight?: number;
  split_penalty_weight?: number;
}

export interface AllocationRequestItem {
  id?: string | number;
  date: string;
  slot_id: number;
  expected_strength: number;
  room_type?: RoomType | string;
  required_facilities?: string[];
  department_id?: number | null;
  preferred_block_id?: number | null;
  preferred_floor?: number | null;
  roll_no?: string | null;
  name?: string | null;
  email?: string | null;
  class_name?: string | null;
  phone?: string | null;
  purpose?: string | null;
  created_at?: string | null;
}

export interface AllocationAssignment {
  request_id: string | number;
  date: string;
  slot_id: number;
  expected_strength: number;
  allocated: boolean;
  room_id?: number | null;
  room_name?: string | null;
  block_id?: number | null;
  block_name?: string | null;
  floor?: number | null;
  capacity?: number | null;
  reason_if_unallocated?: string | null;
  cost?: number | null;
}

export interface AllocationMetricsResponse {
  total_requests: number;
  allocated_count: number;
  unallocated_count: number;
  allocation_rate_pct: number;
  seat_utilization_pct: number;
  average_wastage_pct: number;
  facility_match_pct: number;
  preference_satisfaction_pct: number;
  conflict_count: number;
  block_switch_count: number;
  efficiency_score: number;
  weights_breakdown: Record<string, number>;
}

export interface SimulationResult {
  allocations: AllocationAssignment[];
  metrics: AllocationMetricsResponse;
}

export interface AllocationComparison {
  efficiency_score_delta: number;
  seat_utilization_delta_pct: number;
  average_wastage_reduction_pct: number;
  facility_match_delta_pct: number;
  preference_satisfaction_delta_pct: number;
  unallocated_delta: number;
}

export interface WastageBucket {
  bin: string;
  label: string;
  baseline: number;
  optimized: number;
  baseline_pct: number;
  optimized_pct: number;
}

export interface HeatmapCellPlan {
  allocated: boolean;
  strength: number;
  utilization_pct: number;
  requester?: string | null;
  purpose?: string | null;
  request_id?: string | null;
}

export interface HeatmapSlotCell {
  slot_id: number;
  slot_label: string;
  time_range: string;
  baseline: HeatmapCellPlan;
  optimized: HeatmapCellPlan;
}

export interface HeatmapRoomRow {
  room_id: number;
  room_name: string;
  block_id: number;
  block_name: string;
  floor: number;
  capacity: number;
  room_type: string;
  status: string;
  facilities: string[];
  slots: HeatmapSlotCell[];
}

export interface MaintenanceRoomItem {
  id: number;
  name: string;
  block_id: number;
  block_name: string;
  floor: number;
  capacity: number;
  room_type: string;
  maintenance_note?: string | null;
  affected_future_bookings: number;
}

export interface AllocationSimulateResponse {
  date_range: { start_date?: string | null; end_date?: string | null };
  total_requests: number;
  baseline: SimulationResult;
  optimized: SimulationResult;
  comparison: AllocationComparison;
  wastage_distribution?: WastageBucket[];
  heatmap_matrix?: HeatmapRoomRow[];
  maintenance_rooms?: MaintenanceRoomItem[];
}

export interface AllocationApplyRequest {
  start_date?: string;
  end_date?: string;
  use_existing_bookings?: boolean;
  requests?: AllocationRequestItem[];
  weights?: AllocationWeightsConfig;
}

export interface AllocationApplyResponse {
  status: string;
  total_requests: number;
  applied_count: number;
  unallocated_count: number;
  metrics: AllocationMetricsResponse;
  message: string;
}

export interface AllocationHistoryItem {
  id: number;
  created_at: string;
  status: string;
  date_from?: string | null;
  date_to?: string | null;
  total_requests: number;
  baseline_metrics: Record<string, any>;
  optimized_metrics: Record<string, any>;
  execution_time_ms: number;
}

export interface ReallocationRequest {
  room_id: number;
  reason: string;
  start_date?: string;
  end_date?: string;
  slot_id?: number;
  send_notifications?: boolean;
  preview_only?: boolean;
}

export interface RelocatedBookingSummary {
  booking_id: number;
  reference: string;
  requester_name: string;
  requester_email: string;
  date: string;
  slot_id: number;
  original_room_id: number;
  original_room_name: string;
  replacement_room_id?: number | null;
  replacement_room_name?: string | null;
  replacement_block_name?: string | null;
  status: string;
  email_sent: boolean;
}

export interface ReallocationResponse {
  affected_count: number;
  relocated_count: number;
  unresolved_count: number;
  relocated_bookings: RelocatedBookingSummary[];
  message: string;
}


export interface HodPendingApprovalsResponse {
  hod_approval_required: boolean;
  pending_bookings: Booking[];
  message?: string | null;
}

export interface BlockedRoomSummary {
  id: number;
  name: string;
  block: string;
  block_id: number;
  floor: number;
  room_type: string;
  type: string;
  capacity: number;
}

export interface BlockedRoomItem {
  id: number;
  is_indefinite: boolean;
  room_id: number;
  room: BlockedRoomSummary;
  date?: string | null;
  slot_id?: number | null;
  slot_label: string;
  reason: string;
  note?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  released_at?: string | null;
  released_by?: string | null;
  is_released: boolean;
  status: "ACTIVE" | "UPCOMING" | "PAST" | "RELEASED" | string;
}

export interface BlockedRoomsSummaryCounts {
  currently_blocked: number;
  upcoming_blocks: number;
  maintenance_rooms: number;
}

export interface BlockedRoomsResponse {
  items: BlockedRoomItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  summary: BlockedRoomsSummaryCounts;
}



