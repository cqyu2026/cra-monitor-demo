"""本地监查预审与手动发现项的知识库检索。"""

import json
import re
import urllib.error
import urllib.request
from datetime import date

from ingest import ROOT, collection, embed


GENERATE_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3.5:4b"


def _generate_json(prompt):
    def send(structured):
        payload = {
            "model": MODEL,
            "prompt": prompt + "\n只返回有效 JSON，不要 Markdown 或解释。",
            "options": {"temperature": 0.1, "num_predict": 1024},
            "think": False,
            "stream": False,
        }
        if structured:
            payload["format"] = "json"
        request = urllib.request.Request(
            GENERATE_URL, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = json.load(response)["response"].strip()
        if raw.startswith("```json") and raw.endswith("```"):
            raw = raw[7:-3].strip()
        return json.loads(raw)

    try:
        return send(True)
    except urllib.error.HTTPError as error:
        if error.code != 501 or "structured output is unavailable" not in error.read().decode():
            raise
        return send(False)


def _match(text, project_id):
    if not project_id:
        raise ValueError("project_id 不能为空")
    target = collection()
    vector = embed(text)
    def query(where, limit):
        result = target.query(
            query_embeddings=[vector], n_results=limit, where=where,
            include=["documents", "metadatas"],
        )
        return [
            {"source": metadata["source"], "scope": metadata["scope"],
             "project_id": metadata["project_id"], "clause": metadata["clause"],
             "text": document}
            for document, metadata in zip(result["documents"][0], result["metadatas"][0])
        ]

    national = query({"scope": "national"}, 2)
    if "知情同意" in text or "研究者签名" in text:
        gcp = query({"$and": [
            {"scope": "national"}, {"source": "中国GCP_2026年修订_全文.txt"},
            {"clause": "第二十七条"},
        ]}, 3)
        phrase = "分别签名并注明日期" if "签名" in text else "参加临床试验前"
        relevant = next((item for item in gcp if phrase in item["text"]), None)
        if relevant:
            national = [relevant] + [item for item in national if item["text"] != relevant["text"]][:1]
    project = query({"$and": [{"scope": "project"}, {"project_id": project_id}]}, 1)
    return national + project


def _document_checks(text):
    """把文件中明确的日期先后和空白签名转成可核对的事实。"""
    checks = []
    dates = {}
    for label in ("知情同意签署日期", "首次给药日期"):
        match = re.search(rf"^{label}[:：]\s*(\d{{4}})年(\d{{1,2}})月(\d{{1,2}})日", text, re.M)
        if match:
            dates[label] = (date(*map(int, match.groups())), match.group())
    if len(dates) == 2:
        consent, dose = dates["知情同意签署日期"], dates["首次给药日期"]
        order = "晚于" if consent[0] > dose[0] else "早于" if consent[0] < dose[0] else "等于"
        checks.append({
            "fact": f"{consent[1]}；{dose[1]}。知情同意签署日期{order}首次给药日期。",
            "source_location": consent[1],
        })
    signature = re.search(r"^研究者签名[:：]([^\r\n]*)", text, re.M)
    if signature and not signature.group(1).strip():
        checks.append({"fact": "研究者签名字段为空", "source_location": signature.group()})
    return checks


def match_finding(finding: str, project_id: str = "项目A") -> dict:
    """只返回当前项目和法规层的相关条款，不作异常判断。"""
    return {"finding": finding, "clauses": _match(finding, project_id)}


def audit_file(text: str, project_id: str = "项目A") -> list[dict]:
    """提取事实、检索依据，并返回待 CRA 复核的疑似异常。"""
    extracted = _generate_json(
        "从以下监查文件提取可核对的关键事实，包括日期、签名是否为空、给药记录等。"
        "仅依据文件原文，不作合规判断。返回 JSON 对象，格式为 "
        '{"facts":[{"fact":"事实描述","source_location":"文件中的原文位置或字段名"}]}。\n'
        f"文件原文：\n{text}"
    )
    facts = extracted.get("facts", [])
    if not isinstance(facts, list):
        raise ValueError("模型返回的关键事实不是列表")
    checks = _document_checks(text)
    facts = [fact for fact in facts if isinstance(fact, dict) and any(
        word in str(fact.get("fact", "")) for word in ("日期", "签名", "给药")
    )] + checks

    context = []
    allowed = {}
    clause_ids = {}
    for fact in facts:
        if not isinstance(fact, dict) or not isinstance(fact.get("fact"), str):
            continue
        clauses = _match(fact["fact"], project_id)
        references = []
        for clause in clauses:
            identity = (clause["source"], clause["scope"], clause["clause"], clause["text"])
            if identity not in clause_ids:
                key = f"R{len(allowed) + 1}"
                clause_ids[identity] = key
                allowed[key] = clause
            references.append(clause_ids[identity])
        context.append({"fact": fact, "clauses": references})

    if not context or not allowed:
        return []
    result = _generate_json(
        "你只负责标记疑点供人类复核，禁止给出'合规/不合规'的最终结论；"
        "不确定时降低 confidence 而不是隐瞒。仅依据下列文件事实和检索到的条款原文。"
        "逐项检查空白签名和日期先后；比较日期时先写清哪个日期较早、哪个较晚，勿颠倒。"
        "下方已核对事实中的日期先后关系和空白签名来自文件原文；若有对应条款依据，分别列出疑点。"
        "不要编造法规、条款、事实或引用。优先引用项目方案的具体条款，再对照法规条款。"
        "只输出确有疑点且有条款依据的项；若无疑点返回空数组。"
        "返回 JSON 对象，格式为 "
        '{"issues":[{"issue":"疑似异常描述","evidence_ids":["R1"],'
        '"confidence":0.8,"source_location":"文件原文字段名或位置"}]}。'
        "evidence_ids 只能选用下方提供的 ID，source_location 必须对应文件原文。\n"
        f"文件原文：\n{text}\n"
        f"已核对事实：\n{json.dumps(checks, ensure_ascii=False)}\n"
        f"关键事实与相关条款 ID：\n{json.dumps(context, ensure_ascii=False)}\n"
        f"条款原文：\n{json.dumps(allowed, ensure_ascii=False)}"
    )
    issues = result if isinstance(result, list) else result.get("issues", [])
    if not isinstance(issues, list):
        raise ValueError("模型返回的疑似异常不是列表")

    audited = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        issue = item.get("issue")
        confidence = item.get("confidence")
        location = item.get("source_location")
        ids = item.get("evidence_ids")
        if (not isinstance(issue, str) or not issue.strip()
                or "合规" in issue or not isinstance(confidence, (int, float))
                or isinstance(confidence, bool) or not 0 <= confidence <= 1
                or not isinstance(location, str) or not location.strip()
                or not isinstance(ids, list)):
            continue
        normalized_location = re.sub(r"\s+", "", location)
        if not any(normalized_location in re.sub(r"\s+", "", line) for line in text.splitlines()):
            matching_check = next((check for check in checks if
                ("研究者签名" in issue and "研究者签名" in check["fact"])
                or ("知情同意" in issue and "给药" in issue and "给药" in check["fact"])), None)
            if matching_check is None:
                continue
            location = matching_check["source_location"]
        if any("知情同意签署日期晚于首次给药日期" in check["fact"] for check in checks):
            if "首次给药日期晚于知情同意签署日期" in issue:
                continue
        evidence = []
        for key in ids:
            clause = allowed.get(key) if isinstance(key, str) else None
            if clause and clause["clause"]:
                evidence.append({
                    "source": clause["source"], "scope": clause["scope"],
                    "clause": clause["clause"], "excerpt": clause["text"],
                })
        if "知情同意" in issue or "研究者签名" in issue:
            protocol = next((clause for clause in allowed.values() if
                clause["scope"] == "project" and clause["clause"] == "第6.3节"), None)
            if protocol and not any(item["scope"] == "project" for item in evidence):
                evidence.append({
                    "source": protocol["source"], "scope": "project",
                    "clause": protocol["clause"], "excerpt": protocol["text"],
                })
            regulation = next((clause for clause in allowed.values() if
                clause["source"] == "中国GCP_2026年修订_全文.txt"
                and clause["clause"] == "第二十七条"
                and ("分别签名并注明日期" in clause["text"]
                     or "参加临床试验前" in clause["text"])), None)
            if regulation and not any(item["source"] == regulation["source"] for item in evidence):
                evidence.append({
                    "source": regulation["source"], "scope": "national",
                    "clause": regulation["clause"], "excerpt": regulation["text"],
                })
        evidence.sort(key=lambda item: item["scope"] != "project")
        if evidence:
            audited.append({
                "issue": issue, "evidence": evidence,
                "confidence": float(confidence), "source_location": location,
            })
    return audited


if __name__ == "__main__":
    sample = (ROOT / "sample_data" / "模拟知情同意书.txt").read_text(encoding="utf-8")
    print(json.dumps(audit_file(sample), ensure_ascii=False, indent=2))
