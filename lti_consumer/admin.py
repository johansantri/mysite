from django.contrib import admin
from .models import PlatformKey, LTIExternalTool, LTILink, LTILaunchLog

@admin.register(PlatformKey)
class PlatformKeyAdmin(admin.ModelAdmin):
    list_display = ("kid", "alg", "active", "created_at")
    list_filter = ("active",)

@admin.register(LTIExternalTool)
class LTIExternalToolAdmin(admin.ModelAdmin):
    list_display = ("name", "client_id", "deployment_id", "issuer")
    search_fields = ("name", "client_id", "issuer")

@admin.register(LTILink)
class LTILinkAdmin(admin.ModelAdmin):
    list_display = ("title", "tool", "resource_link_id", "target_link_uri")
    search_fields = ("title", "resource_link_id")

@admin.register(LTILaunchLog)
class LTILaunchLogAdmin(admin.ModelAdmin):
    list_display = ("tool", "link", "state", "success", "created_at")
    list_filter = ("success", "tool")
    search_fields = ("state", "nonce")
    readonly_fields = ("raw_payload",)
