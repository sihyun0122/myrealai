import base64
import io

try:
    from PyPDF2 import PdfReader
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from docx import Document as DocxDoc
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

try:
    import openpyxl
    XLSX_OK = True
except ImportError:
    XLSX_OK = False


IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]


def fmt_size(s):
    if s < 1024:
        return f"{s} B"
    if s < 1024**2:
        return f"{s/1024:.1f} KB"
    if s < 1024**3:
        return f"{s/1024**2:.1f} MB"
    return f"{s/1024**3:.2f} GB"


def is_image(mime):
    return mime in IMAGE_TYPES


def extract_pdf(data):
    if not PDF_OK:
        return "[PDF 라이브러리 없음]"
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for i, p in enumerate(reader.pages):
            t = p.extract_text()
            if t:
                parts.append(f"--- 페이지 {i+1} ---\n{t}")
        return "\n\n".join(parts) if parts else "[텍스트 추출 불가]"
    except Exception as e:
        return f"[PDF 오류: {e}]"


def extract_docx(data):
    if not DOCX_OK:
        return "[Word 라이브러리 없음]"
    try:
        doc = DocxDoc(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[Word 오류: {e}]"


def extract_xlsx(data):
    if not XLSX_OK:
        return "[Excel 라이브러리 없음]"
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        lines = []
        for name in wb.sheetnames:
            lines.append(f"=== {name} ===")
            for row in wb[name].iter_rows(values_only=True):
                r = "\t".join(str(c) if c else "" for c in row)
                if r.strip():
                    lines.append(r)
        wb.close()
        return "\n".join(lines)
    except Exception as e:
        return f"[Excel 오류: {e}]"


def process_file(uploaded):
    data = uploaded.read()
    mime = uploaded.type or ""
    name = uploaded.name
    size = fmt_size(len(data))

    if is_image(mime):
        b64 = base64.standard_b64encode(data).decode("utf-8")
        block = {
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64},
        }
        return block, f"[이미지: {name}]", f"🖼️ {name} ({size})"

    if mime == "application/pdf":
        text = extract_pdf(data)
    elif "wordprocessingml" in mime:
        text = extract_docx(data)
    elif "spreadsheetml" in mime:
        text = extract_xlsx(data)
    else:
        try:
            text = data.decode("utf-8")
        except:
            try:
                text = data.decode("euc-kr")
            except:
                text = f"[읽기 불가: {name}]"

    return None, text, f"📄 {name} ({size})"
