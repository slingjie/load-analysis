/**
 * 数据清洗确认对话框组件
 * 
 * 功能：
 * 1. 展示零值时段详情，包含相邻天/月的负荷对比帮助用户判断
 * 2. 展示负值时段详情
 * 3. 支持用户对每个零值时段做出决策（正常停机 / 异常需插值）
 * 4. 支持全局负值处理策略（保留/取绝对值/置零）
 * 5. 支持"记住我的选择"功能
 */

import React, { useState, useEffect, useMemo } from 'react';
import type {
  CleaningAnalysisResponse,
  ZeroSpanDetail,
  NegativeSpanDetail,
  NullSpanDetail,
  ZeroDecision,
  NegativeStrategy,
  NullStrategy,
  CleaningConfigRequest,
} from '../types';

// localStorage 存储键
const CLEANING_PREFS_KEY = 'storageCycles:cleaningPrefs';

interface StoredCleaningPrefs {
  negativeStrategy: NegativeStrategy;
  rememberNegative: boolean;
  // 可扩展其他偏好
}

interface Props {
  visible: boolean;
  analysis: CleaningAnalysisResponse | null;
  onConfirm: (config: CleaningConfigRequest) => void;
  onCancel: () => void;
  loading?: boolean;
}

// 样式常量
const styles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  dialog: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    maxWidth: '900px',
    width: '90%',
    maxHeight: '85vh',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  header: {
    padding: '16px 24px',
    borderBottom: '1px solid #e0e0e0',
    backgroundColor: '#f5f5f5',
  },
  title: {
    margin: 0,
    fontSize: '18px',
    fontWeight: 600,
  },
  subtitle: {
    margin: '4px 0 0',
    fontSize: '13px',
    color: '#666',
  },
  content: {
    padding: '16px 24px',
    overflowY: 'auto' as const,
    flex: 1,
  },
  section: {
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '15px',
    fontWeight: 600,
    marginBottom: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '22px',
    height: '22px',
    borderRadius: '11px',
    fontSize: '12px',
    fontWeight: 600,
    color: '#fff',
    padding: '0 6px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: '13px',
  },
  th: {
    padding: '10px 8px',
    textAlign: 'left' as const,
    borderBottom: '2px solid #e0e0e0',
    backgroundColor: '#fafafa',
    fontWeight: 600,
  },
  td: {
    padding: '10px 8px',
    borderBottom: '1px solid #f0f0f0',
    verticalAlign: 'middle' as const,
  },
  contextCell: {
    backgroundColor: '#f8f9fa',
    padding: '6px 8px',
    fontSize: '12px',
    lineHeight: 1.5,
  },
  select: {
    padding: '6px 10px',
    borderRadius: '4px',
    border: '1px solid #d0d0d0',
    fontSize: '13px',
    cursor: 'pointer',
    minWidth: '100px',
  },
  footer: {
    padding: '16px 24px',
    borderTop: '1px solid #e0e0e0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#fafafa',
  },
  button: {
    padding: '10px 20px',
    borderRadius: '4px',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    border: 'none',
    transition: 'background-color 0.2s',
  },
  primaryButton: {
    backgroundColor: '#1976d2',
    color: '#fff',
  },
  secondaryButton: {
    backgroundColor: '#e0e0e0',
    color: '#333',
  },
  disabledButton: {
    backgroundColor: '#bdbdbd',
    color: '#fff',
    cursor: 'not-allowed',
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: '#666',
  },
  infoRow: {
    display: 'flex',
    gap: '16px',
    marginBottom: '12px',
    padding: '12px',
    backgroundColor: '#e3f2fd',
    borderRadius: '6px',
    fontSize: '13px',
  },
  infoItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  // 负荷对比小标签
  loadTag: {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '11px',
    marginRight: '6px',
  },
  loadTagNormal: {
    backgroundColor: '#e8f5e9',
    color: '#2e7d32',
  },
  loadTagWarning: {
    backgroundColor: '#fff3e0',
    color: '#e65100',
  },
  loadTagUnknown: {
    backgroundColor: '#f5f5f5',
    color: '#757575',
  },
};

