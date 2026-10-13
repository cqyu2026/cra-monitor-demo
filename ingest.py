"""将本地法规和项目方案写入两层 ChromaDB 知识库。"""

import re
import urllib.request
import json
from pathlib import Path

import chromadb
from chromadb.config import Settings
from parse_document import parse_document


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "chroma_db"
COLLECTION = "cra_knowledge"
OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
CLAUSE = re.compile(r"第\s*(?:[一二三四五六七八九十百千零〇]+|\d+(?:\.\d+)*)\s*(?:条|节)|\d+(?:\.\d+)+\s*节")
DB_SETTINGS = Settings(anonymized_telemetry=False)


def collection():
    return chromadb.PersistentClient(path=str(DB_PATH), settings=DB_SETTINGS).get_or_create_collection(COLLECTION)


def read_text(path):
    return parse_document(path.name, path.read_bytes())


def split_text(text):
    """优先在段落边界切分，正文块约 300-500 字，块间重叠 50 字。"""
    text = re.sub(r"[ \t]+", " ", text).strip()
    start = 0
    while start < len(text):
        limit = min(start + 500, len(text))
        end = limit
        if limit < len(text):
            paragraph = text.rfind("\n\n", start + 300, limit)
            if paragraph > start:
                end = paragraph
        chunk = text[start:end].strip()
        if chunk:
            clauses = list(CLAUSE.finditer(text, 0, end))
            clause = clauses[-1].group().replace(" ", "") if clauses else ""
            yield chunk, clause
        if end == len(text):
            break
        start = max(start + 1, end - 50)


def embed(text):
    payload = json.dumps({"model": EMBEDDING_MODEL, "prompt": text}).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        vector = json.load(response)["embedding"]
    if not vector:
        raise ValueError("Ollama 返回了空向量")
    return vector


def remove_by_source(source, project_id=None):
    """删除来源文件的向量；提供项目 ID 时只删除该项目的同名文件。"""
    where = {"source": source}
    if project_id is not None:
        where = {"$and": [{"source": source}, {"scope": "project"}, {"project_id": project_id}]}
    collection().delete(where=where)


def ingest_file(path, project_id=None, source_type="regulation"):
    """入库一个受支持的本地文档；上传项目文档时传入 project_id 和 source_type。"""
    path = Path(path)
    if source_type == "regulation":
        if project_id is not None:
            raise ValueError("法规层不能指定 project_id")
        scope = "national"
    else:
        if not project_id:
            raise ValueError("项目层必须指定 project_id")
        scope = "project"

    chunks = list(split_text(read_text(path)))
    if not chunks:
        return 0
    target = collection()
    source = path.name
    for index, (content, clause) in enumerate(chunks):
        target.upsert(
            ids=[f"{scope}:{project_id or ''}:{source}:{index}"],
            documents=[content],
            embeddings=[embed(content)],
            metadatas=[{
                "source": source,
                "scope": scope,
                # Chroma metadata 不接受 None；空字符串代表法规层无项目。
                "project_id": project_id or "",
                "source_type": source_type,
                "clause": clause,
            }],
        )
    return len(chunks)


def main():
    client = chromadb.PersistentClient(path=str(DB_PATH), settings=DB_SETTINGS)
    client.get_or_create_collection(COLLECTION)
    client.delete_collection(COLLECTION)
    client.get_or_create_collection(COLLECTION)

    knowledge = ROOT / "knowledge"
    national_files = sorted(knowledge.glob("*.txt")) + sorted((knowledge / "原文下载").glob("*.pdf"))
    national = sum(ingest_file(path, source_type="regulation") for path in national_files)
    project = ingest_file(
        ROOT / "sample_data" / "模拟项目方案_项目A.txt",
        project_id="项目A",
        source_type="protocol",
    )
    print(f"法规层：{national} 块")
    print(f"项目层：{project} 块")


if __name__ == "__main__":
    main()
