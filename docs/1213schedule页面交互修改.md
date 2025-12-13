核心交互逻辑代码整理这个方案的核心思想是**“状态提升”**：将鼠标当前所在的列索引 (hoveredCol) 存储在父组件中，然后分别通知表头（Header）和单元格（Cell）根据这个状态改变样式。1. 状态定义 (State & Handlers)首先在父组件中定义一个状态，用来记录鼠标当前在哪一列（哪个小时）。// 状态：记录当前鼠标悬停的列索引 (0-23)，初始为 null
const [hoveredCol, setHoveredCol] = useState(null);

// 鼠标移入单元格：更新状态
const handleMouseEnter = (colIndex) => {
  setHoveredCol(colIndex);
};

// 鼠标离开整个表格：重置状态（防止鼠标移出后高亮卡住）
const handleMouseLeaveGrid = () => {
  setHoveredCol(null);
};
2. 表头联动 (Header Sync)效果描述： 顶部的表头数字（例如 14, 15）会变成深蓝色背景并高亮。实现逻辑： 在遍历生成表头 <th> 时，判断 hoveredCol === hour，如果相等，则应用高亮样式（背景色、放大、层级提升）。{hours.map((hour) => (
  <th 
    key={hour}
    // 动态类名逻辑
    className={`
      border-b border-gray-200 text-xs font-medium transition-all duration-150 relative
      ${/* 如果当前列被悬停(hoveredCol === hour)，则添加高亮类 */ ''}
      ${hoveredCol === hour 
          ? 'bg-blue-600 text-white scale-110 z-10 shadow-md' // 高亮样式
          : 'bg-gray-50 text-gray-600'                        // 普通样式
      }
    `}
  >
    <div className="flex flex-col items-center justify-center py-2">
      <span>{hour}</span>
      
      {/* 可选：添加一个小箭头指向下方，增强视觉引导 */}
      {hoveredCol === hour && (
        <div className="absolute -bottom-1 w-2 h-2 bg-blue-600 rotate-45 transform"></div>
      )}
    </div>
  </th>
))}
3. 整列高亮 (Column Highlight)效果描述： 一道淡蓝色的光带会贯穿上下，让你清楚知道这列对应的是哪个小时。实现逻辑： 1. 在每个单元格 <td> 上绑定 onMouseEnter。2. 在 <td> 内部使用绝对定位的遮罩层 (Overlay)。3. 关键点： 不要直接改变 td 的背景色，因为 td 本身已经有颜色（表示峰平谷）。叠加一个半透明的 div 是最安全的做法。{/* 遍历生成的单元格 */}
<td 
  key={colIndex}
  // 关键：鼠标移入时，将当前列索引传给父组件状态
  onMouseEnter={() => handleMouseEnter(colIndex)}
  
  // 必须设置为 relative，以便内部的遮罩层可以绝对定位
  className={`
    relative border-b border-gray-100 text-center cursor-crosshair
    ${/* 这里是单元格原本的颜色配置，例如 bg-green-400 */ typeConfig[typeValue].color}
  `}
>
  {/* --- 核心高亮遮罩层 --- 
      条件渲染：只有当 hoveredCol 等于当前列索引时才显示
  */}
  {hoveredCol === colIndex && (
    <div className="
      absolute inset-0            // 撑满整个单元格
      bg-blue-900/10              // 半透明深蓝色背景
      border-x-2 border-blue-500/50 // 左右蓝色边框，形成'通道'感
      pointer-events-none         // 关键！让鼠标事件穿透，不影响点击操作
      z-10                        // 确保浮在内容之上
    "></div>
  )}

  {/* 单元格原本的内容 */}
  <div className="h-10 flex items-center justify-center text-xs text-gray-700/50">
    {typeConfig[typeValue].text}
  </div>
</td>
---
相同配置月份的展示优化方案针对 "如何展示和管理具有相同配置的月份" 这一需求，以下是三种不同维度的交互设计方案。
方案一：动态视图折叠 (Compact/Merged View) - 最推荐这是最直接响应您需求的方案。系统自动检测数据，将相同的行“视觉合并”。核心逻辑：前端在渲染前对 12 个月的数据进行指纹比对 (Hash/Stringify)。如果 Jan, Feb, Dec 的数据一模一样，则只渲染一行。视觉表现：左侧的标题栏（Row Header）变宽，显示 "Jan, Feb, Dec" 或 "Winter Season"。交互方式：查看：默认或通过开关切换到“精简模式”。编辑：用户在该合并行上“刷”配置时，系统自动同步更新背后的 Jan, Feb, Dec 三个月份的数据。分离：如果用户想单独修改 Feb，通常需要先切换回“完整视图”，或者在合并行提供一个“拆分”按钮。优点：极大地节省垂直空间（可能从 12 行变成 3 行），之前的“对齐难”问题也随之解决。用户能直观看到“哪些月份是一样的”。

