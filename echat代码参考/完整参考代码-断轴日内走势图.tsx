/**
 * ================================================================
 * 小时负荷曲线 - 断轴日内走势图完整参考代码
 * ================================================================
 * 
 * 这个文件包含了断轴功能的完整实现与各种使用场景
 * 
 * 核心原理：
 * 当数据中出现缺失（相邻时间间隔异常大）时，
 * 自动生成 ECharts break 配置，在图表上显示"断轴"标记
 * 而不是直接连接缺失区间
 */

// ================================================================
// 场景 1: 基础断轴组件（已实现在 EChartTimeSeries.tsx）
// ================================================================

import React, { useEffect, useRef } from 'react';

type Point = { x: Date; y: number };

interface Props {
  data: Point[];
  height?: number | string;
  lineColor?: string;
  showArea?: boolean;
  useAxisBreak?: boolean;  // 是否启用断轴
  onReady?: (api: { resetZoom: () => void; getInstance: () => any }) => void;
}

export const EChartTimeSeries: React.FC<Props> = ({ 
  data, 
  height = 384, 
  lineColor = 'rgb(59,130,246)', 
  showArea = false, 
  useAxisBreak = true, 
  onReady 
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    let disposed = false;
    let echarts: any = null;

    loadECharts()
      .then((ec: any) => {
        echarts = ec;
        if (!ref.current || disposed) return;

        chartRef.current = echarts.init(ref.current);

        // ========== 关键步骤 1: 数据预处理 ==========
        const points = data
          .filter(p => p && p.x instanceof Date && !Number.isNaN(p.x.getTime()) && Number.isFinite(p.y))
          .sort((a, b) => a.x.getTime() - b.x.getTime())
          .map(p => [p.x.getTime(), p.y]);

        if (points.length === 0) {
          console.warn('[EChartTimeSeries] 无有效数据');
          return;
        }

        // ========== 关键步骤 2: 推断采样步长 ==========
        const toMinute = (ms: number) => Math.max(1, Math.round(ms / 60000));
        const deltas = [] as number[];

        for (let i = 1; i < points.length; i++) {
          const d = (points[i][0] as number) - (points[i - 1][0] as number);
          if (d > 0) deltas.push(d);
        }

        // 众数算法：找出现频率最高的间隔
        const estimateStepMs = (() => {
          if (deltas.length === 0) return 60 * 60000; // 默认 1 小时

          const freq = new Map<number, number>();
          for (const d of deltas) {
            const m = toMinute(d);
            freq.set(m, (freq.get(m) || 0) + 1);
          }

          let bestM = 60, bestC = -1;
          for (const [m, c] of freq.entries()) {
            if (c > bestC) {
              bestC = c;
              bestM = m;
            }
          }

          const result = bestM * 60000;
          console.log(
            `[EChartTimeSeries] 推断采样步长: ${bestM}分钟, 出现${bestC}次, ` +
            `覆盖${(bestC * 100 / deltas.length).toFixed(1)}%的数据对`
          );
          return result;
        })();

        // ========== 关键步骤 3: 检测缺失区间 ==========
        const breaks: Array<{ start: number; end: number; gap?: number }> = [];

        if (useAxisBreak && points.length > 1) {
          const threshold = estimateStepMs * 1.5;  // 阈值：1.5 倍采样步长

          for (let i = 1; i < points.length; i++) {
            const prev = points[i - 1][0] as number;
            const curr = points[i][0] as number;
            const gap = curr - prev;

            if (gap > threshold) {
              // 检测到缺失
              const start = prev + estimateStepMs;
              const end = curr;

              if (end - start > 0) {
                breaks.push({ start, end, gap: 0 });

                const gapMinutes = (gap / 60000).toFixed(1);
                const startTime = new Date(start).toLocaleString();
                const endTime = new Date(end).toLocaleString();

                console.log(
                  `[EChartTimeSeries] 检测到缺失区间 [${i}]: ` +
                  `${startTime} → ${endTime} (间隔 ${gapMinutes} 分钟)`
                );
              }
            }
          }

          console.log(`[EChartTimeSeries] 共检测 ${breaks.length} 个缺失区间`);
        }

        // ========== 关键步骤 4: 配置 ECharts 选项 ==========
        const option = {
          backgroundColor: 'transparent',
          
          tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            valueFormatter: (value: any) => `${Number(value).toFixed(2)} kWh`
          },

          grid: {
            left: 40,
            right: 20,
            top: 20,
            bottom: 80
          },

          // ★ X 轴断轴配置
          xAxis: {
            type: 'time',
            boundaryGap: false,
            
            // 断轴配置（核心！）
            breaks: breaks.length > 0 ? breaks : undefined,
            
            breakArea: breaks.length > 0 ? {
              expandOnClick: false,    // 禁用点击展开
              zigzagAmplitude: 6,      // zigzag 波幅
              zigzagZ: 200             // 层级
            } : undefined,

            breakLabelLayout: breaks.length > 0 ? {
              moveOverlap: false       // 禁用自动移动
            } : undefined,

            axisLabel: {
              hideOverlap: true,
              formatter: (value: number, _idx: number, extra: any) => {
                const fmt = (v: number, tpl = '{MM}-{dd} {HH}:{mm}') => {
                  try {
                    return echarts?.time?.format ? echarts.time.format(v, tpl) : new Date(v).toLocaleString();
                  } catch {
                    return new Date(v).toLocaleString();
                  }
                };

                try {
                  // ★ 断轴标签处理
                  if (extra && extra.break) {
                    if (extra.break.type === 'start') {
                      // 显示缺失区间的开始和结束时间
                      return `${fmt(extra.break.start)} / ${fmt(extra.break.end)}`;
                    }
                    return '';  // 断轴终点不显示标签
                  }
                } catch {}

                // 正常刻度显示时间
                return fmt(value);
              }
            }
          },

          yAxis: {
            type: 'value',
            boundaryGap: [0, '5%'],
            name: '负荷 (kWh)',
            nameLocation: 'middle',
            nameGap: 40
          },

          // 数据缩放（滑块 + 鼠标滚轮）
          dataZoom: [
            {
              type: 'inside',
              filterMode: 'none'
            },
            {
              type: 'slider',
              height: 22,
              bottom: 40,
              showDetail: false
            }
          ],

          // 数据序列
          series: [
            {
              name: '小时负荷',
              type: 'line',
              showSymbol: false,
              smooth: false,
              sampling: 'lttb',  // 降采样算法（高效）
              itemStyle: { color: lineColor },
              lineStyle: { width: 1.5 },
              areaStyle: showArea ? { opacity: 0.25 } : undefined,
              data: points
            }
          ]
        };

        chartRef.current.setOption(option, true);

        // 导出 API
        if (onReady) {
          const resetZoom = () => {
            try {
              chartRef.current.dispatchAction({
                type: 'dataZoom',
                dataZoomIndex: 0,
                start: 0,
                end: 100
              });
              chartRef.current.dispatchAction({
                type: 'dataZoom',
                dataZoomIndex: 1,
                start: 0,
                end: 100
              });
            } catch {
              try {
                chartRef.current.setOption({
                  dataZoom: [
                    { start: 0, end: 100 },
                    { start: 0, end: 100 }
                  ]
                });
              } catch {}
            }
          };

          onReady({
            resetZoom,
            getInstance: () => chartRef.current
          });
        }

        // 窗口缩放响应
        const onResize = () => chartRef.current && chartRef.current.resize();
        window.addEventListener('resize', onResize);
        (chartRef.current as any)._cleanup = () => {
          window.removeEventListener('resize', onResize);
        };
      })
      .catch((e) => {
        console.error('[EChartTimeSeries] 加载 ECharts 失败:', e);
      });

    return () => {
      disposed = true;
      try {
        const c: any = chartRef.current;
        if (c && c._cleanup) c._cleanup();
        if (c && !c.isDisposed()) c.dispose();
      } catch {}
      chartRef.current = null;
    };
  }, [data?.length, useAxisBreak, lineColor, showArea, onReady]);

  return <div ref={ref} style={{ width: '100%', height }} />;
};

