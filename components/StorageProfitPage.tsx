import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  Schedule,
  DateRule,
  MonthlyTouPrices,
  BackendStorageCyclesResponse,
  BackendStorageCurvesResponse,
  BackendStorageProfitWithFormulas,
} from '../types';
import type { LoadDataPoint } from '../utils';
import { fetchStorageCurves, computeStorageCycles, type StorageParamsPayload } from '../storageApi';
import { EChartTimeSeries } from './EChartTimeSeries';

// 复用 ECharts 按需加载逻辑（与 EChartTimeSeries 保持一致）
const loadECharts = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    const w = window as any;
    if (w.echarts) return resolve(w.echarts);
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js';
    script.async = true;
    script.onload = () => resolve(w.echarts);
    script.onerror = (e) => reject(e);
    document.head.appendChild(script);
  });
};

interface StorageProfitPageProps {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    prices: MonthlyTouPrices;
  };
  externalCleanedData?: LoadDataPoint[] | null;
  // 预留：可由 StorageCycles 页将最近一次结果透传进来，用于展示年度汇总
  storageCyclesResult?: BackendStorageCyclesResponse | null;
  // 预留：可由 StorageCycles 页透传最近一次请求的 payload，使收益与曲线与其保持一致
  storageCyclesPayload?: StorageParamsPayload | null;
  // 若从 StorageCycles 页触发跳转，可指定日期并通知消费完毕
  selectedDateFromCycles?: string | null;
  onSelectedDateConsumed?: () => void;
}

const buildDefaultStoragePayload = (
  scheduleData: StorageProfitPageProps['scheduleData'],
  externalCleanedData?: LoadDataPoint[] | null,
): StorageParamsPayload | null => {
  if (!externalCleanedData || !externalCleanedData.length) {
    return null;
  }

  const sorted = externalCleanedData
    .slice()
    .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const points = sorted.map((p) => ({
    // 后端 parse_points_series 使用 pandas.to_datetime 解析，ISO8601 字符串可以正确解析
    timestamp: p.timestamp.toISOString(),
    load_kwh: Number(p.load),
  }));

  const storageDefaults: StorageParamsPayload['storage'] = {
    capacity_kwh: 5000,
    c_rate: 0.5,
    single_side_efficiency: 0.92,
    depth_of_discharge: 0.9,
    soc_min: 0.05,
    soc_max: 0.95,
    initial_soc: undefined,
    reserve_charge_kw: 0,
    reserve_discharge_kw: 0,
    metering_mode: 'monthly_demand_max',
    transformer_capacity_kva: 10000,
    transformer_power_factor: 0.9,
    calc_style: 'window_avg',
    energy_formula: 'physics',
    soc_carry_over: false,
    merge_threshold_minutes: 30,
  };

  return {
    storage: storageDefaults,
    strategySource: {
      monthlySchedule: scheduleData.monthlySchedule,
      dateRules: scheduleData.dateRules,
    },
    monthlyTouPrices: scheduleData.prices,
    points,
  };
};

