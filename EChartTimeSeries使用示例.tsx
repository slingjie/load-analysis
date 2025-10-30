/**
 * 小时负荷曲线 - 断轴日内走势图（使用示例）
 * 
 * 当数据出现缺失时，图表会自动显示"断轴"效果，而不是直接连接
 * 
 * 关键特性：
 * 1. 自动检测缺失区间 (间隔 > 1.5 倍采样步长)
 * 2. 显示 zigzag 断轴标记
 * 3. 标签显示"缺失时间段"
 * 4. 支持缩放、平移、交互
 */

import React, { useMemo, useCallback, useState } from 'react';
import { EChartTimeSeries } from './EChartTimeSeries';

/**
 * 示例 1：正常小时负荷序列（无缺失）
 */
export const Example1_NormalData = () => {
  const data = useMemo(() => {
    const arr = [];
    for (let i = 0; i < 24; i++) {
      const time = new Date('2024-01-01');
      time.setHours(i, 0, 0, 0);
      arr.push({ x: time, y: Math.random() * 100 + 50 });
    }
    return arr;
  }, []);

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h3 className="text-lg font-bold mb-4">示例 1: 无缺失数据 (24小时连贯)</h3>
      <p className="text-gray-600 mb-4">效果: 线条连贯，无断轴</p>
      <EChartTimeSeries 
        data={data} 
        height={300}
        useAxisBreak={true}
      />
    </div>
  );
};

/**
 * 示例 2: 含缺失数据 (11:30 - 13:00 缺失)
 */
export const Example2_MissingData = () => {
  const data = useMemo(() => {
    const arr = [];
    
    // 09:30 - 11:30 (正常)
    for (let i = 9.5; i < 11.5; i += 1/60) {
      const time = new Date('2024-01-01');
      const h = Math.floor(i);
      const m = Math.round((i - h) * 60);
      time.setHours(h, m, 0, 0);
      arr.push({ x: time, y: Math.random() * 100 + 50 });
    }
    
    // 缺失 11:30 - 13:00
    
    // 13:00 - 15:00 (正常)
    for (let i = 13; i < 15; i += 1/60) {
      const time = new Date('2024-01-01');
      time.setHours(i, Math.round((i - Math.floor(i)) * 60), 0, 0);
      arr.push({ x: time, y: Math.random() * 100 + 50 });
    }
    
    return arr;
  }, []);

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h3 className="text-lg font-bold mb-4">示例 2: 含缺失数据 (11:30 - 13:00 缺失 1.5 小时)</h3>
      <p className="text-gray-600 mb-4">效果: 自动生成断轴标记，显示"11:30 / 13:00"</p>
      <EChartTimeSeries 
        data={data} 
        height={300}
        lineColor="rgb(239, 68, 68)"
        useAxisBreak={true}
      />
    </div>
  );
};

/**
 * 示例 3: 多段缺失
 */
export const Example3_MultipleBreaks = () => {
  const data = useMemo(() => {
    const arr = [];
    
    // 分段生成数据
    const segments = [
      { start: 0, end: 3 },       // 00:00 - 03:00
      { start: 5, end: 8 },       // 05:00 - 08:00 (缺失 3-5)
      { start: 10, end: 12 },     // 10:00 - 12:00 (缺失 8-10)
      { start: 15, end: 18 },     // 15:00 - 18:00 (缺失 12-15)
      { start: 20, end: 24 },     // 20:00 - 00:00+1 (缺失 18-20)
    ];
    
    for (const seg of segments) {
      for (let h = seg.start; h < seg.end; h++) {
        for (let m = 0; m < 60; m += 15) {
          const time = new Date('2024-01-01');
          time.setHours(h, m, 0, 0);
          arr.push({ x: time, y: Math.random() * 80 + 40 });
        }
      }
    }
    
    return arr;
  }, []);

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h3 className="text-lg font-bold mb-4">示例 3: 多段缺失 (5 个间隙)</h3>
      <p className="text-gray-600 mb-4">效果: 多个断轴标记，分别标注各缺失区间</p>
      <EChartTimeSeries 
        data={data} 
        height={300}
        lineColor="rgb(34, 197, 94)"
        useAxisBreak={true}
      />
    </div>
  );
};

