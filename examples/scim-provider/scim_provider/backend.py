import dataclasses
import datetime
import operator
import pickle
import uuid
from threading import Lock
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from scim2_filter_parser import lexer
from scim2_filter_parser.parser import SCIMParser
from scim2_models import Attribute
from scim2_models import BaseModel
from scim2_models import CaseExact
from scim2_models import Error
from scim2_models import Meta
from scim2_models import Resource
from scim2_models import ResourceType
from scim2_models import Schema
from scim2_models import SearchRequest
from scim2_models import Uniqueness
from werkzeug.http import generate_etag

from scim_provider.filter import evaluate_filter
from scim_provider.operators import ResolveSortOperator
from scim_provider.utils import SCIMException
from scim_provider.utils import get_by_alias


class Backend:
    """The base class for a SCIM provider backend."""

    def __init__(self):
        self.schemas: Dict[str, Schema] = {}
        self.resource_types: Dict[str, ResourceType] = {}
        self.resource_types_by_endpoint: Dict[str, ResourceType] = {}
        self.models_dict: Dict[str, BaseModel] = {}

    def __enter__(self):
        """Allows the backend to be used as a context manager.

        This enables support for transactions.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the transaction."""
        pass

    def register_schema(self, schema: Schema):
        """Registers a Schema for use with the backend."""
        self.schemas[schema.id] = schema

    def get_schemas(self):
        """Returns all schemas registered with the backend."""
        return self.schemas.values()

    def get_schema(self, schema_id: str) -> Optional[Schema]:
        """Gets a schema by its id."""
        return self.schemas.get(schema_id)

    def register_resource_type(self, resource_type: ResourceType):
        """Registers a ResourceType for use with the backend.

        The schemas used for the resource and its extensions must have
        been registered with the Backend beforehand.
        """
        if resource_type.schema_ not in self.schemas:
            raise RuntimeError(f"Unknown schema: {resource_type.schema_}")
        for resource_extension in resource_type.schema_extensions or []:
            if resource_extension.schema_ not in self.schemas:
                raise RuntimeError(f"Unknown schema: {resource_extension.schema_}")

        self.resource_types[resource_type.id] = resource_type
        self.resource_types_by_endpoint[resource_type.endpoint.lower()] = resource_type

        extensions = [
            self.get_schema(se.schema_).make_model()
            for se in resource_type.schema_extensions or []
        ]
        base_schema = self.get_schema(resource_type.schema_)
        self.models_dict[resource_type.id] = base_schema.make_model()
        if extensions:
            self.models_dict[resource_type.id] = self.models_dict[resource_type.id][
                Union[*extensions]
            ]

    def get_resource_types(self):
        """Returns all resource types registered with the backend."""
        return self.resource_types.values()

    def get_resource_type(self, resource_type_id: str) -> Optional[ResourceType]:
        """Returns the resource type by its id."""
        return self.resource_types.get(resource_type_id)

    def get_resource_type_by_endpoint(self, endpoint: str) -> Optional[ResourceType]:
        """Returns the resource type by its endpoint."""
        return self.resource_types_by_endpoint.get(endpoint.lower())

    def get_model(self, resource_type_id: str) -> Optional[BaseModel]:
        """Returns the Pydantic Python model for a given resource type."""
        return self.models_dict.get(resource_type_id)

    def get_models(self):
        """Returns all Pydantic Python models for all known resource types."""
        return self.models_dict.values()

    def query_resources(
        self,
        search_request: SearchRequest,
        resource_type_id: Optional[str] = None,
    ) -> Tuple[int, List[Resource]]:
        """Queries the backend for a set of resources.

        :param search_request: SearchRequest instance describing the
            query.
        :param resource_type_id: ID of the resource type to query. If
            None, all resource types are queried.
        :return: A tuple of "total results" and a List of found
            Resources. The List must contain a copy of resources.
            Mutating elements in the List must not modify the data
            stored in the backend.
        :raises SCIMException: If the backend only supports querying for
            one resource type at a time, setting resource_type_id to
            None the backend may raise a
            SCIMException(Error.make_too_many_error()).
        """
        raise NotImplementedError

    def get_resource(self, resource_type_id: str, object_id: str) -> Optional[Resource]:
        """Queries the backend for a resources by its ID.

        :param resource_type_id: ID of the resource type to get the
            object from.
        :param object_id: ID of the object to get.
        :return: The resource object if it exists, None otherwise. The
            resource must be a copy, modifying it must not change the
            data stored in the backend.
        """
        raise NotImplementedError

    def delete_resource(self, resource_type_id: str, object_id: str) -> bool:
        """Deletes a resource.

        :param resource_type_id: ID of the resource type to delete the
            object from.
        :param object_id: ID of the object to delete.
        :return: True if the resource was deleted, False otherwise.
        """
        raise NotImplementedError

    def create_resource(
        self, resource_type_id: str, resource: Resource
    ) -> Optional[Resource]:
        """Creates a resource.

        :param resource_type_id: ID of the resource type to create.
        :param resource: Resource to create.
        :return: The created resource. Creation should set system-
            defined attributes (ID, Metadata). May be the same object
            that is passed in.
        """
        raise NotImplementedError

    def update_resource(
        self, resource_type_id: str, resource: Resource
    ) -> Optional[Resource]:
        """Updates a resource. The resource is identified by its ID.

        :param resource_type_id: ID of the resource type to update.
        :param resource: Resource to update.
        :return: The updated resource. Updating should update the
            "meta.lastModified" data. May be the same object that is
            passed in.
        """
        raise NotImplementedError