export const StorageProfitPage: React.FC<StorageProfitPageProps> = ({
  scheduleData,
  externalCleanedData,
  storageCyclesResult,
  storageCyclesPayload,
  selectedDateFromCycles,
  onSelectedDateConsumed,
}) => {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [curvesData, setCurvesData] = useState<BackendStorageCurvesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 若一开始已有 StorageCycles 页传入的结果，优先复用结果；重新加载时再回落为本页请求
  const [cyclesResult, setCyclesResult] = useState<BackendStorageCyclesResponse | null>(storageCyclesResult ?? null);

  // 如果未透传 StorageCycles 结果，则在本页自动拉取一次 cycles + profit 结果
  useEffect(() => {
    let cancelled = false;

    // 如果已经传入结果，直接使用
    if (storageCyclesResult) {
      setCyclesResult(storageCyclesResult);
      return () => { cancelled = true; };
    }

    const payload = buildDefaultStoragePayload(scheduleData, externalCleanedData);
    if (!payload) {
      setCyclesResult(null);
      return () => { cancelled = true; };
    }

    (async () => {
      try {
        const resp = await computeStorageCycles(null, payload);
        if (!cancelled) {
          setCyclesResult(resp);
        }
      } catch (e) {
        // 若无法计算 cycles，本页只展示曲线对比入口，提示用户重新上传或配置
        if (!cancelled) {
          setCyclesResult(null);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [scheduleData, externalCleanedData, storageCyclesResult]);

  // 可选：从 cycles 结果中获取可选日期；否则回退到 externalCleanedData 的日期集合
  const availableDates = useMemo(() => {
    if (cyclesResult?.days?.length) {
      return cyclesResult.days
        .map((d) => d.date)
        .filter(Boolean)
        .sort();
    }
    if (externalCleanedData && externalCleanedData.length) {
      const dateSet = new Set<string>();
      externalCleanedData.forEach((p) => {
        dateSet.add(p.timestamp.toISOString().slice(0, 10));
      });
      return Array.from(dateSet).sort();
    }
    return [];
  }, [cyclesResult, externalCleanedData]);

  // 初始选中第一天
  useEffect(() => {
    if (!selectedDate && availableDates.length > 0) {
      setSelectedDate(availableDates[0]);
    }
  }, [availableDates, selectedDate]);

  // 支持外部跳转指定日期
  useEffect(() => {
    if (selectedDateFromCycles) {
      setSelectedDate(selectedDateFromCycles);
      onSelectedDateConsumed?.();
    }
  }, [selectedDateFromCycles, onSelectedDateConsumed]);

  const handleFetchCurves = useCallback(async () => {
    if (!selectedDate) return;
    const payload =
      storageCyclesPayload ?? buildDefaultStoragePayload(scheduleData, externalCleanedData);
    if (!payload) {
      setError('当前没有可用的负荷数据，请先在 Load Analysis 页上传并清洗负荷。');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetchStorageCurves(payload, selectedDate);
      setCurvesData(res);
    } catch (e: any) {
      setCurvesData(null);
      setError(e?.message || '获取储能收益与负荷对比数据失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }, [externalCleanedData, scheduleData, selectedDate, storageCyclesPayload]);

  const selectedDayProfitMain: BackendStorageProfitWithFormulas['main'] | null = useMemo(() => {
    if (!cyclesResult || !selectedDate) return null;
    const day = cyclesResult.days.find((d) => d.date === selectedDate);
    return (day?.profit?.main) ?? null;
  }, [cyclesResult, selectedDate]);

  const chartOriginalData = useMemo(() => {
    if (!curvesData) return [];
    return curvesData.points_original.map((pt) => ({
      x: new Date(pt.timestamp),
      y: pt.load_kw,
    }));
  }, [curvesData]);

  const chartWithStorageData = useMemo(() => {
    if (!curvesData) return [];
    return curvesData.points_with_storage.map((pt) => ({
      x: new Date(pt.timestamp),
      y: pt.load_kw,
    }));
  }, [curvesData]);

  const yearProfitMain = cyclesResult?.year?.profit?.main ?? null;

  const monthProfitMain: BackendStorageProfitWithFormulas['main'] | null = useMemo(() => {
    if (!cyclesResult || !selectedDate) return null;
    const ym = selectedDate.slice(0, 7);
    const m = cyclesResult.months.find((it) => it.year_month === ym);
    return (m?.profit?.main) ?? null;
  }, [cyclesResult, selectedDate]);

  // 在同一张图中展示两条曲线，并支持开关控制显示/隐藏
  const combinedChartRef = useRef<HTMLDivElement | null>(null);
  const [showOriginal, setShowOriginal] = useState(true);
  const [showWithStorage, setShowWithStorage] = useState(true);

  useEffect(() => {
    if (!curvesData || !combinedChartRef.current) return;

    let disposed = false;
    let chart: any = null;

    loadECharts()
      .then((echarts: any) => {
        if (disposed || !combinedChartRef.current) return;

        chart = echarts.init(combinedChartRef.current);

        const baseSeries: any[] = [];
        if (showOriginal) {
          baseSeries.push({
            name: '原始负荷曲线',
            type: 'line',
            data: chartOriginalData.map(p => [p.x.getTime(), p.y]),
            smooth: true,
            showSymbol: false,
            lineStyle: { color: 'rgb(148,163,184)', width: 1.8 },
            areaStyle: { opacity: 0.08, color: 'rgba(148,163,184,0.35)' },
          });
        }
        if (showWithStorage) {
          baseSeries.push({
            name: '引入储能后的负荷曲线',
            type: 'line',
            data: chartWithStorageData.map(p => [p.x.getTime(), p.y]),
            smooth: true,
            showSymbol: false,
            lineStyle: { color: 'rgb(59,130,246)', width: 1.8 },
            areaStyle: { opacity: 0.10, color: 'rgba(59,130,246,0.35)' },
          });
        }

        const option = {
          tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'line' },
            valueFormatter: (val: any) => (val == null || Number.isNaN(Number(val)) ? '-' : `${Number(val).toFixed(2)} kW`),
          },
          legend: {
            top: 0,
          },
          grid: { left: 50, right: 20, top: 40, bottom: 40 },
          xAxis: {
            type: 'time',
            axisLabel: {
              formatter: (value: number) => {
                const d = new Date(value);
                const h = `${d.getHours()}`.padStart(2, '0');
                const m = `${d.getMinutes()}`.padStart(2, '0');
                return `${h}:${m}`;
              },
            },
            axisLine: { lineStyle: { color: '#cbd5f5' } },
            splitLine: { show: false },
          },
          yAxis: {
            type: 'value',
            name: 'kW',
            axisLine: { lineStyle: { color: '#cbd5f5' } },
            splitLine: { show: true, lineStyle: { color: '#e5e7eb', type: 'dashed' } },
          },
          series: baseSeries,
        };

        chart.setOption(option, true);
        const onResize = () => {
          try {
            chart && chart.resize();
          } catch {
            // ignore
          }
        };
        window.addEventListener('resize', onResize);
        (chart as any)._cleanup = onResize;
      })
      .catch((e) => {
        console.error('[StorageProfitPage] 加载 ECharts 失败', e);
      });

    return () => {
      disposed = true;
      try {
        const c: any = chart;
        const handler = c?._cleanup;
        if (handler) {
          window.removeEventListener('resize', handler);
        }
        if (c && !c.isDisposed()) c.dispose();
      } catch {
        // ignore
      }
    };
  }, [curvesData, chartOriginalData, chartWithStorageData, showOriginal, showWithStorage]);

  return (
    <div className="space-y-6">
      <div id="section-profit-intro" className="p-4 bg-white rounded-xl shadow-sm border border-slate-200 space-y-3">
        <h2 className="text-lg font-semibold text-slate-800">储能收益与负荷对比</h2>
        <p className="text-sm text-slate-600">
          本页基于与储能次数计算相同的 TOU 配置与负荷数据，按日查看“引入储能前后”的负荷曲线与收益指标。
          当前实现使用一组默认的储能参数进行演示，如需与实际项目严格对齐，可在后续迭代中将参数从 StorageCycles 页透传进来。
        </p>
      </div>

      {monthProfitMain && selectedDate && (
        <div id="section-profit-month" className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
          <div className="p-3 rounded-lg bg-sky-50 border border-sky-100">
            <div className="text-xs text-sky-700">
              当前月份：{selectedDate.slice(0, 7)}
            </div>
            <div className="mt-1 text-lg font-semibold text-sky-800">
              {monthProfitMain.profit.toFixed(2)} 元
            </div>
          </div>
          <div className="p-3 rounded-lg bg-sky-50 border border-sky-100">
            <div className="text-xs text-sky-700">当前月份单位收益</div>
            <div className="mt-1 text-lg font-semibold text-sky-800">
              {monthProfitMain.profit_per_kwh.toFixed(3)} 元/kWh
            </div>
          </div>
        </div>
      )}

      <div id="section-profit-selector" className="p-4 bg-white rounded-xl shadow-sm border border-slate-200 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center gap-3 justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">选择日期：</span>
            <select
              className="border border-slate-300 rounded-md px-2 py-1 text-sm"
              value={selectedDate ?? ''}
              onChange={(e) => setSelectedDate(e.target.value || null)}
            >
              {!selectedDate && <option value="">请选择日期</option>}
              {availableDates.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            {selectedDayProfitMain && (
              <div className="text-xs text-slate-600">
                <span className="mr-3">
                  当日收益：<span className="font-semibold text-emerald-600">{selectedDayProfitMain.profit.toFixed(2)} 元</span>
                </span>
                <span>
                  单位收益：<span className="font-semibold text-slate-700">{selectedDayProfitMain.profit_per_kwh.toFixed(3)} 元/kWh</span>
                </span>
              </div>
            )}
            <button
              type="button"
              className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm disabled:opacity-50"
              disabled={!selectedDate || loading}
              onClick={handleFetchCurves}
            >
              {loading ? '加载中...' : '获取该日曲线'}
            </button>
          </div>
        </div>

        {error && <div className="text-xs text-red-600">{error}</div>}

        {yearProfitMain && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2 text-sm">
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
              <div className="text-xs text-emerald-700">全年净收益（主口径）</div>
              <div className="mt-1 text-lg font-semibold text-emerald-700">
                {yearProfitMain.profit.toFixed(2)} 元
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-700">全年放电电量</div>
              <div className="mt-1 text-lg font-semibold text-slate-800">
                {yearProfitMain.discharge_energy_kwh.toFixed(1)} kWh
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-700">全年单位收益</div>
              <div className="mt-1 text-lg font-semibold text-slate-800">
                {yearProfitMain.profit_per_kwh.toFixed(3)} 元/kWh
              </div>
            </div>
          </div>
        )}
      </div>

      {curvesData && (
        <div id="section-profit-curves" className="p-4 bg-white rounded-xl shadow-sm border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">负荷曲线对比（同一张图）</h3>
            <div className="flex items-center gap-3 text-xs text-slate-700">
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  className="rounded border-slate-300"
                  checked={showOriginal}
                  onChange={e => setShowOriginal(e.target.checked)}
                />
                <span>原始负荷曲线</span>
              </label>
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  className="rounded border-slate-300"
                  checked={showWithStorage}
                  onChange={e => setShowWithStorage(e.target.checked)}
                />
                <span>引入储能后的负荷曲线</span>
              </label>
            </div>
          </div>
          <div ref={combinedChartRef} style={{ width: '100%', height: 260 }} />
        </div>
      )}

      {curvesData && (
        <div id="section-profit-metrics" className="p-4 bg-white rounded-xl shadow-sm border border-slate-200 space-y-2 text-sm">
          <h3 className="text-sm font-semibold text-slate-800">当日关键指标</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-500">最大需量（原始）</div>
              <div className="mt-1 font-semibold text-slate-800">
                {curvesData.summary.max_demand_original_kw.toFixed(1)} kW
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">最大需量（储能后）</div>
              <div className="mt-1 font-semibold text-slate-800">
                {curvesData.summary.max_demand_new_kw.toFixed(1)} kW
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">最大需量降低</div>
              <div className="mt-1 font-semibold text-emerald-700">
                {curvesData.summary.max_demand_reduction_kw.toFixed(1)} kW
                {' '}
                ({(curvesData.summary.max_demand_reduction_ratio * 100).toFixed(1)}%)
              </div>
            </div>
            {curvesData.summary.profit_day_main && (
              <div>
                <div className="text-xs text-slate-500">当日净收益（主口径）</div>
                <div className="mt-1 font-semibold text-emerald-700">
                  {curvesData.summary.profit_day_main.profit.toFixed(2)} 元
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
