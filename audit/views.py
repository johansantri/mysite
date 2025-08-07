from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from audit.models import AuditLog
import json

@login_required
def my_activity_logs(request):
    logs_queryset = (
        AuditLog.objects
        .filter(user=request.user)
        .only('timestamp', 'action', 'content_type', 'object_id', 'changes', 'device_type')
        .order_by('-timestamp')
    )

    paginator = Paginator(logs_queryset, 20)
    page = request.GET.get('page')

    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)

    logs = []
    for log in logs_page:
        try:
            if isinstance(log.changes, str):
                parsed_change = json.loads(log.changes)
            elif isinstance(log.changes, dict):
                parsed_change = log.changes
            else:
                parsed_change = {}
        except Exception as e:
            parsed_change = {'invalid': str(log.changes), 'error': str(e)}

        logs.append({
            'timestamp': log.timestamp,
            'action': log.action,
            'content_type': log.content_type,
            'object_id': log.object_id,
            'device_type': log.device_type,
            'change': parsed_change,
        })

    return render(request, 'audit/my_logs.html', {
        'logs': logs,
        'page_obj': logs_page,
    })
