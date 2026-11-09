"""One predictable error envelope for the whole API.

Every failure looks like:
    {"detail": "...", "errors": {"field": ["message"]}}

so the React client has exactly one error path to handle.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, DjangoValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return _envelope({"detail": "Validation failed.", "errors": detail}, 400)
        if isinstance(exc, IntegrityError):
            return _envelope(
                {"detail": "That change conflicts with existing data "
                           "(duplicate code, email, or a related record still in use).",
                 "errors": {}},
                400,
            )
        return None  # let Django return a 500 and log the traceback

    data = response.data
    if isinstance(data, dict) and "detail" not in data:
        # serializer field errors -> {"field": ["msg"]}
        response.data = {
            "detail": "Please correct the highlighted fields.",
            "errors": {k: v if isinstance(v, list) else [v] for k, v in data.items()},
        }
    elif isinstance(data, dict):
        response.data = {"detail": str(data.get("detail", "")), "errors": {}}
    else:
        response.data = {"detail": str(data), "errors": {}}
    return response


def _envelope(payload, status_code):
    from rest_framework.response import Response

    return Response(payload, status=status_code)
