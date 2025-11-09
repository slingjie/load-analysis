import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { MonthlyTouPrices, Schedule, DateRule, BackendStorageCyclesResponse } from '../types';
import { computeStorageCycles, type StorageParamsPayload } from '../storageApi';

interface Props {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    prices: MonthlyTouPrices;
  };
}

export const StorageCyclesPage: React.FC<Props> = ({ scheduleData }) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BackendStorageCyclesResponse | null>(null);

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
    if (!input || !input.files || input.files.length === 0) {
      setError('请选择待测算的负荷文件（CSV/XLSX）');
      return;
    }
    const file = input.files[0];
    setFileName(file.name);

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
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  const monthsData = useMemo(() => result?.months || [], [result]);
  const daysData = useMemo(() => result?.days || [], [result]);

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
      const cats = monthsData.map(m => m.year_month);
      const vals = monthsData.map(m => Number(m.cycles ?? 0));
      chart.setOption({
        tooltip: {},
        xAxis: { type: 'category', data: cats },
        yAxis: { type: 'value', name: 'cycles' },
        series: [{ name: '月次数', type: 'bar', data: vals, itemStyle: { color: '#60a5fa' } }],
        grid: { left: 40, right: 20, bottom: 40, top: 30 },
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [monthsData]);

  useEffect(() => {
    let chart: any = null;
    loadECharts().then((echarts: any) => {
      if (!dayChartRef.current) return;
      chart = echarts.init(dayChartRef.current);
      const days = daysData.filter(d => selectedMonth && d.date.startsWith(selectedMonth));
      const cats = days.map(d => d.date.slice(5));
      const vals = days.map(d => Number(d.cycles ?? 0));
      chart.setOption({
        tooltip: {},
        xAxis: { type: 'category', data: cats },
        yAxis: { type: 'value', name: 'cycles' },
        series: [{ name: '日次数', type: 'line', data: vals, smooth: true, itemStyle: { color: '#34d399' } }],
        grid: { left: 40, right: 20, bottom: 40, top: 30 },
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [daysData, selectedMonth]);

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
        <div className="mt-2 p-3 border rounded bg-white">
          <div className="text-sm text-slate-700">年累计循环数：<b>{result.year?.cycles?.toFixed?.(6) ?? result.year?.cycles}</b></div>
          <div className="text-sm text-slate-700 mt-1">月度结果（前 6 项预览）：
            <ul className="list-disc ml-5">
              {result.months.slice(0, 6).map((m) => (
                <li key={m.year_month}>{m.year_month}: {m.cycles.toFixed?.(6) ?? m.cycles}</li>
              ))}
            </ul>
          </div>
          {/* 图表区：月柱 + 日折线 */}
          <div className="mt-3 grid grid-cols-1 gap-4">
            <div>
              <div className="text-sm font-semibold mb-1">月度次数（bar）</div>
              <div ref={monthChartRef} style={{ width: '100%', height: 280 }} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold mb-1">日度次数（line）</div>
                <div className="text-xs flex items-center gap-1">
                  <span>月份</span>
                  <select className="border rounded px-2 py-0.5" value={selectedMonth || ''}
                    onChange={e => setSelectedMonth(e.target.value)}>
                    {monthsData.map(m => (<option key={m.year_month} value={m.year_month}>{m.year_month}</option>))}
                  </select>
                </div>
              </div>
              <div ref={dayChartRef} style={{ width: '100%', height: 280 }} />
            </div>
          </div>
          {result.excel_path && (
            <div className="mt-2 text-sm">
              报表：<a href={result.excel_path} className="text-blue-600 underline" target="_blank" rel="noreferrer">下载 Excel</a>
            </div>
          )}
          {!!result.qc?.notes?.length && (
            <details className="mt-2">
              <summary className="cursor-pointer text-slate-700">QC 提示（展开查看）</summary>
              <ul className="list-disc ml-5 text-sm text-slate-600">
                {result.qc.notes.map((n, idx) => (<li key={idx}>{n}</li>))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
};
