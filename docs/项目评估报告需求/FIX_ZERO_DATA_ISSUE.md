# 数据为0问题 - 快速解决指南

## 🚨 问题现象

生成的项目评估报告中所有数据显示为 **0** 或 **"当前数据暂不足以给出可靠结论"**。

## ⚡ 快速诊断

### 一键诊断（Windows）

双击运行：
```
run_diagnostic.bat
```

或在PowerShell中：
```powershell
python quick_diagnostic.py
```

### 诊断结果解读

#### ✅ 如果显示"系统完全正常"

**原因**: 您尚未上传负荷数据或运行储能测算

**解决**: 按照正确流程操作

#### ❌ 如果显示错误

查看 [详细调试指南](DEBUG_GUIDE.md) 或 [解决方案文档](DIAGNOSTIC_SOLUTION.md)

## 📋 正确使用流程

### 第1步：上传负荷数据

1. 打开浏览器访问 http://localhost:5173/
2. 点击 **"Load Analysis"** 标签
3. 点击 **"上传负荷文件"** 按钮
4. 选择 CSV 或 Excel 文件
5. 等待数据处理完成（看到绿色勾号 ✓）

### 第2步：运行储能测算

1. 点击 **"Storage Cycles"** 标签
2. 配置储能参数：
   - 储能容量（kWh）
   - 储能功率（kW）
   - 充放电效率
   - SOC范围
3. 点击 **"Calculate"** 按钮
4. 等待计算完成（看到结果数据）

### 第3步：生成项目报告

1. 点击 **"Project Summary"** 标签
2. 确认数据状态检查区域显示：
   - ✓ 负荷数据已上传
   - ✓ 质量报告已生成
   - ✓ 储能测算已完成
3. 填写项目信息：
   - 项目名称（必填）
   - 项目地点（可选）
   - 评估周期（自动填充）
4. 点击 **"生成项目评估报告"**
5. 等待10-30秒

**预期结果**: 报告中包含实际数值，如"约 1234.56 kW"、"约 45.50 万元"等

## 🔍 调试工具

### 工具1: 快速诊断脚本

**文件**: `quick_diagnostic.py`

**功能**:
- 自动检查后端服务状态
- 测试API功能
- 验证数据处理流程
- 生成诊断报告

**使用**:
```powershell
python quick_diagnostic.py
```

### 工具2: 数据流测试

**文件**: `test_data_flow.py`

**功能**:
- 详细测试空数据和完整数据两种场景
- 显示报告中的具体数值
- 保存测试报告

**使用**:
```powershell
python test_data_flow.py
```

### 工具3: 浏览器开发者工具

**使用方法**:
1. 按 **F12** 打开开发者工具
2. 切换到 **Console** 标签
3. 查找以下日志：
   - 🔍 `[buildLoadProfile]` - 负荷数据构建
   - 🔍 `[buildStorageConfig]` - 储能配置构建
   - 🔍 `[buildStorageResults]` - 储能结果构建
   - 📤 `[handleGenerate]` - 发送到后端的数据
4. 切换到 **Network** 标签
5. 找到 `/api/deepseek/project-summary` 请求
6. 查看 **Payload** 内容

## 📚 详细文档

- [DEBUG_GUIDE.md](DEBUG_GUIDE.md) - 完整调试步骤和日志解读
- [DIAGNOSTIC_SOLUTION.md](DIAGNOSTIC_SOLUTION.md) - 问题分析和解决方案
- [docs/项目评估报告数据为空诊断指南.md](docs/项目评估报告数据为空诊断指南.md) - 用户友好版指南

## 🛠️ 服务启动

### 启动后端

**方式1 - 使用脚本**:
```powershell
.\start_backend_with_env.ps1
```

**方式2 - 手动启动**:
```powershell
$env:DEEPSEEK_API_KEY='sk-3008dc675fad4414abee5ea2b75ed54f'
uvicorn backend.app:app --reload
```

**验证**: 访问 http://localhost:8000/docs 应显示API文档

### 启动前端

```powershell
npm run dev
```

**验证**: 访问 http://localhost:5173/ 应显示应用界面

## ❓ 常见问题

### Q1: 诊断显示"后端服务未运行"

**解决**:
```powershell
.\start_backend_with_env.ps1
```

### Q2: 诊断显示"API功能异常"

**可能原因**:
- DeepSeek API Key 未配置或无效
- 网络连接问题

**解决**:
1. 检查 `.env.local` 文件中的 `DEEPSEEK_API_KEY`
2. 确认 API Key 有效
3. 检查网络连接

### Q3: 上传数据后仍然显示0

**诊断步骤**:
1. 打开浏览器开发者工具（F12）
2. 查看 Console 日志
3. 确认是否看到 ✅ 成功的日志
4. 切换到 Network 标签
5. 检查请求数据是否包含实际值

**如果日志显示数据为空**:
- 刷新页面重新上传
- 确认文件格式正确（包含 timestamp 和 load 列）

### Q4: 测算完成后仍然显示0

**检查**:
1. Storage Cycles 页面是否显示计算结果
2. 是否有错误提示
3. 后端日志是否有异常

**解决**: 重新配置参数并点击 Calculate

## 📊 验证清单

运行诊断前检查：
- [ ] 后端服务正在运行（http://localhost:8000）
- [ ] DeepSeek API Key 已配置
- [ ] Python 环境正常

使用应用前检查：
- [ ] 前端服务正在运行（http://localhost:5173）
- [ ] 已上传负荷数据
- [ ] 已运行储能测算
- [ ] 数据状态检查区域全部显示 ✓

## 🆘 获取帮助

如果问题仍未解决，请提供：

1. **诊断脚本输出**:
   ```powershell
   python quick_diagnostic.py > diagnostic_output.txt
   ```

2. **浏览器Console日志**: F12 → Console → 右键 → Save as...

3. **后端日志**: 运行 uvicorn 的终端窗口的输出

4. **Network请求详情**: F12 → Network → 找到请求 → 右键 → Copy → Copy as cURL

5. **生成的报告**: 复制报告内容或提供 Markdown 文件

## 🎯 预期效果

### 诊断成功

```
步骤 1/4: 检查后端服务
✅ 后端服务正在运行

步骤 2/4: 测试空数据场景  
⚠️  报告生成成功，但包含 XX 个零值
   这是正常的，因为没有提供数据

步骤 3/4: 测试完整数据场景
✅ 系统工作正常！报告中包含 6/6 个测试数值

步骤 4/4: 诊断总结
✅ 系统完全正常！
```

### 正常报告示例

```markdown
### 1.2 核心评估结论
- **首年总收益：** 约 45.50 万元
- **等效年循环次数：** 约 280.0 次/年  
- **日均循环次数：** 日均约 0.77 次
- **储能利用小时数：** 年度约 560 小时

### 2.1 负荷基础指标
- **平均负荷：** 约 1234.56 kW
- **峰值负荷：** 约 2345.67 kW
- **谷值负荷：** 约 456.78 kW
```

---

**最后更新**: 2025-11-24  
**适用版本**: v1.1
