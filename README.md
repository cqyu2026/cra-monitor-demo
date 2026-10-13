# 临床试验监查助手（本地演示）

面向 CRA 的本地监查辅助演示。监查文件、知识库、向量库和报告草稿均留在本机；AI 仅提示疑点，最终判断由 CRA 完成。需求边界见 [cra-monitor_SCOPE.md](cra-monitor_SCOPE.md)。

## 准备与启动

1. 使用 Python 3.13，在项目根目录创建虚拟环境并安装依赖。后续命令始终使用这个 `.venv`：

   ```bash
   python3.13 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip check
   ```

   `pip check` 必须通过。Streamlit 的 `st.data_editor` 依赖 pandas；仅能导入 `streamlit` 不代表页面可以运行。若使用已有 `.venv`，先检查依赖，不要用其他 Python 环境操作本项目的 `chroma_db/`。

2. 确认本机 Ollama 已备好 `qwen3.5:4b` 和 `nomic-embed-text` 模型。另开终端启动服务：

   ```bash
   ollama serve
   ```

3. 在项目根目录，首次建库时运行入库脚本，再启动界面：

   ```bash
   .venv/bin/python ingest.py
   .venv/bin/streamlit run app.py --server.headless true
   ```

`ingest.py` 每次都会清空并重建 `chroma_db/` 中的集合；已有数据时不要把它当成无副作用的启动命令。应用只访问本机 Ollama 回环地址；`report_template.md` 位于项目根目录，可直接编辑报告格式，绝不放入 `knowledge/`。
项目内 `.streamlit/config.toml` 已关闭 Streamlit 使用统计，ChromaDB 匿名遥测也已关闭，避免应用运行时向外发送遥测请求。

## 演示话术

“先在 **智能预审** 上传 `sample_data/模拟知情同意书.txt`，确认解析预览，再点击‘开始预审’。系统会把疑似问题、依据条款、置信度和来源位置放在卡片里，供 CRA 复核。接着切到 **人机协同清单**，可以手动录入发现项并匹配条款，也可以对预审发现点击‘采纳’或‘忽略’，或直接编辑清单。最后进入 **报告生成**，勾选已采纳的发现，点击‘生成监查报告’，检查草稿后下载 Markdown 文件。”

如需演示新项目开工，可先在侧边栏填写项目名称、上传 PDF/TXT/Word/Excel/JPG 方案并点击“入库”；完成后项目层块数会刷新，同一项目的同名文件会先移除旧向量再入库。监查文件上传支持相同格式。Word 使用 macOS `textutil`，Excel 使用本机 LibreOffice，JPG 使用 macOS Vision OCR；均不调用云端服务。上传后请核对解析文本预览，尤其是表格与图片中的日期和签名。
