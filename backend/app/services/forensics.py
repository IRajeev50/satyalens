import io, json, subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from PIL import Image, ExifTags

@dataclass(frozen=True)
class Signal:
    detector: str; detector_version: str; signal_type: str; finding: str
    confidence: str; limitations: str; raw: dict

def dhash(image: Image.Image, size=8) -> str:
    gray=image.convert("L").resize((size+1,size))
    bits=[]
    for y in range(size):
        for x in range(size): bits.append(gray.getpixel((x,y)) > gray.getpixel((x+1,y)))
    return f"{sum(v << i for i,v in enumerate(bits)):0{size*size//4}x}"

def inspect_image(data: bytes, c2pa_cli_path: str | None = None, temp_path: str | None = None) -> list[Signal]:
    im=Image.open(io.BytesIO(data)); exif={}
    try:
        exif={str(ExifTags.TAGS.get(k,k)): str(v)[:500] for k,v in im.getexif().items()}
    except Exception: pass
    signals=[Signal("Pillow metadata","11.3.0","metadata", "Embedded metadata found" if exif else "No embedded EXIF metadata found", "Low", "Metadata may be stripped, edited, or forged. Its absence does not imply manipulation.", {"exif":exif}), Signal("dHash","1","perceptual_hash",dhash(im),"Low","A perceptual hash supports later similarity search; it is not an authenticity verdict.",{})]
    if c2pa_cli_path and temp_path:
        try:
            result=subprocess.run([c2pa_cli_path,temp_path,"--json"],capture_output=True,text=True,timeout=10,check=False)
            payload=json.loads(result.stdout) if result.stdout.strip() else {"stderr":result.stderr[:1000],"exit_code":result.returncode}
            found=result.returncode==0 and bool(payload)
            signals.append(Signal("C2PA CLI","external","provenance","Content Credential manifest returned" if found else "No valid Content Credential manifest returned","Moderate" if found else "Low","A valid credential establishes signed provenance assertions, not whether the depicted claim is true. Absence proves nothing.",payload))
        except Exception as exc:
            signals.append(Signal("C2PA CLI","external","provenance","C2PA inspection unavailable","Low","The configured local verifier failed; no provenance conclusion was drawn.",{"error":type(exc).__name__}))
    else:
        signals.append(Signal("C2PA","not_configured","provenance","C2PA verification not configured","Low","No provenance conclusion was drawn. Configure a real C2PA CLI to inspect manifests.",{}))
    return signals
