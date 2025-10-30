# ⚡ 快速修复 - "Failed to fetch" 错误

**错误信息**: `上传文件失败：Failed to fetch`  
**解决时间**: < 5 分钟  
**最后更新**: 2025-10-30

---

## 🎯 3 步快速修复

### ✅ 步骤 1: 启动后端服务 (2 分钟)

**最简单的方式 - 使用启动脚本:**

```powershell
# 打开 PowerShell，进入项目目录
cd "d:\Desktop\ai\1028负荷展示和tou配置"

# 方式 A: 使用 PowerShell 脚本（推荐）
.\start-services.ps1

# 方式 B: 使用 Batch 脚本
.\start-services.bat
```

**或者手动启动:**

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 启动后端
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

**预期显示:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

✅ **后端已启动！** 不要关闭这个窗口

---

### ✅ 步骤 2: 启动前端服务 (1 分钟)

**打开新的 PowerShell 窗口:**

```powershell
# 进入项目目录
cd "d:\Desktop\ai\1028负荷展示和tou配置"

# 启动前端
npm run dev
```

**预期显示:**
```
➜  Local:   http://localhost:5173/
```

✅ **前端已启动！** 不要关闭这个窗口

---

### ✅ 步骤 3: 打开浏览器并测试 (2 分钟)

1. 打开浏览器，访问: **http://localhost:5173**
2. 选择 CSV 文件: `宁国津龙 负荷整理.csv`
3. 点击上传

**预期结果:**
- ✅ 显示"4. 数据完整性分析报告"
- ✅ 显示按月分类表格
- ✅ 没有任何错误信息

---

## 🆘 还是不行？快速检查清单

### ❓ 检查 1: 后端是否正在运行？

```powershell
# 测试后端健康检查
curl http://localhost:8000/health

# 预期输出:
# {"status":"ok"}
```

**如果显示 "无法连接":**
- ❌ 后端未启动，回到步骤 1
- ❌ 虚拟环境激活失败，查看错误信息

### ❓ 检查 2: 前端是否连接到正确的后端地址？

```powershell
# 查看 .env.local 文件
cat .env.local
```

**预期输出:**
```
VITE_BACKEND_BASE_URL=http://localhost:8000
```

**如果不对，编辑文件:**
```powershell
# 用记事本编辑
notepad .env.local
```

确保内容是:
```
GEMINI_API_KEY=PLACEHOLDER_API_KEY
VITE_BACKEND_BASE_URL=http://localhost:8000
```

**编辑后需要重启前端** (Ctrl+C 停止，然后 `npm run dev`)

### ❓ 检查 3: 浏览器有没有缓存问题？

- 按 `F12` 打开开发者工具
- 右键刷新按钮 → "清空缓存并硬性重新加载"
- 重新上传文件

### ❓ 检查 4: 防火墙/代理问题？

```powershell
# 检查端口是否被占用
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# 预期输出应该显示 LISTENING 状态
```

**如果端口已被占用:**
```powershell
# 查找占用 8000 端口的进程 ID
$pid = (netstat -ano | findstr :8000 | % {$_.split()[-1]})

# 杀死该进程
taskkill /PID $pid /F
```

---

## 🔧 详细故障排除

### 情况 A: 后端启动失败

**错误**: `ImportError: No module named 'fastapi'`

**解决:**
```powershell
# 进入虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r backend/requirements.txt

# 再次启动
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

---

### 情况 B: "Port already in use"

**错误**: `Address already in use`

**解决:**
```powershell
# 找到占用端口的进程
$process = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($process) {
    taskkill /PID $process.OwningProcess -F
}

# 启动后端
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

---

### 情况 C: 前端显示错误但后端正常

**症状**: Console 显示 "Failed to fetch"，但 `curl http://localhost:8000/health` 成功

**解决:**
```powershell
# 1. 停止前端 (Ctrl+C)

# 2. 清理缓存
npm cache clean --force
rm -r node_modules
npm install

# 3. 重启前端
npm run dev
```

---

## 📋 最小化测试清单

按顺序测试每一项，找出问题所在:

```powershell
# 1. 后端健康检查
curl http://localhost:8000/health
# 预期: {"status":"ok"}

# 2. 前端加载
curl http://localhost:5173
# 预期: HTML 内容

# 3. 直接测试 API
curl -X POST http://localhost:8000/api/load/analyze `
  -F "file=@宁国津龙 负荷整理.csv"
# 预期: JSON 响应或错误信息

# 4. 在浏览器打开前端
# 预期: 页面正常加载

# 5. 上传文件
# 预期: 显示报告或具体的错误信息
```

---

## 💡 常见原因和解决

| 问题 | 原因 | 解决 |
|------|------|------|
| Failed to fetch | 后端未启动 | 启动后端 |
| Address already in use | 端口被占用 | 杀死占用进程或换端口 |
| CORS 错误 | 浏览器安全策略 | 已在后端配置，尝试清缓存 |
| 无法读取文件 | CSV 格式错误 | 使用提供的测试文件 |
| 后台处理失败 | 后端代码错误 | 查看后端日志中的错误信息 |

---

## ✅ 验收标准

如果以下都满足，问题已解决:

- [x] 后端在 http://localhost:8000 正常响应
- [x] 前端在 http://localhost:5173 正常加载
- [x] 浏览器 Console 无红色错误
- [x] 可以成功上传 CSV 文件
- [x] 显示"数据完整性分析报告"

---

## 🎯 一句话快速启动

```powershell
# 终端 1
.\.venv\Scripts\Activate.ps1; python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

# 终端 2
npm run dev

# 浏览器
打开 http://localhost:5173 上传文件
```

---

**还有问题?** 查看完整的故障排除指南: `test/TROUBLESHOOTING_FRONTEND_UPLOAD.md`

**状态**: ✅ 已就绪修复
