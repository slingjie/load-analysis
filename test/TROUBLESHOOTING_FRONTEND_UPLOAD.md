# 🔧 前端上传报错诊断和修复指南

**错误信息**: `上传文件失败：Failed to fetch`  
**原因**: 通常是后端未启动或网络连接问题  
**诊断时间**: 2025-10-30

---

## 🔍 问题诊断步骤

### 第一步: 检查后端是否运行

**在 PowerShell 中执行:**
```powershell
# 检查是否有 Python 进程监听 8000 端口
netstat -ano | findstr :8000

# 或者尝试连接后端
curl -v http://localhost:8000/health
```

**预期结果:**
```
{
  "status": "ok"
}
```

**如果显示连接拒绝或无响应**: 需要启动后端

---

### 第二步: 启动后端服务

**完整的启动步骤:**

```powershell
# 1. 进入项目目录
cd "d:\Desktop\ai\1028负荷展示和tou配置"

# 2. 激活虚拟环境（如果有）
.\.venv\Scripts\Activate.ps1

# 3. 启动后端（选择其中一种）

# 方式 A: 使用虚拟环境的 Python
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# 方式 B: 使用系统 Python（需要配置环境变量）
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# 方式 C: 不使用 reload 模式（更稳定）
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

**预期输出:**
```
[2025-10-30 14:30:45,123] DEBUG load-analysis: 启动 Uvicorn 服务器
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**⚠️ 常见错误:**
- `ModuleNotFoundError: No module named 'fastapi'` → 缺少依赖，需要 `pip install -r requirements.txt`
- `Address already in use` → 端口被占用，需要 `netstat -ano | findstr :8000` 找到进程并杀死
- `ImportError: No module named 'backend'` → 工作目录错误，需要在项目根目录

---

### 第三步: 检查 Vite 配置和环境变量

**验证前端配置:**

```powershell
# 查看 .env.local 中的后端 URL
cat .env.local

# 预期输出:
# VITE_BACKEND_BASE_URL=http://localhost:8000
```

**如果 .env.local 不存在，创建它:**
```powershell
@"
GEMINI_API_KEY=PLACEHOLDER_API_KEY
VITE_BACKEND_BASE_URL=http://localhost:8000
"@ | Out-File -Encoding UTF8 .env.local
```

---

### 第四步: 启动前端开发服务器

**在新的 PowerShell 窗口中:**

```powershell
# 1. 进入项目目录
cd "d:\Desktop\ai\1028负荷展示和tou配置"

# 2. 启动前端
npm run dev

# 预期输出:
# VITE v5.x.x  build xxxxxx
# ➜  Local:   http://localhost:5173/
# ➜  press h to show help
```

---

### 第五步: 测试上传

**操作步骤:**

1. 打开浏览器，访问 http://localhost:5173
2. 打开浏览器开发者工具 (F12)
3. 选择 "Console" 标签，查看日志
4. 选择 "宁国津龙 负荷整理.csv" 文件并上传
5. 查看 Console 输出的错误信息

**查看详细的网络请求:**

1. 打开 Network 标签
2. 在 Filter 中输入 `api`
3. 上传文件
4. 查看 `load/analyze` 请求的详情
   - Status: 应该显示 200 或对应的错误状态
   - Response: 应该显示返回的数据或错误信息

---

## 🛠️ 常见问题和解决方案

### 问题 1: 后端无法启动

**错误**: `ImportError` 或 `ModuleNotFoundError`

**解决步骤:**

```powershell
# 1. 检查虚拟环境
.\.venv\Scripts\python.exe -c "import fastapi; print('fastapi OK')"

# 2. 如果失败，重新安装依赖
pip install -r backend/requirements.txt

# 3. 检查关键依赖
.\.venv\Scripts\python.exe -c "import fastapi, pandas, uvicorn; print('All OK')"
```

### 问题 2: 前端显示 "Failed to fetch"

**原因可能:**
1. ❌ 后端未启动
2. ❌ 后端崩溃或出错
3. ❌ 网络请求被阻止

**检查步骤:**

```powershell
# 1. 测试后端是否响应
curl http://localhost:8000/health

# 2. 如果失败，查看后端日志（在后端窗口）
# 应该显示错误信息

# 3. 尝试直接上传文件测试
$file = "宁国津龙 负荷整理.csv"
curl -X POST http://localhost:8000/api/load/analyze -F "file=@$file"
```

### 问题 3: CORS 跨域错误

**表现**: 浏览器控制台显示 CORS 错误

**解决**: 后端已配置 CORS，应该能跨域

```python
# backend/app.py 中已有
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**如果仍然报错，尝试:**

```bash
# 重启后端
# 清空浏览器缓存
# 尝试 incognito 窗口
```

### 问题 4: 后端处理文件时出错

**表现**: 收到 400 或 422 错误

**查看具体错误:**

1. 打开浏览器 Network 标签
2. 找到 `load/analyze` 请求
3. 查看 Response 中的 `detail` 字段
4. 常见错误:
   - "缺少有效数据记录" → CSV 文件为空或格式错误
   - "文件解析失败" → 编码或列名问题
   - "负荷列全部为空" → 缺少 load 列

---

## 🚀 完整启动流程（快速版）

**如果以上都不奏效，按这个流程重新开始:**

```powershell
# 终端 1: 后端
cd "d:\Desktop\ai\1028负荷展示和tou配置"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

# 等待显示: Application startup complete

# 终端 2: 前端（在新窗口打开）
cd "d:\Desktop\ai\1028负荷展示和tou配置"
npm run dev

# 等待显示: Local: http://localhost:5173/

# 浏览器
打开 http://localhost:5173

# 测试
上传文件并检查是否成功
```

---

## 🧪 测试后端 API

**如果前端仍然报错，直接测试 API:**

```powershell
# 使用 curl 测试
curl -X POST http://localhost:8000/api/load/analyze `
  -F "file=@宁国津龙 负荷整理.csv"

# 预期返回类似:
# {
#   "report": {...},
#   "cleaned_points": [...],
#   "meta": {...}
# }
```

**如果这个命令成功，说明后端没问题，问题在前端配置或网络连接**

---

## 📝 调试建议

### 启用详细日志

**在浏览器 Console 中运行:**

```javascript
// 启用所有日志
localStorage.setItem('debug', '*');
location.reload();

// 查看网络请求的详细信息
// 打开 Network 标签，重新上传文件
```

### 检查网络连接

```powershell
# 测试后端是否可达
Test-NetConnection -ComputerName localhost -Port 8000

# 查看所有监听端口
netstat -ano | findstr LISTENING
```

### 查看后端日志

后端启动窗口会显示详细日志，包括:
- 文件收到情况
- 文件大小
- 处理过程
- 任何错误

---

## ✅ 验收标准

**问题解决标准:**

- [x] 后端在 http://localhost:8000 可访问
- [x] 前端在 http://localhost:5173 可访问
- [x] `/api/load/analyze` 端点返回 200 状态
- [x] 前端成功上传文件并显示报告
- [x] 浏览器 Console 无红色错误

---

## 📞 还有其他问题？

1. **查看后端错误日志** - 在后端启动窗口中
2. **查看浏览器 Network 标签** - 找到失败的请求
3. **检查 Response 中的错误消息** - detail 字段包含具体错误
4. **运行 `test_completeness_v2.py`** - 验证后端是否正常工作

---

**Last Updated**: 2025-10-30  
**Status**: 准备好进行故障排除
