import React from 'react';
import type { BackendQualityReport, BackendAnalysisMeta } from '../types';

export const QualityReportPanel: React.FC<{ report: BackendQualityReport; meta: BackendAnalysisMeta | null }> = ({ report, meta }) => {
  const missingDayCount = report.missing.missing_days.length;
  const totalMissingHours = report.missing.summary?.total_missing_hours ?? 0;
  const missingByMonth = report.missing.missing_hours_by_month || [];

  const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;
  const formatDateTime = (value: string | null | undefined) => (value ? new Date(value).toLocaleString() : '—');
  const anomalyLabel: Record<string, string> = {
    null: '空值',
    zero: '零值',
    negative: '负值',
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow-lg">
      <h2 className="text-2xl font-bold text-slate-800 mb-4">数据完整性分析报告</h2>

      {/* 基础信息 */}
      <div className="grid gap-4 md:grid-cols-2 mb-6">
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">基础信息</h3>
          <p className="text-sm text-slate-700">时间范围：{formatDateTime(meta?.start)} 至 {formatDateTime(meta?.end)}</p>
          <p className="text-sm text-slate-700">原始记录数：{meta?.total_records ?? 0}</p>
          <p className="text-sm text-slate-700">采样间隔：{meta?.source_interval_minutes ?? '-'} 分钟</p>
        </div>

        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">缺失总体情况</h3>
          <p className="text-sm text-slate-700">缺失天数：{missingDayCount} 天</p>
          <p className="text-sm text-slate-700">缺失小时数：{totalMissingHours} 小时</p>
          <p className="text-sm text-slate-700">
            完整度：
            {meta?.total_records ? (
              `${(100 - (totalMissingHours / ((meta.total_records / (meta.source_interval_minutes || 60)) || 1) * 100)).toFixed(2)}%`
            ) : (
              '-'
            )}
          </p>
        </div>
      </div>

      {/* 按月分类缺失分析 */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-slate-600 mb-3">按月分类缺失统计</h3>
        {missingByMonth.length === 0 ? (
          <p className="text-sm text-slate-700">无缺失数据。</p>
        ) : (
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">月份</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">缺失天数</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">缺失小时数</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {missingByMonth.map((item) => (
                  <tr key={item.month}>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{item.month}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{item.missing_days}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{item.missing_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 缺失日期列表 */}
      {report.missing.missing_days.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">缺失日期列表</h3>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="text-sm text-slate-700 space-y-1">
              {report.missing.missing_days.map((date) => (
                <div key={date}>{date}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 异常值统计 */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-slate-600 mb-3">异常值统计</h3>
        <div className="grid gap-4 md:grid-cols-3">
          {report.anomalies.map((item) => (
            <div key={item.kind} className="p-4 bg-slate-50 rounded-lg border border-slate-200">
              <p className="text-base font-semibold text-slate-800">{anomalyLabel[item.kind] ?? item.kind}</p>
              <p className="text-sm text-slate-700 mt-1">数量：{item.count}</p>
              <p className="text-sm text-slate-700">占比：{formatPercent(item.ratio)}</p>
              {item.samples.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-slate-500">示例：{item.samples.join(', ')}</p>
                  {item.samples.length > 3 && (
                    <p className="text-xs text-slate-400 mt-1">等 {item.samples.length} 个时间点</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 连续零值区间 */}
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-slate-600 mb-3">连续零值区间</h3>
        {report.continuous_zero_spans.length === 0 ? (
          <p className="text-sm text-slate-700">无连续零值。</p>
        ) : (
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">开始</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">结束</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">时长（小时）</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {report.continuous_zero_spans.map((span, idx) => (
                  <tr key={`${span.start}-${span.end}-${idx}`}>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{span.start}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{span.end}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-slate-700">{span.length_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default QualityReportPanel;
