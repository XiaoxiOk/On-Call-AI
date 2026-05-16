from fastapi import Request

from app.services.runtime import ApplicationServices


def get_services(request: Request) -> ApplicationServices:
    return request.app.state.services
