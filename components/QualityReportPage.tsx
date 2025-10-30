import React from 'react';
import type { Schedule, DateRule, BackendAnalysisMeta, BackendQualityReport } from '../types';
import { QualityReportPanel } from './QualityReportPanel';

interface QualityReportPageProps {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
  };
  externalQualityReport?: BackendQualityReport | null;
  externalMetaInfo?: BackendAnalysisMeta | null;
}

export const QualityReportPage: React.FC<QualityReportPageProps> = ({ externalQualityReport, externalMetaInfo }) => {
  const hasData = !!externalQualityReport;
  return (
    <div className="space-y-6">
      <div className="p-6 bg-white rounded-xl shadow-lg">
        <h2 className="text-2xl font-bold text-slate-800">数据完整性分析</h2>
        <p className="text-sm text-slate-600 mt-1">该页面展示上传负荷数据的完整性与异常统计情况。</p>
      </div>

      {!hasData && (
        <div className="p-4 bg-slate-50 rounded-lg border border-dashed border-slate-300 text-sm text-slate-600">
          暂无数据。请先在页面顶部“负荷文件”处上传文件后再查看本页。
        </div>
      )}

      {hasData && externalQualityReport && (
        <QualityReportPanel report={externalQualityReport} meta={externalMetaInfo ?? null} />
      )}
    </div>
  );
};

export default QualityReportPage;

