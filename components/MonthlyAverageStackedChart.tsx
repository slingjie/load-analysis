import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { LoadDataPoint } from '../utils';

// 动态按需加载 ECharts（通过 CDN），避免安装额外依赖
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

type Props = {
  // 小时级清洗后的负荷数据（kWh/h ~ kW）
  data: LoadDataPoint[];
  height?: number | string;
};

// 工具函数：将小时级数据聚合为 12 个月 × 24 小时的“日平均小时负荷”
// 计算口径：对每个“月份-小时”，对所有自然日求平均（只统计该月内出现该小时数据的日期数）
const useMonthlyHourlyAverages = (data: LoadDataPoint[]) => {
  return useMemo(() => {
    // sums[month][hour] = 该月该小时的负荷总和
    const sums: number[][] = Array.from({ length: 12 }, () => Array.from({ length: 24 }, () => 0));
    // daySets[month][hour] = 去重后的日期集合（YYYY-MM-DD），用于统计参与平均的天数
    const daySets: Array<Array<Set<string>>> = Array.from({ length: 12 }, () => Array.from({ length: 24 }, () => new Set<string>()));

    for (const p of data) {
      if (!p || !(p.timestamp instanceof Date) || !Number.isFinite(p.load)) continue;
      const m = p.timestamp.getMonth(); // 0-11
      const h = p.timestamp.getHours(); // 0-23
      const dayKey = `${p.timestamp.getFullYear()}-${m + 1}-${p.timestamp.getDate()}`;
      sums[m][h] += p.load;
      daySets[m][h].add(dayKey);
    }

    // 计算平均值 curves[month] = [24个小时均值]
    const curves: number[][] = Array.from({ length: 12 }, () => Array.from({ length: 24 }, () => 0));
    const hasData: boolean[] = Array.from({ length: 12 }, () => false);
    for (let m = 0; m < 12; m++) {
      for (let h = 0; h < 24; h++) {
        const days = daySets[m][h].size;
        if (days > 0) {
          hasData[m] = true;
          curves[m][h] = sums[m][h] / days;
        } else {
          curves[m][h] = 0;
        }
      }
    }
    return { curves, hasData };
  }, [data]);
};

