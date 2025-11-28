import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  MonthlyTouPrices,
  Schedule,
  DateRule,
  BackendStorageCyclesResponse,
  BackendTipDischargeSummary,
  CleaningAnalysisResponse,
  CleaningConfigRequest,
} from '../types';
import type { LoadDataPoint } from '../utils';
import {
  computeStorageCycles,
  computeStorageCyclesWithProgress,
  analyzeDataForCleaning,
  applyDataCleaning,
  type StorageParamsPayload,
} from '../storageApi';
import UploadProgressRing from './UploadProgressRing';
import CleaningConfirmDialog from './CleaningConfirmDialog';

const CONFIG_STORAGE_PREFIX = 'storageCyclesConfig:';
const SOLVE_CAPACITY_STEPS = 8; // 反推容量时默认预计算步数（可通过界面修改实际步数）

// 基于后端返回的日度 cycles 计算“全年合计等效循环数”
const computeYearEquivalentCyclesFromDays = (
  days: BackendStorageCyclesResponse['days'] | undefined | null,
): number => {
  if (!days || !days.length) return 0;
  const monthDaySets: Array<Set<string>> = Array.from({ length: 12 }, () => new Set<string>());
  const monthTotal: number[] = new Array(12).fill(0);
  const monthYear: Array<number | null> = new Array(12).fill(null);

  days.forEach(d => {
    if (!d?.date) return;
    const parts = String(d.date).split('-');
    if (parts.length !== 3) return;
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    if (!year || !month || month < 1 || month > 12) return;
    const idx = month - 1;
    const dateKey = String(d.date);
    const cyclesVal = Number(d.cycles ?? 0);
    // 只有 cycles > 0 的日期才计入"有效天数"
    if (cyclesVal > 0) {
      monthDaySets[idx].add(dateKey);
    }
    monthTotal[idx] += cyclesVal;
    if (monthYear[idx] == null) {
      monthYear[idx] = year;
    }
  });

  const monthEqCyclesArr: Array<number | null> = new Array(12).fill(null);
  for (let i = 0; i < 12; i++) {
    const validDays = monthDaySets[i].size;
    if (validDays > 0) {
      const y = monthYear[i] ?? new Date().getFullYear();
      const monthDaysCount = new Date(y, i + 1, 0).getDate();
      const total = monthTotal[i];
      monthEqCyclesArr[i] = (total / validDays) * monthDaysCount;
    }
  }

  const yearEqCyclesVal = monthEqCyclesArr.reduce(
    (sum, v) => (v != null ? sum + v : sum),
    0,
  );
  return yearEqCyclesVal;
};

interface Props {
  scheduleData: {
    monthlySchedule: Schedule;
    dateRules: DateRule[];
    prices: MonthlyTouPrices;
  };
  externalCleanedData?: LoadDataPoint[] | null; // 来自“负荷分析”页的已上传点
  onNavigateProfit?: (date: string) => void;
  onLatestRunChange?: (payload: StorageParamsPayload, response: BackendStorageCyclesResponse) => void;
}

