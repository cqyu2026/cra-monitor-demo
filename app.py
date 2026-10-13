"""临床试验监查助手的本地 Streamlit 界面。"""

from datetime import date
from hashlib import sha256
from html import escape
from pathlib import Path
from importlib.util import find_spec
import urllib.error

import streamlit as st

from audit import audit_file, match_finding
from ingest import ROOT, collection, ingest_file, remove_by_source
from parse_document import FORMATS, parse_document


TEMPLATE_PATH = ROOT / "report_template.md"
DEFAULT_TEMPLATE = """# 临床试验监查报告草稿

**项目名称：** {{project_name}}  
**生成日期：** {{date}}

## 监查概况

本报告汇总 CRA 采纳的疑似发现项，供人工核对与完善。

## 发现项明细

{{findings}}

## 备注

请 CRA 核对源文件、依据条款及现场情况，并补充后续处理记录。
"""


def read_upload(upload):
    return parse_document(upload.name, upload.getvalue())


def show_action_error(action, error):
    if isinstance(error, urllib.error.HTTPError):
        st.error(f"{action}失败：本机 Ollama 返回 HTTP {error.code}。请检查模型和服务状态。")
    elif isinstance(error, (urllib.error.URLError, ConnectionError, TimeoutError)):
        st.error(f"{action}失败：无法连接本机 Ollama。请先运行 `ollama serve`，并确认模型已安装。")
    else:
        st.error(f"{action}失败：{error}")


def report_text(project_name, findings):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    lines = []
    for index, item in enumerate(findings, 1):
        detail = (
            f"### {index}. {item['发现项']}\n\n"
            f"- 依据条款：{item.get('依据条款') or '待补充'}\n"
            f"- 依据摘录：{item.get('依据摘录') or '待补充'}\n"
            f"- 来源位置：{item.get('来源位置') or '待补充'}\n"
        )
        if isinstance(item.get("置信度"), (int, float)):
            detail += f"- 置信度：{item['置信度']:.0%}\n"
        lines.append(detail)
    return (template.replace("{{project_name}}", project_name)
            .replace("{{date}}", date.today().isoformat())
            .replace("{{findings}}", "\n".join(lines) if lines else "暂无采纳的发现项。"))


def evidence_fields(clauses):
    cited = [item for item in clauses if item.get("clause")]
    def label(item):
        if item["source"] == "中国GCP_2026年修订_全文.txt":
            return f"《药物临床试验质量管理规范（2026年修订）》{item['clause']}"
        return f"{item['source']} {item['clause']}"
    return (
        "；".join(label(item) for item in cited),
        "\n\n".join(f"{item['source']}：{item.get('excerpt', item.get('text', ''))}" for item in cited),
    )


def add_audit_results(issues):
    existing = {(row["发现项"], row["来源位置"]) for row in st.session_state.findings}
    for item in issues:
        key = (item["issue"], item["source_location"])
        if key in existing:
            continue
        citation, excerpt = evidence_fields(item["evidence"])
        st.session_state.findings.append({
            "发现项": item["issue"], "依据条款": citation, "依据摘录": excerpt,
            "置信度": item["confidence"], "来源位置": item["source_location"],
            "状态": "待处理",
        })
        existing.add(key)
    st.session_state.editor_version += 1


