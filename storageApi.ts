import type { BackendStorageCyclesResponse, MonthlyTouPrices } from './types';

const BASE_URL = (import.meta.env.VITE_BACKEND_BASE_URL || '').replace(/\/$/, '');

export interface StorageParamsPayload {
  storage: {
    capacity_kwh: number;
    c_rate: number;
    single_side_efficiency: number; // η
    depth_of_discharge: number;     // DOD
    soc_min?: number;
    soc_max?: number;
    initial_soc?: number;
    reserve_charge_kw?: number;
    reserve_discharge_kw?: number;
    metering_mode: 'monthly_demand_max' | 'transformer_capacity';
    transformer_capacity_kva?: number;
    transformer_power_factor?: number;
    calc_style?: 'window_avg';
    energy_formula?: 'physics' | 'sample';
    soc_carry_over?: boolean;
    merge_threshold_minutes?: number;
  };
  strategySource: {
    monthlySchedule: any[]; // 24h * 12 months，复用现有结构
    dateRules: any[];       // 复用现有结构
  };
  monthlyTouPrices: MonthlyTouPrices;
}

export const computeStorageCycles = async (
  file: File,
  payload: StorageParamsPayload,
): Promise<BackendStorageCyclesResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('payload', JSON.stringify(payload));

  const url = `${BASE_URL}/api/storage/cycles`;
  console.debug('[storageApi] POST', url, { base: BASE_URL });

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  const contentType = response.headers.get('content-type') || '';
  let result: any = null;
  let rawText: string | null = null;
  try {
    if (contentType.includes('application/json')) {
      result = await response.json().catch(() => null);
    } else {
      rawText = await response.text().catch(() => null);
      try { result = rawText ? JSON.parse(rawText) : null; } catch { /* ignore */ }
    }
  } catch (e) {
    // ignore parse errors
  }

  if (!response.ok) {
    const detail = result?.detail || rawText || `${response.status} ${response.statusText}` || '服务器处理失败，请稍后重试。';
    console.error('[storageApi] computeStorageCycles failed', {
      url,
      status: response.status,
      statusText: response.statusText,
      detail,
      payload,
      rawText,
    });
    throw new Error(detail);
  }

  return result as BackendStorageCyclesResponse;
};

