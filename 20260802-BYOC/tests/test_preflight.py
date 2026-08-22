from scripts.preflight import check_gcs_object_access, check_service_usage


class Response:
    status_code = 200

    def json(self):
        return {"permissions": ["serviceusage.services.use"]}


class ForbiddenResponse:
    status_code = 403


class Session:
    def post(self, endpoint, **kwargs):
        self.endpoint = endpoint
        self.kwargs = kwargs
        return Response()


class ForbiddenSession(Session):
    def post(self, endpoint, **kwargs):
        return ForbiddenResponse()


class Blob:
    def exists(self):
        return True


class Bucket:
    def blob(self, name):
        self.name = name
        return Blob()


class Storage:
    def bucket(self, name):
        return Bucket()


def test_preflight_separates_gcs_and_service_usage_permissions():
    gcs = check_gcs_object_access(Storage(), "gs://bucket/input.json")
    service_usage = check_service_usage(Session(), "project")
    assert gcs == {"ok": True, "permission": "storage.objects.get", "exists": True}
    assert service_usage["ok"] is True
    assert service_usage["permission"] == "serviceusage.services.use"


def test_preflight_reports_missing_service_usage_without_response_body():
    result = check_service_usage(ForbiddenSession(), "project")
    assert result == {"ok": False, "permission": "serviceusage.services.use", "http_status": 403}
