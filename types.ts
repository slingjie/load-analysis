export type TierId = '尖' | '峰' | '平' | '谷' | '深';

export type OperatingLogicId = '待机' | '充' | '放';

export interface CellData {
  tou: TierId;
  op: OperatingLogicId;
}

export type Schedule = CellData[][];

export interface TierInfo {
  id: TierId;
  name: string;
  color: string;
  textColor: string;
}

export interface OperatingLogicInfo {
  id: OperatingLogicId;
  name: string;
  color: string;
  textColor: string;
}

export interface CellPosition {
  monthIndex: number;
  hourIndex: number;
}

export interface DateRule {
  id: string;
  name: string;
  startDate: string; // YYYY-MM-DD
  endDate: string; // YYYY-MM-DD
  schedule: CellData[]; // 24-hour schedule
}

export interface Configuration {
  id: string;
  name: string;
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    // 每月 TOU 电价（下标 0-11 对应 1-12 月），每项为一个 TOU->价格(元/kWh) 映射
    prices: MonthlyTouPrices;
  };
}

export interface BackendCleanedLoadPoint {
  timestamp: string;
  load_kwh: number;
}

export interface BackendMissingHoursByMonth {
  month: string;  // YYYY-MM 格式
  missing_days: number;
  missing_hours: number;
}

export interface BackendMissingSummary {
  missing_days: string[];
  missing_hours_by_month: BackendMissingHoursByMonth[];
  summary: {
    total_missing_days: number;
    total_missing_hours: number;
  };
}

export type AnomalyKind = 'null' | 'zero' | 'negative';

export interface BackendValueAnomaly {
  kind: AnomalyKind;
  count: number;
  ratio: number;
  samples: string[];
}

export interface BackendContinuousZeroSpan {
  start: string;
  end: string;
  length_hours: number;
}

export interface BackendQualityReport {
  missing: BackendMissingSummary;
  anomalies: BackendValueAnomaly[];
  continuous_zero_spans: BackendContinuousZeroSpan[];
}

export interface BackendAnalysisMeta {
  source_interval_minutes: number;
  total_records: number;
  start: string | null;
  end: string | null;
}

export interface BackendLoadAnalysisResponse {
  cleaned_points: BackendCleanedLoadPoint[];
  report: BackendQualityReport;
  meta: BackendAnalysisMeta;
}

// ---------------- 电价相关 ----------------
// 每个 TOU 段对应一个价格（单位：元/kWh），支持为空 null 表示未配置
export type PriceMap = Record<TierId, number | null>;

// 12 个月的电价配置（下标 0-11 对应 1-12 月）
export type MonthlyTouPrices = PriceMap[];

// ---------------- 储能次数 / 收益相关后端响应 ----------------
export interface BackendStorageProfit {
  revenue: number;
  cost: number;
  profit: number;
  discharge_energy_kwh: number;
  charge_energy_kwh: number;
  profit_per_kwh: number;
}

export interface BackendStorageProfitWithFormulas {
  main?: BackendStorageProfit | null;
  physics?: BackendStorageProfit | null;
  sample?: BackendStorageProfit | null;
}

export interface BackendStorageCyclesDay {
  date: string;    // YYYY-MM-DD
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}

export interface BackendStorageCyclesMonth {
  year_month: string; // YYYY-MM
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}

export interface BackendStorageCyclesYear {
  year: number;  // 0 表示服务端未确定年份
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}

export interface BackendStorageCurvesPoint {
  timestamp: string;
  load_kw: number;
}

export interface BackendStorageCurvesSummary {
  max_demand_original_kw: number;
  max_demand_new_kw: number;
  max_demand_reduction_kw: number;
  max_demand_reduction_ratio: number;
  energy_by_tier_original: Record<TierId, number>;
  energy_by_tier_new: Record<TierId, number>;
  bill_by_tier_original: Record<TierId, number>;
  bill_by_tier_new: Record<TierId, number>;
  profit_day_main?: BackendStorageProfit | null;
}

export interface BackendStorageCurvesResponse {
  date: string;
  points_original: BackendStorageCurvesPoint[];
  points_with_storage: BackendStorageCurvesPoint[];
  summary: BackendStorageCurvesSummary;
}

// 尖段放电占比汇总
export interface BackendTipDischargeSummary {
  avg_tip_load_kw: number;            // 尖段平均负荷 kW
  tip_hours: number;                  // 尖段总时长 小时
  discharge_count: number;            // 当前时长内放电次数
  capacity_kwh?: number;              // 当前假设容量 kWh（后端未返回时前端可用配置值兜底）
  energy_need_kwh?: number;           // 尖段能量需求 kWh（未给出时可用 avg * hours 估算）
  ratio?: number;                     // 直接给出的满足率 0-1，可选
  tip_points?: Array<{ time: string; load_kw: number }>; // 尖段代表性点位（供前端小图）
  note?: string;                      // 说明 / 备注
  day_stats?: Array<{ date: string; avg_load_kw: number; tip_hours: number; energy_need_kwh: number; discharge_count: number; ratio: number }>;
  month_stats?: Array<{ month: number; ratio: number }>;
}

export interface BackendStorageQC {
  notes: string[];
  missing_prices: number;
  missing_points: number;
  merged_segments: number;
  limit_mode?: 'monthly_demand_max' | 'transformer_capacity' | null;
  transformer_limit_kw?: number | null;
  monthly_demand_max: { year_month: string; max_kw: number }[];
}

// Window_debug 按月汇总（C1/C2 + charge/discharge 分段）
export interface BackendStorageWindowMonthSummary {
  year_month: string;                // YYYY-MM
  first_charge_cycles: number;       // C1 + charge 等效充电次数之和
  first_discharge_cycles: number;    // C1 + discharge 等效放电次数之和
  second_charge_cycles: number;      // C2 + charge 等效充电次数之和
  second_discharge_cycles: number;   // C2 + discharge 等效放电次数之和
}

export interface BackendStorageCyclesResponse {
  year: BackendStorageCyclesYear;
  months: BackendStorageCyclesMonth[];
  days: BackendStorageCyclesDay[];
  qc: BackendStorageQC;
  excel_path: string | null;
  // 可选：基于 Window_debug 聚合后的按月分解
  window_month_summary?: BackendStorageWindowMonthSummary[];
  // 可选：尖段放电占比分析（前端展示卡片）
  tip_discharge_summary?: BackendTipDischargeSummary;
}
