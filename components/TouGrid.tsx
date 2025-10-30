import React, { useState, useCallback, useRef, useMemo } from 'react';
import type { Schedule, TierId, CellPosition, DateRule, OperatingLogicId } from '../types';
import { MONTHS, HOURS } from '../constants';
import { MergedGridCell } from './MergedGridCell';

interface TouGridProps {
  schedule: Schedule;
  dateRules: DateRule[];
  onScheduleChange: (newSchedule: Schedule) => void;
  selectedTier: TierId;
  selectedOpLogic: OperatingLogicId;
  editMode: 'tou' | 'op';
}

export const TouGrid: React.FC<TouGridProps> = ({ schedule, dateRules, onScheduleChange, selectedTier, selectedOpLogic, editMode }) => {
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState<CellPosition | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<CellPosition | null>(null);
  const [dimmedMonths, setDimmedMonths] = useState<Set<number>>(new Set());
  const gridRef = useRef<HTMLDivElement>(null);

  const affectedMonths = useMemo(() => {
    const affected = new Map<number, string[]>();
    dateRules.forEach(rule => {
      const start = new Date(rule.startDate);
      const end = new Date(rule.endDate);
      const startMonth = start.getUTCMonth();
      const endMonth = end.getUTCMonth();
      const startYear = start.getUTCFullYear();
      const endYear = end.getUTCFullYear();

      for (let y = startYear; y <= endYear; y++) {
        const monthStart = (y === startYear) ? startMonth : 0;
        const monthEnd = (y === endYear) ? endMonth : 11;
        for (let m = monthStart; m <= monthEnd; m++) {
          if (!affected.has(m)) {
            affected.set(m, []);
          }
          if (!affected.get(m)!.includes(rule.name)) {
            affected.get(m)!.push(rule.name);
          }
        }
      }
    });
    return affected;
  }, [dateRules]);

  const handleToggleMonth = useCallback((monthIndex: number) => {
    setDimmedMonths(prev => {
      const newSet = new Set(prev);
      if (newSet.has(monthIndex)) {
        newSet.delete(monthIndex);
      } else {
        newSet.add(monthIndex);
      }
      return newSet;
    });
  }, []);

  const isInSelection = useCallback((monthIndex: number, hourIndex: number) => {
    if (!selectionStart || !selectionEnd) return false;
    const minMonth = Math.min(selectionStart.monthIndex, selectionEnd.monthIndex);
    const maxMonth = Math.max(selectionStart.monthIndex, selectionEnd.monthIndex);
    const minHour = Math.min(selectionStart.hourIndex, selectionEnd.hourIndex);
    const maxHour = Math.max(selectionStart.hourIndex, selectionEnd.hourIndex);
    return monthIndex >= minMonth && monthIndex <= maxMonth && hourIndex >= minHour && hourIndex <= maxHour;
  }, [selectionStart, selectionEnd]);

  const getHourFromMouseEvent = (e: React.MouseEvent<HTMLDivElement>, startHour: number, endHour: number): number => {
    const span = endHour - startHour + 1;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const hourWidth = rect.width / span;
    const clickedHourIndexInSpan = Math.floor(x / hourWidth);
    const clampedIndex = Math.max(0, Math.min(clickedHourIndexInSpan, span - 1));
    return startHour + clampedIndex;
  };

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>, monthIndex: number, startHour: number, endHour: number) => {
    setIsSelecting(true);
    const clickedHour = getHourFromMouseEvent(e, startHour, endHour);
    setSelectionStart({ monthIndex, hourIndex: clickedHour });
    setSelectionEnd({ monthIndex, hourIndex: clickedHour });
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>, monthIndex: number, startHour: number, endHour: number) => {
    if (isSelecting) {
        const currentHour = getHourFromMouseEvent(e, startHour, endHour);
        setSelectionEnd({ monthIndex, hourIndex: currentHour });
    }
  }, [isSelecting]);
  
  const applySelection = useCallback(() => {
     if (!isSelecting || !selectionStart || !selectionEnd) return;
      
    const newSchedule = schedule.map(row => row.map(cell => ({ ...cell })));
    const minMonth = Math.min(selectionStart.monthIndex, selectionEnd.monthIndex);
    const maxMonth = Math.max(selectionStart.monthIndex, selectionEnd.monthIndex);
    const minHour = Math.min(selectionStart.hourIndex, selectionEnd.hourIndex);
    const maxHour = Math.max(selectionStart.hourIndex, selectionEnd.hourIndex);

    for (let m = minMonth; m <= maxMonth; m++) {
      for (let h = minHour; h <= maxHour; h++) {
        if (editMode === 'tou') {
            newSchedule[m][h].tou = selectedTier;
        } else {
            newSchedule[m][h].op = selectedOpLogic;
        }
      }
    }
    onScheduleChange(newSchedule);

    setIsSelecting(false);
    setSelectionStart(null);
    setSelectionEnd(null);
  }, [isSelecting, selectionStart, selectionEnd, selectedTier, selectedOpLogic, editMode, onScheduleChange, schedule]);

  const handleMouseUp = useCallback(() => {
    applySelection();
  }, [applySelection]);
  
  const handleMouseLeave = useCallback(() => {
    if (isSelecting) {
      applySelection();
    }
  }, [isSelecting, applySelection]);


  return (
    <div 
      ref={gridRef}
      className="grid select-none border-t border-l border-slate-300" 
      style={{ gridTemplateColumns: `auto repeat(${HOURS.length}, minmax(48px, 1fr))` }}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      {/* Header Row */}
      <div className="sticky top-0 z-10 bg-slate-100 font-semibold text-slate-600 text-sm p-2 border-b border-r border-slate-300 flex items-center justify-center h-14">Time</div>
      {HOURS.map((hour) => (
        <div key={hour} className="sticky top-0 z-10 text-center bg-slate-100 font-semibold text-slate-600 text-sm p-2 border-b border-r border-slate-300 flex items-center justify-center h-14">
          {hour}
        </div>
      ))}
      
      {/* Grid Body */}
      {schedule.map((monthSchedule, monthIndex) => {
        const affectingRules = affectedMonths.get(monthIndex);
        const tooltipText = affectingRules ? `Affected by: ${affectingRules.join(', ')}` : '';
        const monthLabelBg = monthIndex % 2 === 0 ? 'bg-slate-100' : 'bg-white';
        const isDimmed = dimmedMonths.has(monthIndex);
        
        const monthCells = [];
        let h = 0;
        while (h < HOURS.length) {
            const startHour = h;
            const currentCellData = monthSchedule[h];
            let span = 1;
            while (h + span < HOURS.length && 
                    monthSchedule[h + span].tou === currentCellData.tou &&
                    monthSchedule[h + span].op === currentCellData.op) {
                span++;
            }
            const endHour = h + span - 1;

            const isBlockSelected = Array.from({ length: span }, (_, i) => 
                isInSelection(monthIndex, startHour + i)
            ).some(Boolean);

            monthCells.push(
                <MergedGridCell
                    key={`${monthIndex}-${startHour}`}
                    cellData={currentCellData}
                    startHour={startHour}
                    endHour={endHour}
                    span={span}
                    isSelected={isBlockSelected}
                    isDimmed={isDimmed}
                    onMouseDown={(e) => handleMouseDown(e, monthIndex, startHour, endHour)}
                    onMouseMove={(e) => handleMouseMove(e, monthIndex, startHour, endHour)}
                />
            );
            
            h += span;
        }

        return (
          <React.Fragment key={MONTHS[monthIndex]}>
            <div 
              className={`sticky left-0 ${monthLabelBg} font-semibold text-slate-600 text-sm p-2 border-b border-r border-slate-300 flex items-center justify-center cursor-pointer hover:bg-slate-200 transition-colors`}
              title={tooltipText || 'Click to dim/un-dim month'}
              onClick={() => handleToggleMonth(monthIndex)}
            >
              <span className="flex items-center gap-2">
                {MONTHS[monthIndex]}
                {affectingRules && <span className="text-blue-500 font-bold">*</span>}
              </span>
            </div>
            {monthCells}
          </React.Fragment>
        )
      })}
    </div>
  );
};