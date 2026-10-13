# 项目协作入口

- **定位**：本机运行的临床试验监查辅助 Demo；AI 只提示疑点，由 CRA 复核。
- **运行**：只用本项目 `.venv/bin/python` 和 `.venv/bin/streamlit`。先以 `.venv/bin/python -m pip check` 检查依赖；首次建库才运行 `.venv/bin/python ingest.py`（会清空重建集合）；页面命令为 `.venv/bin/streamlit run app.py --server.headless true`。
- **技术栈**：Python 3.13、Streamlit、Ollama 本机 `qwen3.5:4b` / `nomic-embed-text`、ChromaDB、pypdf。不要调用云端 API 或外部 EDC/CTMS。
- **目录与约定**：需求边界见 `cra-monitor_SCOPE.md`；操作说明见 `README.md`；`knowledge/` 是判断依据，`sample_data/` 是模拟输入；`report_template.md` 是输出格式，不能移入 `knowledge/`。`chroma_db/` 是持久化数据，只能由项目 `.venv` 的代码读写。
- **当前状态与下一步**：见 `PROJECT_CONTEXT.md`。修复依赖检查中的缺项后，重跑未经替代组件的页面级全流程测试；不要把健康检查或替代编辑器测试写成完整通过。
