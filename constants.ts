import type { TierInfo, Schedule, TierId, DateRule, OperatingLogicInfo, OperatingLogicId } from './types';

export const TIER_DEFINITIONS: readonly TierInfo[] = [
  { id: '深', name: 'Deep Valley', color: 'bg-green-400', textColor: 'text-green-900' },
  { id: '谷', name: 'Valley', color: 'bg-green-200', textColor: 'text-green-800' },
  { id: '平', name: 'Flat', color: 'bg-slate-200', textColor: 'text-slate-800' },
  { id: '峰', name: 'Peak', color: 'bg-orange-200', textColor: 'text-orange-800' },
  { id: '尖', name: 'Super Peak', color: 'bg-red-300', textColor: 'text-red-800' },
];

export const TIER_MAP: Map<TierId, TierInfo> = new Map(
  TIER_DEFINITIONS.map((tier) => [tier.id, tier])
);

export const OPERATING_LOGIC_DEFINITIONS: readonly OperatingLogicInfo[] = [
  { id: '待机', name: 'Standby', color: 'bg-gray-300', textColor: 'text-gray-800' },
  { id: '充', name: 'Charge', color: 'bg-blue-300', textColor: 'text-blue-800' },
  { id: '放', name: 'Discharge', color: 'bg-yellow-300', textColor: 'text-yellow-800' },
];

export const OPERATING_LOGIC_MAP: Map<OperatingLogicId, OperatingLogicInfo> = new Map(
  OPERATING_LOGIC_DEFINITIONS.map((op) => [op.id, op])
);

export const MONTHS: readonly string[] = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

export const HOURS: readonly string[] = Array.from({ length: 24 }, (_, i) => `${i}-${i + 1}`);

export const VALID_TIER_IDS = new Set(TIER_DEFINITIONS.map(t => t.id));
export const VALID_OP_LOGIC_IDS = new Set(['待机', '充', '放']);

const INITIAL_MONTHLY_SCHEDULE_TOU: TierId[][] = [
  // Jan
  ['谷', '谷', '谷', '谷', '谷', '谷', '谷', '峰', '平', '平', '平', '平', '谷', '谷', '平', '峰', '峰', '峰', '峰', '尖', '尖', '峰', '峰', '谷'],
  // Feb
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Mar
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Apr
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // May
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Jun
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Jul
  ['平', '平', '谷', '谷', '谷', '谷', '谷', '谷', '平', '平', '平', '谷', '谷', '谷', '平', '峰', '峰', '峰', '峰', '峰', '峰', '峰', '峰', '峰'],
  // Aug
  ['谷', '谷', '谷', '谷', '谷', '谷', '谷', '谷', '平', '平', '平', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '尖', '尖', '峰', '峰', '谷'],
  // Sep
  ['平', '平', '谷', '谷', '谷', '谷', '谷', '谷', '平', '平', '平', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '峰', '峰', '峰', '峰'],
  // Oct
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Nov
  ['谷', '谷', '谷', '谷', '谷', '谷', '峰', '峰', '平', '平', '平', '谷', '谷', '谷', '平', '平', '峰', '峰', '峰', '峰', '峰', '平', '谷', '谷'],
  // Dec
  ['谷', '谷', '谷', '谷', '谷', '平', '平', '平', '平', '平', '平', '谷', '谷', '谷', '平', '峰', '峰', '峰', '峰', '峰', '峰', '峰', '谷', '谷'],
];

export const INITIAL_MONTHLY_SCHEDULE: Schedule = INITIAL_MONTHLY_SCHEDULE_TOU.map(monthSchedule =>
  monthSchedule.map(tou => ({
    tou,
    op: '待机' as OperatingLogicId
  }))
);


export const INITIAL_APP_STATE = {
  monthlySchedule: INITIAL_MONTHLY_SCHEDULE,
  dateRules: [] as DateRule[],
}