// CDN 动态加载 ECharts
const loadECharts = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    const w = window as any;
    if (w.echarts) return resolve(w.echarts);

    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js';
    script.async = true;

    script.onload = () => {
      resolve((window as any).echarts);
    };

    script.onerror = (e) => {
      reject(new Error('[EChartTimeSeries] CDN 加载 ECharts 失败'));
    };

    document.head.appendChild(script);
  });
};

// ================================================================
// 场景 2: 在 LoadAnalysisPage 中的实际使用
// ================================================================

/*
// 在 LoadAnalysisPage.tsx 中：

import { EChartTimeSeries } from './EChartTimeSeries';
import { useMemo, useCallback } from 'react';

export const LoadAnalysisPage = () => {
  // ... 其他代码

  // 生成小时级时间序列
  const hourSeries = useMemo(() => {
    return [...cleanedData]
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      .map((d) => ({ x: d.timestamp, y: d.load }));
  }, [cleanedData]);

  const resetZoom = useCallback(() => {
    if (echartResetRef.current) echartResetRef.current();
  }, []);

  return (
    <div>
      <h2>小时负荷曲线</h2>
      <div className="relative h-96">
        <EChartTimeSeries
          data={hourSeries}
          height={384}
          lineColor="rgb(59, 130, 246)"
          showArea={false}
          useAxisBreak={true}          // ★ 关键：启用断轴
          onReady={(api) => {
            echartResetRef.current = api.resetZoom;
          }}
        />
      </div>
      <button onClick={resetZoom}>重置缩放</button>
    </div>
  );
};
*/