// 格式化时间（简化显示）
const formatTime = (isoStr: string): string => {
  try {
    const d = new Date(isoStr);
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hour = d.getHours().toString().padStart(2, '0');
    const min = d.getMinutes().toString().padStart(2, '0');
    return `${month}/${day} ${hour}:${min}`;
  } catch {
    return isoStr;
  }
};

// 格式化负荷值
const formatLoad = (val: number | null | undefined): string => {
  if (val == null) return '-';
  return `${val.toFixed(1)} kW`;
};

// 判断负荷差异程度
const getLoadDiffLevel = (
  contextLoad: number | null | undefined,
  threshold: number = 50
): 'normal' | 'warning' | 'unknown' => {
  if (contextLoad == null) return 'unknown';
  if (contextLoad < threshold) return 'warning'; // 相邻天负荷也很低，可能正常停机
  return 'normal'; // 相邻天有负荷，说明当前零值可能异常
};

// 负荷对比展示组件
const LoadContext: React.FC<{ span: ZeroSpanDetail }> = ({ span }) => {
  const items = [
    { label: '前一天', value: span.prev_day_avg_load },
    { label: '后一天', value: span.next_day_avg_load },
    { label: '上月同日', value: span.prev_month_same_day_load },
    { label: '下月同日', value: span.next_month_same_day_load },
  ];
  
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
      {items.map((item, idx) => {
        const level = getLoadDiffLevel(item.value);
        const tagStyle = {
          ...styles.loadTag,
          ...(level === 'normal' ? styles.loadTagNormal :
              level === 'warning' ? styles.loadTagWarning :
              styles.loadTagUnknown),
        };
        return (
          <span key={idx} style={tagStyle}>
            {item.label}: {formatLoad(item.value)}
          </span>
        );
      })}
    </div>
  );
};

