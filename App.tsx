import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type { Schedule, TierId, DateRule, OperatingLogicId, Configuration, CellData, BackendAnalysisMeta, BackendQualityReport, MonthlyTouPrices, BackendStorageCyclesResponse } from './types';
import { INITIAL_APP_STATE, VALID_OP_LOGIC_IDS, VALID_TIER_IDS } from './constants';
import * as api from './api';
import { exportScheduleToExcel } from './utils';
import * as XLSX from 'xlsx';
import type { LoadDataPoint } from './utils';
import { analyzeLoadFile } from './loadApi';
import type { StorageParamsPayload } from './storageApi';


// Components
import { ConfigurationManager } from './components/ConfigurationManager';
import { TouGrid } from './components/TouGrid';
import { TierSelector } from './components/TierSelector';
import { OperatingLogicSelector } from './components/OperatingLogicSelector';
import { DateRuleManager } from './components/DateRuleManager';
import { DateRuleModal } from './components/DateRuleModal';
import { JsonOutput } from './components/JsonOutput';
import { ScheduleCopier } from './components/ScheduleCopier';
import { LoadAnalysisPage } from './components/LoadAnalysisPage';
import { EnergyMatrixPage } from './components/EnergyMatrixPage';
import { QualityReportPage } from './components/QualityReportPage';
import { StorageCyclesPage } from './components/StorageCyclesPage';
import { StorageProfitPage } from './components/StorageProfitPage';
import { PriceEditorPage } from './components/PriceEditorPage';
import { FloatingSectionNav, type SectionItem } from './components/FloatingSectionNav';
import { useScrollSpy } from './hooks/useScrollSpy';

// 全局未捕获异常与未处理Promise拒绝的兜底日志，辅助定位白屏
if (typeof window !== 'undefined') {
  window.addEventListener('error', (e) => {
    console.error('[window.onerror]', e.message, e.error);
  });
  window.addEventListener('unhandledrejection', (e) => {
    console.error('[window.unhandledrejection]', e.reason);
  });
}

const EditModeSelector: React.FC<{
  editMode: 'tou' | 'op';
  setEditMode: (mode: 'tou' | 'op') => void;
}> = ({ editMode, setEditMode }) => {
  const baseClasses = "px-4 py-2 rounded-md font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 w-full";
  const activeClasses = "bg-blue-600 text-white shadow-md focus:ring-blue-500";
  const inactiveClasses = "bg-slate-200 text-slate-700 hover:bg-slate-300 focus:ring-slate-400";
  return (
    <div className="p-3 bg-slate-100 rounded-lg border border-slate-200 flex flex-col sm:flex-row items-center gap-4">
        <h2 className="text-lg font-semibold text-slate-700 whitespace-nowrap">Editing Mode:</h2>
        <div className="w-full grid grid-cols-2 gap-2">
            <button onClick={() => setEditMode('tou')} className={`${baseClasses} ${editMode === 'tou' ? activeClasses : inactiveClasses}`}>
                TOU Schedule
            </button>
             <button onClick={() => setEditMode('op')} className={`${baseClasses} ${editMode === 'op' ? activeClasses : inactiveClasses}`}>
                Storage Logic
            </button>
        </div>
    </div>
  );
};


