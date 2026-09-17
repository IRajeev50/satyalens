import hashlib,hmac
from backend.app.services.whatsapp import parse_text_messages, signature_valid

def test_signature():
    body=b'{"ok":true}'; secret='secret'; sig='sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    assert signature_valid(body,sig,secret); assert not signature_valid(body,sig+'x',secret)
def test_parse_only_text_messages():
    p={"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.1","from":"9199","type":"text","text":{"body":"A claim is true"}},{"id":"2","from":"9199","type":"image"}]}}]}]}
    out=parse_text_messages(p); assert len(out)==1 and out[0].text=="A claim is true"
