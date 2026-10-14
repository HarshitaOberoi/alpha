from django.http import JsonResponse

from .models import Organization

# Paths that do not require the X-Organization header.
EXEMPT_PREFIXES = ("/admin/", "/static/")


class OrganizationScopeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        slug = request.headers.get("X-Organization")
        if not slug:
            return JsonResponse(
                {"error": "Missing X-Organization header."}, status=400
            )
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": f"Organization '{slug}' not found."}, status=404
            )
        request.organization = org
        return self.get_response(request)
