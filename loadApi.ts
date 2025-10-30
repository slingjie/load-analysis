import type { BackendLoadAnalysisResponse } from './types';

const BASE_URL = (import.meta.env.VITE_BACKEND_BASE_URL || '').replace(/\/$/, '');

export const analyzeLoadFile = async (file: File): Promise<BackendLoadAnalysisResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${BASE_URL}/api/load/analyze`;
  console.debug('[loadApi] POST', url, { base: BASE_URL });

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  const contentType = response.headers.get('content-type') || '';
  let payload: any = null;
  let rawText: string | null = null;
  try {
    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => null);
    } else {
      rawText = await response.text().catch(() => null);
      try { payload = rawText ? JSON.parse(rawText) : null; } catch { /* ignore */ }
    }
  } catch (e) {
    // ignore parse errors
  }

  if (!response.ok) {
    const detail = payload?.detail || rawText || `${response.status} ${response.statusText}` || '服务器处理失败，请稍后重试。';
    console.error('[loadApi] analyzeLoadFile failed', {
      url,
      status: response.status,
      statusText: response.statusText,
      detail,
      payload,
      rawText,
    });
    throw new Error(detail);
  }

  return payload as BackendLoadAnalysisResponse;
};
