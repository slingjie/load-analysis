# 数据为0问题调试指南

## 问题现象
生成的报告中所有数据显示为 0 或 "当前数据暂不足以给出可靠结论"。

## 已添加的调试工具

### 1. 前端控制台日志
在 `ProjectSummaryPage.tsx` 中已添加详细日志：
- 🔍 `[buildLoadProfile]` - 负荷数据构建过程
- 🔍 `[buildStorageConfig]` - 储能配置构建过程
- 🔍 `[buildStorageResults]` - 储能结果构建过程
- 📤 `[handleGenerate]` - 发送到后端的完整请求数据
- 📥 `[handleGenerate]` - 从后端收到的响应

### 2. 后端日志
在 `backend/services/deepseek_summary.py` 中已添加详细日志：
- 🔍 `[extract_summary_data]` - 接收到的所有参数
- ✅ `[extract_summary_data]` - 提取后的数据结构

## 调试步骤

### 步骤 1: 启动后端服务（带日志）

**选项 A - 使用现有脚本**
```powershell
.\start_backend_with_env.ps1
```

**选项 B - 手动启动**
```powershell
$env:DEEPSEEK_API_KEY='sk-3008dc675fad4414abee5ea2b75ed54f'
cd D:\Desktop\ai\1028负荷展示和tou配置
uvicorn backend.app:app --reload
```

确认看到：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 步骤 2: 启动前端服务

在另一个终端窗口：
```powershell
cd D:\Desktop\ai\1028负荷展示和tou配置
npm run dev
```

确认看到：
```
VITE ready in XXX ms
➜  Local:   http://localhost:5173/
```

### 步骤 3: 运行API测试（可选）

在第三个终端窗口，测试后端是否正常工作：
```powershell
python test_data_flow.py
```

这会运行两个测试：
1. **测试1**: 发送空数据（模拟当前问题）
2. **测试2**: 发送完整数据（验证系统功能）

如果测试2成功生成包含实际数值的报告，说明后端功能正常，问题在前端数据传递。

### 步骤 4: 在浏览器中调试

1. 打开浏览器访问 http://localhost:5173/
2. 按 **F12** 打开开发者工具
3. 切换到 **Console** 标签

#### 场景 A: 复现问题（不上传数据直接生成报告）

1. 点击"Project Summary"标签
2. 填写项目名称和日期
3. 点击"生成项目评估报告"

**预期在控制台看到：**
```
🔍 [buildLoadProfile] 开始构建负荷数据
⚠️ [buildLoadProfile] loadMeta 为空，返回 undefined
🔍 [buildStorageConfig] 开始构建储能配置
⚠️ [buildStorageConfig] storageCyclesPayload 为空，返回 undefined
🔍 [buildStorageResults] 开始构建储能结果
⚠️ [buildStorageResults] storageCyclesResult 为空，返回 undefined
📤 [handleGenerate] 准备发送请求到后端
📤 [handleGenerate] 完整请求数据: { ... }
```

**检查项：**
- `loadMeta` 是否为 `null`？
- `storageCyclesPayload` 是否为 `null`？
- `storageCyclesResult` 是否为 `null`？
- 请求数据中的 `load_profile`、`storage_config`、`storage_results` 是否为 `undefined`？

**切换到 Network 标签：**
1. 找到 `/api/deepseek/project-summary` 请求
2. 点击查看 **Payload** 或 **Request**
3. 确认 JSON 数据结构

#### 场景 B: 正常流程（上传数据后生成报告）

1. 点击"Load Analysis"标签
2. 点击"上传负荷文件"，选择测试数据（如 `负荷测试数据/中恒新材料负荷数据 展示用.csv`）
3. 等待上传和分析完成
4. 点击"Storage Cycles"标签
5. 配置储能参数（如容量4000 kWh，功率2000 kW）
6. 点击"Calculate"按钮
7. 等待计算完成
8. 点击"Project Summary"标签
9. 填写项目信息
10. 点击"生成项目评估报告"

**预期在控制台看到：**
```
🔍 [buildLoadProfile] 开始构建负荷数据
🔍 [buildLoadProfile] loadMeta: { avg_load_kw: 1234.56, max_load_kw: 2345.67, ... }
🔍 [buildLoadProfile] 解析后的值: { avgLoad: 1234.56, maxLoad: 2345.67, ... }
✅ [buildLoadProfile] 构建完成: { avgLoad: '约 1234.56 kW', ... }

🔍 [buildStorageConfig] 开始构建储能配置
🔍 [buildStorageConfig] storageCyclesPayload: { battery_capacity_kwh: 4000, ... }
✅ [buildStorageConfig] 构建完成: { capacityMWh: '4.00', ... }

🔍 [buildStorageResults] 开始构建储能结果
🔍 [buildStorageResults] storageCyclesResult: { year: { equivalent_cycles: 280, ... } }
✅ [buildStorageResults] 构建完成: { effectiveAnnualCycles: '约 280.0 次/年', ... }

📤 [handleGenerate] 完整请求数据: {
  project_name: "xxx",
  load_profile: { avgLoad: '约 1234.56 kW', ... },
  storage_config: { capacityMWh: '4.00', ... },
  storage_results: { effectiveAnnualCycles: '约 280.0 次/年', ... }
}
```

