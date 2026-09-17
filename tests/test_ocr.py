import io
from PIL import Image
import pytest
from backend.app.services import ocr

def png_bytes():
    b=io.BytesIO(); Image.new("RGB",(20,20),"white").save(b,"PNG"); return b.getvalue()
def test_rejects_wrong_mime():
    with pytest.raises(ValueError): ocr.extract_screenshot(png_bytes(),"application/pdf")
def test_ocr_maps_confidence(monkeypatch):
    class Fake:
        class Output: DICT=dict
        @staticmethod
        def image_to_data(*a,**k): return {"text":["सरकार","launched","scheme"],"conf":["90","88","92"]}
    monkeypatch.setitem(__import__('sys').modules,'pytesseract',Fake)
    r=ocr.extract_screenshot(png_bytes(),"image/png")
    assert r.text=="सरकार launched scheme" and r.confidence=="High"
