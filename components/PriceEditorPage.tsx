import React, { useEffect, useMemo, useState } from 'react';
import type { Schedule, DateRule, MonthlyTouPrices, PriceMap, TierId } from '../types';
import { MONTHS } from '../constants';
import { PriceStepChart, PricePoint } from './PriceStepChart';

interface PriceEditorPageProps {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    prices: MonthlyTouPrices;
  };
  onChange: (prices: MonthlyTouPrices) => void;
}

// 将字符串输入解析为 number|null，保留最多 4 位小数
const parsePrice = (s: string): number | null => {
  const v = s.trim();
  if (v === '') return null;
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  return Number(n.toFixed(4));
};

// 生成当前选择条件下的 24 小时价格序列，用于图表
const buildPriceSeries = (
  mode: 'month' | 'rule',
  idx: number,
  schedule: Schedule,
  rules: DateRule[],
  priceMapMonth: PriceMap
): PricePoint[] => {
  const res: PricePoint[] = [];
  if (mode === 'month') {
    for (let h = 0; h < 24; h++) {
      const tou = schedule[idx][h].tou as TierId;
      const price = priceMapMonth[tou] ?? null;
      res.push({ hour: h, price, tou });
    }
  } else {
    const rule = rules[idx];
    if (!rule) return res;
    for (let h = 0; h < 24; h++) {
      const tou = rule.schedule[h].tou as TierId;
      const price = priceMapMonth[tou] ?? null;
      res.push({ hour: h, price, tou });
    }
  }
  return res;
};

