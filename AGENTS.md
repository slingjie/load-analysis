<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Repository Guidelines

## 项目结构与模块组织
根目录采用 Vite + React 框架，核心源文件位于 `App.tsx`、`index.tsx` 与 `components/`。`components/` 按功能拆分可视化组件，`utils.ts`、`constants.ts` 和 `types.ts` 提供通用工具、常量与类型；如需新增模块，请按照业务域建立子目录。静态入口 `index.html` 与配置 `vite.config.ts` 放置在根目录，便于 AI Studio 与本地环境共享流程。

## 构建、测试与开发命令
- `npm install`：安装或更新依赖，首次克隆后执行。
- `npm run dev`：启动 Vite 本地开发服务器，默认端口 5173，支持热更新。
- `npm run build`：生成生产构建并执行 TypeScript 校验，提交前确认无错误。
- `npm run preview`：基于打包结果启动本地预览，用于模拟生产部署。

## 编码风格与命名约定
项目使用 TypeScript + React 19，请保持函数式组件与 Hooks 优先。统一采用 2 空格缩进与分号结尾，组件文件命名使用 PascalCase（如 `LoadAnalysisPage.tsx`），工具函数使用 camelCase。公共常量集中在 `constants.ts`，新增类型定义置于 `types.ts`，并以中文注释解释复杂逻辑或数据结构。

## 测试规范
当前尚未集成自动化测试，请在提交前完成关键场景的手工验证并记录结果。若引入 Vitest，可在 `components/__tests__/` 中创建 `*.test.tsx`，并将运行命令添加为 `npm run test`。新增测试需覆盖核心数据整理流程与用户交互分支，确保导入、导出与图表渲染稳定。

## 提交与合并请求规范
建议采用 Conventional Commits，例如 `feat: 新增分时电价复制功能`，便于自动生成变更日志。PR 描述需包含需求背景、主要改动、验证方式以及受影响的 UI 截图或数据样例；涉及环境变量更新时请同步维护 `README.md` 与 `.env.local` 模板。默认要求至少一名同伴复审，合并前请确认构建通过。

## 安全与配置提示
敏感密钥存放在 `.env.local`，勿提交到版本库，并通过 `import.meta.env` 访问。部署前确认 `GEMINI_API_KEY` 已配置，检查 Chart.js 数据源是否脱敏。发布 XLSX 导出文件前复核内容，避免泄露客户或运营策略信息。
