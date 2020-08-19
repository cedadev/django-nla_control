from django.contrib import admin
from nla_control.models import *
# Register your models here.


class TapeFileAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('logical_path', 'formatted_size', 'stage', 'verified')
    search_fields = ('logical_path',)
    list_filter = ('stage',)
    readonly_fields = ('logical_path', 'size')
admin.site.register(TapeFile, TapeFileAdmin)

class TapeReqAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("__unicode__", 'quota', 'active_request', 'retention', 'storaged_request_start', 'storaged_request_end')
    list_filter = ('quota',)
#    exclude = ('active_request',)
    readonly_fields = ('files', 'request_patterns', 'request_files', 'storaged_request_start', 'storaged_request_end', 'first_files_on_disk', 'last_files_on_disk')
admin.site.register(TapeRequest, TapeReqAdmin)

class QuotaAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('user', 'formatted_size', 'email_address')
    search_fields = ('user',)
admin.site.register(Quota, QuotaAdmin)

class SlotAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('pk', 'tape_request')
    search_fields = ('tape_request',)
    readonly_fields = ('tape_request', 'pid', 'host_ip', 'request_dir')
admin.site.register(StorageDSlot, SlotAdmin)

class RestoreDiskAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('mountpoint', 'formatted_allocated', 'formatted_used')
    search_fields = ('mountpoint',)
#    readonly_fields = ('used_bytes',)
admin.site.register(RestoreDisk, RestoreDiskAdmin)