def main():
    st.set_page_config(page_title="临床试验监查助手", layout="wide")
    st.title("临床试验监查助手")
    if not TEMPLATE_PATH.exists():
        TEMPLATE_PATH.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
    if "findings" not in st.session_state:
        st.session_state.findings = []
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0

    with st.sidebar:
        st.success("本地模式运行中 · 数据不出本机")
        if "ingest_notice" in st.session_state:
            st.success(st.session_state.pop("ingest_notice"))
        project_id = st.text_input("项目名称", value="项目A").strip()
        target = collection()
        national_count = len(target.get(where={"scope": "national"}, include=[])["ids"])
        project_count = len(target.get(where={"$and": [
            {"scope": "project"}, {"project_id": project_id}
        ]}, include=[])["ids"]) if project_id else 0
        st.write(f"法规层：{national_count} 块")
        st.write(f"项目层（{project_id or '未选择'}）：{project_count} 块")
        st.subheader("项目文档上传")
        project_upload = st.file_uploader("上传项目方案 PDF/TXT/Word/Excel/JPG", type=FORMATS, key="project_upload")
        if st.button("入库", disabled=not project_id or project_upload is None):
            filename = Path(project_upload.name).name
            folder = ROOT / "project_docs" / sha256(project_id.encode("utf-8")).hexdigest()[:12]
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / filename
            try:
                with st.spinner("正在向量化并入库项目文档，请稍候…"):
                    path.write_bytes(project_upload.getvalue())
                    remove_by_source(filename, project_id=project_id)
                    count = ingest_file(path, project_id=project_id, source_type="protocol")
            except Exception as error:
                show_action_error("入库", error)
            else:
                st.session_state.ingest_notice = f"已入库 {count} 块"
                st.rerun()

    preview_tab, checklist_tab, report_tab = st.tabs(["智能预审", "人机协同清单", "报告生成"])

    with preview_tab:
        upload = st.file_uploader("上传监查文件 PDF/TXT/Word/Excel/JPG", type=FORMATS, key="audit_upload")
        parsed = ""
        if upload is not None:
            try:
                parsed = read_upload(upload)
                st.text_area("解析文本预览（前 500 字）", parsed[:500], height=180)
            except Exception as error:
                st.error(f"文件解析失败：{error}")
        if st.button("开始预审", disabled=not parsed or not project_id):
            try:
                with st.spinner("正在本地模型预审并检索依据，请稍候…"):
                    st.session_state.last_issues = audit_file(parsed, project_id=project_id)
                    add_audit_results(st.session_state.last_issues)
            except Exception as error:
                show_action_error("预审", error)
        for item in st.session_state.get("last_issues", []):
            citation, excerpt = evidence_fields(item["evidence"])
            st.markdown(
                '<div style="border:1px solid #d6dde5;border-radius:10px;padding:16px;margin:12px 0;">'
                f'<strong>{escape(item["issue"])}</strong><br>'
                f'依据条款：{escape(citation)}<br>'
                f'来源位置：{escape(item["source_location"])}'
                '</div>', unsafe_allow_html=True,
            )
            st.progress(item["confidence"], text=f"置信度：{item['confidence']:.0%}")
            with st.expander("查看依据原文"):
                st.text(excerpt)

    with checklist_tab:
        finding = st.text_area("录入 CRA 发现项")
        if st.button("匹配条款", disabled=not finding.strip() or not project_id):
            try:
                with st.spinner("正在检索本地知识库，请稍候…"):
                    st.session_state.manual_match = match_finding(finding.strip(), project_id=project_id)
            except Exception as error:
                show_action_error("匹配条款", error)
            else:
                citation, excerpt = evidence_fields(st.session_state.manual_match["clauses"])
                st.session_state.findings.append({
                    "发现项": finding.strip(), "依据条款": citation,
                    "依据摘录": excerpt, "置信度": None,
                    "来源位置": "CRA 手动录入", "状态": "待处理",
                })
                st.session_state.editor_version += 1
        if "manual_match" in st.session_state:
            st.subheader("匹配条款")
            for clause in st.session_state.manual_match["clauses"]:
                st.markdown(f"**{clause['source']} · {clause['clause'] or '未定位条款'}**")
                st.text(clause["text"])

        st.subheader("发现项清单")
        if find_spec("pandas"):
            edited = st.data_editor(
                st.session_state.findings, num_rows="dynamic", hide_index=True,
                key=f"findings_editor_{st.session_state.editor_version}",
                column_config={"状态": st.column_config.SelectboxColumn(options=["待处理", "采纳", "忽略"])},
            )
            if edited != st.session_state.findings:
                st.session_state.findings = edited
        else:
            st.caption("当前环境缺少 pandas，使用逐条编辑。")
            for index, item in enumerate(st.session_state.findings):
                with st.expander(f"编辑发现项 {index + 1}"):
                    with st.form(f"finding_form_{index}"):
                        issue = st.text_area("发现项", item.get("发现项", ""))
                        evidence = st.text_area("依据条款", item.get("依据条款", ""))
                        excerpt = st.text_area("依据摘录", item.get("依据摘录", ""))
                        location = st.text_input("来源位置", item.get("来源位置", ""))
                        status = st.selectbox("状态", ["待处理", "采纳", "忽略"],
                                              index=["待处理", "采纳", "忽略"].index(item.get("状态", "待处理")))
                        if st.form_submit_button("保存"):
                            item.update({"发现项": issue, "依据条款": evidence,
                                         "依据摘录": excerpt, "来源位置": location, "状态": status})
                            st.rerun()
                    if st.button("删除此项", key=f"delete_{index}"):
                        st.session_state.findings.pop(index)
                        st.rerun()
        for index, item in enumerate(st.session_state.findings):
            left, middle, right = st.columns([5, 1, 1])
            left.write(item.get("发现项") or "（待填写）")
            if middle.button("采纳", key=f"accept_{index}"):
                st.session_state.findings[index]["状态"] = "采纳"
                st.session_state.editor_version += 1
                st.rerun()
            if right.button("忽略", key=f"ignore_{index}"):
                st.session_state.findings[index]["状态"] = "忽略"
                st.session_state.editor_version += 1
                st.rerun()

    with report_tab:
        accepted = [row for row in st.session_state.findings if row.get("状态") == "采纳"]
        selected = []
        for index, item in enumerate(accepted):
            if st.checkbox(item.get("发现项") or "（未命名发现项）", value=True, key=f"report_{index}"):
                selected.append(item)
        selection = (project_id, tuple(tuple(sorted(item.items())) for item in selected))
        if st.session_state.get("report_selection") != selection:
            st.session_state.pop("report", None)
        if st.button("生成监查报告", disabled=not selected):
            st.session_state.report = report_text(project_id, selected)
            st.session_state.report_selection = selection
        if "report" in st.session_state:
            st.markdown(st.session_state.report)
            st.download_button("下载 Markdown 报告", st.session_state.report,
                               file_name="监查报告草稿.md", mime="text/markdown")


if __name__ == "__main__":
    main()
