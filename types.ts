export type TierId = '谷' | '平' | '峰' | '尖' | '深';

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
    // 每月 TOU 电价，按 0-11 月索引；每项为一个 TOU→价格(元/kWh) 映射
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

// ---------------- 电价类型 ----------------
// 每个 TOU 档对应一个价格（单位：元/kWh）；支持为空（null）表示未设置
export type PriceMap = Record<TierId, number | null>;

// 12 个月的电价配置数组（索引 0-11 对应 1-12 月）
export type MonthlyTouPrices = PriceMap[];