class InMemoryBackend(Backend):
    """This is an example in-memory backend for the SCIM provider.

    It is not optimized for performance. Many operations are O(n) or
    worse, whereas they would perform better with an actual production
    database in the backend. This is intentional to keep the
    implementation simple.
    """

    @dataclasses.dataclass
    class UniquenessDescriptor:
        """Used to mimic uniqueness constraints e.g. from a SQL database."""

        schema: Optional[str]
        attribute_name: str
        case_exact: bool

        def get_attribute(self, resource: Resource):
            if self.schema is not None:
                resource = getattr(resource, get_by_alias(resource, self.schema))
            result = getattr(resource, get_by_alias(resource, self.attribute_name))
            if not self.case_exact:
                result = result.lower()
            return result

    @classmethod
    def collect_unique_attrs(
        cls, attributes: List[Attribute], schema: Optional[str]
    ) -> List[UniquenessDescriptor]:
        ret = []
        for attr in attributes:
            if attr.uniqueness != Uniqueness.none:
                ret.append(
                    cls.UniquenessDescriptor(
                        schema, attr.name, attr.case_exact == CaseExact.true
                    )
                )
        return ret

    @classmethod
    def collect_resource_unique_attrs(
        cls, resource_type: ResourceType, schemas: Dict[str, Schema]
    ) -> List[List[UniquenessDescriptor]]:
        ret = cls.collect_unique_attrs(schemas[resource_type.schema_].attributes, None)
        for extension in resource_type.schema_extensions or []:
            ret.extend(
                InMemoryBackend.collect_unique_attrs(
                    schemas[extension.schema_].attributes, extension.schema_
                )
            )
        return ret

    def __init__(self):
        super().__init__()
        self.resources: List[Resource] = []
        self.unique_attributes: Dict[str, List[List[str]]] = {}
        self.lock: Lock = Lock()

    def __enter__(self):
        """See super docs.

        The InMemoryBackend uses a simple Lock to synchronize all
        access.
        """
        super().__enter__()
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        self.lock.release()

    def register_resource_type(self, resource_type: ResourceType):
        super().register_resource_type(resource_type)
        self.unique_attributes[resource_type.id] = self.collect_resource_unique_attrs(
            resource_type, self.schemas
        )

    def query_resources(
        self,
        search_request: SearchRequest,
        resource_type_id: Optional[str] = None,
    ) -> Tuple[int, List[Resource]]:
        start_index = (search_request.start_index or 1) - 1

        tree = None
        if search_request.filter is not None:
            token_stream = lexer.SCIMLexer().tokenize(search_request.filter)
            tree = SCIMParser().parse(token_stream)

        found_resources = [
            r
            for r in self.resources
            if (resource_type_id is None or r.meta.resource_type == resource_type_id)
            and (tree is None or evaluate_filter(r, tree))
        ]

        if search_request.sort_by is not None:
            descending = search_request.sort_order == SearchRequest.SortOrder.descending
            sort_operator = ResolveSortOperator(search_request.sort_by)

            # To ensure that unset attributes are sorted last (when ascending, as defined in the RFC),
            # we have to divide the result set into a set and unset subset.
            unset_values = []
            set_values = []
            for resource in found_resources:
                result = sort_operator(resource)
                if result is None:
                    unset_values.append(resource)
                else:
                    set_values.append((resource, result))

            set_values.sort(key=operator.itemgetter(1), reverse=descending)
            set_values = [value[0] for value in set_values]
            if descending:
                found_resources = unset_values + set_values
            else:
                found_resources = set_values + unset_values

        found_resources = found_resources[start_index:]
        if search_request.count is not None:
            found_resources = found_resources[: search_request.count]
        return len(found_resources), found_resources

    def _get_resource_idx(self, resource_type_id: str, object_id: str) -> Optional[int]:
        return next(
            (
                idx
                for idx, r in enumerate(self.resources)
                if r.meta.resource_type == resource_type_id and r.id == object_id
            ),
            None,
        )

    def get_resource(self, resource_type_id: str, object_id: str) -> Optional[Resource]:
        resource_dict_idx = self._get_resource_idx(resource_type_id, object_id)
        if resource_dict_idx is not None:
            return self.resources[resource_dict_idx].model_copy(deep=True)
        return None

    def delete_resource(self, resource_type_id: str, object_id: str) -> bool:
        found = self.get_resource(resource_type_id, object_id)
        if found:
            self.resources = [
                r
                for r in self.resources
                if not (r.meta.resource_type == resource_type_id and r.id == object_id)
            ]
            return True
        return False

    def create_resource(
        self, resource_type_id: str, resource: Resource
    ) -> Optional[Resource]:
        resource = resource.model_copy(deep=True)
        resource.id = uuid.uuid4().hex
        utcnow = datetime.datetime.now(datetime.UTC)
        resource.meta = Meta(
            resource_type=resource_type_id,
            created=utcnow,
            last_modified=utcnow,
            location="/v2"
            + self.resource_types[resource_type_id].endpoint
            + "/"
            + resource.id,
        )
        self._touch_resource(resource, utcnow)

        for unique_attribute in self.unique_attributes[resource_type_id]:
            new_value = unique_attribute.get_attribute(resource)
            for existing_resource in self.resources:
                if existing_resource.meta.resource_type == resource_type_id:
                    existing_value = unique_attribute.get_attribute(existing_resource)
                    if existing_value == new_value:
                        raise SCIMException(Error.make_uniqueness_error())

        self.resources.append(resource)
        return resource

    @staticmethod
    def _touch_resource(resource: Resource, last_modified: datetime.datetime):
        """Touches a resource (updates last_modified and version).

        Version is generated by hashing last_modified. Another option
        would be to hash the entire resource instead.
        """
        resource.meta.last_modified = last_modified
        etag = generate_etag(pickle.dumps(resource.meta.last_modified))
        resource.meta.version = f'W/"{etag}"'

    def update_resource(
        self, resource_type_id: str, resource: Resource
    ) -> Optional[Resource]:
        found_res_idx = self._get_resource_idx(resource_type_id, resource.id)
        if found_res_idx is not None:
            updated_resource = self.models_dict[resource_type_id].model_validate(
                resource.model_dump()
            )
            self._touch_resource(updated_resource, datetime.datetime.now(datetime.UTC))

            for unique_attribute in self.unique_attributes[resource_type_id]:
                new_value = unique_attribute.get_attribute(updated_resource)
                for existing_resource in self.resources:
                    if (
                        existing_resource.meta.resource_type == resource_type_id
                        and existing_resource.id != updated_resource.id
                    ):
                        existing_value = unique_attribute.get_attribute(
                            existing_resource
                        )
                        if existing_value == new_value:
                            raise SCIMException(Error.make_uniqueness_error())

            self.resources[found_res_idx] = updated_resource
            return updated_resource
        return None
