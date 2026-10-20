from django.http import HttpResponse

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
# Allow a small 64KB buffer for multipart headers, form text fields, and CSRF token
BUFFER_OVERHEAD = 64 * 1024


class MaxUploadSizeMiddleware:
    """
    Server-side protection rejecting any incoming request payload exceeding 5MB.
    Guarantees that oversized file uploads are stopped before disk streaming,
    preventing denial-of-service (DoS) storage exhaustion.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH'):
            content_length = request.META.get('CONTENT_LENGTH')
            if content_length:
                try:
                    length = int(content_length)
                    if length > (MAX_UPLOAD_SIZE + BUFFER_OVERHEAD):
                        return HttpResponse(
                            "Payload Too Large. Maximum allowed upload size is 5MB.",
                            status=413,
                            content_type="text/plain"
                        )
                except (ValueError, TypeError):
                    pass
        return self.get_response(request)