/**
 * 示例 4: 禁用断轴（对比效果）
 */
export const Example4_NoBreak = () => {
  const data = useMemo(() => {
    const arr = [];
    
    // 09:30 - 11:30
    for (let i = 9.5; i < 11.5; i += 1/60) {
      const time = new Date('2024-01-01');
      const h = Math.floor(i);
      const m = Math.round((i - h) * 60);
      time.setHours(h, m, 0, 0);
      arr.push({ x: time, y: Math.random() * 100 + 50 });
    }
    
    // 13:00 - 15:00
    for (let i = 13; i < 15; i += 1/60) {
      const time = new Date('2024-01-01');
      time.setHours(i, Math.round((i - Math.floor(i)) * 60), 0, 0);
      arr.push({ x: time, y: Math.random() * 100 + 50 });
    }
    
    return arr;
  }, []);

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h3 className="text-lg font-bold mb-4">示例 4: 禁用断轴 (useAxisBreak=false)</h3>
      <p className="text-gray-600 mb-4">⚠️ 效果: 缺失区间被直接连接（不推荐！）</p>
      <EChartTimeSeries 
        data={data} 
        height={300}
        lineColor="rgb(168, 85, 247)"
        useAxisBreak={false}  // 禁用
      />
    </div>
  );
};

/**
 * 示例 5: 在 LoadAnalysisPage 中的实际使用
 */
export const RealUsageInLoadAnalysisPage = () => {
  const [echartResetRef, setEchartResetRef] = React.useRef<(() => void) | null>(null);

  // 这是 LoadAnalysisPage.tsx 中的实际代码
  const cleanedData = [
    // ... 来自后端的数据
    { timestamp: new Date('2024-01-01 00:00'), load: 100 },
    { timestamp: new Date('2024-01-01 01:00'), load: 110 },
    // ... 更多数据
  ];

  const hourSeries = useMemo(() => {
    return [...cleanedData]
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      .map((d) => ({ x: d.timestamp, y: d.load }));
  }, [cleanedData]);

  const resetZoom = useCallback(() => {
    if (echartResetRef.current) echartResetRef.current();
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow-lg">
      <h2 className="text-2xl font-bold text-slate-800 mb-4">2. 小时负荷曲线</h2>
      <div className="relative h-96">
        <EChartTimeSeries
          data={hourSeries}
          height={384}
          showArea={false}
          useAxisBreak={true}  // ← 关键配置
          onReady={(api) => { 
            setEchartResetRef(api.resetZoom); 
          }}
        />
      </div>
      <div className="flex items-center justify-between mt-2 text-xs text-slate-600">
        <span>提示：底部滑块拖动双柄/选区调整范围；拖拽平移；滚轮缩放；双击放大</span>
        <button 
          onClick={resetZoom} 
          className="px-2 py-1 border border-slate-300 rounded-md hover:bg-slate-50"
        >
          重置缩放
        </button>
      </div>
    </div>
  );
};

/**
 * 整合示例页面
 */
export const AllExamples = () => {
  return (
    <div className="space-y-6 p-8 bg-gray-50">
      <h1 className="text-3xl font-bold">断轴日内走势图 - 使用示例</h1>
      <p className="text-gray-600">
        当小时负荷数据出现缺失时，图表自动显示断轴效果，而不是直接连接
      </p>
      
      <Example1_NormalData />
      <Example2_MissingData />
      <Example3_MultipleBreaks />
      <Example4_NoBreak />
      <RealUsageInLoadAnalysisPage />
    </div>
  );
};
