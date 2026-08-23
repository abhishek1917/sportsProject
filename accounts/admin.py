from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse


class UserAdmin(BaseUserAdmin):
    def response_add(self, request, obj, post_url_continue=None):
        if "_addanother" not in request.POST and "_continue" not in request.POST:
            self.message_user(request, f"User “{obj.username}” was created successfully.")
            return HttpResponseRedirect(reverse("admin:auth_user_change", args=[obj.pk]))
        return super().response_add(request, obj, post_url_continue)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
