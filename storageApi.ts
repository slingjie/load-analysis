import type {
  BackendStorageCyclesResponse,
  BackendStorageCurvesResponse,
  MonthlyTouPrices,
  CleaningAnalysisResponse,
  CleaningConfigRequest,
  CleaningResultResponse,
} from './types';

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
  // 可选：直接复用“负荷分析”页面上传后的点数组（程序互通）
  // 若提供 points，可不传 file；后端将优先使用 points。
  points?: { timestamp: string; load_kwh: number }[];
}

export const computeStorageCycles = async (
  file: File | null,
  payload: StorageParamsPayload,
): Promise<BackendStorageCyclesResponse> => {
  const formData = new FormData();
  if (file) formData.append('file', file);
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

// 带上传进度与取消能力的版本（主要针对开始测算按钮上传大文件时的交互优化）
export const computeStorageCyclesWithProgress = (
  file: File | null,
  payload: StorageParamsPayload,
  onUploadProgress?: (loaded: number, total: number) => void,
): { promise: Promise<BackendStorageCyclesResponse>; abort: () => void } => {
  const formData = new FormData();
  if (file) formData.append('file', file);
  formData.append('payload', JSON.stringify(payload));
  const url = `${BASE_URL}/api/storage/cycles`;
  console.debug('[storageApi] XHR POST cycles', url, { base: BASE_URL, hasFile: !!file });

  const xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);

  if (onUploadProgress) {
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onUploadProgress(e.loaded, e.total);
      }
    };
  }

  const promise = new Promise<BackendStorageCyclesResponse>((resolve, reject) => {
    xhr.onerror = () => {
      reject(new Error('网络错误，无法提交测算请求。'));
    };
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 4) {
        const contentType = xhr.getResponseHeader('content-type') || '';
        let result: any = null;
        let rawText: string | null = null;
        try {
          rawText = xhr.responseText;
          if (contentType.includes('application/json')) {
            result = JSON.parse(rawText);
          } else {
            try { result = rawText ? JSON.parse(rawText) : null; } catch { /* ignore */ }
          }
        } catch { /* ignore parse */ }

        if (xhr.status < 200 || xhr.status >= 300) {
          const detail = result?.detail || rawText || `${xhr.status} ${xhr.statusText}` || '服务器处理失败，请稍后重试。';
          console.error('[storageApi] computeStorageCyclesWithProgress failed', {
            url,
            status: xhr.status,
            statusText: xhr.statusText,
            detail,
            payload,
            rawText,
          });
          reject(new Error(detail));
          return;
        }
        resolve(result as BackendStorageCyclesResponse);
      }
    };
    try {
      xhr.send(formData);
    } catch (err) {
      reject(err instanceof Error ? err : new Error(String(err)));
    }
  });

  return {
    promise,
    abort: () => { try { xhr.abort(); } catch { /* ignore */ } },
  };
};

export const fetchStorageCurves = async (
  payload: StorageParamsPayload,
  date: string,
): Promise<BackendStorageCurvesResponse> => {
  const url = `${BASE_URL}/api/storage/cycles/curves`;
  console.debug('[storageApi] POST', url, { base: BASE_URL, date });

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload, date }),
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
    const detail = result?.detail || rawText || `${response.status} ${response.statusText}` || '获取储能收益曲线失败，请稍后重试。';
    console.error('[storageApi] fetchStorageCurves failed', {
      url,
      status: response.status,
      statusText: response.statusText,
      detail,
      payload,
      rawText,
    });
    throw new Error(detail);
  }

  return result as BackendStorageCurvesResponse;
};

// ===================== 数据清洗相关 API =====================

/**
 * 分析上传的数据，检测零值、负值时段，返回清洗建议
 */
export const analyzeDataForCleaning = async (
  file: File,
): Promise<CleaningAnalysisResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${BASE_URL}/api/cleaning/analyze`;
  console.debug('[storageApi] POST cleaning/analyze', url);

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
    const detail = result?.detail || rawText || `${response.status} ${response.statusText}` || '分析数据失败';
    console.error('[storageApi] analyzeDataForCleaning failed', { url, status: response.status, detail });
    throw new Error(detail);
  }

  return result as CleaningAnalysisResponse;
};

/**
 * 应用用户确认的清洗配置，返回清洗后的数据
 */
export const applyDataCleaning = async (
  file: File,
  config: CleaningConfigRequest,
): Promise<CleaningResultResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  // 后端期望 payload 字段包含 config 对象
  formData.append('payload', JSON.stringify({ config }));

  const url = `${BASE_URL}/api/cleaning/apply`;
  console.debug('[storageApi] POST cleaning/apply', url);

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
    const detail = result?.detail || rawText || `${response.status} ${response.statusText}` || '数据清洗失败';
    console.error('[storageApi] applyDataCleaning failed', { url, status: response.status, detail });
    throw new Error(detail);
  }

  return result as CleaningResultResponse;
};
