"""Chen nguyen trang bia tu Bia.docx vao dau file tai lieu da build.

Cach dung:
    python prepend-cover.py                      # Bia.docx -> tai-lieu-thiet-ke-he-thong.docx
    python prepend-cover.py <cover.docx> <target.docx>

Giu nguyen dinh dang trang bia (paragraph, bang, logo). Copy luon anh nhung trong
bia sang file dich va cap nhat quan he (rId) de khong mat hinh. Them ngat trang sau
bia de phan noi dung chinh bat dau o trang moi.
"""
import sys
from pathlib import Path

import io

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Cac the mang reference toi anh/quan he can doi rId
_REL_ATTRS = [qn("r:embed"), qn("r:link"), qn("r:id")]


def _copy_media_and_remap(cover_doc, target_doc, element):
    """Copy anh tu cover sang target va doi cac rId trong element cho khop.

    Dung target_part.get_or_add_image(): python-docx tu dat ten anh khong trung
    voi anh san co (tranh loi 'Duplicate name' / Word load nham anh).
    """
    cover_part = cover_doc.part
    target_part = target_doc.part
    for node in element.iter():
        for attr in _REL_ATTRS:
            rid = node.get(attr)
            if not rid or rid not in cover_part.rels:
                continue
            rel = cover_part.rels[rid]
            if rel.is_external:
                new_rid = target_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            else:
                blob = rel.target_part.blob
                new_rid, _ = target_part.get_or_add_image(io.BytesIO(blob))
            node.set(attr, new_rid)


def _page_break_paragraph():
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    p.append(r)
    return p


def prepend_cover(cover_path: Path, target_path: Path):
    if not cover_path.exists():
        raise FileNotFoundError(f"Khong tim thay file bia: {cover_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Khong tim thay file dich: {target_path}")

    cover_doc = Document(str(cover_path))
    target_doc = Document(str(target_path))

    target_body = target_doc.element.body
    # Vi tri chen: truoc phan tu dau tien cua than tai lieu dich
    first_child = target_body[0]

    # Lay cac phan tu bia (bo qua sectPr cuoi cung cua bia)
    cover_elements = [
        ch for ch in cover_doc.element.body.iterchildren()
        if ch.tag != qn("w:sectPr")
    ]

    for el in cover_elements:
        _copy_media_and_remap(cover_doc, target_doc, el)
        first_child.addprevious(el)

    # Ngat trang sau bia
    first_child.addprevious(_page_break_paragraph())

    target_doc.save(str(target_path))
    print(f"Da chen trang bia tu '{cover_path.name}' vao '{target_path.name}'.")


if __name__ == "__main__":
    here = Path(__file__).parent
    if len(sys.argv) >= 3:
        cover = Path(sys.argv[1])
        target = Path(sys.argv[2])
    else:
        cover = here / "Bia.docx"
        target = here / "tai-lieu-thiet-ke-he-thong.docx"
    prepend_cover(cover, target)
