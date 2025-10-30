<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/15ua8yH5DNKvVVeFC8dKl3mJ_9GYEJYlJ

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. (Optional) 配置前端访问后端的地址：在 `.env.local` 中新增 `VITE_BACKEND_BASE_URL=http://localhost:8000`
4. Run the app:
   `npm run dev`

## 启动 Python 后端

1. 准备虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r backend/requirements.txt
   ```
2. 启动服务：
   ```bash
   uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
   ```
3. 服务默认暴露 `/api/load/analyze` 接口用于 Excel 数据清洗分析，同时提供 `/health` 健康检查。
