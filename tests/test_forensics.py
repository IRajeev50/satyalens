import io
from PIL import Image
from backend.app.services.forensics import dhash, inspect_image

def image_bytes(color="white"):
    b=io.BytesIO(); Image.new("RGB",(32,32),color).save(b,"PNG"); return b.getvalue()
def test_dhash_is_stable():
    im=Image.open(io.BytesIO(image_bytes())); assert dhash(im)==dhash(im) and len(dhash(im))==16
def test_unconfigured_c2pa_is_honest():
    signals=inspect_image(image_bytes())
    c2pa=[x for x in signals if x.signal_type=="provenance"][0]
    assert c2pa.detector_version=="not_configured" and "not configured" in c2pa.finding
