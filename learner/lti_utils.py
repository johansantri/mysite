import hmac
import hashlib
import base64
from urllib.parse import parse_qs, urlparse, urlencode, quote,parse_qsl
from lxml import etree
import logging
import time

logger = logging.getLogger(__name__)

def percent_encode(s):
    """Percent-encode a string according to RFC 3986."""
    return quote(str(s), safe='~')

def generate_oauth_signature(params, consumer_secret, launch_url):
    """Generate OAuth signature for LTI launch request."""
    # Parse launch_url to get base_url and query params
    parsed_url = urlparse(launch_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}".rstrip('/')
    query_params = dict(parse_qsl(parsed_url.query))

    # Combine query params from URL with provided params
    full_params = {**params, **query_params}

    # Sort and percent-encode parameters (RFC 5849)
    encoded_params = []
    for k, v in sorted(full_params.items()):
        encoded_k = percent_encode(k)
        encoded_v = percent_encode(v)
        encoded_params.append(f"{encoded_k}={encoded_v}")

    param_string = '&'.join(encoded_params)

    # Build base string
    base_string = '&'.join([
        "POST",
        percent_encode(base_url),
        percent_encode(param_string)
    ])

    # Generate signature
    key = f"{percent_encode(consumer_secret)}&"  # Empty token secret
    raw = base_string.encode('utf-8')
    hashed = hmac.new(key.encode('utf-8'), raw, hashlib.sha1)
    signature = base64.b64encode(hashed.digest()).decode()

    # Debug logging
    logger.debug("Base URL: %s", base_url)
    logger.debug("Base String: %s", base_string)
    logger.debug("Signing Key: %s", key)
    logger.debug("OAuth Signature: %s", signature)

    return signature

def verify_oauth_signature(request):
    """Verify OAuth signature for incoming LTI callback."""
    # Extract OAuth parameters from Authorization header
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('OAuth '):
        logger.warning("No OAuth header provided")
        return False

    # Parse OAuth parameters
    params = {}
    try:
        auth_params = auth_header[6:].split(',')
        for param in auth_params:
            key, value = param.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"')
            params[key] = value
    except Exception as e:
        logger.error("Failed to parse Authorization header: %s", e)
        return False

    oauth_signature = params.pop('oauth_signature', '')
    logger.debug("Received OAuth signature: %s", oauth_signature)
    logger.debug("Received OAuth params: %s", params)

    # Validate timestamp
    oauth_timestamp = params.get('oauth_timestamp')
    if oauth_timestamp:
        try:
            timestamp = int(oauth_timestamp)
            current_time = int(time.time())
            if abs(current_time - timestamp) > 600:  # Allow 10-minute window
                logger.warning("Invalid timestamp: %s, current: %s", timestamp, current_time)
                return False
        except ValueError:
            logger.warning("Invalid timestamp format: %s", oauth_timestamp)
            return False

    # Get consumer key and shared secret
    consumer_key = params.get("oauth_consumer_key")
    if not consumer_key:
        logger.warning("No oauth_consumer_key provided")
        return False

    try:
        from courses.models import LTIExternalTool1
        tool = LTIExternalTool1.objects.get(consumer_key=consumer_key)
        logger.debug("Found tool with consumer_key: %s", consumer_key)
    except LTIExternalTool1.DoesNotExist:
        logger.warning("No tool found for consumer_key: %s", consumer_key)
        return False

    shared_secret = tool.shared_secret

    # Build base string
    base_url = request.build_absolute_uri(request.path).rstrip('/')
    all_params = sorted(params.items())
    param_str = urlencode(all_params, safe='~')
    base_string = "&".join([
        "POST",
        percent_encode(base_url),
        percent_encode(param_str)
    ])
    signing_key = percent_encode(shared_secret) + "&"

    # Generate signature
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_signature = base64.b64encode(hashed.digest()).decode()

    logger.debug("Base URL: %s", base_url)
    logger.debug("Base string: %s", base_string)
    logger.debug("Signing key: %s", signing_key)
    logger.debug("Computed signature: %s", computed_signature)
    logger.debug("OAuth signature match: %s", computed_signature == oauth_signature)

    return computed_signature == oauth_signature

def parse_lti_grade_xml(xml_body):
    """Parse LTI Outcome XML to extract sourcedId and score."""
    try:
        root = etree.fromstring(xml_body)
        ns = {'ims': 'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'}
        sourcedid_elem = root.find('.//ims:resultRecord/ims:sourcedGUID/ims:sourcedId', namespaces=ns)
        score_elem = root.find('.//ims:result/ims:resultScore/ims:textString', namespaces=ns)

        if sourcedid_elem is None or score_elem is None:
            logger.error("Missing XML elements: sourcedId=%s, score=%s", sourcedid_elem, score_elem)
            raise ValueError("Invalid XML structure")

        sourcedid = sourcedid_elem.text
        score = float(score_elem.text)
        logger.debug("Parsed sourcedId: %s, score: %s", sourcedid, score)
        return sourcedid, score
    except etree.ParseError as e:
        logger.error("XML parsing error: %s", e)
        raise
    except ValueError as e:
        logger.error("Score conversion error: %s", e)
        raise