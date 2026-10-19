"""Private enrollment receipts: bounded validation, isolated storage, live authorization."""
from io import BytesIO
from pathlib import Path
import re
import secrets
import warnings

MAX_BYTES = 10 * 1024 * 1024
KEY = re.compile(r"[a-f0-9]{32}\Z")


def validate_receipt(filename, data):
    """Return a normalized name, MIME type and safe bytes; never trust the suffix alone."""
    from PIL import Image, ImageOps
    name = str(filename or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w .()-]", "_", name)[:120]
    suffix = Path(name).suffix.lower()
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose a non-empty receipt no larger than 10 MB.")
    if suffix in {".jpg", ".jpeg", ".png"}:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as img:
                    if img.format not in {"JPEG", "PNG"} or img.width * img.height > 25_000_000:
                        raise ValueError("Choose a JPG or PNG image under 25 megapixels.")
                    if (suffix == ".png") != (img.format == "PNG"):
                        raise ValueError("The receipt extension does not match the image.")
                    img.load()
                    clean = ImageOps.exif_transpose(img).convert("RGB")
                    out = BytesIO()
                    clean.save(out, format="PNG" if suffix == ".png" else "JPEG", **({} if suffix == '.png' else {'quality': 92}))
            data = out.getvalue()  # Removes EXIF/location information and appended payloads.
            if len(data) > MAX_BYTES:
                raise ValueError("The processed receipt is larger than 10 MB. Use a smaller image.")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("This image could not be read. Upload a valid JPG or PNG.") from exc
        return name, "image/png" if suffix == ".png" else "image/jpeg", data
    if suffix != ".pdf" or not data.startswith(b"%PDF-"):
        raise ValueError("Receipts must be JPG, PNG, or PDF files.")
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import IndirectObject, DictionaryObject, ArrayObject
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise ValueError("Use an unencrypted PDF with 1–100 pages.")
        forbidden = {"/OpenAction", "/AA", "/JS", "/JavaScript", "/Launch", "/EmbeddedFiles", "/EmbeddedFile", "/RichMedia", "/XFA", "/AcroForm"}
        seen, count = set(), 0
        def inspect(obj, depth=0):
            nonlocal count
            count += 1
            if depth > 80 or count > 100_000:
                raise ValueError("This PDF is too complex. Upload an image of the receipt instead.")
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in seen:
                    return
                seen.add(key)
                obj = obj.get_object()
            if isinstance(obj, DictionaryObject):
                if any(str(k) in forbidden or (isinstance(v, str) and v in forbidden) for k, v in obj.items()):
                    raise ValueError("Interactive PDFs and embedded files are not accepted. Upload a plain PDF or image.")
                for value in obj.values():
                    inspect(value, depth + 1)
            elif isinstance(obj, ArrayObject):
                for value in obj:
                    inspect(value, depth + 1)
        inspect(reader.trailer)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        data = out.getvalue()
        if len(data) > MAX_BYTES:
            raise ValueError("The processed PDF is larger than 10 MB.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("This PDF could not be read. Upload a valid PDF or image.") from exc
    return name, "application/pdf", data


def read_upload():
    import frappe
    files = getattr(frappe.request, "files", {})
    uploads = files.getlist("receipt") if hasattr(files, "getlist") else []
    if len(uploads) > 1 or any(key != 'receipt' for key in files):
        frappe.throw("Attach only one receipt.")
    if not uploads or not uploads[0].filename:
        return None
    try:
        return validate_receipt(uploads[0].filename, uploads[0].stream.read(MAX_BYTES + 1))
    except ValueError as exc:
        frappe.throw(str(exc))


def receipt_path(key):
    import frappe
    if not isinstance(key, str) or not KEY.fullmatch(key):
        frappe.throw("Receipt unavailable.", frappe.PermissionError)
    root = Path(frappe.get_site_path("private", "files", "nightjar-receipts"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (key + '.bin')
    if path.is_symlink() or path.resolve().parent != root.resolve():
        frappe.throw("Receipt unavailable.", frappe.PermissionError)
    return path


def save_receipt(doc, upload):
    import frappe
    name, mime, data = upload
    key = secrets.token_hex(16)
    path = receipt_path(key)
    with path.open('xb') as f:
        path.chmod(0o600)
        f.write(data)
    # Included in standard bench --with-files backups. No publicly addressable File row.
    frappe.db.after_rollback.add(lambda: path.unlink(missing_ok=True))
    doc.receipt_key, doc.receipt_name = key, name
    doc.receipt_size, doc.receipt_type = len(data), mime


def remove_receipt(key):
    if key:
        receipt_path(key).unlink(missing_ok=True)


def receipt_response(doc):
    import frappe
    from werkzeug.wrappers import Response
    if not doc.receipt_key:
        frappe.throw("This request has no receipt.", frappe.DoesNotExistError)
    path = receipt_path(doc.receipt_key)
    if not path.is_file():
        frappe.throw("Receipt unavailable. Contact the administrator.", frappe.DoesNotExistError)
    response = Response(path.read_bytes(), mimetype=doc.receipt_type)
    from urllib.parse import quote
    from werkzeug.http import dump_options_header
    filename = doc.receipt_name or 'receipt'
    fallback = filename.encode('ascii', 'ignore').decode() or 'receipt'
    response.headers['Content-Disposition'] = dump_options_header('attachment', {
        'filename': fallback, "filename*": "UTF-8''" + quote(filename, safe='')
    })
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response
