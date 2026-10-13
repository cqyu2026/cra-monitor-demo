"""在本机将上传文件提取为纯文本。"""

from io import BytesIO
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory

from pypdf import PdfReader


FORMATS = ["pdf", "txt", "doc", "docx", "xls", "xlsx", "jpg", "jpeg"]
OCR_SCRIPT = Path(__file__).with_name("ocr.swift")


def parse_document(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".txt":
        return data.decode("utf-8-sig")
    if suffix == ".pdf":
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    if suffix not in {".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg"}:
        raise ValueError(f"不支持的文件类型：{suffix}")

    with TemporaryDirectory() as folder:
        source = Path(folder) / f"upload{suffix}"
        source.write_bytes(data)
        if suffix in {".doc", ".docx"}:
            command = ["/usr/bin/textutil", "-convert", "txt", "-stdout", str(source)]
        elif suffix in {".jpg", ".jpeg"}:
            command = ["/usr/bin/swift", str(OCR_SCRIPT), str(source)]
        else:
            command = ["soffice", "-env:UserInstallation=file://" + folder + "/lo-profile",
                       "--headless", "--convert-to", "html", "--outdir", folder, str(source)]
        result = run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError(f"本地文件解析失败：{result.stderr.strip() or result.stdout.strip()}")
        if suffix in {".xls", ".xlsx"}:
            html = source.with_suffix(".html")
            if not html.exists():
                raise ValueError("Excel 未能转换为文本，请检查文件是否损坏。")
            converted = run(["/usr/bin/textutil", "-convert", "txt", "-stdout", str(html)],
                            capture_output=True, text=True, timeout=120)
            if converted.returncode:
                raise ValueError(f"Excel 文本提取失败：{converted.stderr.strip()}")
            text = converted.stdout
        else:
            text = result.stdout
        if not text.strip():
            raise ValueError("没有提取到文字，请检查文件内容或图片清晰度。")
        return text.strip()
