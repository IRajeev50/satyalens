import hashlib, hmac
from dataclasses import dataclass

@dataclass(frozen=True)
class InboundText:
    message_id: str; sender: str; text: str

def signature_valid(body: bytes, header: str | None, secret: str | None) -> bool:
    if not secret or not header or not header.startswith("sha256="): return False
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:],expected)

def parse_text_messages(payload: dict) -> list[InboundText]:
    output=[]
    for entry in payload.get("entry",[]):
        for change in entry.get("changes",[]):
            value=change.get("value",{})
            for msg in value.get("messages",[]):
                if msg.get("type")=="text" and msg.get("id") and msg.get("from"):
                    text=(msg.get("text") or {}).get("body","").strip()
                    if text: output.append(InboundText(msg["id"],msg["from"],text))
    return output
