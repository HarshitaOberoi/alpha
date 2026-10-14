from django.contrib import admin

from .models import CapitalCall, LineItem, Match, Organization, Transaction

admin.site.register(Organization)
admin.site.register(CapitalCall)
admin.site.register(LineItem)
admin.site.register(Transaction)
admin.site.register(Match)
