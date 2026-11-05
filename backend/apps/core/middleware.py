from django.http import JsonResponse


class LivenessMiddleware:
    """Answer `GET /health` before host validation and the HTTPS redirect.

    Platform health checks (e.g. Render's) come from inside the platform's network over plain
    HTTP, often with an internal Host header, so they would otherwise get a 400 (DisallowedHost)
    or a redirect. The response is static and touches no data, so exposing it to any host is
    harmless. `/ready`, which checks the database and cache, still goes through the full stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/health" and request.method == "GET":
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