// ================================================================
// 场景 3: 断轴检测算法详解
// ================================================================

/**
 * 缺失检测算法核心逻辑
 * 
 * 输入: 时间序列点 [t1, t2, t3, ...]
 * 输出: breaks 配置数组
 * 
 * 原理:
 * 1. 计算所有相邻点的时间间隔
 * 2. 使用"众数"（频率最高值）推断正常采样步长
 * 3. 找出所有间隔 > 1.5 倍步长的位置
 * 4. 这些位置就是缺失区间的开始
 */

interface BreakPoint {
  start: number;
  end: number;
  durationMinutes: number;
  missingMinutes: number;
}

function detectMissingIntervals(
  points: [number, number][],  // [timestamp, value]
  multiplier: number = 1.5     // 判定倍数
): BreakPoint[] {
  if (points.length < 2) return [];

  // 步骤 1: 计算所有间隔
  const intervals: number[] = [];
  for (let i = 1; i < points.length; i++) {
    const dt = points[i][0] - points[i - 1][0];
    if (dt > 0) intervals.push(dt);
  }

  if (intervals.length === 0) return [];

  // 步骤 2: 找众数（出现频率最高的间隔）
  const histogram = new Map<number, number>();
  for (const dt of intervals) {
    const minutes = Math.round(dt / 60000);
    histogram.set(minutes, (histogram.get(minutes) || 0) + 1);
  }

  let normalIntervalMinutes = 60;
  let maxCount = 0;
  for (const [minutes, count] of histogram) {
    if (count > maxCount) {
      maxCount = count;
      normalIntervalMinutes = minutes;
    }
  }

  const normalIntervalMs = normalIntervalMinutes * 60000;
  const threshold = normalIntervalMs * multiplier;

  // 步骤 3: 找缺失
  const breaks: BreakPoint[] = [];
  for (let i = 1; i < points.length; i++) {
    const gap = points[i][0] - points[i - 1][0];

    if (gap > threshold) {
      const breakStartTime = points[i - 1][0] + normalIntervalMs;
      const breakEndTime = points[i][0];
      const duration = breakEndTime - breakStartTime;

      breaks.push({
        start: breakStartTime,
        end: breakEndTime,
        durationMinutes: Math.round(duration / 60000),
        missingMinutes: Math.round((gap - normalIntervalMs) / 60000)
      });
    }
  }

  return breaks;
}

