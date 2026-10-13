# 项目交接状态

更新时间：2026-10-13。

## 现役入口

- 需求边界：[cra-monitor_SCOPE.md](cra-monitor_SCOPE.md)。
- 启动、演示与数据边界：[README.md](README.md)。
- 规则与项目环境约束：[AGENTS.md](AGENTS.md)。
- 代码：`ingest.py`（两层入库）、`audit.py`（检索与预审）、`app.py`（三个 Streamlit 标签页）、`parse_document.py` / `ocr.swift`（本地文件解析）、`report_template.md`（可编辑报告格式）。

## 已验证与待完成

- 当前项目 `.venv` 为 Python 3.13，ChromaDB 1.5.9；用 `.venv/bin/python` 读取时，`chroma_db/` 共有 142 块。不得用别的 Python/ChromaDB 环境操作该目录。
- 本机 8501 端口有项目 Streamlit 进程，健康端点返回 200；这仅证明服务存活，不证明页面可用。
- 用项目 `.venv` 的 Streamlit 页面测试器并临时替代 `st.data_editor` 时，上传预览、两项预审提示、项目第 6.3 节与中国 GCP 第 27 条依据、手动匹配、采纳、报告和下载控件已走通。侧边栏测试入库增加 1 块，测试后清理并恢复 142 块。模板缺失自动生成与编辑后重生成已验证。
- `.venv` 缺少 pandas，清单页面已提供逐条编辑回退；表格编辑器仍需安装 pandas。`.venv/bin/python -m pip check` 尚有其他 Streamlit 依赖缺项，因此完整页面验收尚未通过。
- 2026-10-13 增加 Word（doc/docx）、Excel（xls/xlsx）、JPG/JPEG 上传解析，均使用本机工具。Word 样例、原生 XLSX 中文样例和 JPG OCR 样例已验证；Streamlit 页面测试器显示两个上传框可用且无页面异常。尚未对真实 XLS 文件或全部格式走完整模型预审。
- `cra-monitor_SCOPE.md` 列出的 WHO 模板、真实试验方案、ICF 与机构 SOP 当前未在 `knowledge/` 中；当前目录实际包含中国 GCP 文本、ICH E6(R3) 中文 PDF、安全性报告 PDF 和其他本地法规/知情同意资料。恢复完整知识库材料前，不要宣称原定知识库范围已全部到位。

## 当前状态

本地 Demo 已实现，知识收尾进行中；未发布、未完成真实页面全流程验收。`chroma_db/`、`.venv/` 和项目运行进程均保留。