export const PriceEditorPage: React.FC<PriceEditorPageProps> = ({ scheduleData, onChange }) => {
  const { monthlySchedule, dateRules, prices } = scheduleData;

  // 右侧小色块图例颜色（与图表背景色系协调）
  // 图例与图表底色保持一致（与 PriceStepChart 中的 TOU_BG 对齐）
  const TOU_SWATCH: Record<TierId, string> = useMemo(() => ({
    '深': 'rgba(16, 185, 129, 0.10)',  // 与背景相同的半透明绿色
    '谷': 'rgba(134, 239, 172, 0.22)', // 半透明浅绿
    '平': 'rgba(148, 163, 184, 0.20)', // 半透明灰蓝
    '峰': 'rgba(251, 146, 60, 0.18)',  // 半透明橙
    '尖': 'rgba(248, 113, 113, 0.18)', // 半透明红
  }), []);

  // 计算每个月实际使用到的 TOU 档位集合（综合“月度默认规则”+“日期规则”）
  const usedTiersByMonth = useMemo(() => {
    // 先基于月度默认规则收集
    const monthSets: Array<Set<TierId>> = monthlySchedule.map((month) => {
      const s = new Set<TierId>();
      month.forEach(c => s.add(c.tou as TierId));
      return s;
    });

    // 再叠加日期规则：将规则使用到的 TOU 档位分配到其覆盖到的“月份（按月份编号 0..11，不区分年份）”
    const expandMonthsInRange = (startDate: string, endDate: string): number[] => {
      // 简化：按“月份编号”展开，不按年份区分
      const s = new Date(`${startDate}T00:00:00`);
      const e = new Date(`${endDate}T00:00:00`);
      // 从起始月份到结束月份逐月推进
      const res: number[] = [];
      let cur = new Date(s.getFullYear(), s.getMonth(), 1);
      const last = new Date(e.getFullYear(), e.getMonth(), 1);
      while (cur.getTime() <= last.getTime()) {
        res.push(cur.getMonth());
        cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
      }
      return Array.from(new Set(res));
    };

    const tiersOfRule = (ruleSchedule: any[]): Set<TierId> => {
      const s = new Set<TierId>();
      (ruleSchedule || []).forEach(cell => {
        const tou = (cell?.tou as TierId) || null;
        if (tou) s.add(tou);
      });
      return s;
    };

    (dateRules || []).forEach(rule => {
      try {
        const months = expandMonthsInRange(rule.startDate, rule.endDate);
        const ts = tiersOfRule(rule.schedule);
        months.forEach(m => {
          ts.forEach(t => monthSets[m].add(t));
        });
      } catch { /* ignore bad rule */ }
    });

    return monthSets;
  }, [monthlySchedule, dateRules]);

  // 规范化：清空当月未使用的 TOU 档的电价（综合月度+日期规则），避免“无尖却有尖价”的困惑
  useEffect(() => {
    const next = prices.map((pm, i) => {
      const used = usedTiersByMonth[i];
      const p: PriceMap = { ...pm } as any;
      (['深','谷','平','峰','尖'] as TierId[]).forEach(t => {
        if (!used.has(t)) p[t] = null;
      });
      return p;
    }) as MonthlyTouPrices;
    const same = JSON.stringify(next) === JSON.stringify(prices);
    if (!same) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usedTiersByMonth]);

  // 展示模式与索引：按月/按规则
  const [viewMode, setViewMode] = useState<'month' | 'rule'>('month');
  const [viewIndex, setViewIndex] = useState<number>(0); // month: 0-11; rule: 0..n-1

  // 批量应用：勾选月份 + 价格模板
  const [selectedMonths, setSelectedMonths] = useState<Set<number>>(new Set());
  const [batchPrice, setBatchPrice] = useState<PriceMap>({ '深': null, '谷': 0.3000, '平': 0.6000, '峰': 0.9000, '尖': null });

  // 缺价扫描与一键补齐（按中位数）
  const TIER_ORDER: TierId[] = useMemo(() => ['深','谷','平','峰','尖'], []);
  const missingStat = useMemo(() => {
    const details = prices.map((pm, i) => {
      const used = usedTiersByMonth[i];
      const missingTiers = TIER_ORDER.filter(t => used.has(t) && (pm[t] === null || !Number.isFinite(Number(pm[t]))));
      return { monthIndex: i, missingTiers };
    });
    const totalMissing = details.reduce((acc, d) => acc + d.missingTiers.length, 0);
    const monthsWithMissing = details.filter(d => d.missingTiers.length > 0).map(d => d.monthIndex);
    return { totalMissing, details, monthsWithMissing };
  }, [prices, usedTiersByMonth, TIER_ORDER]);

  const fillMissingByMedian = () => {
    // 计算每个档位的中位数（仅统计被使用的且为有效数值的项）
    const medians: Partial<Record<TierId, number>> = {};
    TIER_ORDER.forEach(t => {
      const values: number[] = [];
      for (let i = 0; i < 12; i++) {
        if (usedTiersByMonth[i].has(t)) {
          const v = prices[i][t];
          if (typeof v === 'number' && Number.isFinite(v)) values.push(v);
        }
      }
      if (values.length > 0) {
        const arr = values.slice().sort((a,b) => a - b);
        const mid = Math.floor(arr.length / 2);
        medians[t] = arr.length % 2 === 0 ? (arr[mid - 1] + arr[mid]) / 2 : arr[mid];
      }
    });
    const next = prices.map((pm, i) => {
      const used = usedTiersByMonth[i];
      const p: PriceMap = { ...pm } as any;
      TIER_ORDER.forEach(t => {
        const cur = p[t];
        const needFill = used.has(t) && (cur === null || !Number.isFinite(Number(cur)));
        if (needFill && medians[t] != null) {
          p[t] = Number((medians[t] as number).toFixed(4));
        }
      });
      return p;
    }) as MonthlyTouPrices;
    onChange(next);
  };

  const seriesData = useMemo(() => {
    const monthIdx = Math.min(Math.max(viewIndex, 0), 11);
    const priceMap = prices[monthIdx];
    return buildPriceSeries(viewMode, viewIndex, monthlySchedule, dateRules, priceMap);
  }, [viewMode, viewIndex, monthlySchedule, dateRules, prices]);

  const updateMonthPrice = (m: number, tou: TierId, value: number | null) => {
    const used = usedTiersByMonth[m];
    if (!used.has(tou)) return; // 未使用的档位不接受修改
    const next = prices.map((p, i) => i === m ? { ...p, [tou]: value } : p) as MonthlyTouPrices;
    onChange(next);
  };

  const copyMonthToAll = (m: number) => {
    const src = prices[m];
    const next = Array.from({ length: 12 }, (_, i) => {
      const used = usedTiersByMonth[i];
      const pm: PriceMap = { ...src } as any;
      (['深','谷','平','峰','尖'] as TierId[]).forEach(t => {
        if (!used.has(t)) pm[t] = null; // 目标月未使用的档位置空
      });
      return pm;
    }) as MonthlyTouPrices;
    onChange(next);
  };

  const toggleMonth = (m: number) => {
    setSelectedMonths(prev => {
      const s = new Set(prev);
      if (s.has(m)) s.delete(m); else s.add(m);
      return s;
    });
  };

  const applyBatchToSelected = () => {
    if (selectedMonths.size === 0) return;
    const next = prices.map((p, i) => {
      if (!selectedMonths.has(i)) return p;
      const used = usedTiersByMonth[i];
      const pm: PriceMap = { ...p } as any;
      (['深','谷','平','峰','尖'] as TierId[]).forEach(t => {
        pm[t] = used.has(t) ? (batchPrice as any)[t] : null; // 未使用档位清空
      });
      return pm;
    }) as MonthlyTouPrices;
    onChange(next);
  };

  return (
    <div className="space-y-6">
      {/* 缺价扫描与补齐 */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="font-medium">电价缺失扫描：</span>
            <span>共缺失 {missingStat.totalMissing} 项</span>
            {missingStat.monthsWithMissing.length > 0 && (
              <span className="ml-2">
                涉及月份：{missingStat.monthsWithMissing.map(m => MONTHS[m]).join('、')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded"
              onClick={fillMissingByMedian}
              disabled={missingStat.totalMissing === 0}
              title="将所有缺失的档位价格按同档位的年度中位数进行补齐"
            >
              一键补齐（按中位数）
            </button>
          </div>
        </div>
        {missingStat.details.some(d => d.missingTiers.length > 0) && (
          <ul className="mt-2 list-disc ml-5">
            {missingStat.details.filter(d => d.missingTiers.length > 0).map(d => (
              <li key={d.monthIndex}>
                {MONTHS[d.monthIndex]} 缺失：{d.missingTiers.join('、')}
              </li>
            ))}
          </ul>
        )}
      </div>
      {/* 月份电价表 */}
      <div id="section-price-table" className="scroll-mt-24 bg-white rounded-xl shadow-lg p-4">
        <h2 className="text-xl font-bold text-slate-800 mb-3">分时电价编辑（元/kWh）</h2>
        <div className="overflow-auto">
          <table className="min-w-full border border-slate-200 rounded-lg">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-2.5 py-1.5 text-left text-xs font-semibold text-slate-600">月份</th>
                {(['深','谷','平','峰','尖'] as TierId[]).map(t => (
                  <th key={t} className="px-2 py-1.5 text-center text-xs font-semibold text-slate-600">{t}</th>
                ))}
                <th className="px-2 py-1.5 text-center text-xs font-semibold text-slate-600">操作</th>
              </tr>
            </thead>
            <tbody>
              {prices.map((pm, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/60'}>
                  <td className="px-2.5 py-0.5 text-xs text-slate-700">{MONTHS[i]}</td>
                  {(['深','谷','平','峰','尖'] as TierId[]).map((t) => {
                    const used = usedTiersByMonth[i].has(t);
                    return (
                      <td key={t} className="px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.0001"
                          className={`w-24 border rounded px-1.5 py-0.5 text-xs ${used ? 'border-slate-300' : 'border-slate-200 bg-slate-50 text-slate-400'}`}
                          value={used ? (pm[t] ?? '') : ''}
                          onChange={(e) => used && updateMonthPrice(i, t, parsePrice(e.target.value))}
                          placeholder={used ? "空" : "未使用"}
                          disabled={!used}
                        />
                      </td>
                    );
                  })}
                  <td className="px-2 py-0.5 text-center">
                    <button className="px-2.5 py-0.5 bg-blue-600 text-white rounded text-xs" onClick={() => copyMonthToAll(i)}>复制到全年</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 批量设置 */}
      <div id="section-price-batch" className="scroll-mt-24 bg-white rounded-xl shadow-lg p-4">
        <h3 className="text-lg font-semibold text-slate-800 mb-3">批量设置</h3>
        <div className="flex flex-wrap gap-2 mb-3 text-sm">
          {Array.from({ length: 12 }, (_, i) => (
            <label key={i} className={`px-2 py-1 rounded border cursor-pointer ${selectedMonths.has(i) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-300'}`}>
              <input type="checkbox" className="mr-1" checked={selectedMonths.has(i)} onChange={() => toggleMonth(i)} />{MONTHS[i]}
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 items-end">
          {(['深','谷','平','峰','尖'] as TierId[]).map((t) => (
            <label key={t} className="text-sm text-slate-700">
              <span className="mr-1">{t}</span>
              <input
                type="number"
                step="0.0001"
                className="w-28 border border-slate-300 rounded px-2 py-1"
                value={batchPrice[t] ?? ''}
                onChange={(e) => setBatchPrice(prev => ({ ...prev, [t]: parsePrice(e.target.value) }))}
                placeholder="空"
              />
            </label>
          ))}
          <button className="px-4 py-2 bg-green-600 text-white rounded text-sm" onClick={applyBatchToSelected}>
            应用到选中月份
          </button>
        </div>
      </div>

      {/* 时序图 */}
      <div id="section-price-chart" className="scroll-mt-24 bg-white rounded-xl shadow-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-700 flex items-center gap-2">
              <span>展示模式</span>
              <select className="border border-slate-300 rounded px-2 py-1 text-sm" value={viewMode} onChange={(e) => { setViewMode(e.target.value as any); setViewIndex(0); }}>
                <option value="month">按月（默认规则）</option>
                <option value="rule">按日期规则</option>
              </select>
            </label>
            {viewMode === 'month' ? (
              <label className="text-sm text-slate-700 flex items-center gap-2">
                <span>月份</span>
                <select className="border border-slate-300 rounded px-2 py-1 text-sm" value={viewIndex} onChange={(e) => setViewIndex(Number(e.target.value))}>
                  {Array.from({ length: 12 }, (_, i) => (
                    <option key={i} value={i}>{MONTHS[i]}</option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="text-sm text-slate-700 flex items-center gap-2">
                <span>规则</span>
                <select className="border border-slate-300 rounded px-2 py-1 text-sm" value={viewIndex} onChange={(e) => setViewIndex(Number(e.target.value))}>
                  {dateRules.length === 0 ? <option value={0}>无规则</option> : dateRules.map((r, i) => (
                    <option key={r.id} value={i}>{r.name}</option>
                  ))}
                </select>
              </label>
            )}
          </div>

          {/* 右侧小色块图例，与左侧控件同一行、同高度 */}
          <div className="flex items-center gap-3 px-2 py-1 bg-white/90 border border-slate-200 rounded-lg shadow-sm">
            {(['深','谷','平','峰','尖'] as TierId[]).map(t => (
              <span key={t} className="inline-flex items-center gap-1.5 text-xs text-slate-700">
                <span style={{ width: 12, height: 12, borderRadius: 2, background: TOU_SWATCH[t], border: '1px solid rgba(0,0,0,0.15)' }} />
                <span>{t}</span>
              </span>
            ))}
          </div>
        </div>

        <PriceStepChart data={seriesData} height={360} />
      </div>
    </div>
  );
};

export default PriceEditorPage;
