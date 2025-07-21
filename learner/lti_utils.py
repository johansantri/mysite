import hmac
import hashlib
import base64
from urllib.parse import parse_qs, urlparse, urlencode, quote
from lxml import etree


def percent_encode(s):
    return quote(str(s), safe='~')


def verify_oauth_signature(request):
    params = request.POST.dict()
    oauth_signature = params.pop('oauth_signature', '')

    # Ambil consumer key
    consumer_key = params.get("oauth_consumer_key")
    if not consumer_key:
        return False

    # Ambil shared secret dari DB (dari tool Moodle)
    from .models import LTIExternalTool  # sesuaikan dengan model Anda
    try:
        tool = LTIExternalTool.objects.get(consumer_key=consumer_key)
    except LTIExternalTool.DoesNotExist:
        return False

    shared_secret = tool.shared_secret

    # Buat base string
    base_url = request.build_absolute_uri(request.path)
    all_params = sorted(params.items())
    param_str = urlencode(all_params, safe='~')
    base_string = "&".join([
        "POST",
        percent_encode(base_url),
        percent_encode(param_str)
    ])
    signing_key = percent_encode(shared_secret) + "&"

    # HMAC-SHA1
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_signature = base64.b64encode(hashed.digest()).decode()

    return computed_signature == oauth_signature


def parse_lti_grade_xml(xml_body):
    """
    Ekstrak <sourcedId> dan <textString> dari LTI Outcome XML.
    """
    root = etree.fromstring(xml_body)
    ns = {'ims': 'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'}

    sourcedid = root.find('.//ims:resultRecord/ims:sourcedGUID/ims:sourcedId', namespaces=ns).text
    score_str = root.find('.//ims:result/ims:resultScore/ims:textString', namespaces=ns).text

    return sourcedid, float(score_str)
