from django.contrib import admin
from nla_control.models import *
# Register your models here.


class TapeFileAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('formatted_logical_path', 'formatted_size', 'stage', 'verified')
    search_fields = ('logical_path',)
    list_filter = ('stage',)
    fields = ('formatted_logical_path', 'verified', 'stage', 'restore_disk', 'formatted_size')
    readonly_fields = ('formatted_logical_path', 'formatted_size')
admin.site.register(TapeFile, TapeFileAdmin)

class TapeReqAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("__unicode__", 'quota', 'active_request', 'retention', 'storaged_request_start', 'storaged_request_end')
    list_filter = ('quota',)
    exclude = ('request_files', 'files',)
    readonly_fields = ('first_1000_files', 'request_patterns', 'first_1000_request_files', 'storaged_request_start', 'storaged_request_end', 'first_files_on_disk', 'last_files_on_disk')
admin.site.register(TapeRequest, TapeReqAdmin)

class QuotaAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('user', 'formatted_size', 'email_address')
    search_fields = ('user',)
admin.site.register(Quota, QuotaAdmin)

class SlotAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('pk', 'tape_request', 'pid', 'host_ip')
    search_fields = ('pk', 'tape_request',)
    readonly_fields = ('tape_request', 'pid', 'host_ip', 'request_dir')
    
admin.site.register(StorageDSlot, SlotAdmin)

class RestoreDiskAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('mountpoint', 'formatted_allocated', 'formatted_used')
    search_fields = ('mountpoint',)
#    readonly_fields = ('used_bytes',)
admin.site.register(RestoreDisk, RestoreDiskAdmin)
