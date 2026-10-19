from io import BytesIO
import pytest
from PIL import Image
from pypdf import PdfWriter, PdfReader
from nightjar_learning.receipts import validate_receipt, MAX_BYTES

def image(kind='PNG'):
    out=BytesIO();Image.new('RGB',(20,20),'purple').save(out,kind);return out.getvalue()

def pdf(script=False, encrypted=False):
    writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    if script:writer.add_js('app.alert("test")')
    if encrypted:writer.encrypt('password')
    out=BytesIO();writer.write(out);return out.getvalue()

@pytest.mark.parametrize('filename,data',[('receipt.png',image()),('receipt.jpg',image('JPEG')),('receipt.pdf',pdf())])
def test_normalizes_supported_receipts(filename,data):
    name,mime,result=validate_receipt('../'+filename,data)
    assert name==filename and result and len(result)<=MAX_BYTES
    if mime=='application/pdf':assert len(PdfReader(BytesIO(result)).pages)==1
    else:Image.open(BytesIO(result)).verify()

@pytest.mark.parametrize('filename,data',[
 ('empty.png',b''),('huge.png',b'x'*(MAX_BYTES+1)),('fake.jpg',b'<script>bad</script>'),
 ('wrong.png',image('JPEG')),('receipt.svg',b'<svg/>'),('bad.pdf',b'%PDF-broken'),
 ('script.pdf',pdf(script=True)),('encrypted.pdf',pdf(encrypted=True)),('receipt.exe',image()),
])
def test_rejects_invalid_unsafe_or_oversize_receipts(filename,data):
    with pytest.raises(ValueError):validate_receipt(filename,data)

def test_strips_appended_image_payload():
    result=validate_receipt('receipt.png',image()+b'UNEXPECTED-PAYLOAD')[2]
    assert b'UNEXPECTED-PAYLOAD' not in result