---
参考代码：
```
import React, { useState, useMemo, useEffect } from 'react';
import { Layers, LayoutList, Zap, Check, MousePointer2, BatteryCharging, ArrowUpCircle, Circle, ArrowDownCircle } from 'lucide-react';

const TOUScheme1 = () => {
  // --- 常量定义 ---
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const hours = Array.from({ length: 24 }, (_, i) => i);

  // 1. TOU 电价配置定义
  const touTiers = {
    0: { id: 0, label: '深 (Deep)', color: 'bg-green-400', hover: 'hover:bg-green-500', text: '深', priceDesc: '最低价' },
    1: { id: 1, label: '谷 (Valley)', color: 'bg-green-200', hover: 'hover:bg-green-300', text: '谷', priceDesc: '低价' },
    2: { id: 2, label: '平 (Flat)', color: 'bg-gray-100', hover: 'hover:bg-gray-200', text: '平', priceDesc: '平价' },
    3: { id: 3, label: '峰 (Peak)', color: 'bg-orange-300', hover: 'hover:bg-orange-400', text: '峰', priceDesc: '高价' },
    4: { id: 4, label: '尖 (Super)', color: 'bg-red-400', hover: 'hover:bg-red-500', text: '尖', priceDesc: '最高价' },
  };

  // 2. Storage 储能动作定义 (新增)
  const storageActions = {
    0: { id: 0, label: '待机 (Idle)', icon: <Circle size={14} className="text-gray-400" />, color: 'text-gray-500', bg: 'bg-gray-50/50' },
    1: { id: 1, label: '充电 (Charge)', icon: <ArrowDownCircle size={16} className="text-blue-600" />, color: 'text-blue-700 font-bold', bg: 'bg-blue-100/80' },
    2: { id: 2, label: '放电 (Discharge)', icon: <ArrowUpCircle size={16} className="text-orange-600" />, color: 'text-orange-700 font-bold', bg: 'bg-orange-100/80' },
  };

  // --- 状态管理 ---
  
  // 模式状态：'tou' | 'storage'
  const [editMode, setEditMode] = useState('tou'); 
  const [isCompactMode, setIsCompactMode] = useState(true);
  
  // 画笔状态
  const [selectedTouTier, setSelectedTouTier] = useState(3); // TOU模式下的画笔
  const [selectedStorageAction, setSelectedStorageAction] = useState(1); // Storage模式下的画笔

  const [hoveredCol, setHoveredCol] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // 数据层 1：TOU 数据
  const [touGridData, setTouGridData] = useState(() => {
    // 模拟数据初始化...
    const winterPattern = Array.from({ length: 24 }, (_, i) => (i >= 18 && i <= 21 ? 3 : i < 7 ? 1 : 2));
    const summerPattern = Array.from({ length: 24 }, (_, i) => (i >= 10 && i <= 15 ? 4 : 2));
    const defaultPattern = Array.from({ length: 24 }, () => 2);
    return months.map((m) => {
      if (['Jan', 'Feb', 'Dec'].includes(m)) return [...winterPattern];
      if (['Jul', 'Aug'].includes(m)) return [...summerPattern];
      return [...defaultPattern];
    });
  });

  // 数据层 2：储能数据 (新增)
  const [storageGridData, setStorageGridData] = useState(() => {
    // 默认全待机
    const defaultStorage = Array.from({ length: 24 }, () => 0); 
    return months.map(() => [...defaultStorage]);
  });

  // --- 核心逻辑：严格分组 (Strict Grouping) ---
  // 只有当 TOU配置 和 储能配置 都完全一致时，才合并月份
  const groupedRows = useMemo(() => {
    if (!isCompactMode) {
      return months.map((month, index) => ({
        id: `single-${index}`,
        label: month,
        touData: touGridData[index],
        storageData: storageGridData[index],
        monthIndices: [index],
        isMerged: false
      }));
    }

    const groups = [];
    const processedIndices = new Set();

    months.forEach((_, index) => {
      if (processedIndices.has(index)) return;

      // 联合指纹：TOU数据 + Storage数据
      const currentTouStr = JSON.stringify(touGridData[index]);
      const currentStorageStr = JSON.stringify(storageGridData[index]);
      const combinedFingerprint = currentTouStr + "|" + currentStorageStr;

      const sameGroupIndices = [index];

      for (let j = index + 1; j < months.length; j++) {
        if (!processedIndices.has(j)) {
          const targetTouStr = JSON.stringify(touGridData[j]);
          const targetStorageStr = JSON.stringify(storageGridData[j]);
          const targetFingerprint = targetTouStr + "|" + targetStorageStr;

          if (targetFingerprint === combinedFingerprint) {
            sameGroupIndices.push(j);
            processedIndices.add(j);
          }
        }
      }
      
      groups.push({
        id: `group-${index}`,
        label: sameGroupIndices.map(i => months[i]).join(', '),
        touData: touGridData[index],
        storageData: storageGridData[index],
        monthIndices: sameGroupIndices,
        isMerged: sameGroupIndices.length > 1
      });
      processedIndices.add(index);
    });

    return groups;
  }, [touGridData, storageGridData, isCompactMode]);

  // --- 操作处理 ---

  const updateCells = (monthIndices, hourIndex) => {
    if (editMode === 'tou') {
      setTouGridData(prev => {
        const next = [...prev];
        monthIndices.forEach(idx => {
          const row = [...next[idx]];
          row[hourIndex] = selectedTouTier;
          next[idx] = row;
        });
        return next;
      });
    } else {
      setStorageGridData(prev => {
        const next = [...prev];
        monthIndices.forEach(idx => {
          const row = [...next[idx]];
          row[hourIndex] = selectedStorageAction;
          next[idx] = row;
        });
        return next;
      });
    }
  };

  const handleMouseDown = (monthIndices, hourIndex) => {
    setIsDragging(true);
    updateCells(monthIndices, hourIndex);
  };

  const handleMouseEnterCell = (monthIndices, hourIndex) => {
    setHoveredCol(hourIndex);
    if (isDragging) {
      updateCells(monthIndices, hourIndex);
    }
  };

  useEffect(() => {
    const handleGlobalMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-6 font-sans select-none">
      
      {/* --- 顶部工具栏 --- */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-6 space-y-4">
        
        {/* 第一行：标题与模式切换 */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 border-b border-gray-100 pb-4">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
              <Zap className="text-blue-600 fill-current" />
              EMS Configuration
            </h2>
            
            {/* 核心模式切换 */}
            <div className="flex bg-gray-100 p-1 rounded-lg border border-gray-200">
              <button
                onClick={() => setEditMode('tou')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                  editMode === 'tou' ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                1. 电价配置 (TOU)
              </button>
              <button
                onClick={() => setEditMode('storage')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                  editMode === 'storage' ? 'bg-white shadow text-orange-600' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                2. 储能策略 (Storage)
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm text-gray-500 bg-gray-50 px-3 py-1 rounded">
            <LayoutList size={14} />
            <span className="cursor-pointer hover:text-blue-600" onClick={() => setIsCompactMode(!isCompactMode)}>
              {isCompactMode ? '智能折叠模式' : '完整视图模式'}
            </span>
          </div>
        </div>

        {/* 第二行：动态画笔选择器 */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-500 flex items-center gap-1 min-w-fit">
            <MousePointer2 size={14} /> 
            {editMode === 'tou' ? '选择电价类型:' : '选择充放动作:'}
          </span>
          
          <div className="flex flex-wrap gap-2">
            {editMode === 'tou' ? (
              // TOU 画笔
              Object.values(touTiers).map((tier) => (
                <button
                  key={tier.id}
                  onClick={() => setSelectedTouTier(tier.id)}
                  className={`
                    relative px-4 py-1.5 rounded-md text-xs font-semibold transition-all border
                    ${selectedTouTier === tier.id 
                      ? `${tier.color} border-black/10 ring-2 ring-blue-500 ring-offset-2 scale-105` 
                      : 'bg-white border-gray-200 hover:bg-gray-50 text-gray-600'}
                  `}
                >
                  {tier.label}
                </button>
              ))
            ) : (
              // Storage 画笔
              Object.values(storageActions).map((action) => (
                <button
                  key={action.id}
                  onClick={() => setSelectedStorageAction(action.id)}
                  className={`
                    relative px-4 py-1.5 rounded-md text-xs font-semibold transition-all border flex items-center gap-2
                    ${selectedStorageAction === action.id 
                      ? 'bg-white border-blue-500 ring-2 ring-blue-500 ring-offset-2 scale-105 text-gray-800' 
                      : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}
                  `}
                >
                  {action.icon}
                  {action.label}
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* --- 主表格区域 --- */}
      <div 
        className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden"
        onMouseLeave={() => setHoveredCol(null)}
      >
        <div className="overflow-x-auto pb-4">
          <table className="w-full border-collapse min-w-[800px]">
            <thead>
              <tr className="bg-gray-50/80 backdrop-blur">
                <th className="p-3 border-b border-r border-gray-200 text-left w-48 sticky left-0 bg-gray-50 z-20">
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                    {isCompactMode ? 'Month Groups' : 'Month'}
                  </span>
                </th>
                {hours.map((hour) => (
                  <th 
                    key={hour}
                    className={`
                      w-10 border-b border-gray-200 text-xs font-medium transition-all duration-200 relative
                      ${hoveredCol === hour ? 'bg-blue-600 text-white scale-110 z-10 shadow-lg rounded-t-sm' : 'text-gray-500'}
                    `}
                  >
                    <div className="h-10 flex flex-col items-center justify-center">
                      <span>{hour}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {groupedRows.map((group) => (
                <tr key={group.id} className="group hover:bg-gray-50/50 transition-colors">
                  
                  {/* 行标题 */}
                  <td className="border-r border-b border-gray-100 bg-white p-2 sticky left-0 z-10">
                    <div className="flex flex-col items-start justify-center h-full min-h-[3rem]">
                      <span className={`text-sm font-semibold truncate max-w-[11rem] ${group.isMerged ? 'text-blue-700' : 'text-gray-700'}`}>
                        {group.label}
                      </span>
                      {group.isMerged && (
                        <span className="text-[10px] text-blue-500 bg-blue-50 px-1.5 rounded-full mt-0.5 border border-blue-100">
                          {group.monthIndices.length} months
                        </span>
                      )}
                    </div>
                  </td>

                  {/* 数据格子 - 核心融合逻辑 */}
                  {hours.map((hourIndex) => {
                    const touVal = group.touData[hourIndex];
                    const storageVal = group.storageData[hourIndex];
                    
                    const touConfig = touTiers[touVal];
                    const storageConfig = storageActions[storageVal];
                    const isHovered = hoveredCol === hourIndex;

                    // 动态计算样式
                    let cellClass = `relative border-b border-gray-100 cursor-crosshair transition-all duration-200 `;
                    let content = null;

                    if (editMode === 'tou') {
                      // 模式A: TOU编辑 - 背景全亮，显示文本
                      cellClass += touConfig.color; // 使用鲜艳颜色
                      content = (
                        <span className="text-xs text-black/40 font-medium">{touConfig.text}</span>
                      );
                    } else {
                      // 模式B: Storage编辑 - 背景淡化(作为底图)，显示前景图标
                      // 技巧：在 style 中使用 opacity 或 mix-blend-mode，这里直接用 opacity 类
                      // 为了保持底色可见但不仅喧宾夺主，我们可以给一个白色半透明遮罩
                      cellClass += touConfig.color; 
                      content = (
                        <div className="flex items-center justify-center w-full h-full relative z-10">
                          {/* 背景淡化遮罩 */}
                          <div className="absolute inset-0 bg-white/60"></div>
                          
                          {/* 动作图标 */}
                          <div className={`relative z-20 flex flex-col items-center transform transition-transform ${isHovered ? 'scale-110' : ''}`}>
                            {storageConfig.icon}
                            {/* 在高亮或非待机状态下显示文字，增加辨识度 */}
                            {storageConfig.id !== 0 && (
                              <span className={`text-[9px] font-bold leading-none mt-0.5 ${storageConfig.color}`}>
                                {storageConfig.id === 1 ? '充' : '放'}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <td 
                        key={hourIndex}
                        onMouseDown={() => handleMouseDown(group.monthIndices, hourIndex)}
                        onMouseEnter={() => handleMouseEnterCell(group.monthIndices, hourIndex)}
                        className={cellClass}
                      >
                        {/* 纵向高亮 (通用) */}
                        {isHovered && (
                          <div className="absolute inset-0 border-x border-blue-500/30 pointer-events-none z-30 bg-blue-500/5"></div>
                        )}

                        {/* 内容容器 */}
                        <div className="h-12 flex items-center justify-center select-none">
                          {content}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 text-xs text-gray-500 px-2 border-l-4 border-blue-500 pl-4 py-1 bg-blue-50 rounded-r">
        <strong>操作提示：</strong> 
        {editMode === 'tou' 
          ? "当前正在配置「电价时段」。背景色代表电价高低 (绿=谷, 红=峰)。" 
          : "当前正在配置「储能策略」。背景色仍显示电价以供参考，请根据底色选择合适的充电(蓝)或放电(橙)时机。"
        }
      </div>
    </div>
  );
};

export default TOUScheme1;
```