// 月份复选选择器（支持单选/多选两种模式）
const MonthSelector: React.FC<{
  selected: number[]; // 选中的月份索引（0-11）
  onChange: (next: number[]) => void;
  available: boolean[]; // 每月是否有数据
  singleMode: boolean;
  onToggleMode: () => void;
}> = ({ selected, onChange, available, singleMode, onToggleMode }) => {
  const toggle = (idx: number) => {
    if (!available[idx]) return; // 无数据的月份不允许选择
    if (singleMode) {
      onChange([idx]);
      return;
    }
    if (selected.includes(idx)) {
      onChange(selected.filter((m) => m !== idx));
    } else {
      onChange([...selected, idx].sort((a, b) => a - b));
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-medium text-slate-700">月份选择：</span>
        <button
          type="button"
          onClick={onToggleMode}
          className="px-2 py-1 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-700"
        >
          {singleMode ? '切换为多选' : '切换为单选'}
        </button>
        {!singleMode && (
          <>
            <button
              type="button"
              onClick={() => onChange(available.map((ok, i) => (ok ? i : -1)).filter((x) => x >= 0))}
              className="px-2 py-1 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-700"
            >
              全选
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              className="px-2 py-1 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-700"
            >
              全不选
            </button>
          </>
        )}
      </div>
      <div className="grid grid-cols-6 sm:grid-cols-8 lg:grid-cols-12 gap-2">
        {Array.from({ length: 12 }, (_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => toggle(i)}
            disabled={!available[i]}
            className={
              'px-2 py-1 rounded-md border text-sm ' +
              (selected.includes(i)
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50') +
              (!available[i] ? ' opacity-50 cursor-not-allowed' : '')
            }
            title={available[i] ? '' : '无该月数据'}
          >
            {i + 1}月
          </button>
        ))}
      </div>
    </div>
  );
};

export const MonthlyAverageStackedChart: React.FC<Props> = ({ data, height = 384 }) => {
  const { curves, hasData } = useMonthlyHourlyAverages(data);
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // 默认选中：有数据的月份；若全无数据则空
  const defaultSelected = useMemo(() => hasData.map((ok, i) => (ok ? i : -1)).filter((x) => x >= 0), [hasData]);
  const [selectedMonths, setSelectedMonths] = useState<number[]>(defaultSelected);
  const [singleMode, setSingleMode] = useState<boolean>(false);
  // 新增：堆叠模式开关（关闭可避免多月叠加导致坐标被放大，从而产生“看起来小10倍”的错觉）
  const [stackMode, setStackMode] = useState<boolean>(false);
  // 新增：末端标签显示开关（曲线不多时在末端标注“X月”，提高辨识度）
  const [showEndLabels, setShowEndLabels] = useState<boolean>(true);

  useEffect(() => {
    // 当可用月份变化时，重置默认选择
    setSelectedMonths(hasData.map((ok, i) => (ok ? i : -1)).filter((x) => x >= 0));
  }, [hasData.join(',')]);

  useEffect(() => {
    let echarts: any = null;
    let disposed = false;
    loadECharts()
      .then((ec) => {
        echarts = ec;
        if (!ref.current) return;
        chartRef.current = echarts.init(ref.current);

        const hours = Array.from({ length: 24 }, (_, i) => `${i}`);
        const endLabelEnabled = showEndLabels && selectedMonths.length <= 6;
        const series = selectedMonths.map((mIdx) => ({
          name: `${mIdx + 1}月`,
          type: 'line',
          // 仅在开启堆叠模式时才进行堆叠；默认关闭以保证每条曲线与纵轴刻度直观对应
          stack: stackMode ? '月度日均' : undefined,
          showSymbol: false,
          smooth: false,
          sampling: 'lttb',
          lineStyle: { width: 1.5 },
          emphasis: { focus: 'series', lineStyle: { width: 2.2 } },
          blur: { lineStyle: { opacity: 0.25 } },
          endLabel: endLabelEnabled
            ? {
                show: true,
                formatter: '{a}',
                // 轻微留白背景以提升可读性
                backgroundColor: 'rgba(255,255,255,0.8)',
                padding: [2, 4],
                borderRadius: 3,
              }
            : undefined,
          data: curves[mIdx]?.map((v, h) => [hours[h], Number.isFinite(v) ? Number(v.toFixed(3)) : 0]) ?? [],
        }));

        const option = {
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'axis',
            valueFormatter: (v: any) => (Number.isFinite(v) ? `${v} kW` : `${v}`),
          },
          legend: { type: 'scroll' as const, top: 0 },
          grid: { left: 48, right: endLabelEnabled ? 80 : 24, top: 28, bottom: 48 },
          xAxis: {
            type: 'category' as const,
            boundaryGap: false,
            name: '时',
            data: hours,
            axisLabel: { formatter: (v: string) => `${v}` },
          },
          yAxis: {
            type: 'value' as const,
            name: '负荷 (kW)',
            boundaryGap: [0, '5%'],
            axisLabel: {
              formatter: (v: number) => `${v}`,
            },
          },
          series,
        };

        chartRef.current.setOption(option, true);
        const onResize = () => chartRef.current && chartRef.current.resize();
        window.addEventListener('resize', onResize);
        (chartRef.current as any)._cleanup = () => window.removeEventListener('resize', onResize);
      })
      .catch((e) => {
        console.error('[MonthlyAverageStackedChart] 加载 ECharts 失败', e);
      });

    return () => {
      try {
        const c: any = chartRef.current;
        if (c && c._cleanup) c._cleanup();
        if (c && !c.isDisposed()) c.dispose();
      } catch {}
      chartRef.current = null;
    };
  }, [curves, selectedMonths.join(','), stackMode, showEndLabels, hasData.join(',')]);

  return (
    <div className="flex flex-col gap-3">
      <MonthSelector
        selected={selectedMonths}
        onChange={setSelectedMonths}
        available={hasData}
        singleMode={singleMode}
        onToggleMode={() => setSingleMode((v) => !v)}
      />
      <div className="flex items-center gap-3 text-sm text-slate-700">
        <label className="inline-flex items-center gap-2 select-none cursor-pointer">
          <input
            type="checkbox"
            className="accent-slate-600"
            checked={stackMode}
            onChange={(e) => setStackMode(e.target.checked)}
          />
          <span>堆叠显示</span>
        </label>
        {stackMode && (
          <span className="text-xs text-slate-500">提示：堆叠开启时，纵轴反映多月叠加总值，单条曲线相对看起来会更小。</span>
        )}
        <label className="inline-flex items-center gap-2 select-none cursor-pointer">
          <input
            type="checkbox"
            className="accent-slate-600"
            checked={showEndLabels}
            onChange={(e) => setShowEndLabels(e.target.checked)}
          />
          <span>显示末端标签</span>
        </label>
        {showEndLabels && selectedMonths.length > 6 && (
          <span className="text-xs text-slate-500">提示：曲线数量较多（&gt;6），为避免遮挡已自动隐藏末端标签。</span>
        )}
      </div>
      <div ref={ref} style={{ width: '100%', height }} />
      <p className="text-xs text-slate-500">说明：横轴为 0–23 点；纵轴单位为 kW（小时平均功率）。支持单选/多选对比；可开启“堆叠显示”；可显示“末端标签”快速辨识曲线（曲线较多时自动隐藏）。</p>
    </div>
  );
};

export default MonthlyAverageStackedChart;