### 步骤 5: 检查后端日志

在运行 `uvicorn` 的终端窗口中，查找：

```
INFO:     127.0.0.1:XXXXX - "POST /api/deepseek/project-summary HTTP/1.1" 200 OK
INFO:deepseek_summary:🔍 [extract_summary_data] 开始提取数据
INFO:deepseek_summary:🔍 [extract_summary_data] project_info: {...}
INFO:deepseek_summary:🔍 [extract_summary_data] load_profile: {...}
INFO:deepseek_summary:🔍 [extract_summary_data] storage_config: {...}
INFO:deepseek_summary:🔍 [extract_summary_data] storage_results: {...}
INFO:deepseek_summary:✅ [extract_summary_data] 提取完成
INFO:deepseek_summary:✅ [extract_summary_data] loadProfileSummary keys: ['avgLoad', 'peakLoad', ...]
```

**检查项：**
- `load_profile` 是 `None` 还是有实际数据？
- `storage_config` 是 `None` 还是有实际数据？
- `storage_results` 是 `None` 还是有实际数据？
- 提取后的 keys 列表是否为空？

## 常见问题诊断

### 问题 1: 控制台显示 loadMeta 为 null

**原因**: 用户未上传负荷数据

**解决**: 
1. 切换到 Load Analysis 页面
2. 点击"上传负荷文件"
3. 选择 CSV 或 Excel 文件
4. 等待处理完成

### 问题 2: 控制台显示 storageCyclesPayload 或 storageCyclesResult 为 null

**原因**: 用户未运行储能测算

**解决**:
1. 切换到 Storage Cycles 页面
2. 填写储能参数
3. 点击 Calculate 按钮
4. 等待计算完成

### 问题 3: 前端显示有数据，但后端收到的是 None

**原因**: 前端到后端的数据传递问题

**调试**:
1. 在 Network 标签查看实际发送的 JSON
2. 检查 `summaryApi.ts` 中的 API 请求代码
3. 确认环境变量 `VITE_BACKEND_BASE_URL` 正确配置

### 问题 4: 后端收到数据，但 DeepSeek 生成的报告仍全是0

**原因**: DeepSeek Prompt 未正确使用提供的字段

**调试**:
1. 查看后端日志中的 `extracted` 结构
2. 检查 `build_deepseek_prompt()` 函数中的字段映射说明
3. 运行 `test_data_flow.py` 的测试2验证

## 预期结果

### 正常情况（已上传数据+已测算）

**前端控制台：**
- ✅ 所有 build 函数都返回包含实际数值的对象
- ✅ 请求数据包含完整的 load_profile、storage_config、storage_results
- ✅ 响应包含带实际数值的 Markdown 报告

**后端日志：**
- ✅ extract_summary_data 收到非空的各项参数
- ✅ loadProfileSummary、storageConfig、storageResults keys 都不为空
- ✅ DeepSeek API 调用成功
- ✅ 返回报告包含实际数值

**生成的报告：**
- ✅ 首年收益显示具体金额（如"约 45.50 万元"）
- ✅ 循环次数显示具体值（如"约 280.0 次/年"）
- ✅ 负荷数据显示具体值（如"约 1234.56 kW"）

### 异常情况（未上传数据/未测算）

**前端控制台：**
- ⚠️ build 函数返回 undefined
- ⚠️ 弹出警告对话框提示数据缺失
- ⚠️ 请求数据中部分字段为 undefined

**后端日志：**
- ⚠️ extract_summary_data 收到 None 参数
- ⚠️ 相应的 keys 列表为空

**生成的报告：**
- ⚠️ 数值显示为"约 0.00"或"当前数据暂不足以给出可靠结论"

## 下一步

根据调试结果：

1. **如果是场景A（数据缺失）** → 这是正常的，用户需要先上传数据和运行测算
2. **如果是场景B（数据传递问题）** → 提供前端控制台和 Network 标签的截图
3. **如果是 DeepSeek 问题** → 提供后端日志和生成的报告内容

## 快速验证脚本

运行以下脚本可快速验证系统是否正常：

```powershell
# 1. 确认后端运行
curl http://localhost:8000/docs

# 2. 测试API（应该返回200）
python test_data_flow.py

# 3. 如果测试2成功但测试1失败，说明系统正常，用户需要上传数据
# 4. 如果两个测试都失败，检查后端日志和 DeepSeek API Key
```

---

**创建时间**: 2025-11-24
**适用版本**: v1.0