export const CleaningConfirmDialog: React.FC<Props> = ({
  visible,
  analysis,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  // 从 localStorage 读取偏好
  const savedPrefs = useMemo<StoredCleaningPrefs | null>(() => {
    try {
      const stored = localStorage.getItem(CLEANING_PREFS_KEY);
      if (stored) return JSON.parse(stored);
    } catch {}
    return null;
  }, []);

  // 空值处理策略 - 用户可选
  const [nullStrategy, setNullStrategy] = useState<NullStrategy>('interpolate');

  // 负值处理策略
  const [negativeStrategy, setNegativeStrategy] = useState<NegativeStrategy>(
    savedPrefs?.negativeStrategy ?? 'keep'
  );
  const [rememberNegative, setRememberNegative] = useState(savedPrefs?.rememberNegative ?? false);

  // 零值时段决策 Map: span.id -> 'normal' | 'abnormal'
  const [zeroDecisions, setZeroDecisions] = useState<Record<string, ZeroDecision>>({});

  // 初始化零值决策（默认基于相邻天数据智能判断）
  useEffect(() => {
    if (!analysis?.zero_spans) return;
    const initial: Record<string, ZeroDecision> = {};
    analysis.zero_spans.forEach(span => {
      // 智能默认值：如果相邻天都有较高负荷，则默认标记为异常
      const hasPrevLoad = span.prev_day_avg_load != null && span.prev_day_avg_load > 50;
      const hasNextLoad = span.next_day_avg_load != null && span.next_day_avg_load > 50;
      initial[span.id] = (hasPrevLoad || hasNextLoad) ? 'abnormal' : 'normal';
    });
    setZeroDecisions(initial);
  }, [analysis]);

  // 批量操作
  const setAllZeroDecisions = (decision: ZeroDecision) => {
    if (!analysis?.zero_spans) return;
    const newDecisions: Record<string, ZeroDecision> = {};
    analysis.zero_spans.forEach(span => {
      newDecisions[span.id] = decision;
    });
    setZeroDecisions(newDecisions);
  };

  // 保存偏好
  const savePreferences = () => {
    if (rememberNegative) {
      const prefs: StoredCleaningPrefs = {
        negativeStrategy,
        rememberNegative: true,
      };
      localStorage.setItem(CLEANING_PREFS_KEY, JSON.stringify(prefs));
    }
  };

  // 提交
  const handleConfirm = () => {
    savePreferences();
    const config: CleaningConfigRequest = {
      null_strategy: nullStrategy,  // 使用用户选择的策略
      negative_strategy: negativeStrategy,
      zero_decisions: zeroDecisions,
      remember_negative: rememberNegative,
    };
    onConfirm(config);
  };

  // 统计数据
  const stats = useMemo(() => {
    if (!analysis) return null;
    const abnormalCount = Object.values(zeroDecisions).filter(d => d === 'abnormal').length;
    const normalCount = Object.values(zeroDecisions).filter(d => d === 'normal').length;
    return {
      nullCount: analysis.null_point_count,
      zeroSpanCount: analysis.zero_spans.length,
      negativeSpanCount: analysis.negative_spans.length,
      abnormalCount,
      normalCount,
    };
  }, [analysis, zeroDecisions]);

  if (!visible || !analysis) return null;

  const hasZeroSpans = analysis.zero_spans.length > 0;
  const hasNegativeSpans = analysis.negative_spans.length > 0;
  const hasNullPoints = analysis.null_point_count > 0;

  return (
    <div style={styles.overlay} onClick={onCancel}>
      <div style={styles.dialog} onClick={e => e.stopPropagation()}>
        {/* 头部 */}
        <div style={styles.header}>
          <h2 style={styles.title}>📋 数据清洗确认</h2>
          <p style={styles.subtitle}>
            请检查以下异常数据，并选择处理方式。确认后将进行插值处理并计算储能次数。
          </p>
        </div>

        {/* 内容区域 */}
        <div style={styles.content}>
          {/* 数据概览 */}
          <div style={styles.infoRow}>
            <div style={styles.infoItem}>
              <strong>总数据点:</strong> {analysis.total_actual_points?.toLocaleString() ?? '-'}
            </div>
            <div style={styles.infoItem}>
              <strong>完整度:</strong> {((analysis.completeness_ratio ?? 0) * 100).toFixed(1)}%
            </div>
          </div>

          {/* 空值点区域 - 始终显示 */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <span style={{...styles.badge, backgroundColor: hasNullPoints ? '#9e9e9e' : '#4caf50'}}>
                {analysis.null_point_count || 0}
              </span>
              空值数据点（缺失值）
              {hasNullPoints ? (
                <span style={{fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px'}}>
                  检测到 {analysis.null_spans?.length || 0} 段空值时段
                </span>
              ) : (
                <span style={{fontSize: '12px', color: '#4caf50', fontWeight: 'normal', marginLeft: '8px'}}>
                  ✓ 无空值
                </span>
              )}
            </div>
            
            {hasNullPoints ? (
              <div style={{
                padding: '12px 16px',
                backgroundColor: '#f5f5f5',
                borderRadius: '6px',
                marginTop: '8px',
              }}>
                {/* 空值统计信息 */}
                <div style={{
                  display: 'flex',
                  gap: '24px',
                  marginBottom: '12px',
                  fontSize: '13px',
                  color: '#555',
                  flexWrap: 'wrap',
                }}>
                  <span>
                    <strong style={{color: '#333'}}>空值点数：</strong>
                    {analysis.null_point_count} 个
                  </span>
                  <span>
                    <strong style={{color: '#333'}}>对应时长：</strong>
                    {analysis.null_hours != null ? (
                      analysis.null_hours >= 24 
                        ? `${(analysis.null_hours / 24).toFixed(1)} 天`
                        : `${analysis.null_hours.toFixed(1)} 小时`
                    ) : '-'}
                  </span>
                  <span>
                    <strong style={{color: '#333'}}>占比：</strong>
                    {analysis.total_actual_points && analysis.null_point_count != null
                      ? ((analysis.null_point_count / (analysis.total_actual_points + analysis.null_point_count)) * 100).toFixed(2)
                      : '-'}%
                  </span>
                </div>

                {/* 空值时段列表 */}
                {analysis.null_spans && analysis.null_spans.length > 0 && (
                  <div style={{marginBottom: '12px'}}>
                    <table style={styles.table}>
                      <thead>
                        <tr>
                          <th style={styles.th}>时间段</th>
                          <th style={styles.th}>时长</th>
                          <th style={styles.th}>星期</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis.null_spans.slice(0, 10).map((span) => (
                          <tr key={span.id}>
                            <td style={styles.td}>
                              {formatTime(span.start_time)} ~ {formatTime(span.end_time)}
                            </td>
                            <td style={styles.td}>
                              {span.duration_hours.toFixed(1)}h ({span.point_count}点)
                            </td>
                            <td style={styles.td}>{span.weekday}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {analysis.null_spans.length > 10 && (
                      <div style={{marginTop: '8px', fontSize: '12px', color: '#666'}}>
                        还有 {analysis.null_spans.length - 10} 段空值时段未显示...
                      </div>
                    )}
                  </div>
                )}
                
                {/* 处理策略选择 */}
                <div style={{display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap'}}>
                  <label style={{fontWeight: 500, fontSize: '13px'}}>空值处理方式：</label>
                  <select
                    style={{...styles.select, minWidth: '200px'}}
                    value={nullStrategy}
                    onChange={(e) => setNullStrategy(e.target.value as NullStrategy)}
                  >
                    <option value="interpolate">📈 线性插值填充（推荐）</option>
                    <option value="keep">⏸️ 保留空值不处理</option>
                    <option value="delete">🗑️ 删除空值所在行</option>
                  </select>
                  <span style={{fontSize: '12px', color: '#888'}}>
                    {nullStrategy === 'interpolate' && '根据前后数据自动估算填充'}
                    {nullStrategy === 'keep' && '保留原始空值，可能影响计算准确性'}
                    {nullStrategy === 'delete' && '删除包含空值的数据行'}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{
                padding: '12px 16px',
                backgroundColor: '#e8f5e9',
                borderRadius: '6px',
                marginTop: '8px',
                color: '#2e7d32',
                fontSize: '13px',
              }}>
                数据完整，未检测到空值
              </div>
            )}
          </div>

          {/* 零值时段区域 - 始终显示 */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <span style={{...styles.badge, backgroundColor: hasZeroSpans ? '#ff9800' : '#4caf50'}}>
                {analysis.zero_spans.length}
              </span>
              连续零值时段
              {hasZeroSpans ? (
                <span style={{fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px'}}>
                  检测到 {analysis.zero_spans.length} 段负荷为0的连续时段，请判断是正常停机还是数据缺失
                </span>
              ) : (
                <span style={{fontSize: '12px', color: '#4caf50', fontWeight: 'normal', marginLeft: '8px'}}>
                  ✓ 无连续零值时段
                </span>
              )}
            </div>

            {hasZeroSpans ? (
              <>
                {/* 批量操作 */}
                <div style={{marginBottom: '12px', display: 'flex', gap: '8px'}}>
                  <button
                    style={{...styles.button, ...styles.secondaryButton, padding: '6px 12px', fontSize: '12px'}}
                    onClick={() => setAllZeroDecisions('normal')}
                  >
                    全部标记为正常
                  </button>
                  <button
                    style={{...styles.button, ...styles.secondaryButton, padding: '6px 12px', fontSize: '12px'}}
                    onClick={() => setAllZeroDecisions('abnormal')}
                  >
                    全部标记为异常
                  </button>
                </div>

                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>时间段</th>
                      <th style={styles.th}>时长</th>
                      <th style={styles.th}>星期</th>
                      <th style={styles.th}>相邻日期负荷参考</th>
                      <th style={styles.th}>判断</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.zero_spans.map((span) => (
                      <tr key={span.id}>
                        <td style={styles.td}>
                          {formatTime(span.start_time)} ~ {formatTime(span.end_time)}
                        </td>
                        <td style={styles.td}>
                          {span.duration_hours.toFixed(1)}h ({span.point_count}点)
                        </td>
                        <td style={styles.td}>{span.weekday}</td>
                        <td style={{...styles.td, ...styles.contextCell}}>
                          <LoadContext span={span} />
                        </td>
                        <td style={styles.td}>
                          <select
                            style={styles.select}
                            value={zeroDecisions[span.id] || 'normal'}
                            onChange={(e) => setZeroDecisions(prev => ({
                              ...prev,
                              [span.id]: e.target.value as ZeroDecision,
                            }))}
                          >
                            <option value="normal">正常停机</option>
                            <option value="abnormal">异常缺失</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                {/* 决策统计 */}
                {stats && (
                  <div style={{marginTop: '10px', fontSize: '13px', color: '#666'}}>
                    <span style={{color: '#4caf50'}}>✓ 正常保留: {stats.normalCount}个</span>
                    <span style={{marginLeft: '16px', color: '#ff5722'}}>→ 需要插值: {stats.abnormalCount}个</span>
                  </div>
                )}
              </>
            ) : (
              <div style={{
                padding: '12px 16px',
                backgroundColor: '#e8f5e9',
                borderRadius: '6px',
                marginTop: '8px',
                color: '#2e7d32',
                fontSize: '13px',
              }}>
                数据正常，未检测到连续零值时段
              </div>
            )}
          </div>

          {/* 负值时段区域 - 始终显示 */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <span style={{...styles.badge, backgroundColor: hasNegativeSpans ? '#f44336' : '#4caf50'}}>
                {analysis.negative_spans.length}
              </span>
              负值时段
              {hasNegativeSpans ? (
                <span style={{fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px'}}>
                  负值通常表示反向馈电（如光伏发电）
                </span>
              ) : (
                <span style={{fontSize: '12px', color: '#4caf50', fontWeight: 'normal', marginLeft: '8px'}}>
                  ✓ 无负值
                </span>
              )}
            </div>

            {hasNegativeSpans ? (
              <>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>时间段</th>
                      <th style={styles.th}>时长</th>
                      <th style={styles.th}>最小值</th>
                      <th style={styles.th}>平均值</th>
                      <th style={styles.th}>星期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.negative_spans.slice(0, 10).map((span) => (
                      <tr key={span.id}>
                        <td style={styles.td}>
                          {formatTime(span.start_time)} ~ {formatTime(span.end_time)}
                        </td>
                        <td style={styles.td}>
                          {span.duration_hours.toFixed(1)}h ({span.point_count}点)
                        </td>
                        <td style={{...styles.td, color: '#f44336'}}>
                          {span.min_value.toFixed(2)} kW
                        </td>
                        <td style={{...styles.td, color: '#f44336'}}>
                          {span.avg_value.toFixed(2)} kW
                        </td>
                        <td style={styles.td}>{span.weekday}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {analysis.negative_spans.length > 10 && (
                  <div style={{marginTop: '8px', fontSize: '12px', color: '#666'}}>
                    还有 {analysis.negative_spans.length - 10} 个负值时段未显示...
                  </div>
                )}

                {/* 负值处理策略 */}
                <div style={{marginTop: '16px', display: 'flex', alignItems: 'center', gap: '16px'}}>
                  <label style={{fontWeight: 500, fontSize: '13px'}}>负值处理策略：</label>
                  <select
                    style={{...styles.select, minWidth: '140px'}}
                    value={negativeStrategy}
                    onChange={(e) => setNegativeStrategy(e.target.value as NegativeStrategy)}
                  >
                    <option value="keep">保留原值（反向馈电）</option>
                    <option value="abs">取绝对值</option>
                    <option value="zero">置为零</option>
                  </select>
                </div>
              </>
            ) : (
              <div style={{
                padding: '12px 16px',
                backgroundColor: '#e8f5e9',
                borderRadius: '6px',
                marginTop: '8px',
                color: '#2e7d32',
                fontSize: '13px',
              }}>
                数据正常，未检测到负值
              </div>
            )}
          </div>

          {/* 无任何异常时的简洁提示（三个区域都无异常时显示） */}
          {!hasZeroSpans && !hasNegativeSpans && !hasNullPoints && (
            <div style={{
              padding: '20px',
              textAlign: 'center',
              color: '#4caf50',
              fontSize: '15px',
              backgroundColor: '#e8f5e9',
              borderRadius: '8px',
              marginTop: '16px',
            }}>
              🎉 数据质量良好，所有检查项均已通过！
            </div>
          )}
        </div>

        {/* 底部 */}
        <div style={styles.footer}>
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={rememberNegative}
              onChange={(e) => setRememberNegative(e.target.checked)}
            />
            记住负值处理偏好
          </label>

          <div style={{display: 'flex', gap: '12px'}}>
            <button
              style={{...styles.button, ...styles.secondaryButton}}
              onClick={onCancel}
              disabled={loading}
            >
              取消
            </button>
            <button
              style={{
                ...styles.button,
                ...(loading ? styles.disabledButton : styles.primaryButton),
              }}
              onClick={handleConfirm}
              disabled={loading}
            >
              {loading ? '处理中...' : '确认并计算'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CleaningConfirmDialog;
