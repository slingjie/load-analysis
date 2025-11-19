import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { MonthlyTouPrices, Schedule, DateRule, BackendStorageCyclesResponse } from '../types';
import type { LoadDataPoint } from '../utils';
import { computeStorageCycles, type StorageParamsPayload } from '../storageApi';

interface Props {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    prices: MonthlyTouPrices;
  };
  externalCleanedData?: LoadDataPoint[] | null; // 来自“负荷分析”页的已上传点
}

export const StorageCyclesPage: React.FC<Props> = ({ scheduleData, externalCleanedData }) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string>('');
  const [useAnalyzedData, setUseAnalyzedData] = useState<boolean>(!!(externalCleanedData && externalCleanedData.length > 0));

  // �Ƿ��Ѵ����ɷ������ݣ����ڽ���ͳ�ƣ�
  const hasExternalData = !!(externalCleanedData && externalCleanedData.length > 0);
  const reusedStats = useMemo(() => {
    if (!externalCleanedData || !externalCleanedData.length) return null;
    const sorted = externalCleanedData
      .slice()
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    const count = sorted.length;
    const start = sorted[0]?.timestamp;
    const end = sorted[sorted.length - 1]?.timestamp;
    return { count, start, end };
  }, [externalCleanedData]);

  // 当负荷分析数据变化时自动勾选/取消
  React.useEffect(() => {
    setUseAnalyzedData(!!(externalCleanedData && externalCleanedData.length > 0));
  }, [externalCleanedData]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BackendStorageCyclesResponse | null>(null);

  // 将 Date 转为“本地朴素时间”字符串（YYYY-MM-DD HH:mm:ss），避免 UTC 偏移与日界错位
  const toLocalNaiveString = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    const y = d.getFullYear();
    const m = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hh = pad(d.getHours());
    const mm = pad(d.getMinutes());
    const ss = pad(d.getSeconds());
    return `${y}-${m}-${day} ${hh}:${mm}:${ss}`;
  };

  // 简化的默认参数（可在页面上编辑的表单项可后续补充）
  const [params, setParams] = useState({
    capacity_kwh: 5000,
    c_rate: 0.5,
    single_side_efficiency: 0.92,
    depth_of_discharge: 0.9,
    reserve_charge_kw: 0,
    reserve_discharge_kw: 0,
    metering_mode: 'monthly_demand_max' as const,
    transformer_capacity_kva: 10000,
    transformer_power_factor: 0.9,
    energy_formula: 'physics' as const,
    merge_threshold_minutes: 30,
  });

  // 简单表单校验
  const validateParams = (): string | null => {
    const p = params;
    if (!(p.capacity_kwh > 0)) return '容量(capacity_kwh) 必须大于 0';
    if (!(p.c_rate > 0)) return '倍率(c_rate) 必须大于 0';
    if (!(p.single_side_efficiency > 0 && p.single_side_efficiency <= 1)) return '单边效率(η) 需在 (0, 1]';
    if (!(p.depth_of_discharge > 0 && p.depth_of_discharge <= 1)) return 'DOD 需在 (0, 1]';
    if (!(p.merge_threshold_minutes >= 0)) return '合并阈值需为非负整数';
    if (p.metering_mode === 'transformer_capacity') {
      if (!(p.transformer_capacity_kva > 0)) return '变压器容量(kVA) 必须大于 0';
      if (!(p.transformer_power_factor > 0 && p.transformer_power_factor <= 1)) return '功率因数需在 (0, 1]';
    }
    return null;
  };

  const handleUpload = async () => {
    setError(null);
    setResult(null);
    const input = fileRef.current;
    let file: File | null = null;
    if (input && input.files && input.files.length > 0) {
      file = input.files[0];
      setFileName(file.name);
    }
    if (!file && !useAnalyzedData) {
      setError('请选择待测算的负荷文件（CSV/XLSX）或勾选“使用负荷分析已上传数据”');
      return;
    }

    // 勾选了复用但没有可用数据，直接提示并中止
    if (useAnalyzedData && (!externalCleanedData || externalCleanedData.length === 0)) {
      setError('“负荷分析”页没有可用数据，请先在“负荷分析”页上传并处理，或在本页选择负荷文件。');
      return;
    }

    // 仅在有有效数据时构造 points，并按时间排序
    const pointsPayload = (useAnalyzedData && externalCleanedData && externalCleanedData.length > 0)
      ? externalCleanedData
          .slice()
          .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
          .map(p => ({
            timestamp: toLocalNaiveString(p.timestamp),
            load_kwh: Number(p.load),
          }))
      : undefined;

    const payload: StorageParamsPayload = {
      storage: {
        capacity_kwh: params.capacity_kwh,
        c_rate: params.c_rate,
        single_side_efficiency: params.single_side_efficiency,
        depth_of_discharge: params.depth_of_discharge,
        reserve_charge_kw: params.reserve_charge_kw,
        reserve_discharge_kw: params.reserve_discharge_kw,
        metering_mode: params.metering_mode,
        transformer_capacity_kva: params.metering_mode === 'transformer_capacity' ? params.transformer_capacity_kva : undefined,
        transformer_power_factor: params.metering_mode === 'transformer_capacity' ? params.transformer_power_factor : undefined,
        calc_style: 'window_avg',
        energy_formula: params.energy_formula,
        merge_threshold_minutes: params.merge_threshold_minutes,
      },
      strategySource: {
        monthlySchedule: scheduleData.monthlySchedule,
        dateRules: scheduleData.dateRules,
      },
      monthlyTouPrices: scheduleData.prices,
      points: pointsPayload,
    };

    try {
      const v = validateParams();
      if (v) { setError(v); return; }
      setLoading(true);
      const resp = await computeStorageCycles(file, payload);
      setResult(resp);
    } catch (e: any) {
      setError(e?.message || '计算失败');
    } finally {
      setLoading(false);
    }
  };

  // ========== 图表渲染（ECharts 动态加载） ==========
  const monthChartRef = useRef<HTMLDivElement>(null);
  const dayChartRef = useRef<HTMLDivElement>(null);
  const heatmapChartRef = useRef<HTMLDivElement>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [monthlyViewMode, setMonthlyViewMode] = useState<'aggregate' | 'byYear'>('aggregate');

  const monthsData = useMemo(() => result?.months || [], [result]);
  const daysData = useMemo(() => result?.days || [], [result]);

  // 月度曲线：按“月份维度”聚合不同年份（同一月份的 cycles 求和）
  const monthAxisLabels = useMemo(
    () => Array.from({ length: 12 }, (_, i) => `${i + 1}月`),
    [],
  );

  const aggregatedMonthlyCycles = useMemo(() => {
    const sums = new Array(12).fill(0);
    const hasData = new Array(12).fill(false);
    monthsData.forEach((m: any) => {
      if (!m?.year_month) return;
      const parts = String(m.year_month).split('-');
      if (parts.length !== 2) return;
      const month = parseInt(parts[1], 10);
      if (!month || month < 1 || month > 12) return;
      const idx = month - 1;
      sums[idx] += Number(m.cycles ?? 0);
      hasData[idx] = true;
    });
    // 对于完全没有数据的月份返回 null，使折线在该点断开
    return sums.map((v, idx) => (hasData[idx] ? v : null));
  }, [monthsData]);

  // 热力图维度：横轴为 1–31 日，纵轴为 1–12 月
  const heatmapXAxisDays = useMemo(
    () => Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, '0')),
    [],
  );
  const heatmapYAxisMonths = useMemo(
    () => Array.from({ length: 12 }, (_, i) => `${i + 1}月`),
    [],
  );

  // 将日度数据转换为 12×31 的热力图矩阵
  const heatmapData = useMemo(() => {
    if (!daysData.length) return [] as number[][];
    const valueMap = new Map<string, number>();
    daysData.forEach((d: any) => {
      if (!d?.date) return;
      const parts = String(d.date).split('-');
      if (parts.length !== 3) return;
      const m = parseInt(parts[1], 10);
      const day = parseInt(parts[2], 10);
      if (!m || !day) return;
      const key = `${m}-${day}`;
      valueMap.set(key, Number(d.cycles ?? 0));
    });
    const data: number[][] = [];
    for (let m = 1; m <= 12; m++) {
      for (let d = 1; d <= 31; d++) {
        const v = valueMap.get(`${m}-${d}`) ?? 0;
        // x: 第几日（0-based），y: 第几月（0-based）
        data.push([d - 1, m - 1, v]);
      }
    }
    return data;
  }, [daysData]);

  // 按天数据统计：每月有效天数 / 有效循环数 / 等效循环数 + 年度汇总
  const {
    monthValidDays,
    monthTotalCycles,
    monthEquivalentCycles,
    yearValidDays,
    yearTotalCycles,
    yearEquivalentCycles,
    monthFirstChargeRatePct,
    monthFirstDischargeRatePct,
    monthSecondChargeRatePct,
    monthSecondDischargeRatePct,
  } = useMemo(() => {
    const monthDaySets: Array<Set<string>> = Array.from({ length: 12 }, () => new Set<string>());
    const monthTotal: number[] = new Array(12).fill(0);
    const monthYear: Array<number | null> = new Array(12).fill(null);
    const yearDaySet = new Set<string>();

    daysData.forEach((d: any) => {
      if (!d?.date) return;
      const parts = String(d.date).split('-');
      if (parts.length !== 3) return;
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10);
      if (!year || !month || month < 1 || month > 12) return;
      const idx = month - 1;
      const dateKey = String(d.date);
      monthDaySets[idx].add(dateKey);
      yearDaySet.add(dateKey);
      monthTotal[idx] += Number(d.cycles ?? 0);
      if (monthYear[idx] == null) {
        monthYear[idx] = year;
      }
    });

    const monthValidDaysArr: number[] = new Array(12).fill(0);
    const monthEqCyclesArr: Array<number | null> = new Array(12).fill(null);

    // 从后端 window_month_summary 中取 C1/C2 + charge/discharge 的月度循环数
    const firstChargeCycles: number[] = new Array(12).fill(0);
    const firstDischargeCycles: number[] = new Array(12).fill(0);
    const secondChargeCycles: number[] = new Array(12).fill(0);
    const secondDischargeCycles: number[] = new Array(12).fill(0);

    (result?.window_month_summary ?? []).forEach((m: any) => {
      if (!m?.year_month) return;
      const parts = String(m.year_month).split('-');
      if (parts.length !== 2) return;
      const month = parseInt(parts[1], 10);
      if (!month || month < 1 || month > 12) return;
      const idx = month - 1;
      firstChargeCycles[idx] += Number(m.first_charge_cycles ?? 0);
      firstDischargeCycles[idx] += Number(m.first_discharge_cycles ?? 0);
      secondChargeCycles[idx] += Number(m.second_charge_cycles ?? 0);
      secondDischargeCycles[idx] += Number(m.second_discharge_cycles ?? 0);
    });

    const firstChargeRatePct: Array<number | null> = new Array(12).fill(null);
    const firstDischargeRatePct: Array<number | null> = new Array(12).fill(null);
    const secondChargeRatePct: Array<number | null> = new Array(12).fill(null);
    const secondDischargeRatePct: Array<number | null> = new Array(12).fill(null);

    for (let i = 0; i < 12; i++) {
      const validDays = monthDaySets[i].size;
      monthValidDaysArr[i] = validDays;
      if (validDays > 0) {
        const y = monthYear[i] ?? new Date().getFullYear();
        // 计算该月自然天数（处理好 2 月闰年）
        const monthDaysCount = new Date(y, i + 1, 0).getDate();
        const total = monthTotal[i];
        monthEqCyclesArr[i] = (total / validDays) * monthDaysCount;

        // “满充率/满放率”= 日均次数 × 100%（单位 %）
        const d = validDays;
        const fCharge = firstChargeCycles[i];
        const fDischarge = firstDischargeCycles[i];
        const sCharge = secondChargeCycles[i];
        const sDischarge = secondDischargeCycles[i];
        firstChargeRatePct[i] = d > 0 ? (fCharge / d) * 100 : null;
        firstDischargeRatePct[i] = d > 0 ? (fDischarge / d) * 100 : null;
        secondChargeRatePct[i] = d > 0 ? (sCharge / d) * 100 : null;
        secondDischargeRatePct[i] = d > 0 ? (sDischarge / d) * 100 : null;
      }
    }

    const yearValidDaysCount = yearDaySet.size;
    const yearTotalCyclesVal = monthTotal.reduce((sum, v) => sum + v, 0);
    const yearEqCyclesVal = monthEqCyclesArr.reduce(
      (sum, v) => (v != null ? sum + v : sum),
      0,
    );

    return {
      monthValidDays: monthValidDaysArr,
      monthTotalCycles: monthTotal,
      monthEquivalentCycles: monthEqCyclesArr,
      yearValidDays: yearValidDaysCount,
      yearTotalCycles: yearTotalCyclesVal,
      yearEquivalentCycles: yearEqCyclesVal,
      monthFirstChargeRatePct: firstChargeRatePct,
      monthFirstDischargeRatePct: firstDischargeRatePct,
      monthSecondChargeRatePct: secondChargeRatePct,
      monthSecondDischargeRatePct: secondDischargeRatePct,
    };
  }, [daysData, result?.window_month_summary]);

  useEffect(() => {
    if (!monthsData.length) { setSelectedMonth(null); return; }
    if (selectedMonth && monthsData.find(m => m.year_month === selectedMonth)) return;
    setSelectedMonth(monthsData[0]?.year_month || null);
  }, [monthsData, selectedMonth]);

  // 动态加载 ECharts（复用其他组件做法）
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

  useEffect(() => {
    let chart: any = null;
    loadECharts().then((echarts: any) => {
      if (!monthChartRef.current) return;
      chart = echarts.init(monthChartRef.current);
      const cats =
        monthlyViewMode === 'aggregate'
          ? monthAxisLabels
          : monthsData.map(m => m.year_month);
      const vals =
        monthlyViewMode === 'aggregate'
          ? aggregatedMonthlyCycles
          : monthsData.map(m => Number(m.cycles ?? 0));
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params[0] : params;
            const label = p.axisValue;
            const value =
              p.data == null || Number.isNaN(Number(p.data))
                ? '-'
                : Number(p.data).toFixed(3);
            if (monthlyViewMode === 'aggregate') {
              // 按月合计视图：月份 + 合计次数
              return `${label}：合计 ${value} 次`;
            }
            // 按年拆分视图：直接显示对应 year_month 的次数
            return `${label}：${value} 次`;
          },
        },
        xAxis: { type: 'category', data: cats, name: '月份' },
        yAxis: { type: 'value', name: '次数' },
        toolbox: {
          feature: {
            saveAsImage: {
              name: 'storage-cycles-monthly',
            },
          },
          right: 10,
          top: 10,
        },
        series: [{
          name: '月度次数',
          type: 'line',
          data: vals,
          smooth: true,
          // 在“按月合计”模式下遇到 null 会断开；按年拆分模式下 monthsData 不会出现 null
          areaStyle: { color: 'rgba(96,165,250,0.15)' },
          itemStyle: { color: '#60a5fa' },
        }],
        grid: { left: 40, right: 20, bottom: 40, top: 30 },
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [aggregatedMonthlyCycles, monthAxisLabels, monthsData, monthlyViewMode]);

  useEffect(() => {
    let chart: any = null;
    loadECharts().then((echarts: any) => {
      if (!dayChartRef.current) return;
      chart = echarts.init(dayChartRef.current);
      const days = daysData.filter(d => selectedMonth && d.date.startsWith(selectedMonth));
      const cats = days.map(d => d.date.slice(5));
      const vals = days.map(d => Number(d.cycles ?? 0));
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params[0] : params;
            const label = p.axisValue;
            const value =
              p.data == null || Number.isNaN(Number(p.data))
                ? '-'
                : Number(p.data).toFixed(3);
            return `${label}：${value} 次`;
          },
        },
        xAxis: { type: 'category', data: cats, name: '日期' },
        yAxis: {
          type: 'value',
          name: '次数',
          axisLabel: {
            formatter: (value: number) =>
              Number.isNaN(Number(value)) ? '-' : Number(value).toFixed(3),
          },
        },
        toolbox: {
          feature: {
            saveAsImage: {
              name: 'storage-cycles-daily',
            },
          },
          right: 10,
          top: 10,
        },
        series: [{ name: '日度次数', type: 'line', data: vals, smooth: true, itemStyle: { color: '#34d399' } }],
        grid: { left: 40, right: 20, bottom: 40, top: 30 },
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [daysData, selectedMonth]);

  // 全年每日充放次数热力图
  useEffect(() => {
    let chart: any = null;
    loadECharts().then((echarts: any) => {
      if (!heatmapChartRef.current) return;
      chart = echarts.init(heatmapChartRef.current);
      const maxVal = heatmapData.reduce((max, d) => (d[2] > max ? d[2] : max), 0) || 1;
      chart.setOption({
        tooltip: {
          position: 'top',
          formatter: (params: any) => {
            const xIdx = params.data[0];
            const yIdx = params.data[1];
            const v = params.data[2];
            const dayLabel = heatmapXAxisDays[xIdx] ?? '';
            const monthLabel = heatmapYAxisMonths[yIdx] ?? '';
            const value =
              v == null || Number.isNaN(Number(v))
                ? '-'
                : Number(v).toFixed(3);
            return `${monthLabel}${dayLabel}日<br/>充放次数：${value}`;
          },
        },
        grid: { left: 60, right: 40, top: 40, bottom: 40 },
        xAxis: {
          type: 'category',
          data: heatmapXAxisDays,
          name: '日',
          splitArea: { show: true },
        },
        yAxis: {
          type: 'category',
          data: heatmapYAxisMonths,
          name: '月',
          // 反向显示，使 1 月在上方、12 月在下方
          inverse: true,
          splitArea: { show: true },
        },
        toolbox: {
          feature: {
            saveAsImage: {
              name: 'storage-cycles-heatmap',
            },
          },
          right: 10,
          top: 10,
        },
        visualMap: {
          min: 0,
          max: maxVal,
          calculable: true,
          orient: 'vertical',
          right: 0,
          top: 'middle',
          inRange: {
            color: ['#e0f2fe', '#60a5fa', '#1d4ed8'],
          },
        },
        series: [{
          name: '每日充放次数',
          type: 'heatmap',
          data: heatmapData,
        }],
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [heatmapData, heatmapXAxisDays, heatmapYAxisMonths]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={() => setFileName(fileRef.current?.files?.[0]?.name || '')} />
        <button className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm" onClick={() => fileRef.current?.click()}>
          选择负荷文件
        </button>
        <span className="text-sm text-slate-600">{fileName || '未选择文件'}</span>
        <button className="ml-2 px-3 py-1.5 rounded bg-green-600 text-white text-sm" onClick={handleUpload} disabled={loading}>
          {loading ? '计算中…' : '开始测算'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={useAnalyzedData} onChange={e => setUseAnalyzedData(e.target.checked)} />
          <span>使用“负荷分析”页已上传数据</span>
        </label>
      </div>

      {/* 参数表单（简化） */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span>容量 (kWh)</span>
          <input className="border rounded px-2 py-1" type="number" step="1" min="1" value={params.capacity_kwh}
            onChange={e => setParams(p => ({ ...p, capacity_kwh: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>倍率 (C-rate)</span>
          <input className="border rounded px-2 py-1" type="number" step="0.01" min="0" value={params.c_rate}
            onChange={e => setParams(p => ({ ...p, c_rate: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>单边效率 η</span>
          <input className="border rounded px-2 py-1" type="number" step="0.001" min="0" max="1" value={params.single_side_efficiency}
            onChange={e => setParams(p => ({ ...p, single_side_efficiency: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>DOD</span>
          <input className="border rounded px-2 py-1" type="number" step="0.01" min="0" max="1" value={params.depth_of_discharge}
            onChange={e => setParams(p => ({ ...p, depth_of_discharge: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>充电余量 (kW)</span>
          <input className="border rounded px-2 py-1" type="number" step="1" min="0" value={params.reserve_charge_kw}
            onChange={e => setParams(p => ({ ...p, reserve_charge_kw: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>放电余量 (kW)</span>
          <input className="border rounded px-2 py-1" type="number" step="1" min="0" value={params.reserve_discharge_kw}
            onChange={e => setParams(p => ({ ...p, reserve_discharge_kw: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>合并阈值 (分钟)</span>
          <input className="border rounded px-2 py-1" type="number" step="1" min="0" value={params.merge_threshold_minutes}
            onChange={e => setParams(p => ({ ...p, merge_threshold_minutes: Number(e.target.value) }))} />
        </label>
        <label className="flex flex-col gap-1">
          <span>计费口径</span>
          <select className="border rounded px-2 py-1" value={params.metering_mode}
            onChange={e => setParams(p => ({ ...p, metering_mode: e.target.value as any }))}>
            <option value="monthly_demand_max">monthly_demand_max</option>
            <option value="transformer_capacity">transformer_capacity</option>
          </select>
        </label>
        {params.metering_mode === 'transformer_capacity' && (
          <>
            <label className="flex flex-col gap-1">
              <span>变压器容量 (kVA)</span>
              <input className="border rounded px-2 py-1" type="number" step="1" min="1" value={params.transformer_capacity_kva}
                onChange={e => setParams(p => ({ ...p, transformer_capacity_kva: Number(e.target.value) }))} />
            </label>
            <label className="flex flex-col gap-1">
              <span>功率因数</span>
              <input className="border rounded px-2 py-1" type="number" step="0.01" min="0" max="1" value={params.transformer_power_factor}
                onChange={e => setParams(p => ({ ...p, transformer_power_factor: Number(e.target.value) }))} />
            </label>
          </>
        )}
        <label className="flex flex-col gap-1">
          <span>能量公式</span>
          <select className="border rounded px-2 py-1" value={params.energy_formula}
            onChange={e => setParams(p => ({ ...p, energy_formula: e.target.value as any }))}>
            <option value="physics">physics</option>
            <option value="sample">sample</option>
          </select>
        </label>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {result && (
        <div className="mt-2 space-y-3">
          {/* 循环有效/等效统计表格（按月 + 年度汇总） */}
          <div className="p-3 border rounded-xl bg-white shadow-sm overflow-x-auto">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-semibold text-slate-800">
                循环有效/等效统计（按月）
              </div>
              <div className="text-[11px] md:text-xs text-slate-500">
                基于日度循环结果按自然月折算
              </div>
            </div>
            <table className="min-w-full text-xs md:text-sm border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-3 py-2 text-left font-medium text-slate-600">月份</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">有效天数（天）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">平均日循环数（次/天）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">有效循环数（次）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">等效循环数（次）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">第一次充电满充率（%）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">第一次充电满放率（%）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">第二次充电满充率（%）</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">第二次充电满放率（%）</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 12 }, (_, i) => {
                  const monthLabel = `${i + 1}月`;
                  const validDays = monthValidDays[i] ?? 0;
                  const totalCycles = monthTotalCycles[i] ?? 0;
                  const eqCycles = monthEquivalentCycles[i];
                  const fChargePct = monthFirstChargeRatePct[i];
                  const fDischargePct = monthFirstDischargeRatePct[i];
                  const sChargePct = monthSecondChargeRatePct[i];
                  const sDischargePct = monthSecondDischargeRatePct[i];
                  const avgDailyCycles =
                    validDays > 0 ? totalCycles / validDays : null;
                  const totalStr =
                    totalCycles === 0
                      ? '-'
                      : Number(totalCycles).toFixed(3);
                  const eqStr =
                    eqCycles == null || eqCycles === 0
                      ? '-'
                      : Number(eqCycles).toFixed(3);
                  const fChargeStr =
                    fChargePct == null
                      ? '-'
                      : `${Number(fChargePct).toFixed(3)}%`;
                  const fDischargeStr =
                    fDischargePct == null
                      ? '-'
                      : `${Number(fDischargePct).toFixed(3)}%`;
                  const sChargeStr =
                    sChargePct == null
                      ? '-'
                      : `${Number(sChargePct).toFixed(3)}%`;
                  const sDischargeStr =
                    sDischargePct == null
                      ? '-'
                      : `${Number(sDischargePct).toFixed(3)}%`;
                  const avgDailyStr =
                    avgDailyCycles == null || avgDailyCycles === 0
                      ? '-'
                      : Number(avgDailyCycles).toFixed(3);
                  return (
                    <tr
                      key={monthLabel}
                      className="border-b border-slate-100 last:border-0 even:bg-slate-50/60 hover:bg-slate-100/70 transition-colors"
                    >
                      <td className="px-3 py-1.5 text-slate-700">{monthLabel}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {validDays || '-'}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {avgDailyStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {totalStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {eqStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {fChargeStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {fDischargeStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {sChargeStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {sDischargeStr}
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t border-slate-200 bg-slate-100/80">
                  <td className="px-3 py-1.5 font-semibold text-slate-800">全年合计</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {yearValidDays || '-'}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {yearValidDays && yearTotalCycles
                      ? Number(yearTotalCycles / yearValidDays).toFixed(3)
                      : '-'}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {yearTotalCycles === 0
                      ? '-'
                      : Number(yearTotalCycles).toFixed(3)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {yearEquivalentCycles === 0
                      ? '-'
                      : Number(yearEquivalentCycles).toFixed(3)}
                  </td>
                  {/* 目前年度满充/满放率不做汇总，保持为空 */}
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">-</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">-</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">-</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">-</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* 图表区：左侧月度曲线 + 全年日度热力图，右侧单月日度曲线与报表/QC */}
          <div className="grid grid-cols-1 xl:grid-cols-[2fr_minmax(0,1fr)] gap-4">
            <div className="space-y-4">
              <div className="p-3 border rounded bg-white">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-sm font-semibold">月度充放次数（曲线）</div>
                  <div className="text-xs flex items-center gap-1">
                    <span>视图</span>
                    <select
                      className="border rounded px-2 py-0.5"
                      value={monthlyViewMode}
                      onChange={e => setMonthlyViewMode(e.target.value as 'aggregate' | 'byYear')}
                    >
                      <option value="aggregate">按月合计</option>
                      <option value="byYear">按年拆分</option>
                    </select>
                  </div>
                </div>
                <div ref={monthChartRef} style={{ width: '100%', height: 260 }} />
              </div>
              <div className="p-3 border rounded bg-white">
                <div className="text-sm font-semibold mb-1">全年每日充放次数热力图</div>
                <div ref={heatmapChartRef} style={{ width: '100%', height: 320 }} />
                <div className="mt-1 text-xs text-slate-500">
                  第一行对应 1 月、第二行对应 2 月，横轴为 1–31 日，每个格子表示当日的充放次数。
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="p-3 border rounded bg-white">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold mb-1">单月日度次数曲线</div>
                  <div className="text-xs flex items-center gap-1">
                    <span>月份</span>
                    <select
                      className="border rounded px-2 py-0.5"
                      value={selectedMonth || ''}
                      onChange={e => setSelectedMonth(e.target.value)}
                    >
                      {monthsData.map(m => (
                        <option key={m.year_month} value={m.year_month}>{m.year_month}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div ref={dayChartRef} style={{ width: '100%', height: 260 }} />
              </div>

              {result.excel_path && (
                <div className="p-3 border rounded bg-white text-sm">
                  报表：
                  <a
                    href={result.excel_path}
                    className="text-blue-600 underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    下载 Excel 详细结果
                  </a>
                </div>
              )}

              {!!result.qc?.notes?.length && (
                <div className="p-3 border rounded bg白">
                  <details>
                    <summary className="cursor-pointer text-slate-700 text-sm">QC 提示（展开查看）</summary>
                    <ul className="list-disc ml-5 text-sm text-slate-600 mt-1">
                      {result.qc.notes.map((n, idx) => (<li key={idx}>{n}</li>))}
                    </ul>
                  </details>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
