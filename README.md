<div align="center">

# ⚡ 负荷数据分析与储能测算系统

**Load Analysis & Energy Storage Sizing Platform**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个专业的电力负荷数据可视化分析与储能系统定容测算平台

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [项目结构](#-项目结构) • [API 文档](#-api-文档) • [开发指南](#-开发指南)

</div>

---

## 📋 项目简介

本系统是一个集成化的电力负荷分析与储能测算平台，专为电力规划、能源管理和储能项目设计人员开发。通过智能化的数据处理和可视化技术，帮助用户快速完成负荷特性分析和储能系统容量配置。

### 🎯 核心功能

- 📊 **负荷数据可视化** - 多维度展示负荷曲线、峰谷特性、负荷率等关键指标
- 🔋 **储能定容测算** - 基于负荷数据自动计算储能容量、充放电次数、经济效益
- 💰 **电价管理** - 灵活配置分时电价、峰谷平时段，支持多种电价策略
- 📈 **数据清洗分析** - 自动识别异常数据、缺失值处理、数据质量评估
- 📄 **报告生成** - 一键导出专业分析报告，支持 Excel、PDF 格式

---

## 🚀 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|---------|
| Node.js | 16.0+ |
| Python | 3.8+ |
| npm | 8.0+ |
| pip | 21.0+ |

### 安装步骤

#### 1️⃣ 克隆仓库

```bash
git clone https://github.com/slingjie/load-analysis.git
cd load-analysis
```

#### 2️⃣ 安装前端依赖

```bash
npm install
```

#### 3️⃣ 配置环境变量

创建 `.env.local` 文件并配置：

```env
# Gemini API 密钥（可选，用于 AI 功能）
GEMINI_API_KEY=your_api_key_here

# 后端服务地址
VITE_BACKEND_BASE_URL=http://localhost:8000
```

#### 4️⃣ 安装 Python 后端依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt
```

#### 5️⃣ 启动服务

**方式一：手动启动**

```bash
# 终端 1 - 启动前端
npm run dev

# 终端 2 - 启动后端
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

**方式二：一键启动（Windows）**

```bash
# 使用批处理脚本
start-services.bat

# 或使用 PowerShell 脚本
.\start-services.ps1
```

#### 6️⃣ 访问应用

- 🌐 **前端界面**：http://localhost:5173
- 📚 **API 文档**：http://localhost:8000/docs
- 🏥 **健康检查**：http://localhost:8000/health

---

## 📁 项目结构

```
load-analysis/
├── 📂 backend/                 # Python 后端服务
│   ├── app.py                 # FastAPI 主应用
│   ├── requirements.txt       # Python 依赖
│   └── ...                    # 业务逻辑模块
├── 📂 components/             # React 组件
│   ├── LoadAnalysis.tsx      # 负荷分析组件
│   ├── StorageCalculator.tsx # 储能测算组件
│   └── ...                    # 其他组件
├── 📂 hooks/                  # React Hooks
├── 📂 test/                   # 测试文件
├── 📂 负荷测试数据/           # 测试用负荷数据
├── 📂 储能测算界面开发/       # 储能模块开发文档
├── 📄 App.tsx                 # 应用主入口
├── 📄 api.ts                  # API 接口封装
├── 📄 loadApi.ts              # 负荷数据 API
├── 📄 storageApi.ts           # 储能测算 API
├── 📄 types.ts                # TypeScript 类型定义
├── 📄 utils.ts                # 工具函数
├── 📄 constants.ts            # 常量配置
├── 📄 package.json            # 前端依赖配置
├── 📄 vite.config.ts          # Vite 构建配置
├── 📄 tsconfig.json           # TypeScript 配置
└── 📄 README.md               # 项目文档
```

---

## 🔧 技术栈

### 前端技术

| 技术 | 用途 |
|------|------|
| **React 18** | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具 |
| **ECharts** | 数据可视化 |
| **Ant Design** | UI 组件库 |

### 后端技术

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架 |
| **Pandas** | 数据处理 |
| **NumPy** | 数值计算 |
| **Uvicorn** | ASGI 服务器 |
| **Pydantic** | 数据验证 |

---

## 📖 功能详解

### 1. 📊 负荷数据分析

- **数据上传**：支持 Excel (.xlsx, .xls) 格式的负荷数据导入
- **数据清洗**：
  - 自动识别并处理缺失值
  - 异常数据检测与标记
  - 数据质量评分
- **可视化展示**：
  - 日负荷曲线图
  - 月度负荷热力图
  - 峰谷分布统计
  - 负荷率分析
- **指标计算**：
  - 最大负荷、最小负荷
  - 平均负荷、负荷率
  - 峰谷差、峰谷比
  - 年用电量

### 2. 🔋 储能定容测算

- **容量配置**：
  - 基于负荷特性的容量推荐
  - 充放电功率配置
  - 充放电时段设置
- **测算分析**：
  - 充放电次数统计
  - 能量转换效率计算
  - 削峰填谷效果评估
  - 投资回收期分析
- **策略优化**：
  - 多种充放电策略对比
  - 经济效益最优化
  - 季节性策略调整

### 3. 💰 电价管理

- **电价配置**：
  - 分时电价设置（峰、平、谷）
  - 时段灵活划分
  - 阶梯电价支持
- **成本分析**：
  - 用电成本计算
  - 储能收益分析
  - 节省费用统计

### 4. 📄 报告导出

- **数据报告**：
  - 负荷特性分析报告
  - 储能测算结果报告
  - 经济效益评估报告
- **图表导出**：
  - 高清图表导出
  - Excel 数据表格
  - PDF 综合报告

---

## 🛠️ API 文档

### 主要接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/load/analyze` | POST | 负荷数据分析 |
| `/api/storage/calculate` | POST | 储能容量测算 |
| `/api/price/configure` | POST | 电价配置 |
| `/health` | GET | 服务健康检查 |

### 完整 API 文档

启动后端服务后访问：**http://localhost:8000/docs**

支持 Swagger UI 交互式文档和 ReDoc 文档格式。

---

## 📚 开发文档

项目包含详细的开发文档和需求说明：

- 📖 [完整的负荷可视化需求 1.0](0.0完整的负荷可视化需求1.0.md)
- 🧹 [数据清洗需求](0.1数据清洗需求.md)
- 💡 [电价编辑和展示功能](0.2电价编辑和展示功能.md)
- 🧭 [界面目录导航方式选择](0.3界面目录导航方式选择.md)
- 🔋 [储能充放次数测算需求](1.1新需求储能充放次数测算.md)
- 📝 [储能次数计算待办](储能次数计算待办.md)
- 💬 [沟通记录](沟通记录.md)

---

## 🐛 故障排查

### 常见问题

**Q: 前端无法连接后端？**
```bash
# 检查后端是否启动
curl http://localhost:8000/health

# 确认 .env.local 中的 VITE_BACKEND_BASE_URL 配置正确
```

**Q: Python 依赖安装失败？**
```bash
# 升级 pip
python -m pip install --upgrade pip

# 清理缓存后重新安装
pip cache purge
pip install -r backend/requirements.txt
```

**Q: npm install 报错？**
```bash
# 清理 npm 缓存
npm cache clean --force

# 删除 node_modules 后重新安装
rm -rf node_modules package-lock.json
npm install
```

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 开源协议

本项目采用 MIT 协议开源 - 详见 [LICENSE](LICENSE) 文件

---

## 👥 联系方式

- 项目作者：[@slingjie](https://github.com/slingjie)
- 项目地址：https://github.com/slingjie/load-analysis
- Issue 反馈：https://github.com/slingjie/load-analysis/issues

---

## 🙏 致谢

感谢以下开源项目：

- [React](https://reactjs.org/) - UI 框架
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [ECharts](https://echarts.apache.org/) - 可视化库
- [Pandas](https://pandas.pydata.org/) - 数据处理
- [Vite](https://vitejs.dev/) - 构建工具

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给一个 Star！**

Made with ❤️ by [slingjie](https://github.com/slingjie)

</div>