export const StorageCyclesPage: React.FC<Props> = ({
  scheduleData,
  externalCleanedData,
  onNavigateProfit,
  onLatestRunChange,
}) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string>('');
  const [useAnalyzedData, setUseAnalyzedData] = useState<boolean>(!!(externalCleanedData && externalCleanedData.length > 0));

  // 是否已存在外部清洗后的数据，便于展示统计范围
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
  const [progress, setProgress] = useState<number>(0); // 保留给兼容但主要使用环形
  const [cyclePhase, setCyclePhase] = useState<'idle'|'uploading'|'computing'|'done'|'error'>('idle');
  const [cycleProgressPct, setCycleProgressPct] = useState(0);
  const [showCycleRing, setShowCycleRing] = useState(false);
  const [uploadBytesTotal, setUploadBytesTotal] = useState<number | null>(null);
  const [uploadEtaSeconds, setUploadEtaSeconds] = useState<number | null>(null);
  const cycleAbortRef = useRef<() => void>(() => {});
  const uploadSamplesRef = useRef<Array<{time:number;loaded:number}>>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BackendStorageCyclesResponse | null>(null);
  const [savedConfigName, setSavedConfigName] = useState('');
  const [availableConfigs, setAvailableConfigs] = useState<string[]>([]);
  const [selectedSavedConfig, setSelectedSavedConfig] = useState('');
  const [configNotice, setConfigNotice] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [targetYearEqCyclesInput, setTargetYearEqCyclesInput] = useState<string>('');
  const [solveStartCapacityKwh, setSolveStartCapacityKwh] = useState<number>(5000);
  const [solveStepCapacityKwh, setSolveStepCapacityKwh] = useState<number>(500);
  const [solveSteps, setSolveSteps] = useState<number>(SOLVE_CAPACITY_STEPS);
  const [solveSuggestion, setSolveSuggestion] = useState<{
    targetYearEq: number;
    bestCapacityKwh: number;
    bestYearEqCycles: number;
  } | null>(null);
  const didAutoApplyDefaultRef = useRef(false);

  // ================== 数据清洗相关状态 ==================
  // 是否启用清洗流程（用户可关闭）
  const [enableCleaning, setEnableCleaning] = useState(true);
  // 清洗分析结果
  const [cleaningAnalysis, setCleaningAnalysis] = useState<CleaningAnalysisResponse | null>(null);
  // 清洗对话框可见性
  const [cleaningDialogVisible, setCleaningDialogVisible] = useState(false);
  // 清洗进行中
  const [cleaningLoading, setCleaningLoading] = useState(false);
  // 待处理的文件（用于对话框确认后继续）
  const pendingFileRef = useRef<File | null>(null);
  // 清洗后的数据点（用于后续计算）
  const cleanedPointsRef = useRef<{ timestamp: string; load_kwh: number }[] | null>(null);

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

  // 简化的默认参数（可在页面上编辑的表单项）
  const [params, setParams] = useState({
    capacity_kwh: 5000,
    c_rate: 0.5,
    single_side_efficiency: 0.92,
    depth_of_discharge: 0.9,
    soc_min: 0.05,
    soc_max: 0.95,
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
    if (!(p.soc_min >= 0 && p.soc_min < 1)) return 'SOC 下限需在 [0, 1) 之间';
    if (!(p.soc_max > 0 && p.soc_max <= 1)) return 'SOC 上限需在 (0, 1] 之间';
    if (!(p.soc_min < p.soc_max)) return 'SOC 下限需小于 SOC 上限';
    if (!(p.merge_threshold_minutes >= 0)) return '合并阈值需为非负整数';
    if (p.metering_mode === 'transformer_capacity') {
      if (!(p.transformer_capacity_kva > 0)) return '变压器容量(kVA) 必须大于 0';
      if (!(p.transformer_power_factor > 0 && p.transformer_power_factor <= 1)) return '功率因数需在 (0, 1]';
    }
    return null;
  };

  const loadStoredConfigs = useCallback(() => {
    if (typeof window === 'undefined') return;
    const names = Object.keys(window.localStorage ?? {})
      .filter(key => key.startsWith(CONFIG_STORAGE_PREFIX))
      .map(key => key.slice(CONFIG_STORAGE_PREFIX.length));
    setAvailableConfigs(names);
    setSelectedSavedConfig(prev => (names.includes(prev) ? prev : ''));
  }, []);

  useEffect(() => {
    loadStoredConfigs();
  }, [loadStoredConfigs]);

  // 页面初次加载时自动加载“最近保存”的配置（按 savedAt 最大值选取）
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (didAutoApplyDefaultRef.current) return;

    try {
      const keys = Object.keys(window.localStorage ?? {}).filter(key =>
        key.startsWith(CONFIG_STORAGE_PREFIX),
      );
      if (!keys.length) return;

      let latestName: string | null = null;
      let latestPayload: any = null;
      let latestTs = 0;

      keys.forEach(fullKey => {
        const raw = window.localStorage.getItem(fullKey);
        if (!raw) return;
        try {
          const parsed = JSON.parse(raw);
          const savedAt = parsed?.savedAt;
          const ts = savedAt ? Date.parse(savedAt) : 0;
          if (Number.isFinite(ts) && ts >= latestTs) {
            latestTs = ts;
            latestPayload = parsed;
            latestName = fullKey.slice(CONFIG_STORAGE_PREFIX.length);
          }
        } catch {
          // 单个配置解析失败不影响整体
        }
      });

      if (!latestPayload || !latestName) return;

      // 应用最近保存的配置到基础参数与反推容量参数
      if (latestPayload.params) {
        setParams(p => ({ ...p, ...latestPayload.params }));
      }
      if (latestPayload.solveConfig) {
        const cfg = latestPayload.solveConfig as any;
        if (typeof cfg.solveStartCapacityKwh === 'number') {
          setSolveStartCapacityKwh(cfg.solveStartCapacityKwh);
        }
        if (typeof cfg.solveStepCapacityKwh === 'number') {
          setSolveStepCapacityKwh(cfg.solveStepCapacityKwh);
        }
        if (typeof cfg.solveSteps === 'number' && cfg.solveSteps > 0) {
          setSolveSteps(cfg.solveSteps);
        }
        if (cfg.targetYearEqCyclesInput != null) {
          setTargetYearEqCyclesInput(String(cfg.targetYearEqCyclesInput));
        }
      }

      setSavedConfigName(latestName);
      setSelectedSavedConfig(latestName);
      setConfigNotice(`已自动加载最近保存的配置“${latestName}”`);
      didAutoApplyDefaultRef.current = true;
    } catch {
      // 自动加载失败时静默降级，不影响手动选择
    }
  }, []);

  const handleUpload = async () => {
    setError(null);
    setResult(null);
    setSolveSuggestion(null);
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
      setError('"负荷分析"页没有可用数据，请先在"负荷分析"页上传并处理，或在本页选择负荷文件。');
      return;
    }

    // ===== 新增：数据清洗流程 =====
    // 如果启用清洗并且是上传新文件（非复用已分析数据），则先分析数据
    console.log('[StorageCycles] 清洗流程检查:', { enableCleaning, hasFile: !!file, useAnalyzedData });
    if (enableCleaning && file && !useAnalyzedData) {
      try {
        console.log('[StorageCycles] 开始数据清洗分析...');
        setLoading(true);
        setCyclePhase('uploading');
        setShowCycleRing(true);
        setCycleProgressPct(10);
        
        // 调用后端分析接口
        console.log('[StorageCycles] 调用 analyzeDataForCleaning API...');
        const analysis = await analyzeDataForCleaning(file);
        console.log('[StorageCycles] 分析结果:', analysis);
        setCycleProgressPct(40);
        
        // 判断是否需要用户确认（有零值、负值时段或空值需要用户知晓）
        const needsConfirm = analysis.zero_spans.length > 0 || 
                            analysis.negative_spans.length > 0 ||
                            analysis.null_point_count > 0;
        
        console.log('[StorageCycles] needsConfirm:', needsConfirm, {
          zeroSpans: analysis.zero_spans.length,
          negativeSpans: analysis.negative_spans.length,
          nullPoints: analysis.null_point_count,
        });
        
        if (needsConfirm) {
          // 保存状态，等待用户确认
          console.log('[StorageCycles] 需要用户确认，显示清洗对话框');
          setCleaningAnalysis(analysis);
          pendingFileRef.current = file;
          setCleaningDialogVisible(true);
          setLoading(false);
          setShowCycleRing(false);
          setCyclePhase('idle');
          return; // 等待用户在对话框中确认
        }
        
        // 无零值/负值异常，但仍需处理空值
        // 使用默认配置进行清洗（空值插值，无零值/负值处理）
        setCycleProgressPct(50);
        const defaultConfig: CleaningConfigRequest = {
          null_strategy: 'interpolate',
          negative_strategy: 'keep',
          zero_decisions: {},
        };
        const cleanResult = await applyDataCleaning(file, defaultConfig);
        
        // 保存清洗后的数据点
        const cleanedPoints = cleanResult.cleaned_points.map(p => ({
          timestamp: p.timestamp,
          load_kwh: p.load_kwh,
        }));
        
        console.log('[StorageCycles] 自动清洗完成（无需用户确认）', {
          nullInterpolated: cleanResult.null_points_interpolated,
          totalPoints: cleanedPoints.length,
        });
        
        setLoading(false);
        setShowCycleRing(false);
        
        // 使用清洗后的数据继续计算
        await proceedWithCalculation(file, false, cleanedPoints);
        return;
      } catch (e: any) {
        setLoading(false);
        setShowCycleRing(false);
        setCyclePhase('error');
        setError(`数据分析失败: ${e?.message || '未知错误'}`);
        return;
      }
    }

    // 未启用清洗或使用已分析数据，继续原有的计算流程
    await proceedWithCalculation(file, useAnalyzedData);
  };

  // 清洗对话框确认后的回调
  const handleCleaningConfirm = async (config: CleaningConfigRequest) => {
    const file = pendingFileRef.current;
    if (!file) {
      setError('文件丢失，请重新选择');
      setCleaningDialogVisible(false);
      return;
    }

    try {
      setCleaningLoading(true);
      
      // 调用后端应用清洗
      const cleanResult = await applyDataCleaning(file, config);
      
      // 保存清洗后的数据点
      cleanedPointsRef.current = cleanResult.cleaned_points.map(p => ({
        timestamp: p.timestamp,
        load_kwh: p.load_kwh,
      }));
      
      console.log('[StorageCycles] 清洗完成', {
        nullInterpolated: cleanResult.null_points_interpolated,
        zeroKept: cleanResult.zero_spans_kept,
        zeroInterpolated: cleanResult.zero_spans_interpolated,
        negativeKept: cleanResult.negative_points_kept,
      });
      
      setCleaningDialogVisible(false);
      setCleaningLoading(false);
      
      // 使用清洗后的数据继续计算
      await proceedWithCalculation(file, false, cleanedPointsRef.current);
    } catch (e: any) {
      setCleaningLoading(false);
      setError(`数据清洗失败: ${e?.message || '未知错误'}`);
    }
  };

  // 清洗对话框取消
  const handleCleaningCancel = () => {
    setCleaningDialogVisible(false);
    pendingFileRef.current = null;
    setCleaningAnalysis(null);
  };

  // 抽取计算流程为独立函数
  const proceedWithCalculation = async (
    file: File | null,
    useExternal: boolean,
    cleanedPoints?: { timestamp: string; load_kwh: number }[],
  ) => {
    // 仅在有有效数据时构造 points，并按时间排序
    let pointsPayload: { timestamp: string; load_kwh: number }[] | undefined;
    
    if (cleanedPoints && cleanedPoints.length > 0) {
      // 使用清洗后的数据
      pointsPayload = cleanedPoints;
    } else if (useExternal && externalCleanedData && externalCleanedData.length > 0) {
      // 使用负荷分析页的数据
      pointsPayload = externalCleanedData
        .slice()
        .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
        .map(p => ({
          timestamp: toLocalNaiveString(p.timestamp),
          load_kwh: Number(p.load),
        }));
    }

    const payload: StorageParamsPayload = {
      storage: {
        capacity_kwh: params.capacity_kwh,
        c_rate: params.c_rate,
        single_side_efficiency: params.single_side_efficiency,
        depth_of_discharge: params.depth_of_discharge,
        soc_min: params.soc_min,
        soc_max: params.soc_max,
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

    // 简单防呆：无放电窗口或尖价全空时阻止测算，避免算出 0
    const hasDischarge = Array.isArray(payload.strategySource?.monthlySchedule)
      && payload.strategySource.monthlySchedule.some((monthRow: any[]) =>
        Array.isArray(monthRow) && monthRow.some(cell => cell?.op === '放'));
    const hasAnyPrice = Array.isArray(payload.monthlyTouPrices)
      && payload.monthlyTouPrices.some(mp => mp && Object.values(mp).some(v => v != null));
    console.debug('[StorageCycles] payload preview', payload, { hasDischarge, hasAnyPrice });
    if (!hasDischarge) {
      setError('当前排程没有放电窗口，请先在排程/逻辑中设置“放”时段后再测算。');
      return;
    }
    if (!hasAnyPrice) {
      setError('当前电价配置全部为空，请先设置 TOU 电价（含尖/峰/平/谷）。');
      return;
    }

    try {
      const v = validateParams();
      if (v) { setError(v); return; }
      setLoading(true);
      // 如果有清洗后的数据，不需要上传文件
      const shouldUploadFile = file && !cleanedPoints;
      setCyclePhase(shouldUploadFile ? 'uploading' : 'computing');
      setCycleProgressPct(0);
      setShowCycleRing(true);
      setUploadEtaSeconds(null);
      uploadSamplesRef.current = [];

      if (shouldUploadFile) {
        const { promise, abort } = computeStorageCyclesWithProgress(file, payload, (loaded, total) => {
          setUploadBytesTotal(total);
          const pct = Math.round((loaded / total) * 100);
          setCycleProgressPct(pct);
          const now = performance.now();
          uploadSamplesRef.current.push({ time: now, loaded });
          if (uploadSamplesRef.current.length > 6) uploadSamplesRef.current.shift();
          if (loaded < total) {
            if (uploadSamplesRef.current.length >= 2) {
              const first = uploadSamplesRef.current[0];
              const last = uploadSamplesRef.current[uploadSamplesRef.current.length - 1];
              const bytesDelta = last.loaded - first.loaded;
              const timeDeltaSec = (last.time - first.time)/1000;
              if (bytesDelta > 0 && timeDeltaSec > 0) {
                const speed = bytesDelta / timeDeltaSec;
                const remaining = total - loaded;
                setUploadEtaSeconds(remaining / speed);
              }
            }
          } else {
            setCyclePhase('computing');
            setUploadEtaSeconds(null);
          }
        });
        cycleAbortRef.current = abort;
        const resp = await promise;
        setResult(resp);
        onLatestRunChange?.(payload, resp);
        setCyclePhase('done');
        setCycleProgressPct(100);
      } else {
        // 无文件：直接调用原始 fetch 并使用模拟进度
        setCyclePhase('computing');
        let fakePct = 0;
        const fakeTimer = window.setInterval(() => {
          fakePct = Math.min(95, fakePct + 5);
          setCycleProgressPct(fakePct);
        }, 400);
        try {
          const resp = await computeStorageCycles(null, payload);
          window.clearInterval(fakeTimer);
          setCycleProgressPct(100);
          setResult(resp);
          onLatestRunChange?.(payload, resp);
          setCyclePhase('done');
        } catch (err: any) {
          window.clearInterval(fakeTimer);
          throw err;
        }
      }
    } catch (e: any) {
      setCyclePhase('error');
      setError(e?.message || '计算失败');
    } finally {
      setLoading(false);
      setTimeout(() => { setShowCycleRing(false); setCyclePhase('idle'); }, 2000);
    }
  };

  const handleSaveConfig = () => {
    if (typeof window === 'undefined') return;
    const name = savedConfigName.trim();
    if (!name) {
      setConfigNotice('请输入配置名称以保存当前参数');
      return;
    }
    const solveConfig = {
      targetYearEqCyclesInput,
      solveStartCapacityKwh,
      solveStepCapacityKwh,
      solveSteps,
    };
    window.localStorage.setItem(
      `${CONFIG_STORAGE_PREFIX}${name}`,
      JSON.stringify({ params, solveConfig, savedAt: new Date().toISOString() }),
    );
    setConfigNotice(`配置“${name}”已保存`);
    loadStoredConfigs();
  };

  const handleLoadSavedConfig = () => {
    if (typeof window === 'undefined' || !selectedSavedConfig) return;
    const raw = window.localStorage.getItem(`${CONFIG_STORAGE_PREFIX}${selectedSavedConfig}`);
    if (!raw) {
      setConfigNotice(`配置“${selectedSavedConfig}”不存在`);
      loadStoredConfigs();
      return;
    }
    try {
      const parsed = JSON.parse(raw);
      if (parsed.params) {
        setParams(p => ({ ...p, ...parsed.params }));
        if (parsed.solveConfig) {
          const cfg = parsed.solveConfig as any;
          if (typeof cfg.solveStartCapacityKwh === 'number') {
            setSolveStartCapacityKwh(cfg.solveStartCapacityKwh);
          }
          if (typeof cfg.solveStepCapacityKwh === 'number') {
            setSolveStepCapacityKwh(cfg.solveStepCapacityKwh);
          }
          if (typeof cfg.solveSteps === 'number' && cfg.solveSteps > 0) {
            setSolveSteps(cfg.solveSteps);
          }
          if (cfg.targetYearEqCyclesInput != null) {
            setTargetYearEqCyclesInput(String(cfg.targetYearEqCyclesInput));
          }
        }
        setSavedConfigName(selectedSavedConfig);
        setConfigNotice(`已加载“${selectedSavedConfig}”`);
      } else {
        setConfigNotice('配置内容缺少参数');
      }
    } catch (err) {
      setConfigNotice('配置解析失败');
    }
  };

  const handleExportConfig = () => {
    if (typeof window === 'undefined') return;
    const candidateName =
      savedConfigName || selectedSavedConfig || `storage-config-${Date.now()}`;
    const safeName = candidateName.replace(/\s+/g, '-');
    const payload = {
      name: safeName,
      params,
      solveConfig: {
        targetYearEqCyclesInput,
        solveStartCapacityKwh,
        solveStepCapacityKwh,
        solveSteps,
      },
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeName}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    setConfigNotice(`已导出配置 ${safeName}`);
  };

  const handleImportClick = () => {
    importInputRef.current?.click();
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (parsed.params) {
        setParams(p => ({ ...p, ...parsed.params }));
        if (parsed.solveConfig) {
          const cfg = parsed.solveConfig as any;
          if (typeof cfg.solveStartCapacityKwh === 'number') {
            setSolveStartCapacityKwh(cfg.solveStartCapacityKwh);
          }
          if (typeof cfg.solveStepCapacityKwh === 'number') {
            setSolveStepCapacityKwh(cfg.solveStepCapacityKwh);
          }
          if (typeof cfg.solveSteps === 'number' && cfg.solveSteps > 0) {
            setSolveSteps(cfg.solveSteps);
          }
          if (cfg.targetYearEqCyclesInput != null) {
            setTargetYearEqCyclesInput(String(cfg.targetYearEqCyclesInput));
          }
        }
        const name = (parsed.name ?? file.name.replace(/\.[^.]+$/, '')).trim();
        if (name) setSavedConfigName(name);
        setConfigNotice(`已导入配置 ${name || file.name}`);
      } else {
        setConfigNotice('导入文件缺少 params 字段');
      }
    } catch (err) {
      setConfigNotice('导入失败，文件必须为 JSON');
    } finally {
      if (event.target) {
        event.target.value = '';
      }
      loadStoredConfigs();
    }
  };

  // 按目标“全年合计等效循环数”反推容量（基于预计算映射 + 线性插值）
  const handleSolveCapacityByTargetCycles = async () => {
    setError(null);
    setSolveSuggestion(null);

    const target = Number(targetYearEqCyclesInput);
    if (!Number.isFinite(target) || target <= 0) {
      setError('请先输入大于 0 的目标全年合计等效循环数');
      return;
    }
    if (!(solveStartCapacityKwh > 0)) {
      setError('请先输入大于 0 的起始容量');
      return;
    }
    if (!(solveStepCapacityKwh > 0)) {
      setError('请先输入大于 0 的容量步长');
      return;
    }
    if (!(solveSteps > 0)) {
      setError('请先输入大于 0 的预计算步数');
      return;
    }

    const input = fileRef.current;
    let file: File | null = null;
    if (input && input.files && input.files.length > 0) {
      file = input.files[0];
      setFileName(prev => prev || file.name);
    }
    if (!file && !useAnalyzedData) {
      setError('请选择待测算的负荷文件（CSV/XLSX）或勾选“使用负荷分析已上传数据”');
      return;
    }

    if (useAnalyzedData && (!externalCleanedData || externalCleanedData.length === 0)) {
      setError('“负荷分析”页没有可用数据，请先在“负荷分析”页上传并处理，或在本页选择负荷文件。');
      return;
    }

    const pointsPayload = (useAnalyzedData && externalCleanedData && externalCleanedData.length > 0)
      ? externalCleanedData
          .slice()
          .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
          .map(p => ({
            timestamp: toLocalNaiveString(p.timestamp),
            load_kwh: Number(p.load),
          }))
      : undefined;

    const baseStorage = {
      c_rate: params.c_rate,
      single_side_efficiency: params.single_side_efficiency,
      depth_of_discharge: params.depth_of_discharge,
      soc_min: params.soc_min,
      soc_max: params.soc_max,
      reserve_charge_kw: params.reserve_charge_kw,
      reserve_discharge_kw: params.reserve_discharge_kw,
      metering_mode: params.metering_mode,
      transformer_capacity_kva: params.metering_mode === 'transformer_capacity' ? params.transformer_capacity_kva : undefined,
      transformer_power_factor: params.metering_mode === 'transformer_capacity' ? params.transformer_power_factor : undefined,
      calc_style: 'window_avg' as const,
      energy_formula: params.energy_formula,
      merge_threshold_minutes: params.merge_threshold_minutes,
    };

    const hasDischarge = Array.isArray(scheduleData.monthlySchedule)
      && scheduleData.monthlySchedule.some((monthRow: any[]) =>
        Array.isArray(monthRow) && monthRow.some(cell => cell?.op === '放'));
    const hasAnyPrice = Array.isArray(scheduleData.prices)
      && scheduleData.prices.some(mp => mp && Object.values(mp).some(v => v != null));
    if (!hasDischarge) {
      setError('当前排程没有放电窗口，请先在排程/逻辑中设置“放”时段后再测算。');
      return;
    }
    if (!hasAnyPrice) {
      setError('当前电价配置全部为空，请先设置 TOU 电价（含尖/峰/平/谷）。');
      return;
    }

    const v = validateParams();
    if (v) {
      setError(v);
      return;
    }

    const capacities: number[] = [];
    const yearEqCyclesList: number[] = [];
    const responses: BackendStorageCyclesResponse[] = [];

    setLoading(true);
    try {
      const steps = solveSteps > 0 ? solveSteps : SOLVE_CAPACITY_STEPS;
      for (let i = 0; i < steps; i++) {
        const cap = solveStartCapacityKwh + i * solveStepCapacityKwh;
        if (!(cap > 0)) continue;
        const payload: StorageParamsPayload = {
          storage: {
            ...baseStorage,
            capacity_kwh: cap,
          },
          strategySource: {
            monthlySchedule: scheduleData.monthlySchedule,
            dateRules: scheduleData.dateRules,
          },
          monthlyTouPrices: scheduleData.prices,
          points: pointsPayload,
        };
        const resp = await computeStorageCycles(file, payload);
        const yearEq = computeYearEquivalentCyclesFromDays(resp.days);
        capacities.push(cap);
        yearEqCyclesList.push(yearEq);
        responses.push(resp);
      }

      if (!capacities.length) {
        setError('容量搜索未产生有效结果，请检查起始容量与步长设置。');
        return;
      }

      let bestIdx = 0;
      let bestDiff = Math.abs(yearEqCyclesList[0] - target);
      for (let i = 1; i < yearEqCyclesList.length; i++) {
        const diff = Math.abs(yearEqCyclesList[i] - target);
        if (diff < bestDiff) {
          bestDiff = diff;
          bestIdx = i;
        }
      }

      let interpCapacity = capacities[bestIdx];
      const minCycles = Math.min(...yearEqCyclesList);
      const maxCycles = Math.max(...yearEqCyclesList);
      if (target >= minCycles && target <= maxCycles) {
        for (let i = 0; i < yearEqCyclesList.length - 1; i++) {
          const c1 = yearEqCyclesList[i];
          const c2 = yearEqCyclesList[i + 1];
          if ((target >= c1 && target <= c2) || (target >= c2 && target <= c1)) {
            const cap1 = capacities[i];
            const cap2 = capacities[i + 1];
            if (c1 !== c2) {
              interpCapacity = cap1 + (target - c1) * (cap2 - cap1) / (c2 - c1);
            } else {
              interpCapacity = (cap1 + cap2) / 2;
            }
            break;
          }
        }
      }

      let finalCapacity = interpCapacity;
      let finalResp: BackendStorageCyclesResponse | null = null;
      const existingIdx = capacities.findIndex(c => Math.abs(c - interpCapacity) < 1e-6);
      if (existingIdx >= 0) {
        finalResp = responses[existingIdx];
        finalCapacity = capacities[existingIdx];
      } else {
        const payload: StorageParamsPayload = {
          storage: {
            ...baseStorage,
            capacity_kwh: interpCapacity,
          },
          strategySource: {
            monthlySchedule: scheduleData.monthlySchedule,
            dateRules: scheduleData.dateRules,
          },
          monthlyTouPrices: scheduleData.prices,
          points: pointsPayload,
        };
        finalResp = await computeStorageCycles(file, payload);
      }

      const finalYearEq = computeYearEquivalentCyclesFromDays(finalResp?.days ?? []);
      setParams(p => ({ ...p, capacity_kwh: finalCapacity }));
      setResult(finalResp);
      setSolveSuggestion({
        targetYearEq: target,
        bestCapacityKwh: finalCapacity,
        bestYearEqCycles: finalYearEq,
      });
    } catch (err: any) {
      setError(err?.message || '按目标全年等效循环数反推容量失败');
    } finally {
      setLoading(false);
    }
  };

  // ========== 图表渲染（ECharts 动态加载） ==========
  const monthChartRef = useRef<HTMLDivElement>(null);
  const dayChartRef = useRef<HTMLDivElement>(null);
  const heatmapChartRef = useRef<HTMLDivElement>(null);
  const tipDayChartRef = useRef<HTMLDivElement>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [selectedDayForProfit, setSelectedDayForProfit] = useState<string | null>(null);
  const [monthlyViewMode, setMonthlyViewMode] = useState<'aggregate' | 'byYear'>('aggregate');

  const monthsData = useMemo(() => result?.months || [], [result]);
  const daysData = useMemo(() => result?.days || [], [result]);
  const tipSummary = useMemo(() => {
    const rawNullable =
      (result as any)?.tip_discharge_summary ??
      (result as any)?.tip_discharge ??
      (result as any)?.tip;
    if (!rawNullable) return null;
    const raw: BackendTipDischargeSummary = rawNullable;
    const avg = Number(
      raw.avg_tip_load_kw ??
      (raw as any)?.avg_kw ??
      (raw as any)?.avg_load_kw ??
      (raw as any)?.tip_avg_kw ??
      0,
    );
    const tipHours = Number(
      raw.tip_hours ??
      (raw as any)?.hours ??
      (raw as any)?.duration_hours ??
      0,
    );
    const dischargeCount = Number(
      raw.discharge_count ??
      (raw as any)?.cycles ??
      (raw as any)?.count ??
      0,
    );
    const capacity = Number(
      (raw.capacity_kwh ?? (raw as any)?.capacity ?? params.capacity_kwh) ?? 0,
    );
    const energyNeed = (() => {
      const v =
        raw.energy_need_kwh ??
        (raw as any)?.tip_energy_need_kwh ??
        (raw as any)?.energy_need;
      if (v != null) return Number(v);
      return avg * tipHours;
    })();
    const ratioFromBackend = (() => {
      const v =
        raw.ratio ??
        (raw as any)?.tip_ratio ??
        (raw as any)?.ratio_tip ??
        null;
      if (v == null) return null;
      const num = Number(v);
      if (!Number.isFinite(num)) return null;
      return Math.min(1, Math.max(0, num));
    })();
    const ratioCalculated =
      dischargeCount <= 0 || !capacity || tipHours <= 0
        ? 0
        : Math.min(1, (capacity * dischargeCount) > 0 ? energyNeed / (capacity * dischargeCount) : 0);
    return {
      ratio: ratioFromBackend ?? ratioCalculated,
      avgTipLoadKw: avg,
      tipHours,
      dischargeCount,
      capacityKwh: capacity,
      energyNeedKwh: energyNeed,
      note: raw.note,
      tipPoints: (raw as any)?.tip_points ?? (raw as any)?.points,
      dayStats: (raw as any)?.day_stats,
      monthStats: (raw as any)?.month_stats,
    };
  }, [params.capacity_kwh, result]);
  const tipMonthMap = useMemo(() => {
    const stats = tipSummary?.monthStats;
    if (!stats) return [];
    const arr: Array<number | null> = new Array(12).fill(null);
    stats.forEach((m) => {
      const idx = Number(m.month) - 1;
      if (idx >= 0 && idx < 12 && m.ratio != null) {
        arr[idx] = Number(m.ratio);
      }
    });
    return arr;
  }, [tipSummary?.monthStats]);

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
      const cyclesVal = Number(d.cycles ?? 0);
      // 判断该日期是否有实际数据：cycles > 0 或 profit 存在且非空
      // 只有有实际数据的日期才计入"有效天数"
      const hasValidData =
        cyclesVal > 0 ||
        (d.profit != null && typeof d.profit === 'object' && Object.keys(d.profit).length > 0);
      if (hasValidData) {
        monthDaySets[idx].add(dateKey);
        yearDaySet.add(dateKey);
      }
      monthTotal[idx] += cyclesVal;
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

  const avgOrNull = useMemo(
    () => (vals: Array<number | null>) => {
      const arr = vals.filter(v => v != null && !Number.isNaN(Number(v))) as number[];
      if (!arr.length) return null;
      return arr.reduce((s, v) => s + v, 0) / arr.length;
    },
    [],
  );
  const avgFirstChargeRate = useMemo(() => avgOrNull(monthFirstChargeRatePct), [avgOrNull, monthFirstChargeRatePct]);
  const avgFirstDischargeRate = useMemo(() => avgOrNull(monthFirstDischargeRatePct), [avgOrNull, monthFirstDischargeRatePct]);
  const avgSecondChargeRate = useMemo(() => avgOrNull(monthSecondChargeRatePct), [avgOrNull, monthSecondChargeRatePct]);
  const avgSecondDischargeRate = useMemo(() => avgOrNull(monthSecondDischargeRatePct), [avgOrNull, monthSecondDischargeRatePct]);
  const avgTipRatio = useMemo(() => avgOrNull(tipMonthMap), [avgOrNull, tipMonthMap]);

  // KPI 概览卡片：年累计、月均、最高月与最低月
  const kpiMetrics = useMemo(() => {
    if (!result) return null;
    const totalCycles = Number(result.year?.cycles ?? 0);

    const monthList = monthsData
      .map(m => ({
        yearMonth: m.year_month,
        cycles: Number((m as any)?.cycles ?? 0),
      }))
      .filter(m => Number.isFinite(m.cycles));

    if (!monthList.length) {
      return {
        totalCycles,
        avgCycles: 0,
        maxMonth: null as { yearMonth: string; cycles: number } | null,
        minMonth: null as { yearMonth: string; cycles: number } | null,
      };
    }

    let maxMonth = monthList[0];
    let minMonth = monthList[0];
    for (const m of monthList) {
      if (m.cycles > maxMonth.cycles) maxMonth = m;
      if (m.cycles < minMonth.cycles) minMonth = m;
    }
    const avgCycles = monthList.length ? totalCycles / monthList.length : 0;

    return {
      totalCycles,
      avgCycles,
      maxMonth,
      minMonth,
    };
  }, [result, monthsData]);

  useEffect(() => {
    if (!monthsData.length) { setSelectedMonth(null); return; }
    if (selectedMonth && monthsData.find(m => m.year_month === selectedMonth)) return;
    setSelectedMonth(monthsData[0]?.year_month || null);
  }, [monthsData, selectedMonth]);

  const daysInSelectedMonth = useMemo(() => {
    if (!selectedMonth) return [];
    return daysData
      .filter(d => d.date && d.date.startsWith(selectedMonth))
      .map(d => d.date)
      .sort();
  }, [daysData, selectedMonth]);

  useEffect(() => {
    if (!daysInSelectedMonth.length) {
      setSelectedDayForProfit(null);
      return;
    }
    setSelectedDayForProfit(prev =>
      prev && daysInSelectedMonth.includes(prev) ? prev : daysInSelectedMonth[0],
    );
  }, [daysInSelectedMonth]);

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
        xAxis: {
          type: 'category',
          data: cats,
          name: '月份',
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          name: '次数',
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: true, lineStyle: { color: '#e5e7eb', type: 'dashed' } },
        },
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
        xAxis: {
          type: 'category',
          data: cats,
          name: '日期',
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          name: '次数',
          axisLabel: {
            formatter: (value: number) =>
              Number.isNaN(Number(value)) ? '-' : Number(value).toFixed(3),
          },
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: true, lineStyle: { color: '#e5e7eb', type: 'dashed' } },
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
            color: ['#eff6ff', '#3b82f6', '#1e40af'],
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

  // 尖放电占比：日度折线
  useEffect(() => {
    let chart: any = null;
    loadECharts().then((echarts: any) => {
      if (!tipDayChartRef.current || !tipSummary?.dayStats) return;
      const data = tipSummary.dayStats;
      chart = echarts.init(tipDayChartRef.current);
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params[0] : params;
            const val = p?.data?.value ?? p?.data ?? 0;
            return `${p?.axisValue || ''}<br/>尖占比：${(Number(val) * 100).toFixed(1)}%`;
          },
        },
        grid: { left: 40, right: 10, top: 20, bottom: 30 },
        xAxis: {
          type: 'category',
          data: data.map(d => d.date?.slice(5) || ''),
          axisLabel: { interval: 'auto', rotate: 45, fontSize: 10 },
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 1,
          axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
          axisLine: { lineStyle: { color: '#cbd5f5' } },
          splitLine: { show: true, lineStyle: { color: '#e5e7eb', type: 'dashed' } },
        },
        series: [{
          type: 'line',
          data: data.map(d => Number(d.ratio ?? 0)),
          smooth: true,
          itemStyle: { color: '#f97316' },
          areaStyle: { color: 'rgba(249,115,22,0.12)' },
        }],
      });
    }).catch(() => {/* ignore */});
    return () => { try { chart && chart.dispose && chart.dispose(); } catch { /* ignore */ } };
  }, [tipSummary?.dayStats, tipSummary?.ratio]);

  // 不再使用旧伪进度条逻辑，保留占位以防后续扩展


  return (
    <div className="space-y-8">
      <div id="section-cycles-upload" className="scroll-mt-24 p-6 bg-white rounded-xl shadow-lg space-y-4">
        <div className="flex items-center gap-3">
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="sr-only" onChange={() => setFileName(fileRef.current?.files?.[0]?.name || '')} />
          <button className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm whitespace-nowrap w-[110px]" onClick={() => fileRef.current?.click()}>
            选择负荷文件
          </button>
          <span className="text-sm text-slate-600 whitespace-nowrap max-w-[160px] overflow-hidden text-ellipsis">{fileName || '未选择文件'}</span>
          <div className="flex items-center gap-2 w-full">
            <button className="ml-2 px-3 py-1.5 rounded bg-green-600 text-white text-sm disabled:opacity-60" onClick={handleUpload} disabled={loading}>
              {cyclePhase === 'uploading' ? '上传中…' : cyclePhase === 'computing' ? '计算中…' : '开始测算'}
            </button>
            {showCycleRing && (
              <div className="flex items-center gap-2">
                <UploadProgressRing
                  progress={cycleProgressPct}
                  status={cyclePhase === 'computing' ? 'computing' : cyclePhase === 'uploading' ? 'uploading' : cyclePhase === 'done' ? 'done' : cyclePhase === 'error' ? 'error' : 'idle'}
                  size={36}
                  stroke={4}
                  labelOverride={cyclePhase === 'computing' ? '计算' : undefined}
                />
                {cyclePhase === 'uploading' && uploadEtaSeconds != null && (
                  <span className="text-[11px] text-slate-600 w-16">剩余≈{Math.max(1, Math.round(uploadEtaSeconds))}秒</span>
                )}
                {(cyclePhase === 'uploading' || cyclePhase === 'computing') && (
                  <button
                    type="button"
                    onClick={() => {
                      try { cycleAbortRef.current(); } catch { /* ignore */ }
                      setCyclePhase('error');
                      setError('已取消测算');
                      setShowCycleRing(false);
                      setLoading(false);
                    }}
                    className="text-[11px] px-2 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50"
                  >取消</button>
                )}
              </div>
            )}
            {/* 跳转收益对比按钮移至主操作区最右侧 */}
            {onNavigateProfit && (
              <div className="flex-1 flex justify-end items-center">
                <button
                  type="button"
                  className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm ml-4"
                  disabled={!selectedDayForProfit}
                  onClick={() => {
                    if (selectedDayForProfit) onNavigateProfit(selectedDayForProfit);
                  }}
                >跳转收益对比</button>
              </div>
            )}
          </div>
        </div>
        {/* 已替换为环形进度，不再显示旧线性条 */}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useAnalyzedData} onChange={e => setUseAnalyzedData(e.target.checked)} />
            <span>使用“负荷分析”页已上传数据</span>
          </label>
          <div className="text-xs text-slate-500">
            {hasExternalData
              ? '勾选后将复用全局已清洗的小时级负荷数据，无需在本页重复上传。'
              : '当前暂无可复用的“负荷分析”页数据，仅支持通过本页上传负荷文件。'}
          </div>
        </div>


        {/* 数据清洗开关 */}
        <div className="flex items-center gap-3 text-sm bg-blue-50 p-3 rounded-lg">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={enableCleaning}
              onChange={e => setEnableCleaning(e.target.checked)}
            />
            <span className="font-medium">启用数据清洗</span>
          </label>
          <span className="text-xs text-slate-600">
            {enableCleaning
              ? '上传文件后将检测零值/负值/空值，由您确认后再计算'
              : '直接使用原始数据计算，不做任何清洗处理'}
          </span>
        </div>

        {/* 参数表单（简化）：基础参数 + 高级设置折叠 */}
        <div id="section-cycles-params" className="scroll-mt-24 space-y-3 text-sm">
          {/* 常规配置标题与说明 */}
          <div className="flex items-baseline justify-between">
            <div className="text-sm font-semibold text-slate-800">常规配置</div>
            <div className="text-[11px] text-slate-500">
              建议先设置容量与余量，再根据需求选择计费口径与能量公式。
            </div>
          </div>
          {/* 基础参数：高频必填（常规配置） */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <label className="flex flex-col gap-1">
              <span>容量</span>
              <div className="flex items-center gap-1">
                <input
                  className="border rounded px-2 py-1 flex-1"
                  type="number"
                  step="1"
                  min="1"
                  value={params.capacity_kwh}
                  onChange={e => setParams(p => ({ ...p, capacity_kwh: Number(e.target.value) }))}
                />
                <span className="text-xs text-slate-500 pr-1">kWh</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                储能额定容量，用于计算可参与调度的能量规模。
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span>充电余量</span>
              <div className="flex items-center gap-1">
                <input
                  className="border rounded px-2 py-1 flex-1"
                  type="number"
                  step="1"
                  min="0"
                  value={params.reserve_charge_kw}
                  onChange={e => setParams(p => ({ ...p, reserve_charge_kw: Number(e.target.value) }))}
                />
                <span className="text-xs text-slate-500 pr-1">kW</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                为上游负荷预留的充电功率，上限越大可用充电功率越小。
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span>放电余量</span>
              <div className="flex items-center gap-1">
                <input
                  className="border rounded px-2 py-1 flex-1"
                  type="number"
                  step="1"
                  min="0"
                  value={params.reserve_discharge_kw}
                  onChange={e => setParams(p => ({ ...p, reserve_discharge_kw: Number(e.target.value) }))}
                />
                <span className="text-xs text-slate-500 pr-1">kW</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                为下游负荷预留的放电功率，上限越大可用放电功率越小。
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span>计费口径</span>
              <select
                className="border rounded px-2 py-1"
                value={params.metering_mode}
                onChange={e => setParams(p => ({ ...p, metering_mode: e.target.value as any }))}
              >
                <option value="monthly_demand_max">monthly_demand_max</option>
                <option value="transformer_capacity">transformer_capacity</option>
              </select>
              <div className="text-[11px] text-slate-500 mt-0.5">
                决定需量上限的计算方式，会影响尖峰削峰空间与收益测算。
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span>能量公式</span>
              <select
                className="border rounded px-2 py-1"
                value={params.energy_formula}
                onChange={e => setParams(p => ({ ...p, energy_formula: e.target.value as any }))}
              >
                <option value="physics">physics</option>
                <option value="sample">sample</option>
              </select>
              <div className="text-[11px] text-slate-500 mt-0.5">
                physics 为物理模型精算，sample 为样本法近似，建议优先使用 physics。
              </div>
            </label>
          </div>

          {/* 反推容量：按目标全年等效循环数搜索（可选，可折叠） */}
          <details className="rounded-lg border border-dashed border-emerald-300 bg-emerald-50/60 px-3 py-2 text-xs md:text-sm">
            <summary className="cursor-pointer text-xs md:text-sm text-slate-700 select-none">
              按目标全年合计等效循环数反推容量（可选）
            </summary>
            <div className="mt-2 space-y-2">
              <div className="flex justify-end mb-1">
                <button
                  type="button"
                  className="px-2 py-1 rounded bg-emerald-600 text-white text-xs disabled:opacity-60"
                  onClick={handleSolveCapacityByTargetCycles}
                  disabled={loading}
                >
                  按目标值反推容量
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <label className="flex flex-col gap-1">
                  <span>目标全年合计等效循环数</span>
                  <input
                    className="border rounded px-2 py-1 w-full"
                    type="number"
                    min="0"
                    step="0.01"
                    value={targetYearEqCyclesInput}
                    onChange={e => setTargetYearEqCyclesInput(e.target.value)}
                    placeholder="例如 300"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span>起始容量</span>
                  <div className="flex items-center gap-1">
                    <input
                      className="border rounded px-2 py-1 w-full"
                      type="number"
                      min="1"
                      step="1"
                      value={solveStartCapacityKwh}
                      onChange={e => setSolveStartCapacityKwh(Number(e.target.value) || 0)}
                    />
                    <span className="text-xs text-slate-500 pr-1">kWh</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    默认取当前容量附近区间起点，可按需调整。
                  </div>
                </label>
                <label className="flex flex-col gap-1">
                  <span>容量步长</span>
                  <div className="flex items-center gap-1">
                    <input
                      className="border rounded px-2 py-1 w-full"
                      type="number"
                      min="1"
                      step="1"
                      value={solveStepCapacityKwh}
                      onChange={e => setSolveStepCapacityKwh(Number(e.target.value) || 0)}
                    />
                    <span className="text-xs text-slate-500 pr-1">kWh</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    将按起始容量起步，每步增加此容量，预计算 {solveSteps > 0 ? solveSteps : SOLVE_CAPACITY_STEPS} 个容量点。
                  </div>
                </label>
                <label className="flex flex-col gap-1">
                  <span>预计算步数</span>
                  <input
                    className="border rounded px-2 py-1 w-full"
                    type="number"
                    min="1"
                    step="1"
                    value={solveSteps}
                    onChange={e => setSolveSteps(Number(e.target.value) || 0)}
                  />
                </label>
              </div>
              <div className="text-[11px] text-slate-500">
                该功能仅用于反推推荐容量，不会覆盖“开始测算”按钮的单次测算逻辑。
              </div>
            </div>
          </details>

          {/* 高级设置：倍率 / 效率 / DOD / 合并阈值等 */}
          <details className="rounded-lg border border-dashed border-slate-300 bg-slate-50/70 px-3 py-2">
            <summary className="cursor-pointer text-xs md:text-sm text-slate-700 select-none">
              高级设置（倍率、效率、DOD、SOC、合并阈值等）
            </summary>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-3">
              <label className="flex flex-col gap-1">
                <span>倍率</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="0.01"
                    min="0"
                    value={params.c_rate}
                    onChange={e => setParams(p => ({ ...p, c_rate: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">C</span>
                </div>
              </label>
              <label className="flex flex-col gap-1">
                <span>单边效率</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="0.001"
                    min="0"
                    max="1"
                    value={params.single_side_efficiency}
                    onChange={e => setParams(p => ({ ...p, single_side_efficiency: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">η</span>
                </div>
              </label>
              <label className="flex flex-col gap-1">
                <span>DOD</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={params.depth_of_discharge}
                    onChange={e => setParams(p => ({ ...p, depth_of_discharge: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">比例</span>
                </div>
              </label>
              <label className="flex flex-col gap-1">
                <span>SOC 下限</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={params.soc_min}
                    onChange={e => setParams(p => ({ ...p, soc_min: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">比例</span>
                </div>
              </label>
              <label className="flex flex-col gap-1">
                <span>SOC 上限</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={params.soc_max}
                    onChange={e => setParams(p => ({ ...p, soc_max: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">比例</span>
                </div>
              </label>
              <label className="flex flex-col gap-1">
                <span>合并阈值</span>
                <div className="flex items-center gap-1">
                  <input
                    className="border rounded px-2 py-1 flex-1"
                    type="number"
                    step="1"
                    min="0"
                    value={params.merge_threshold_minutes}
                    onChange={e => setParams(p => ({ ...p, merge_threshold_minutes: Number(e.target.value) }))}
                  />
                  <span className="text-xs text-slate-500 pr-1">分钟</span>
                </div>
              </label>

              {params.metering_mode === 'transformer_capacity' && (
                <>
                  <label className="flex flex-col gap-1">
                    <span>变压器容量</span>
                    <div className="flex items-center gap-1">
                      <input
                        className="border rounded px-2 py-1 flex-1"
                        type="number"
                        step="1"
                        min="1"
                        value={params.transformer_capacity_kva}
                        onChange={e => setParams(p => ({ ...p, transformer_capacity_kva: Number(e.target.value) }))}
                      />
                      <span className="text-xs text-slate-500 pr-1">kVA</span>
                    </div>
                  </label>
                  <label className="flex flex-col gap-1">
                    <span>功率因数</span>
                    <div className="flex items-center gap-1">
                      <input
                        className="border rounded px-2 py-1 flex-1"
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={params.transformer_power_factor}
                        onChange={e => setParams(p => ({ ...p, transformer_power_factor: Number(e.target.value) }))}
                      />
                      <span className="text-xs text-slate-500 pr-1">cosφ</span>
                    </div>
                  </label>
                </>
              )}
            </div>
          </details>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <input
            type="text"
            value={savedConfigName}
            onChange={e => setSavedConfigName(e.target.value)}
            placeholder="保存配置名称"
            className="border rounded px-2 py-1 text-xs w-36"
          />
          <button
            onClick={handleSaveConfig}
            className="px-2 py-1 rounded bg-slate-900 text-white text-xs disabled:opacity-40"
            disabled={!savedConfigName.trim()}
          >
            保存配置
          </button>
          <select
            value={selectedSavedConfig}
            onChange={e => setSelectedSavedConfig(e.target.value)}
            className="border rounded px-2 py-1 text-xs"
          >
            <option value="">选择已保存配置</option>
            {availableConfigs.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <button
            onClick={handleLoadSavedConfig}
            className="px-2 py-1 rounded bg-blue-500 text-white text-xs disabled:opacity-40"
            disabled={!selectedSavedConfig}
          >
            加载配置
          </button>
          <button
            onClick={handleExportConfig}
            className="px-2 py-1 rounded border border-slate-400 text-xs"
          >
            导出 JSON
          </button>
          <button
            onClick={handleImportClick}
            className="px-2 py-1 rounded border border-slate-400 text-xs"
          >
            导入 JSON
          </button>
          <input
            type="file"
            ref={importInputRef}
            className="sr-only"
            accept="application/json"
            onChange={handleImportFile}
          />
        </div>
        {configNotice && (
          <div className="text-[11px] text-slate-500">{configNotice}</div>
        )}

        {error && <div className="text-red-600 text-sm">{error}</div>}
      </div>

      {result && (
        <div className="mt-2 space-y-3">
          {kpiMetrics && (
            <div id="section-cycles-kpi" className="scroll-mt-24 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2.5 bg-white rounded-xl shadow-lg border border-slate-200 border-l-4 border-blue-500">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs text-slate-500">年累计循环次数</div>
                  <span className="text-xs">🔄</span>
                </div>
                <div className="text-base md:text-xl font-semibold text-slate-900">
                  {kpiMetrics.totalCycles.toFixed(2)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">单位：次/年</div>
                <div className="text-[11px] text-slate-500 mt-2 text-right">
                  全年合计等效循环数：{yearEquivalentCycles === 0 ? '-' : Number(yearEquivalentCycles).toFixed(2)} 次
                </div>
                {solveSuggestion && (
                  <div className="text-[11px] text-emerald-600 mt-1 text-right">
                    目标 {solveSuggestion.targetYearEq.toFixed(2)} 次，推荐容量约{' '}
                    {solveSuggestion.bestCapacityKwh.toFixed(0)} kWh（等效 {solveSuggestion.bestYearEqCycles.toFixed(2)} 次）
                  </div>
                )}
              </div>
              <div className="p-2.5 bg-white rounded-xl shadow-lg border border-slate-200 border-l-4 border-emerald-500">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs text-slate-500">月均循环次数</div>
                  <span className="text-xs">📊</span>
                </div>
                <div className="text-base md:text-xl font-semibold text-slate-900">
                  {kpiMetrics.avgCycles.toFixed(2)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">单位：次/月</div>
              </div>
              <div className="p-2.5 bg-white rounded-xl shadow-lg border border-slate-200 border-l-4 border-orange-500">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs text-slate-500">最高月循环次数</div>
                  <span className="text-xs">📈</span>
                </div>
                <div className="text-base md:text-xl font-semibold text-slate-900">
                  {kpiMetrics.maxMonth ? kpiMetrics.maxMonth.cycles.toFixed(2) : '--'}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  {kpiMetrics.maxMonth?.yearMonth || '—'}（次/月）
                </div>
              </div>
              <div className="p-2.5 bg-white rounded-xl shadow-lg border border-slate-200 border-l-4 border-slate-400">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs text-slate-500">最低月循环次数</div>
                  <span className="text-xs">📉</span>
                </div>
                <div className="text-base md:text-xl font-semibold text-slate-900">
                  {kpiMetrics.minMonth ? kpiMetrics.minMonth.cycles.toFixed(2) : '--'}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  {kpiMetrics.minMonth?.yearMonth || '—'}（次/月）
                </div>
              </div>
            </div>
          )}

          {/* 循环有效/等效统计表格（按月 + 年度汇总） */}
          <div id="section-cycles-stats" className="scroll-mt-24 p-3 border rounded-xl bg-white shadow-sm overflow-x-auto">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-semibold text-slate-800">
                循环有效/等效统计（按月）
              </div>
              <div className="text-[11px] md:text-xs text-slate-500">
                基于日度循环结果按自然月折算
              </div>
            </div>
            <div className="max-h-80 overflow-y-auto">
              <table className="min-w-full text-xs md:text-sm border-collapse">
                <thead className="sticky top-0 bg-slate-50 z-10">
                  <tr className="border-b border-slate-200">
                    <th className="px-3 py-2 text-left font-medium text-slate-600">月份</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">有效天数（天）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600 bg-slate-50">平均日循环数（次/天）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600 bg-slate-50">有效循环数（次）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">等效循环数（次）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">第一次充电满充率（%）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">第一次充电满放率（%）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">第二次充电满充率（%）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">第二次充电满放率（%）</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">平均尖占比（%）</th>
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
                  const tipRatio = tipMonthMap[i];
                  const tipRatioStr =
                    tipRatio == null
                      ? '-'
                      : `${(tipRatio * 100).toFixed(1)}%`;
                  return (
                    <tr
                      key={monthLabel}
                      className="border-b border-slate-100 last:border-0 even:bg-slate-50/60 hover:bg-slate-100/70 transition-colors"
                    >
                      <td className="px-3 py-1.5 text-slate-700">{monthLabel}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {validDays || '-'}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700 bg-slate-50">
                        {avgDailyStr}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700 bg-slate-50 font-semibold">
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
                      <td className="px-3 py-1.5 text-right tabular-nums text-slate-700">
                        {tipRatioStr}
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t border-slate-200 bg-slate-100/80">
                  <td className="px-3 py-1.5 font-semibold text-slate-800">全年合计</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {yearValidDays || '-'}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800 bg-slate-100">
                    {yearValidDays && yearTotalCycles
                      ? Number(yearTotalCycles / yearValidDays).toFixed(3)
                      : '-'}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800 bg-slate-100">
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
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {avgFirstChargeRate == null ? '-' : `${avgFirstChargeRate.toFixed(3)}%`}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {avgFirstDischargeRate == null ? '-' : `${avgFirstDischargeRate.toFixed(3)}%`}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {avgSecondChargeRate == null ? '-' : `${avgSecondChargeRate.toFixed(3)}%`}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {avgSecondDischargeRate == null ? '-' : `${avgSecondDischargeRate.toFixed(3)}%`}
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-slate-800">
                    {avgTipRatio == null ? '-' : `${(avgTipRatio * 100).toFixed(1)}%`}
                  </td>
                </tr>
              </tbody>
              </table>
            </div>
          </div>

          {/* 图表区：四块图统一为 2×2 网格，尺寸协调 */}
          <div id="section-cycles-charts" className="scroll-mt-24 grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* 月度充放次数（曲线） */}
            <div className="p-3 border rounded bg-white flex flex-col">
              <div className="flex items-center justify-between mb-2">
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
              <div ref={monthChartRef} style={{ width: '100%', height: 280 }} />
            </div>

            {/* 单月日度次数曲线 */}
            <div className="p-3 border rounded bg-white flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold mb-1">单月日度次数曲线</div>
                <div className="text-xs flex items-center gap-2 flex-wrap">
                  <div className="flex items-center gap-1">
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
                  {onNavigateProfit && (
                    <div className="flex items-center gap-1">
                      <span>日期</span>
                      <select
                        className="border rounded px-2 py-0.5"
                        value={selectedDayForProfit || ''}
                        onChange={e => setSelectedDayForProfit(e.target.value || null)}
                      >
                        {daysInSelectedMonth.map(d => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              </div>
              <div ref={dayChartRef} style={{ width: '100%', height: 280 }} />
            </div>

            {/* 全年每日充放次数热力图 */}
            <div className="p-3 border rounded bg-white flex flex-col">
              <div className="text-sm font-semibold mb-2">全年每日充放次数热力图</div>
              <div ref={heatmapChartRef} style={{ width: '100%', height: 280 }} />
              <div className="mt-1 text-xs text-slate-500">
                第一行对应 1 月、第二行对应 2 月，横轴为 1–31 日，每个格子表示当日的充放次数。
              </div>
            </div>

            {/* 尖放电占比 */}
            <div id="section-cycles-tip" className="scroll-mt-24 p-3 border rounded bg-white flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-semibold text-slate-800">尖放电占比</div>
                  {tipSummary && (
                    <div className="text-[11px] text-slate-500">
                      放电次数：{tipSummary.dischargeCount}
                    </div>
                  )}
                </div>
                {tipSummary ? (
                  <>
                    <div className="text-3xl font-semibold text-slate-900">
                      {(tipSummary.ratio * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-600 mt-2 leading-relaxed">
                      公式：{Number.isFinite(tipSummary.avgTipLoadKw) ? tipSummary.avgTipLoadKw.toFixed(1) : '--'} kW × {Number.isFinite(tipSummary.tipHours) ? tipSummary.tipHours.toFixed(2) : '--'}h ÷ ({Number.isFinite(tipSummary.capacityKwh) ? tipSummary.capacityKwh : '--'} kWh × {tipSummary.dischargeCount || 1})
                    </div>
                    <div className="text-xs text-slate-600 mt-1">
                      尖能量需求：{Number.isFinite(tipSummary.energyNeedKwh) ? tipSummary.energyNeedKwh.toFixed(1) : '--'} kWh
                    </div>
                    {tipSummary.dischargeCount === 0 && (
                      <div className="text-xs text-orange-600 mt-1">
                        放电次数为 0，按规则占比为 0%
                      </div>
                    )}
                    <div className="mt-3">
                      <div className="text-xs text-slate-600 mb-1">日尖占比</div>
                      <div ref={tipDayChartRef} style={{ width: '100%', height: 180 }} />
                    </div>
                    {tipSummary.note && (
                      <div className="mt-2 text-[11px] text-slate-500 leading-relaxed">
                        {tipSummary.note}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-xs text-slate-500">
                    暂无尖放电占比数据，后端返回 tip_discharge_summary 后自动展示。
                  </div>
                )}
              </div>
            </div>
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
            <div className="p-3 border rounded bg-white">
              <details>
                <summary className="cursor-pointer text-slate-700 text-sm">QC 提示（展开查看）</summary>
                <ul className="list-disc ml-5 text-sm text-slate-600 mt-1">
                  {result.qc.notes.map((n, idx) => (<li key={idx}>{n}</li>))}
                </ul>
              </details>
            </div>
          )}
        </div>
      )}

      {/* 数据清洗确认对话框 */}
      <CleaningConfirmDialog
        visible={cleaningDialogVisible}
        analysis={cleaningAnalysis}
        onConfirm={handleCleaningConfirm}
        onCancel={handleCleaningCancel}
        loading={cleaningLoading}
      />
    </div>
  );
};
