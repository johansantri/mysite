from user_agents import parse as parse_ua

def detect_device_type(user_agent_str):
    try:
        user_agent = parse_ua(user_agent_str)
        if user_agent.is_mobile:
            return 'Mobile'
        elif user_agent.is_tablet:
            return 'Tablet'
        elif user_agent.is_pc:
            return 'PC'
        else:
            return 'Other'
    except Exception:
        return None

from audit.middleware import get_current_request

def get_request_info():
    request = get_current_request()
    if request and hasattr(request, 'audit_log_info'):
        ip = request.audit_log_info.get('ip_address')
        user_agent = request.audit_log_info.get('user_agent')
        device_type = detect_device_type(user_agent or '')
        path = request.path if hasattr(request, 'path') else None
        return ip, user_agent, device_type, path
    return None, None, None, None
