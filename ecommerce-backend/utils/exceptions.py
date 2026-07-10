from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    # Call DRF's default handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Reformat all DRF errors into a consistent structure
        error_message = response.data

        if isinstance(response.data, dict):
            # Extract first error message if it's a dict
            errors = []
            for key, value in response.data.items():
                if isinstance(value, list):
                    errors.append(f"{key}: {value[0]}")
                else:
                    errors.append(f"{key}: {value}")
            error_message = " | ".join(errors)

        elif isinstance(response.data, list):
            error_message = response.data[0]

        response.data = {"error": error_message}

    else:
        # Handle unexpected server errors
        response = Response(
            {"error": "Something went wrong. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response