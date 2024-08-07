import copy
import json
import logging
import traceback
from typing import Dict
from typing import Optional
from urllib.parse import urljoin

from pydantic import ValidationError
from scim2_models import AuthenticationScheme
from scim2_models import Bulk
from scim2_models import ChangePassword
from scim2_models import Context
from scim2_models import Error
from scim2_models import ETag
from scim2_models import Filter
from scim2_models import ListResponse
from scim2_models import Meta
from scim2_models import Patch
from scim2_models import PatchOp
from scim2_models import Resource
from scim2_models import ResourceType
from scim2_models import Schema
from scim2_models import SearchRequest
from scim2_models import ServiceProviderConfig
from scim2_models import Sort
from werkzeug import Request
from werkzeug import Response
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound
from werkzeug.exceptions import NotImplemented as WerkzeugNotImplemented
from werkzeug.exceptions import PreconditionFailed
from werkzeug.exceptions import Unauthorized
from werkzeug.http import unquote_etag
from werkzeug.routing import Map
from werkzeug.routing import Rule
from werkzeug.routing.exceptions import RequestRedirect

from scim_provider.backend import Backend
from scim_provider.operators import patch_resource
from scim_provider.utils import SCIMException
from scim_provider.utils import merge_resources


class SCIMProvider:
    """A WSGI application implementing a SCIM provider (server)."""

    def __init__(self, backend: Backend):
        self.bearer_tokens = set()
        self.backend = backend
        self.page_size = 50
        self.log = logging.getLogger("SCIMProvider")

        # Register the URL mapping. The endpoint refers to the name of the function to be called in this SCIMProvider ("call_" + endpoint).
        self.url_map = Map(
            [
                Rule(
                    "/v2/ServiceProviderConfig",
                    endpoint="service_provider_config",
                    methods=("GET",),
                ),
                Rule(
                    "/v2/ResourceTypes",
                    endpoint="resource_types",
                    methods=("GET",),
                ),
                Rule(
                    "/v2/ResourceTypes/<string:resource_type>",
                    endpoint="resource_type",
                    methods=("GET",),
                ),
                Rule(
                    "/v2/Schemas",
                    endpoint="schemas",
                    methods=("GET",),
                ),
                Rule(
                    "/v2/Schemas/<string:schema_id>",
                    endpoint="schema",
                    methods=("GET",),
                ),
                Rule(
                    "/v2/Me",
                    endpoint="me",
                    methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
                ),
                Rule(
                    "/v2/<string:resource_endpoint>",
                    endpoint="resource",
                    methods=("GET", "POST"),
                ),
                Rule(
                    "/v2/<string:resource_endpoint>/.search",
                    endpoint="resource_search",
                    methods=("POST",),
                ),
                Rule(
                    "/v2/<string:resource_endpoint>/<string:resource_id>",
                    endpoint="single_resource",
                    methods=("GET", "PUT", "PATCH", "DELETE"),
                ),
                Rule(
                    "/v2/Bulk",
                    endpoint="bulk",
                    methods=("POST",),
                ),
                Rule("/v2/", endpoint="query_all", methods=("GET",)),
                Rule("/v2/.search", endpoint="query_all", methods=("POST",)),
            ]
        )

    @staticmethod
    def adjust_location(
        request: Request, resource: Resource, cp=False
    ) -> Optional[Resource]:
        """Adjusts the "meta.location" attribute of a resource to match the
        hostname the client used to access this server. If a static URL is
        used,

        :param request: The werkzeug request object
        :param resource: The resource to modify
        :param cp: Whether or not to return a modified copy of the
            resource or to modify the resource in-place.
        """
        location = urljoin(request.url + "/", resource.meta.location)
        if cp:
            obj = resource.model_copy(deep=True)
            obj.meta.location = location
            return obj

        resource.meta.location = location

    def apply_patch_operation(self, resource: Resource, patch_operation: PatchOp):
        """Applies a PATCH operation to a resource."""
        for op in patch_operation.operations:
            patch_resource(resource, op)

    @staticmethod
    def continue_etag(request: Request, resource: Resource) -> bool:
        """Given a request and a resource, checks whether the ETag matches and
        allows continuing with the request.

        If the HTTP header "If-Match" is set, the request may only
        continue if the ETag matches. If the HTTP header "If-None-Match"
        is set, the request may only continue if the ETag does not
        match.
        """
        cont = True
        resource_version, _ = unquote_etag(resource.meta.version)
        if request.if_none_match:
            cont &= not request.if_none_match.contains_weak(resource_version)
        if request.if_match:
            cont &= request.if_match.contains_weak(resource_version)
        return cont

    def call_single_resource(
        self, request: Request, resource_endpoint: str, resource_id: str, **kwargs
    ):
        find_endpoint = "/" + resource_endpoint
        resource_type = self.backend.get_resource_type_by_endpoint(find_endpoint)
        if not resource_type:
            raise NotFound

        match request.method:
            case "GET":
                if resource := self.backend.get_resource(resource_type.id, resource_id):
                    if self.continue_etag(request, resource):
                        response_args = self.get_attrs_from_request(request)
                        self.adjust_location(request, resource)
                        return self.make_response(
                            resource.model_dump(
                                scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
                                **response_args,
                            )
                        )
                    else:
                        return self.make_response(None, status=304)
                raise NotFound
            case "DELETE":
                if self.backend.delete_resource(resource_type.id, resource_id):
                    return self.make_response(None, 204)
                else:
                    raise NotFound
            case "PUT":
                response_args = self.get_attrs_from_request(request)
                resource = self.backend.get_resource(resource_type.id, resource_id)
                if resource is None:
                    raise NotFound
                if not self.continue_etag(request, resource):
                    raise PreconditionFailed

                updated_attributes = self.backend.get_model(
                    resource_type.id
                ).model_validate(request.json)
                merge_resources(resource, updated_attributes)
                updated = self.backend.update_resource(resource_type.id, resource)
                return self.make_response(
                    updated.model_dump(
                        scim_ctx=Context.RESOURCE_REPLACEMENT_RESPONSE,
                        **response_args,
                    )
                )
            case _:  # "PATCH"
                payload = request.json
                # MS Entra sometimes passes a "id" attribute
                if "id" in payload:
                    del payload["id"]
                operations = payload.get("Operations", [])
                for operation in operations:
                    if "name" in operation:
                        # MS Entra sometimes passes a "name" attribute
                        del operation["name"]

                patch_operation = PatchOp.model_validate(payload)
                response_args = self.get_attrs_from_request(request)
                resource = self.backend.get_resource(resource_type.id, resource_id)
                if resource is None:
                    raise NotFound
                if not self.continue_etag(request, resource):
                    raise PreconditionFailed

                self.apply_patch_operation(resource, patch_operation)
                updated = self.backend.update_resource(resource_type.id, resource)

                if response_args:
                    return self.make_response(
                        updated.model_dump(
                            scim_ctx=Context.RESOURCE_REPLACEMENT_RESPONSE,
                            **response_args,
                        )
                    )
                else:
                    # RFC 7644, section 3.5.2:
                    # A PATCH operation MAY return a 204 (no content)
                    # if no attributes were requested
                    return self.make_response(
                        None, 204, headers={"ETag": updated.meta.version}
                    )

    @staticmethod
    def get_attrs_from_request(request: Request) -> Dict:
        """Parses the "attributes" an "excludedAttributes" HTTP request
        parameters."""
        ret = {}
        if "attributes" in request.args:
            ret["attributes"] = [
                a.strip() for a in request.args["attributes"].split(",")
            ]
        if "excludedAttributes" in request.args:
            ret["excluded_attributes"] = [
                a.strip() for a in request.args["excludedAttributes"].split(",")
            ]
        if "attributes" in ret and "excluded_attributes" in ret:
            # RFC 7644, Section 3.9
            # attributes and excludedAttributes are mutually exclusive
            raise BadRequest
        return ret

    def build_search_request(self, request: Request):
        """Constructs a SearchRequest object from a werkzeug request.

        :param request: werkzeug request
        :return: SearchRequest instance
        """
        if request.method == "POST":
            # This was a POST against /.search, see RFC 7644, Section 3.4.3
            return SearchRequest.model_validate(
                request.json, scim_ctx=Context.SEARCH_REQUEST
            )
        count = min(int(request.args.get("count", self.page_size)), self.page_size)
        start_index = max(1, int(request.args.get("startIndex", 1)))
        search_request = SearchRequest(
            start_index=start_index,
            count=count,
            filter=request.args.get("filter"),
        )
        if "attributes" in request.args:
            search_request.attributes = [
                a.strip() for a in request.args["attributes"].split(",")
            ]
        if "excludedAttributes" in request.args:
            search_request.excluded_attributes = [
                a.strip() for a in request.args["excludedAttributes"].split(",")
            ]
        if "sortBy" in request.args:
            search_request.sort_by = request.args["sortBy"]
        if request.args.get("sortOrder") == "descending":
            search_request.sort_order = SearchRequest.SortOrder.descending
        return search_request

    def query_resource(self, request: Request, resource: Optional[ResourceType]):
        search_request = self.build_search_request(request)
        if search_request.attributes and search_request.excluded_attributes:
            # RFC 7644, Section 3.4.2.5
            raise BadRequest

        kwargs = {}
        if resource is not None:
            kwargs["resource_type_id"] = resource.id
        total_results, results = self.backend.query_resources(
            search_request=search_request, **kwargs
        )
        for r in results:
            self.adjust_location(request, r)

        resources = [
            s.model_dump(
                scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
                attributes=search_request.attributes,
                excluded_attributes=search_request.excluded_attributes,
            )
            for s in results
        ]

        return ListResponse.of(*self.backend.get_models())(
            total_results=total_results,
            items_per_page=search_request.count,
            start_index=search_request.start_index,
            resources=resources,
        )

    def call_resource(self, request: Request, resource_endpoint: str, **kwargs):
        resource_type = self.backend.get_resource_type_by_endpoint(
            "/" + resource_endpoint
        )
        if not resource_type:
            raise NotFound

        match request.method:
            case "GET":
                return self.make_response(
                    self.query_resource(request, resource_type).model_dump(
                        scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
                    )
                )
            case _:  # "POST"
                payload = request.json
                resource = self.backend.get_model(resource_type.id).model_validate(
                    payload, scim_ctx=Context.RESOURCE_CREATION_REQUEST
                )
                created_resource = self.backend.create_resource(
                    resource_type.id,
                    resource,
                )
                self.adjust_location(request, created_resource)
                return self.make_response(
                    created_resource.model_dump(
                        scim_ctx=Context.RESOURCE_CREATION_RESPONSE
                    ),
                    status=201,
                    headers={"Location": created_resource.meta.location},
                )

    def call_query_all(self, request: Request, **kwargs):
        return self.make_response(
            self.query_resource(request, None).model_dump(
                scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
            )
        )

    def call_resource_search(self, request: Request, resource_endpoint: str, **kwargs):
        resource_type = self.backend.get_resource_type_by_endpoint(
            "/" + resource_endpoint
        )
        if not resource_type:
            raise NotFound
        return self.make_response(
            self.query_resource(request, resource_type).model_dump(
                scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
            )
        )

    def call_me(self, request: Request, **kwargs):
        """Called for the /Me-Endpoint.

        RFC 7644, Section 3.11 allows raising a 501 (Not Implemented) if
        the endpoint does not provide this feature.
        """
        raise WerkzeugNotImplemented

    def register_schema(self, schema: Schema):
        self.backend.register_schema(schema)

    def register_resource_type(self, resource_type: ResourceType):
        self.backend.register_resource_type(resource_type)

    def register_bearer_token(self, token: str):
        """Registers a static bearer token for authentication.

        :param token: Bearer token
        """
        self.bearer_tokens.add(token)

    def check_auth(self, request: Request):
        """Checks the authorization headers."""
        if not self.bearer_tokens:
            return
        if (
            not request.authorization
            or request.authorization.token not in self.bearer_tokens
        ):
            raise Unauthorized

    @staticmethod
    def make_response(content, status=200, **kwargs):
        """Constructs a werkzeug response from any JSON-serializable
        content."""
        etag = None
        if content is not None:
            etag = content.get("meta", {}).get("version")
            content = json.dumps(content)
        kwargs.setdefault("headers", {})
        if etag:
            kwargs["headers"].setdefault("ETag", etag)
        kwargs["headers"].setdefault("Cache-Control", "no-cache")
        kwargs["headers"].setdefault("Server", "scim-provider")
        return Response(
            content,
            status=status,
            content_type="application/scim+json",
            **kwargs,
        )

    def make_error(self, error: Error):
        """Constructs a werkzeug response from a SCIM Error."""
        return self.make_response(error.model_dump(), status=int(error.status))

    @staticmethod
    def forbid_filter(request: Request):
        """RFC 7644, Section 4: "If a "filter" is provided, the service
        provider SHOULD respond with HTTP status code 403 (Forbidden)"."""
        if "filter" in request.args:
            raise Forbidden

    def call_service_provider_config(self, request, **kwargs):
        """Returns the ServiceProviderConfig."""
        self.forbid_filter(request)
        auth_scheme = (
            []
            if not self.bearer_tokens
            else [
                AuthenticationScheme(
                    type="oauthbearertoken",
                    name="bearer_token",
                    description="HTTP Bearer Token",
                    spec_uri="https://datatracker.ietf.org/doc/html/rfc6750",
                )
            ]
        )
        return self.make_response(
            ServiceProviderConfig(
                documentation_uri="https://www.example.com/",
                patch=Patch(supported=True),
                bulk=Bulk(supported=False),
                filter=Filter(supported=True, max_results=1000),
                change_password=ChangePassword(supported=True),
                sort=Sort(supported=True),
                etag=ETag(supported=True),
                authentication_schemes=auth_scheme,
                meta=Meta(
                    resource_type="ServiceProviderConfig",
                    location=request.url,
                ),
            ).model_dump()
        )

    def call_resource_type(self, request, resource_type: str, **kwargs):
        """Returns a single resource type."""
        self.forbid_filter(request)
        if res := self.backend.get_resource_type(resource_type):
            cp = copy.copy(res)
            cp.meta.location = request.url
            return self.make_response(cp.model_dump())
        raise NotFound

    def call_schema(self, request, schema_id: str):
        """Returns a single schema."""
        self.forbid_filter(request)
        if res := self.backend.get_schema(schema_id):
            cp = copy.copy(res)
            cp.meta.location = request.url
            return self.make_response(cp.model_dump())
        raise NotFound

    def call_resource_types(self, request, **kwargs):
        """Returns a ListResponse of all known resource types."""
        self.forbid_filter(request)
        results = self.backend.get_resource_types()
        resp = ListResponse.of(ResourceType)(
            total_results=len(results),
            items_per_page=len(results),
            start_index=1,
            resources=[self.adjust_location(request, s, True) for s in results],
        ).model_dump()
        return self.make_response(resp)

    def call_schemas(self, request, **kwargs):
        """Returns a ListResponse of all known schemas."""
        self.forbid_filter(request)
        results = self.backend.get_schemas()
        resp = ListResponse.of(Schema)(
            total_results=len(results),
            items_per_page=len(results),
            start_index=1,
            resources=[self.adjust_location(request, s, True) for s in results],
        ).model_dump()
        return self.make_response(resp)

    def wsgi_app(self, request, environ):
        try:
            if environ.get("PATH_INFO", "").endswith(".scim"):
                # RFC 7644, Section 3.8
                # Just strip .scim suffix, the provider always returns application/scim+json
                environ["PATH_INFO"], _, _ = environ["PATH_INFO"].rpartition(".scim")
            urls = self.url_map.bind_to_environ(environ)
            endpoint, args = urls.match()

            if endpoint != "service_provider_config":
                # RFC7643, Section 5: skip authentication for ServiceProviderConfig
                self.check_auth(request)

            # Wrap the entire call in a transaction. Should probably be optimized (use transaction only when necessary).
            with self.backend:
                response = getattr(self, f"call_{endpoint}")(request, **args)
            return response
        except RequestRedirect as e:
            # urls.match may cause a redirect, handle it as a special case of HTTPException
            self.log.exception(e)
            return e.get_response(environ)
        except HTTPException as e:
            self.log.exception(e)
            return self.make_error(Error(status=e.code, detail=e.description))
        except SCIMException as e:
            self.log.exception(e)
            return self.make_error(e.scim_error)
        except ValidationError as e:
            self.log.exception(e)
            return self.make_error(Error(status=400, detail=str(e)))
        except Exception as e:
            self.log.exception(e)
            tb = traceback.format_exc()
            return self.make_error(Error(status=500, detail=str(e) + "\n" + tb))

    def __call__(self, environ, start_response):
        """The actual WSGI server implementation."""
        request = Request(environ)
        response = self.wsgi_app(request, environ)
        if "Location" not in response.headers:
            # The spec is not explicit about requiring the "Location" header in all responses,
            # but the examples in RFC 7644 include the "Location" header even for responses that
            # did not create a new resource
            response.headers.add("Location", request.url)
        if self.bearer_tokens and not request.authorization:
            # RFC 7644, Section 2
            response.headers.add("WWW-Authenticate", 'Bearer realm="SCIM Provider"')
        return response(environ, start_response)