const App: React.FC = () => {
  // --- Page State ---
  const [currentPage, setCurrentPage] = useState<'editor' | 'price' | 'analysis' | 'matrix' | 'quality' | 'storage' | 'profit'>('editor');
  const [profitSelectedDate, setProfitSelectedDate] = useState<string | null>(null);
  const [lastStorageRun, setLastStorageRun] = useState<{
    payload: StorageParamsPayload;
    response: BackendStorageCyclesResponse;
  } | null>(null);
  
  // --- Configuration State ---
  const [configurations, setConfigurations] = useState<{id: string, name: string}[]>([]);
  const [currentConfigId, setCurrentConfigId] = useState<string | null>(null);
  const [currentConfigName, setCurrentConfigName] = useState<string>('');
  const [isDirty, setIsDirty] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // --- Global Load Analysis Data (共享给 Analysis 与 Matrix 两页) ---
  const [loadCleanedData, setLoadCleanedData] = useState<LoadDataPoint[]>([]);
  const [loadQuality, setLoadQuality] = useState<BackendQualityReport | null>(null);
  const [loadMeta, setLoadMeta] = useState<BackendAnalysisMeta | null>(null);
  const [isLoadUploading, setIsLoadUploading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showLoadSlow, setShowLoadSlow] = useState(false);
  const loadFileInputRef = useRef<HTMLInputElement>(null);

  // --- 悬浮目录：根据当前页面组织小节（仅桌面端展示） ---
  const navSections: SectionItem[] = useMemo(() => {
    switch (currentPage) {
      case 'editor':
        return [
          { id: 'section-config', title: '配置管理' },
          { id: 'section-edit-mode', title: '编辑模式' },
          { id: 'section-tou-grid', title: '分时表格' },
          { id: 'section-schedule-copy', title: '批量复制' },
          { id: 'section-date-rules', title: '日期规则' },
          { id: 'section-json-output', title: '数据导出' },
        ];
      case 'price':
        return [
          { id: 'section-price-table', title: '月份电价表' },
          { id: 'section-price-batch', title: '批量设置' },
          { id: 'section-price-chart', title: '时序图' },
        ];
      case 'analysis':
        // 本项目中已隐藏上传功能，故不纳入目录
        return [
          { id: 'section-load-hour-curve', title: '小时负荷曲线' },
          { id: 'section-monthly-stacked', title: '月度日均堆叠图' },
          { id: 'section-monthly-overlay', title: '电价×月日均（双轴）' },
          { id: 'section-analysis-note', title: '本页说明' },
        ];
      case 'matrix':
        return [
          { id: 'section-matrix-table', title: '日×时矩阵' },
          { id: 'section-matrix-note', title: '本页说明' },
        ];
      case 'quality':
        return loadQuality
          ? [
              { id: 'section-quality-base', title: '基础信息' },
              { id: 'section-quality-missing-summary', title: '缺失总体情况' },
              { id: 'section-quality-missing-month', title: '按月缺失统计' },
              { id: 'section-quality-missing-days', title: '缺失日期列表' },
              { id: 'section-quality-anomaly', title: '异常值统计' },
              { id: 'section-quality-note', title: '本页说明' },
            ]
          : [ { id: 'section-quality-note', title: '本页说明' } ];
      case 'profit':
        return [
          { id: 'section-profit-intro', title: '功能说明' },
          { id: 'section-profit-month', title: '收益汇总' },
          { id: 'section-profit-selector', title: '日期选择' },
          { id: 'section-profit-curves', title: '曲线对比' },
          { id: 'section-profit-metrics', title: '指标对比' },
        ];
      default:
        return [];
    }
  }, [currentPage, loadQuality]);

  const activeTocId = useScrollSpy(navSections.map(s => s.id), { topThreshold: 120 });
  
  // --- Schedule Data State ---
  const [appState, setAppState] = useState(INITIAL_APP_STATE);
  const cleanStateRef = useRef(JSON.stringify(INITIAL_APP_STATE));
  const cleanConfigNameRef = useRef('');

  // Ref to hold the latest isDirty value for callbacks, preventing dependency cycles
  const isDirtyRef = useRef(isDirty);
  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);


  // --- UI State ---
  const [selectedTier, setSelectedTier] = useState<TierId>('谷');
  const [selectedOpLogic, setSelectedOpLogic] = useState<OperatingLogicId>('待机');
  const [editMode, setEditMode] = useState<'tou' | 'op'>('tou');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<DateRule | null>(null);

  // --- Effects ---
  // 全局上传慢提示
  useEffect(() => {
    let t: number | undefined;
    if (isLoadUploading) {
      t = window.setTimeout(() => setShowLoadSlow(true), 5000);
    } else {
      setShowLoadSlow(false);
    }
    return () => { if (t) window.clearTimeout(t); };
  }, [isLoadUploading]);

  // Stable callback to load a configuration. Uses a ref for the dirty check to avoid re-creating the function.
  const handleSelectConfig = useCallback(async (id: string, initialLoad = false) => {
    if (!initialLoad && isDirtyRef.current && !window.confirm("You have unsaved changes. Are you sure you want to discard them?")) return;

    setIsLoading(true);
    try {
      const config = await api.getConfiguration(id);
      if (config) {
        setAppState(config.scheduleData);
        cleanStateRef.current = JSON.stringify(config.scheduleData);
        cleanConfigNameRef.current = config.name;
        setCurrentConfigId(config.id);
        setCurrentConfigName(config.name);
      } else {
        throw new Error("Configuration not found.");
      }
    } catch (error) {
      console.error("Failed to load configuration:", error);
      alert(`Error loading configuration: ${(error as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Load configuration list on initial mount. This now only runs once.
  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        const configList = await api.getConfigurations();
        setConfigurations(configList);
        if (configList.length > 0) {
          await handleSelectConfig(configList[0].id, true);
        } else {
          // No configs exist, start with a fresh one, marked as dirty
          setAppState(INITIAL_APP_STATE);
          setCurrentConfigId(null);
          setCurrentConfigName('My First Schedule');
          cleanStateRef.current = JSON.stringify(INITIAL_APP_STATE);
          cleanConfigNameRef.current = ''; // Make it dirty by default
          setIsDirty(true);
        }
      } catch (error) {
        console.error("Failed to load configurations:", error);
        alert("Could not load configurations. Working with a temporary session.");
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, [handleSelectConfig]);

  // Check for unsaved changes when appState or name changes
  useEffect(() => {
    const currentStateString = JSON.stringify(appState);
    const isStateDirty = currentStateString !== cleanStateRef.current;
    const isNameDirty = currentConfigName !== cleanConfigNameRef.current;
    setIsDirty(isStateDirty || isNameDirty);
  }, [appState, currentConfigName]);

  // --- Configuration Handlers ---

  const loadConfigurationsList = useCallback(async () => {
    const configList = await api.getConfigurations();
    setConfigurations(configList);
  }, []);

  const handleNewConfig = useCallback(() => {
    if (isDirtyRef.current && !window.confirm("You have unsaved changes. Are you sure you want to discard them?")) return;
    
    setAppState(INITIAL_APP_STATE);
    setCurrentConfigId(null);
    setCurrentConfigName('New Schedule');

    // Make it dirty so the user is prompted to save it.
    cleanStateRef.current = JSON.stringify(INITIAL_APP_STATE);
    cleanConfigNameRef.current = ''; // An empty clean name ensures the current name makes it dirty.
  }, []);
  
  const performSave = async (name: string, id: string | null) => {
    setIsSaving(true);
    try {
      const savedConfig = await api.saveConfiguration(name, appState, id);
      cleanStateRef.current = JSON.stringify(appState);
      cleanConfigNameRef.current = savedConfig.name;
      setCurrentConfigId(savedConfig.id);
      setCurrentConfigName(savedConfig.name);
      await loadConfigurationsList();
      // Select the newly saved config in the dropdown
      // This needs a tick to allow React to re-render the options
      setTimeout(() => {
        const select = document.getElementById('config-select') as HTMLSelectElement;
        if (select) select.value = savedConfig.id;
      }, 0);
      alert(`Configuration "${savedConfig.name}" saved successfully!`);
      return savedConfig;
    } catch (error) {
       console.error("Failed to save configuration:", error);
       alert(`Error saving configuration: ${(error as Error).message}`);
       return null;
    } finally {
       setIsSaving(false);
    }
  };

  const handleNameChange = (newName: string) => {
    setCurrentConfigName(newName);
  };
  
  const handleSaveConfig = useCallback(async () => {
    if (!currentConfigName.trim()) {
      alert("Configuration name cannot be empty.");
      return;
    }
    await performSave(currentConfigName, currentConfigId);
  }, [appState, currentConfigId, currentConfigName, loadConfigurationsList]);
  
  const handleSaveAsConfig = useCallback(() => {
    // Set the ID to null to indicate this will be a new config on the next save.
    setCurrentConfigId(null);
    
    // Suggest a new name for the copy.
    setCurrentConfigName(prevName => `${prevName} (copy)`);

    // This configuration is now a new, unsaved entity. We mark it as dirty by making
    // the "clean" reference different from the current state. The useEffect for isDirty
    // will pick up this change and enable the Save button.
    cleanConfigNameRef.current = ''; // Guarantees `currentConfigName !== cleanConfigNameRef.current`
  }, []);

  const handleExportConfig = useCallback(async () => {
    if (!currentConfigName.trim()) {
      alert("Please provide a name for the configuration before exporting.");
      return;
    }
    setIsExporting(true);
    try {
      // Use a brief timeout to allow the UI to update to the "Exporting..." state
      await new Promise(resolve => setTimeout(resolve, 50)); 
      exportScheduleToExcel(appState, currentConfigName);
    } catch (error) {
      console.error("Failed to export configuration:", error);
      alert(`Error exporting configuration: ${(error as Error).message}`);
    } finally {
      setIsExporting(false);
    }
  }, [appState, currentConfigName]);
  
  const handleDeleteConfig = useCallback(async () => {
    if (!currentConfigId) {
      alert("Cannot delete an unsaved configuration.");
      return;
    }
    
    // FIX: Removed window.confirm to ensure functionality in all environments.
    // The original code was: if (window.confirm(...)) { ... }
    setIsLoading(true);
    try {
      await api.deleteConfiguration(currentConfigId);
      const newConfigList = await api.getConfigurations();
      setConfigurations(newConfigList);
      alert(`Configuration "${currentConfigName}" deleted.`);

      if (newConfigList.length > 0) {
        await handleSelectConfig(newConfigList[0].id);
      } else {
        handleNewConfig();
      }

    } catch (error) {
      console.error("Failed to delete configuration:", error);
      alert(`Error deleting configuration: ${(error as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  }, [currentConfigId, currentConfigName, handleSelectConfig, handleNewConfig]);

    const handleImportClick = () => {
        if (isDirtyRef.current && !window.confirm("Importing a new file will discard your unsaved changes. Are you sure you want to continue?")) {
            return;
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
            fileInputRef.current.click();
        }
    };

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setIsImporting(true);
        
        try {
            const fileReader = new FileReader();
            fileReader.onload = (e) => {
                try {
                    const data = new Uint8Array(e.target?.result as ArrayBuffer);
                    const workbook = XLSX.read(data, { type: 'array' });

                    // --- 1. Process Monthly Schedule ---
                    const touSheetName = workbook.SheetNames.includes('Monthly TOU') ? 'Monthly TOU' : 'Monthly Schedule';
                    if (!workbook.SheetNames.includes(touSheetName)) throw new Error(`Sheet "${touSheetName}" not found.`);
                    
                    const touSheet = workbook.Sheets[touSheetName];
                    const touData: any[][] = XLSX.utils.sheet_to_json(touSheet, { header: 1 });
                    if (touData.length < 13) throw new Error(`${touSheetName} sheet must have 12 data rows.`);

                    const opSheetName = 'Monthly OpLogic';
                    let opData: any[][] | null = null;
                    if(workbook.SheetNames.includes(opSheetName)) {
                        const opSheet = workbook.Sheets[opSheetName];
                        opData = XLSX.utils.sheet_to_json(opSheet, { header: 1 });
                        if (opData.length < 13) throw new Error(`${opSheetName} sheet must have 12 data rows.`);
                    }
                    
                    const newMonthlySchedule: Schedule = [];
                    for(let i = 1; i <= 12; i++) {
                        const touRow = touData[i];
                        if(!touRow || touRow.length < 25) throw new Error(`Row ${i+1} in ${touSheetName} is missing columns.`);
                        const opRow = opData ? opData[i] : null;
                        if(opData && (!opRow || opRow.length < 25)) throw new Error(`Row ${i+1} in ${opSheetName} is missing columns.`);
                        
                        const scheduleRow: CellData[] = [];
                        for (let j = 1; j <= 24; j++) {
                            const tou = (touRow[j] === '深谷' ? '深' : touRow[j]) as TierId;
                            const op = (opRow ? opRow[j] : '待机') as OperatingLogicId;
                            if (!VALID_TIER_IDS.has(tou)) throw new Error(`Invalid TOU ID "${tou || 'empty'}" found in Monthly Schedule.`);
                            if (!VALID_OP_LOGIC_IDS.has(op)) throw new Error(`Invalid OpLogic ID "${op || 'empty'}" found in Monthly Schedule.`);
                            scheduleRow.push({ tou, op });
                        }
                        newMonthlySchedule.push(scheduleRow);
                    }

                    // --- 2. Process Date Rules ---
                    const newDateRules: DateRule[] = [];
                    const rulesTouSheetName = workbook.SheetNames.includes('Date Rules TOU') ? 'Date Rules TOU' : 'Date Rules';
                    if (workbook.SheetNames.includes(rulesTouSheetName)) {
                        const rulesTouSheet = workbook.Sheets[rulesTouSheetName];
                        const rulesTouData: any[][] = XLSX.utils.sheet_to_json(rulesTouSheet, { header: 1, defval: null });
                        
                        const rulesOpSheetName = 'Date Rules OpLogic';
                        let rulesOpData: any[][] | null = null;
                        if (workbook.SheetNames.includes(rulesOpSheetName)) {
                            rulesOpData = XLSX.utils.sheet_to_json(workbook.Sheets[rulesOpSheetName], { header: 1, defval: null });
                        }

                        if (rulesTouData.length > 1) {
                            const header = rulesTouData[0] || [];
                            const isNewFormat = header[1] === 'time_range';
                            const currentYear = new Date().getFullYear();

                            const parseTimeRange = (timeRange: string, year: number) => {
                                if (typeof timeRange !== 'string' || !timeRange.includes('-') || !timeRange.includes('/')) throw new Error('Invalid format');
                                const parts = timeRange.split('-');
                                if (parts.length !== 2) throw new Error('Invalid format');
                                const [startStr, endStr] = parts;
                                const startParts = startStr.split('/');
                                const endParts = endStr.split('/');
                                if (startParts.length !== 2 || endParts.length !== 2) throw new Error('Invalid format');
                                const [startMonth, startDay] = startParts.map(p => parseInt(p, 10));
                                const [endMonth, endDay] = endParts.map(p => parseInt(p, 10));
                                if (isNaN(startMonth) || isNaN(startDay) || isNaN(endMonth) || isNaN(endDay)) throw new Error('Invalid date parts');
                                
                                const startDate = new Date(Date.UTC(year, startMonth - 1, startDay));
                                const endDate = new Date(Date.UTC(year, endMonth - 1, endDay));
                                if (endDate < startDate) {
                                    endDate.setUTCFullYear(year + 1);
                                }
                                const toYMD = (date: Date) => date.toISOString().split('T')[0];
                                return { startDate: toYMD(startDate), endDate: toYMD(endDate) };
                            };
                            
                            const formatExcelDate = (excelDate: any): string => {
                                if (typeof excelDate === 'number' && excelDate > 0) {
                                    // @ts-ignore
                                    const date = XLSX.SSF.parse_date_code(excelDate);
                                    const d = new Date(Date.UTC(date.y, date.m - 1, date.d));
                                    return d.toISOString().split('T')[0];
                                }
                                if (typeof excelDate === 'string' && excelDate.trim()) {
                                     try {
                                        return new Date(excelDate).toISOString().split('T')[0];
                                    } catch(e) {
                                        throw new Error(`Invalid date string: ${excelDate}`);
                                    }
                                }
                                throw new Error(`Invalid or empty date value: ${excelDate}`);
                            };


                            for (let i = 1; i < rulesTouData.length; i++) {
                                const touRow = rulesTouData[i];
                                if (!touRow || touRow.every(cell => cell === null)) continue;

                                let name: string, startDate: string, endDate: string;
                                let touSchedule: any[], opSchedule: any[];

                                if (isNewFormat) {
                                    if (touRow.length < 26) throw new Error(`Row ${i + 1} in ${rulesTouSheetName} is missing columns for time_range format.`);
                                    name = touRow[0];
                                    const timeRange = touRow[1];
                                    touSchedule = touRow.slice(2, 26);
                                    if (!name || !timeRange) throw new Error(`Missing name or time_range in Date Rules row ${i + 1}.`);
                                    
                                    try {
                                        const dates = parseTimeRange(timeRange, currentYear);
                                        startDate = dates.startDate;
                                        endDate = dates.endDate;
                                    } catch (e) {
                                        throw new Error(`Invalid time_range format in row ${i + 1}: "${timeRange}". Expected MM/DD-MM/DD.`);
                                    }
                                    const opRow = rulesOpData ? rulesOpData.find(r => r && r[0] === name && r[1] === timeRange) : null;
                                    opSchedule = opRow ? opRow.slice(2, 26) : Array(24).fill('待机');
                                } else {
                                    if (touRow.length < 27) throw new Error(`Row ${i + 1} in ${rulesTouSheetName} is missing columns for Start/End Date format.`);
                                    name = touRow[0];
                                    const rawStartDate = touRow[1];
                                    const rawEndDate = touRow[2];
                                    if (!name || !rawStartDate || !rawEndDate) throw new Error(`Missing name or dates in Date Rules row ${i + 1}.`);
                                    
                                    startDate = formatExcelDate(rawStartDate);
                                    endDate = formatExcelDate(rawEndDate);
                                    touSchedule = touRow.slice(3, 27);
                                    
                                    const opRow = rulesOpData ? rulesOpData.find(r => r && r[0] === name && String(r[1]) === String(rawStartDate)) : null;
                                    opSchedule = opRow ? opRow.slice(3, 27) : Array(24).fill('待机');
                                }

                                const ruleSchedule: CellData[] = [];
                                for (let j = 0; j < 24; j++) {
                                    const tou = (touSchedule[j] === '深谷' ? '深' : touSchedule[j]) as TierId;
                                    const op = opSchedule[j] as OperatingLogicId;
                                    if (!VALID_TIER_IDS.has(tou)) throw new Error(`Invalid TOU "${tou || 'empty'}" in rule "${name}".`);
                                    if (!VALID_OP_LOGIC_IDS.has(op)) throw new Error(`Invalid OpLogic "${op || 'empty'}" in rule "${name}".`);
                                    ruleSchedule.push({ tou, op });
                                }
                               
                                newDateRules.push({
                                    id: `imported_${Date.now()}_${i}`,
                                    name,
                                    startDate,
                                    endDate,
                                    schedule: ruleSchedule,
                                });
                            }
                        }
                    }
                    
                    // --- 3. (Optional) Process TOU Prices ---
                    let newPrices: MonthlyTouPrices | null = null;
                    try {
                      if (workbook.SheetNames.includes('TOU Prices')) {
                        const priceSheet = workbook.Sheets['TOU Prices'];
                        const priceData: any[][] = XLSX.utils.sheet_to_json(priceSheet, { header: 1, defval: null });
                        if (priceData.length >= 13) {
                          // 解析表头，支持两种顺序：
                          // 1) 旧：['Month','深','谷','平','峰','尖']
                          // 2) 新：['Month','尖','峰','平','谷','深']
                          const header: any[] = (priceData[0] || []).map((h) => (h ?? '').toString().trim());
                          const findIdx = (key: string) => {
                            const idx = header.findIndex((h) => h === key);
                            return idx >= 0 ? idx : -1;
                          };
                          const idxMap: Record<'深'|'谷'|'平'|'峰'|'尖', number> = {
                            '深': findIdx('深'),
                            '谷': findIdx('谷'),
                            '平': findIdx('平'),
                            '峰': findIdx('峰'),
                            '尖': findIdx('尖'),
                          };
                          // 回退：若未识别到表头，则按旧版固定列位 1..5
                          const fallback = (v: number, fb: number) => (v >= 0 ? v : fb);
                          const out: any[] = [];
                          for (let i = 1; i <= 12; i++) {
                            const row = priceData[i] || [];
                            const pm = {
                              '深': row[fallback(idxMap['深'], 1)] === '' || row[fallback(idxMap['深'], 1)] == null ? null : Number(row[fallback(idxMap['深'], 1)]),
                              '谷': row[fallback(idxMap['谷'], 2)] === '' || row[fallback(idxMap['谷'], 2)] == null ? null : Number(row[fallback(idxMap['谷'], 2)]),
                              '平': row[fallback(idxMap['平'], 3)] === '' || row[fallback(idxMap['平'], 3)] == null ? null : Number(row[fallback(idxMap['平'], 3)]),
                              '峰': row[fallback(idxMap['峰'], 4)] === '' || row[fallback(idxMap['峰'], 4)] == null ? null : Number(row[fallback(idxMap['峰'], 4)]),
                              '尖': row[fallback(idxMap['尖'], 5)] === '' || row[fallback(idxMap['尖'], 5)] == null ? null : Number(row[fallback(idxMap['尖'], 5)]),
                            } as any;
                            out.push(pm);
                          }
                          newPrices = out as MonthlyTouPrices;
                        }
                      }
                    } catch (e) {
                      console.warn('解析 TOU Prices 表失败，使用默认电价。', e);
                    }

                    // 基于新导入的月度 TOU 表，清空目标月未使用档位的电价
                    if (newPrices) {
                      const TIERS: TierId[] = ['深','谷','平','峰','尖'];
                      for (let i = 0; i < 12; i++) {
                        const used = new Set<TierId>(newMonthlySchedule[i].map(c => c.tou as TierId));
                        // merge tiers used in date rules that cover month i (ignore year)
                        (newDateRules || []).forEach(rule => {
                          try {
                            const sDate = new Date(`${rule.startDate}T00:00:00`);
                            const eDate = new Date(`${rule.endDate}T00:00:00`);
                            let cur = new Date(sDate.getFullYear(), sDate.getMonth(), 1);
                            const last = new Date(eDate.getFullYear(), eDate.getMonth(), 1);
                            while (cur.getTime() <= last.getTime()) {
                              const mi = cur.getMonth();
                              if (mi === i) {
                                (rule.schedule as any[] || []).forEach(cell => {
                                  const tou = (cell?.tou as TierId) || null;
                                  if (tou) used.add(tou);
                                });
                                break;
                              }
                              cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
                            }
                          } catch { /* ignore bad rule */ }
                        });
                        TIERS.forEach(t => {
                          if (!used.has(t)) (newPrices as any)[i][t] = null;
                        });
                      }
                    }

                    // After successful parsing, update the state
                    setAppState({ monthlySchedule: newMonthlySchedule, dateRules: newDateRules, prices: newPrices ?? INITIAL_APP_STATE.prices });
                    setCurrentConfigId(null);
                    setCurrentConfigName(file.name.replace(/\.xlsx$/i, '') || "Imported Schedule");
                    cleanStateRef.current = '';
                    cleanConfigNameRef.current = '';
                    alert('Excel data imported successfully! Remember to "Save" to create a new configuration.');

                } catch (err: any) {
                    console.error('Failed to parse Excel file:', err);
                    alert(`Import failed: ${err.message}`);
                } finally {
                    setIsImporting(false);
                }
            };
            fileReader.readAsArrayBuffer(file);
        } catch (err: any) {
            console.error('Failed to read file:', err);
            alert(`Import failed: Could not read file. ${err.message}`);
            setIsImporting(false);
        }
    };

  // --- Existing Handlers (Wrapped to trigger dirty state) ---
  
  const handleScheduleChange = useCallback((newSchedule: Schedule) => {
    setAppState(prevState => ({ ...prevState, monthlySchedule: newSchedule }));
  }, []);

  const handleCopySchedule = useCallback((sourceMonthIndex: number, targetMonthIndices: number[]) => {
    setAppState(prevState => {
      const newSchedule = prevState.monthlySchedule.map(row => [...row]);
      const sourceSchedule = newSchedule[sourceMonthIndex];
      targetMonthIndices.forEach(targetIndex => {
        newSchedule[targetIndex] = sourceSchedule.map(cell => ({ ...cell }));
      });
      return { ...prevState, monthlySchedule: newSchedule };
    });
  }, []);
  
  const handleSaveRule = useCallback((rule: DateRule) => {
    setAppState(prevState => {
      const newRules = [...prevState.dateRules];
      const index = newRules.findIndex(r => r.id === rule.id);
      if (index > -1) {
        newRules[index] = rule;
      } else {
        newRules.push(rule);
      }
      return { ...prevState, dateRules: newRules };
    });
    setIsModalOpen(false);
    setEditingRule(null);
  }, []);

  const handleDeleteRule = useCallback((ruleId: string) => {
    // FIX: Removed window.confirm to ensure functionality in all environments.
    // The original code was: if (window.confirm(...)) { ... }
    setAppState(prevState => ({
      ...prevState,
      dateRules: prevState.dateRules.filter(r => r.id !== ruleId),
    }));
  }, []);

  const handleOpenModal = (rule: DateRule | null) => {
    setEditingRule(rule);
    setIsModalOpen(true);
  };

  if (isLoading && configurations.length === 0) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-100"><div className="text-xl font-semibold text-slate-600">Loading Configurations...</div></div>;
  }
  
  // 导航按钮：缩小内边距，降低头部整体高度
  const navButtonBaseClasses = "px-4 py-1.5 rounded-md font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500";
  const navButtonActiveClasses = "bg-white text-blue-600 shadow";
  const navButtonInactiveClasses = "bg-transparent text-slate-600 hover:bg-slate-300/50";

  return (
    <>
      {/* 悬浮导航栏：固定顶部，不随页面滚动 */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-2">
          {/* 顶部行：居中标题 + 右侧上传按钮（绝对定位保证标题真正居中） */}
          <div className="relative flex items-center">
            <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-slate-800 text-center w-full">
              Interactive Schedule & Load Analysis
            </h1>
            <div className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <button
                onClick={() => loadFileInputRef.current?.click()}
                disabled={isLoadUploading}
                className={`px-3 py-1.5 rounded-md font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${isLoadUploading ? 'opacity-50 cursor-not-allowed' : ''} bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500`}
              >
                {isLoadUploading ? '处理中...' : (loadCleanedData.length > 0 ? '重新上传负荷' : '上传负荷文件')}
              </button>
            </div>
          </div>
          <nav className="mt-2 flex justify-center">
            <div className="bg-slate-200 rounded-lg p-1 flex space-x-1">
              <button 
                onClick={() => setCurrentPage('editor')} 
                className={`${navButtonBaseClasses} ${currentPage === 'editor' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'editor' ? 'page' : undefined}
              >
                Schedule Editor
              </button>
              <button 
                onClick={() => setCurrentPage('price')} 
                className={`${navButtonBaseClasses} ${currentPage === 'price' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'price' ? 'page' : undefined}
              >
                TOU Prices
              </button>
              <button 
                onClick={() => setCurrentPage('analysis')} 
                className={`${navButtonBaseClasses} ${currentPage === 'analysis' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'analysis' ? 'page' : undefined}
              >
                Load Analysis
              </button>
              <button 
                onClick={() => setCurrentPage('matrix')} 
                className={`${navButtonBaseClasses} ${currentPage === 'matrix' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'matrix' ? 'page' : undefined}
              >
                Energy Matrix
              </button>
              <button 
                onClick={() => setCurrentPage('quality')} 
                className={`${navButtonBaseClasses} ${currentPage === 'quality' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'quality' ? 'page' : undefined}
              >
                Data Quality
              </button>
              <button 
                onClick={() => setCurrentPage('storage')} 
                className={`${navButtonBaseClasses} ${currentPage === 'storage' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'storage' ? 'page' : undefined}
              >
                Storage Cycles
              </button>
              <button 
                onClick={() => setCurrentPage('profit')} 
                className={`${navButtonBaseClasses} ${currentPage === 'profit' ? navButtonActiveClasses : navButtonInactiveClasses}`}
                aria-current={currentPage === 'profit' ? 'page' : undefined}
              >
                Storage Profit
              </button>
            </div>
          </nav>
        </div>
      </header>

      {/* 内容容器：根据精简后的头部高度调整留白，避免遮挡 */}
      <div className="container mx-auto p-4 sm:p-6 lg:p-8 pt-28">

      {/* 导航已移动到固定顶部 */}

      {/* 全局：负荷文件上传（供 Load Analysis 与 Energy Matrix 共用） */}
      <div className="mt-4 mb-6 p-3 bg-slate-100 rounded-lg border border-slate-200 flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="text-sm text-slate-700 font-semibold">负荷文件：</div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadFileInputRef.current?.click()}
            disabled={isLoadUploading}
            className={`px-4 py-2 rounded-md font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${isLoadUploading ? 'opacity-50 cursor-not-allowed' : ''} bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500`}
          >
            {isLoadUploading ? '处理中...' : (loadCleanedData.length > 0 ? '重新上传负荷文件' : '上传负荷文件（Excel/CSV）')}
          </button>
          {loadCleanedData.length > 0 && (
            <span className="text-xs text-green-700">已加载 {loadCleanedData.length} 小时，范围：{loadMeta?.start ? new Date(loadMeta.start).toLocaleString() : '-'} ~ {loadMeta?.end ? new Date(loadMeta.end).toLocaleString() : '-'}</span>
          )}
        </div>
        {loadError && <div className="text-xs text-red-600">{loadError}</div>}
        {showLoadSlow && isLoadUploading && (
          <div className="text-xs text-slate-500">文件较大，正在清洗中，请耐心等待…</div>
        )}
        <input
          type="file"
          ref={loadFileInputRef}
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setIsLoadUploading(true);
            setLoadError(null);
            setLoadCleanedData([]);
            setLoadQuality(null);
            setLoadMeta(null);
            try {
              const response = await analyzeLoadFile(file);
              const normalized: LoadDataPoint[] = (response.cleaned_points || [])
                .map((p) => {
                  const t = p?.timestamp ? new Date(p.timestamp) : null;
                  const loadValue = Number(p?.load_kwh ?? 0);
                  if (!t || isNaN(t.getTime())) return null as any;
                  return { timestamp: t, load: Number.isFinite(loadValue) ? loadValue : 0 } as LoadDataPoint;
                })
                .filter((x): x is LoadDataPoint => x !== null);
              if (normalized.length === 0) throw new Error('后端未返回有效的小时级数据。');
              setLoadCleanedData(normalized);
              setLoadQuality(response.report);
              setLoadMeta(response.meta);
            } catch (err) {
              const message = err instanceof Error ? err.message : String(err);
              setLoadError(`上传失败：${message}`);
              setLoadCleanedData([]);
              setLoadQuality(null);
              setLoadMeta(null);
            } finally {
              setIsLoadUploading(false);
              setTimeout(() => { if (event.target) (event.target as HTMLInputElement).value = ''; }, 0);
            }
          }}
          className="hidden"
          accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
        />
      </div>

      {currentPage === 'editor' && (
        <>
          {/* 配置管理 */}
          <div id="section-config" className="scroll-mt-24">
          <ConfigurationManager
            configurations={configurations}
            currentConfigId={currentConfigId}
            configName={currentConfigName}
            isDirty={isDirty}
            isLoading={isLoading}
            isSaving={isSaving}
            isExporting={isExporting}
            isImporting={isImporting}
            onSelect={(id) => handleSelectConfig(id)}
            onNew={handleNewConfig}
            onSave={handleSaveConfig}
            onSaveAs={handleSaveAsConfig}
            onDelete={handleDeleteConfig}
            onNameChange={handleNameChange}
            onExport={handleExportConfig}
            onImportClick={handleImportClick}
          />
          </div>

          {/* 编辑模式 */}
          <div id="section-edit-mode" className="scroll-mt-24 grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <EditModeSelector editMode={editMode} setEditMode={setEditMode} />
            {editMode === 'tou' 
                ? <TierSelector selectedTier={selectedTier} onTierSelect={setSelectedTier} />
                : <OperatingLogicSelector selectedOpLogic={selectedOpLogic} onOpLogicSelect={setSelectedOpLogic} />
            }
          </div>

          {/* 分时表格 */}
          <div id="section-tou-grid" className="scroll-mt-24 bg-white rounded-xl shadow-lg p-1 overflow-x-auto">
             <TouGrid 
                schedule={appState.monthlySchedule}
                dateRules={appState.dateRules}
                onScheduleChange={handleScheduleChange}
                selectedTier={selectedTier}
                selectedOpLogic={selectedOpLogic}
                editMode={editMode}
            />
          </div>

           {/* 批量复制 */}
           <div id="section-schedule-copy" className="scroll-mt-24 mt-6">
              <ScheduleCopier onCopy={handleCopySchedule} />
            </div>

          {/* 日期规则 */}
          <div id="section-date-rules" className="scroll-mt-24">
          <DateRuleManager 
            rules={appState.dateRules}
            onAdd={() => handleOpenModal(null)}
            onEdit={handleOpenModal}
            onDelete={handleDeleteRule}
          />
          </div>

          <DateRuleModal
            isOpen={isModalOpen}
            rule={editingRule}
            onClose={() => setIsModalOpen(false)}
            onSave={handleSaveRule}
          />

          {/* 数据导出 */}
          <div id="section-json-output" className="scroll-mt-24">
            <JsonOutput data={appState} />
          </div>
        </>
      )}

      {currentPage === 'price' && (
        <PriceEditorPage
          scheduleData={appState}
          onChange={(newPrices) => {
            setAppState(prev => ({ ...prev, prices: newPrices }));
          }}
        />
      )}

      {currentPage === 'analysis' && (
        <LoadAnalysisPage 
          scheduleData={appState}
          externalCleanedData={loadCleanedData}
          externalQualityReport={loadQuality}
          externalMetaInfo={loadMeta}
          hideUploader={true}
        />
      )}

      {currentPage === 'matrix' && (
        <EnergyMatrixPage 
          scheduleData={appState}
          externalCleanedData={loadCleanedData}
          hideUploader={true}
        />
      )}

{currentPage === 'quality' && (
        <QualityReportPage 
          scheduleData={appState}
          externalQualityReport={loadQuality}
          externalMetaInfo={loadMeta}
        />
      )}

      {currentPage === 'profit' && (
        <StorageProfitPage
          scheduleData={appState}
          externalCleanedData={loadCleanedData}
          storageCyclesResult={lastStorageRun?.response ?? null}
          storageCyclesPayload={lastStorageRun?.payload ?? null}
          selectedDateFromCycles={profitSelectedDate}
          onSelectedDateConsumed={() => setProfitSelectedDate(null)}
        />
      )}
      {/* Storage Cycles 页面保持挂载，避免切换时状态重置 */}
      <div className={currentPage === 'storage' ? 'p-4' : 'p-4 hidden'}>
        <StorageCyclesPage 
          scheduleData={appState}
          externalCleanedData={loadCleanedData}
          onNavigateProfit={(date) => {
            setProfitSelectedDate(date);
            setCurrentPage('profit');
          }}
          onLatestRunChange={(payload, response) => {
            setLastStorageRun({ payload, response });
          }}
        />
      </div>

       <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            accept=".xlsx, application/vnd.openxmlformats-officedocument.spreadsheet.sheet"
        />
      {/* 悬浮目录（固定定位，不随页面滚动改变位置） */}
      <FloatingSectionNav sections={navSections} activeId={activeTocId} />
    </div>
    </>
  );
};

export default App;