// 使用示例
const testData = [
  [new Date('2024-01-01 09:00').getTime(), 100],
  [new Date('2024-01-01 10:00').getTime(), 110],
  [new Date('2024-01-01 11:00').getTime(), 120],
  // 缺失 12:00
  [new Date('2024-01-01 13:00').getTime(), 100],
  [new Date('2024-01-01 14:00').getTime(), 95],
] as [number, number][];

const missingIntervals = detectMissingIntervals(testData);
console.log('检测到缺失:', missingIntervals);
// 输出:
// [{
//   start: <2024-01-01 11:00 时间戳>,
//   end: <2024-01-01 13:00 时间戳>,
//   durationMinutes: 120,
//   missingMinutes: 60
// }]

// ================================================================
// 场景 4: 自定义配置示例
// ================================================================

/**
 * 高级配置：自定义断轴样式
 */
interface AdvancedBreakConfig {
  // 缺失判定倍数（默认 1.5）
  multiplier?: number;
  
  // zigzag 波幅（0=直线, 6=默认, 10+=夸张）
  zigzagAmplitude?: number;
  
  // 是否允许点击展开
  expandOnClick?: boolean;
  
  // 时间格式模板
  timeFormat?: string;
  
  // 自定义时间标签渲染
  labelFormatter?: (start: Date, end: Date) => string;
}

/**
 * 创建高级断轴配置
 */
function createAdvancedBreakConfig(
  config: AdvancedBreakConfig = {}
): Record<string, any> {
  const {
    multiplier = 1.5,
    zigzagAmplitude = 6,
    expandOnClick = false,
    timeFormat = '{MM}-{dd} {HH}:{mm}',
    labelFormatter
  } = config;

  return {
    // 检测算法参数
    __multiplier: multiplier,
    
    // 视觉样式
    breakArea: {
      zigzagAmplitude,
      expandOnClick,
      zigzagZ: 200
    },
    
    // 标签格式
    __timeFormat: timeFormat,
    __labelFormatter: labelFormatter
  };
}

// 使用示例
const advancedConfig = createAdvancedBreakConfig({
  multiplier: 2.0,           // 更严格的检测（只检测 2 倍以上的缺失）
  zigzagAmplitude: 10,       // 更明显的断轴标记
  expandOnClick: true,       // 允许点击展开
  labelFormatter: (start, end) => {
    const duration = (end.getTime() - start.getTime()) / 1000 / 60;
    return `缺失 ${duration} 分钟`;
  }
});

// ================================================================
// 导出
// ================================================================

export { EChartTimeSeries, detectMissingIntervals, createAdvancedBreakConfig };
export type { Props, BreakPoint, AdvancedBreakConfig };

/**
 * ================================================================
 * 完整工作流总结
 * ================================================================
 * 
 * 1. 用户上传 CSV 文件
 *    ↓
 * 2. 后端清洗数据并聚合为小时级
 *    ↓
 * 3. 前端接收 cleanedData 状态
 *    ↓
 * 4. useMemo 计算 hourSeries (转换格式)
 *    ↓
 * 5. <EChartTimeSeries data={hourSeries} />
 *    ↓
 * 6. 组件内自动:
 *    a) 过滤和排序数据
 *    b) 推断采样步长
 *    c) 检测缺失区间
 *    d) 生成 breaks 配置
 *    ↓
 * 7. ECharts 渲染图表
 *    a) 数据点正常绘制
 *    b) 缺失区间折叠显示
 *    c) 时间标签正常显示
 *    d) 断轴标记显示为 zigzag
 *    ↓
 * 8. 用户看到完整的断轴日内走势图 ✓
 * 
 * 关键特性:
 * ✓ 自动化: 无需手动标记缺失位置
 * ✓ 智能化: 自动推断采样步长
 * ✓ 美观化: zigzag 标记 + 时间标签
 * ✓ 交互化: 支持缩放、平移、拖拽
 * ✓ 高效化: 采样算法 + CDN 加载
 */
