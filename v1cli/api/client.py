"""VersionOne API client."""

from typing import Any

import httpx

from v1cli.api.models import DeliveryGroup, Feature, Member, Project, StatusInfo, Story, Task
from v1cli.config.auth import get_auth_token, get_v1_url, get_verify_ssl


class V1APIError(Exception):
    """Raised when a V1 API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class V1Client:
    """Async client for VersionOne REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        verify_ssl: bool | None = None,
    ):
        """Initialize the client.

        Args:
            base_url: V1 instance URL (defaults to V1_URL env var)
            token: API token (defaults to V1_TOKEN env var)
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certs (defaults to V1_VERIFY_SSL env var)
        """
        self.base_url = base_url or get_v1_url()
        self.token = token or get_auth_token()
        self.timeout = timeout
        self.verify_ssl = verify_ssl if verify_ssl is not None else get_verify_ssl()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "V1Client":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in context."""
        if self._client is None:
            raise RuntimeError("V1Client must be used as async context manager")
        return self._client

    async def _query(
        self,
        asset_type: str,
        select: list[str],
        filter_: list[str] | None = None,
        where: dict[str, str] | None = None,
        sort: list[str] | None = None,
        page_size: int | None = None,
        page_start: int = 0,
    ) -> list[dict[str, Any]]:
        """Execute a query against the V1 query API.

        Args:
            asset_type: The asset type to query (e.g., 'Story', 'Epic')
            select: Attributes to retrieve
            filter_: Filter conditions
            where: Equality conditions
            sort: Sort order
            page_size: Max results to return
            page_start: Starting offset

        Returns:
            List of result dictionaries
        """
        payload: dict[str, Any] = {
            "from": asset_type,
            "select": select,
        }
        if filter_:
            payload["filter"] = filter_
        if where:
            payload["where"] = where
        if sort:
            payload["sort"] = sort
        if page_size:
            payload["page"] = {"start": str(page_start), "size": str(page_size)}

        response = await self.client.post("/query.v1", json=payload)
        self._check_response(response)

        data = response.json()
        # query.v1 returns nested arrays
        if isinstance(data, list) and len(data) > 0:
            return data[0] if isinstance(data[0], list) else data
        return []

    async def _create(self, asset_type: str, data: dict[str, Any]) -> str:
        """Create a new asset.

        Args:
            asset_type: The asset type to create
            data: Asset attributes

        Returns:
            The OID of the created asset
        """
        payload = {"AssetType": asset_type, **data}
        response = await self.client.post("/api/asset", json=payload)
        self._check_response(response)

        result = response.json()
        return result.get("oid", result.get("id", ""))

    async def _update(self, oid: str, data: dict[str, Any]) -> bool:
        """Update an existing asset.

        Args:
            oid: The asset OID
            data: Attributes to update

        Returns:
            True if successful
        """
        payload = {"from": oid, "update": data}
        response = await self.client.post("/api/asset", json=payload)
        self._check_response(response)
        return True

    def _check_response(self, response: httpx.Response) -> None:
        """Check response for errors and raise if needed."""
        if response.status_code == 401:
            raise V1APIError("Authentication failed. Check your V1_TOKEN.", 401)
        if response.status_code == 404:
            raise V1APIError("Resource not found.", 404)
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", str(error_data))
            except Exception:
                message = response.text
            raise V1APIError(f"API error: {message}", response.status_code)

    async def get_meta(self, asset_type: str) -> dict[str, Any]:
        """Get schema metadata for an asset type.

        Args:
            asset_type: The asset type (e.g., 'Epic', 'Story', 'Task')

        Returns:
            Dictionary with asset type metadata including attributes
        """
        response = await self.client.get(
            f"/meta.v1/{asset_type}",
            headers={"Accept": "application/json"},
        )
        self._check_response(response)
        return response.json()

    async def get_asset_attributes(self, asset_type: str) -> list[dict[str, Any]]:
        """Get available attributes for an asset type.

        Args:
            asset_type: The asset type (e.g., 'Epic', 'Story', 'Task')

        Returns:
            List of attribute definitions with name, type, and other metadata
        """
        meta = await self.get_meta(asset_type)
        attributes = []

        for attr_name, attr_data in meta.get("Attributes", {}).items():
            # Skip internal/system attributes
            if attr_name.startswith("_"):
                continue

            attributes.append({
                "name": attr_data.get("Name", attr_name),
                "type": attr_data.get("AttributeType", "Unknown"),
                "is_readonly": attr_data.get("IsReadonly", False),
                "is_required": attr_data.get("IsRequired", False),
                "is_multi_value": attr_data.get("IsMultivalue", False),
                "related_asset": attr_data.get("RelatedAsset", {}).get("nameref"),
            })

        return sorted(attributes, key=lambda x: x["name"])

    async def query_with_config(
        self,
        asset_type: str,
        parent_oid: str | None = None,
        parent_field: str = "Super",
        config_select: list[str] | None = None,
        config_filters: list[str] | None = None,
        config_sort: list[str] | None = None,
        include_done: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute a query using configuration-based field lists.

        This method allows CLI commands to use custom query configurations
        instead of hardcoded field lists.

        Args:
            asset_type: V1 asset type (e.g., "Epic", "Story", "Task")
            parent_oid: Optional parent OID to filter by
            parent_field: Field name for parent relationship (default "Super")
            config_select: List of fields to select (from AssetQueryConfig)
            config_filters: List of filter conditions (from AssetQueryConfig)
            config_sort: List of sort fields (from AssetQueryConfig)
            include_done: Include closed/completed items

        Returns:
            List of raw result dictionaries from V1 API
        """
        filters: list[str] = []

        # Add parent filter if specified
        if parent_oid:
            filters.append(f"{parent_field}='{parent_oid}'")

        # Add config filters
        if config_filters:
            filters.extend(config_filters)

        # Add done/closed filter
        if not include_done:
            filters.append("AssetState!='Closed'")

        # Use provided fields or minimal default
        select = config_select or ["Name", "Number"]
        sort = config_sort or ["Name"]

        return await self._query(
            asset_type,
            select=select,
            filter_=filters if filters else None,
            sort=sort,
        )

    # High-level methods

    async def get_me(self) -> Member:
        """Get the current authenticated user."""
        results = await self._query(
            "Member",
            select=["Name", "Email", "Username"],
            where={"IsSelf": "true"},
        )
        if not results:
            raise V1APIError("Could not find current user")

        item = results[0]
        return Member(
            oid=item["_oid"],
            name=item.get("Name", ""),
            email=item.get("Email", ""),
            username=item.get("Username", ""),
        )

    async def get_my_stories(
        self,
        project_oids: list[str] | None = None,
        include_done: bool = False,
    ) -> list[Story]:
        """Get stories owned by the current user.

        Args:
            project_oids: Filter to specific projects
            include_done: Include completed stories

        Returns:
            List of stories
        """
        filters = ["Owners.IsSelf='true'"]
        if not include_done:
            filters.append("AssetState!='Closed'")
        if project_oids:
            scope_filter = "|".join(f"Scope='{oid}'" for oid in project_oids)
            filters.append(f"({scope_filter})")

        return await self._get_stories(filters)

    async def get_stories(
        self,
        parent_oid: str,
        include_done: bool = False,
    ) -> list[Story]:
        """Get stories under a parent (Feature or Story).

        Args:
            parent_oid: The parent OID (Feature or Story)
            include_done: Include completed stories

        Returns:
            List of child stories
        """
        # Stories whose parent is the given feature/story
        filters = [f"Super='{parent_oid}'"]
        if not include_done:
            filters.append("AssetState!='Closed'")

        return await self._get_stories(filters)

    async def _get_stories(self, filters: list[str]) -> list[Story]:
        """Internal method to fetch stories with filters."""
        results = await self._query(
            "Story",
            select=[
                "Number",
                "Name",
                "Description",
                "Status.Name",
                "Status",
                "Scope.Name",
                "Scope",
                "Owners.Name",
                "Owners",
                "Super.Name",
                "Super",
                "Estimate",
            ],
            filter_=filters,
            sort=["-ChangeDateUTC"],
        )

        stories = []
        for item in results:
            owners = item.get("Owners.Name", [])
            if isinstance(owners, str):
                owners = [owners] if owners else []

            owner_oids = item.get("Owners", [])
            if isinstance(owner_oids, dict):
                owner_oids = [owner_oids.get("_oid", "")] if owner_oids else []
            elif isinstance(owner_oids, list):
                owner_oids = [o.get("_oid", "") if isinstance(o, dict) else str(o) for o in owner_oids]

            status_data = item.get("Status")
            status_oid = None
            if isinstance(status_data, dict):
                status_oid = status_data.get("_oid")
            elif isinstance(status_data, str):
                status_oid = status_data

            scope_data = item.get("Scope")
            scope_oid = ""
            if isinstance(scope_data, dict):
                scope_oid = scope_data.get("_oid", "")
            elif isinstance(scope_data, str):
                scope_oid = scope_data

            super_data = item.get("Super")
            parent_oid = None
            if isinstance(super_data, dict):
                parent_oid = super_data.get("_oid")
            elif isinstance(super_data, str):
                parent_oid = super_data

            stories.append(
                Story(
                    oid=item["_oid"],
                    number=item.get("Number", ""),
                    name=item.get("Name", ""),
                    description=item.get("Description", ""),
                    status=item.get("Status.Name"),
                    status_oid=status_oid,
                    scope_name=item.get("Scope.Name", ""),
                    scope_oid=scope_oid,
                    owners=owners,
                    owner_oids=owner_oids,
                    parent_name=item.get("Super.Name"),
                    parent_oid=parent_oid,
                    estimate=item.get("Estimate"),
                )
            )

        return stories

    async def get_story_by_number(self, identifier: str) -> Story | None:
        """Get a story by its display number (e.g., S-12345) or OID (e.g., Story:12345)."""
        select = [
            "Number",
            "Name",
            "Description",
            "Status.Name",
            "Status",
            "Scope.Name",
            "Scope",
            "Owners.Name",
            "Owners",
            "Super.Name",
            "Super",
            "Estimate",
        ]

        # Check if it's an OID token
        if ":" in identifier and identifier.split(":")[0].lower() == "story":
            results = await self._query(
                "Story",
                select=select,
                filter_=[f"ID='{identifier}'"],
            )
        else:
            # Normalize number format
            if not identifier.upper().startswith("S-"):
                identifier = f"S-{identifier}"
            results = await self._query(
                "Story",
                select=select,
                where={"Number": identifier},
            )

        if not results:
            return None

        item = results[0]
        # Same parsing as _get_stories
        owners = item.get("Owners.Name", [])
        if isinstance(owners, str):
            owners = [owners] if owners else []

        status_data = item.get("Status")
        status_oid = None
        if isinstance(status_data, dict):
            status_oid = status_data.get("_oid")

        scope_data = item.get("Scope")
        scope_oid = ""
        if isinstance(scope_data, dict):
            scope_oid = scope_data.get("_oid", "")

        super_data = item.get("Super")
        parent_oid = None
        if isinstance(super_data, dict):
            parent_oid = super_data.get("_oid")

        return Story(
            oid=item["_oid"],
            number=item.get("Number", ""),
            name=item.get("Name", ""),
            description=item.get("Description", ""),
            status=item.get("Status.Name"),
            status_oid=status_oid,
            scope_name=item.get("Scope.Name", ""),
            scope_oid=scope_oid,
            owners=owners,
            owner_oids=[],
            parent_name=item.get("Super.Name"),
            parent_oid=parent_oid,
            estimate=item.get("Estimate"),
        )

    async def update_story_status(self, story_oid: str, status_oid: str) -> bool:
        """Update a story's status.

        Args:
            story_oid: The story OID
            status_oid: The new status OID

        Returns:
            True if successful
        """
        return await self._update(story_oid, {"Status": status_oid})

    async def assign_story_to_me(self, story_oid: str, member_oid: str) -> bool:
        """Assign a story to the current user.

        Args:
            story_oid: The story OID
            member_oid: The member OID to assign

        Returns:
            True if successful
        """
        return await self._update(story_oid, {"Owners": member_oid})

    async def get_scopes(self) -> list[Project]:
        """Get all accessible scopes (high-level containers)."""
        results = await self._query(
            "Scope",
            select=["Name", "Description"],
            filter_=["AssetState!='Closed'"],
            sort=["Name"],
        )

        return [
            Project(
                oid=item["_oid"],
                name=item.get("Name", ""),
                description=item.get("Description", ""),
            )
            for item in results
        ]

    async def get_projects(
        self,
        categories: list[str] | None = None,
        status: str | None = "Implementation",
        include_all_statuses: bool = False,
    ) -> list[Project]:
        """Get projects (Business Epic category only).

        Args:
            categories: List of category names to include. If None, includes
                       only 'Business Epic' (actual projects users work in).
            status: Filter by status name. Default is 'Implementation'.
            include_all_statuses: If True, ignore status filter and show all.
        """
        if categories is None:
            categories = ["Business Epic"]

        # Build category filter: Category.Name='X'|Category.Name='Y'
        cat_filters = "|".join(f"Category.Name='{cat}'" for cat in categories)
        filters = ["AssetState!='Closed'", f"({cat_filters})"]

        # Add status filter unless showing all
        if not include_all_statuses and status:
            filters.append(f"Status.Name='{status}'")

        results = await self._query(
            "Epic",
            select=["Name", "Description", "Number", "Category.Name", "Scope.Name", "Super.Name", "Status.Name"],
            filter_=filters,
            sort=["Name"],
        )

        return [
            Project(
                oid=item["_oid"],
                name=item.get("Name", ""),
                description=item.get("Description", ""),
                number=item.get("Number", ""),
                category=item.get("Category.Name"),
                scope_name=item.get("Scope.Name", ""),
                parent_name=item.get("Super.Name"),
                status=item.get("Status.Name"),
            )
            for item in results
        ]

    async def get_delivery_groups(
        self,
        project_oid: str,
        include_done: bool = False,
    ) -> list[DeliveryGroup]:
        """Get Delivery Groups under a project (roadmap/release items).

        Args:
            project_oid: The parent project (Business Epic) OID
            include_done: Include closed delivery groups

        Returns:
            List of Delivery Groups
        """
        filters = [f"Super='{project_oid}'", "Category.Name='Delivery Group'"]
        if not include_done:
            filters.append("AssetState!='Closed'")

        results = await self._query(
            "Epic",
            select=[
                "Name",
                "Number",
                "Status.Name",
                "PlannedStart",
                "PlannedEnd",
                "Category.Name",
            ],
            filter_=filters,
            sort=["PlannedStart", "Name"],
        )

        return [
            DeliveryGroup(
                oid=item["_oid"],
                name=item.get("Name", ""),
                number=item.get("Number", ""),
                status=item.get("Status.Name"),
                delivery_type=None,  # Type attribute not available in all V1 instances
                planned_start=item.get("PlannedStart"),
                planned_end=item.get("PlannedEnd"),
                progress=None,  # PercentDone not available in all V1 instances
                estimate=None,  # Estimate not available in all V1 instances
                category=item.get("Category.Name"),
            )
            for item in results
        ]

    async def get_project_by_name(self, name: str) -> Project | None:
        """Find a project (Business Epic) by name (case-insensitive partial match)."""
        projects = await self.get_projects()
        name_lower = name.lower()
        for project in projects:
            if name_lower in project.name.lower():
                return project
        return None

    async def get_project_by_number(self, identifier: str) -> Project | None:
        """Find a project (Business Epic) by number (e.g., E-100) or OID (e.g., Epic:100)."""
        select = ["Name", "Description", "Number", "Category.Name", "Scope.Name", "Super.Name", "Status.Name"]

        # Check if it's an OID token
        if ":" in identifier and identifier.split(":")[0].lower() == "epic":
            results = await self._query(
                "Epic",
                select=select,
                filter_=[f"ID='{identifier}'"],
            )
        else:
            if not identifier.upper().startswith("E-"):
                identifier = f"E-{identifier}"
            results = await self._query(
                "Epic",
                select=select,
                where={"Number": identifier},
            )

        if not results:
            return None

        item = results[0]
        return Project(
            oid=item["_oid"],
            name=item.get("Name", ""),
            description=item.get("Description", ""),
            number=item.get("Number", ""),
            category=item.get("Category.Name"),
            scope_name=item.get("Scope.Name", ""),
            parent_name=item.get("Super.Name"),
            status=item.get("Status.Name"),
        )

    async def get_features(
        self,
        parent_oid: str,
        include_done: bool = False,
    ) -> list[Feature]:
        """Get features under a parent (Delivery Group or Business Epic).

        Features are Epic assets with Type='Feature'.

        Args:
            parent_oid: The parent OID (Delivery Group or Business Epic)
            include_done: Include closed features

        Returns:
            List of child features
        """
        # Query child Epics under the parent (features are Epics under Delivery Groups)
        filters = [f"Super='{parent_oid}'", "Category.Name!='Delivery Group'"]
        if not include_done:
            filters.append("AssetState!='Closed'")

        results = await self._query(
            "Epic",
            select=["Number", "Name", "Description", "Status.Name", "Status", "Scope.Name", "Scope", "Super.Name", "Category.Name"],
            filter_=filters,
            sort=["-ChangeDateUTC"],
        )

        features = []
        for item in results:
            status_data = item.get("Status")
            status_oid = None
            if isinstance(status_data, dict):
                status_oid = status_data.get("_oid")

            scope_data = item.get("Scope")
            scope_oid = ""
            if isinstance(scope_data, dict):
                scope_oid = scope_data.get("_oid", "")

            features.append(
                Feature(
                    oid=item["_oid"],
                    number=item.get("Number", ""),
                    name=item.get("Name", ""),
                    description=item.get("Description"),
                    scope_name=item.get("Scope.Name", ""),
                    scope_oid=scope_oid,
                    parent_name=item.get("Super.Name"),
                    status=item.get("Status.Name"),
                    status_oid=status_oid,
                    category=item.get("Category.Name"),
                )
            )

        return features

    async def create_feature(
        self,
        name: str,
        parent_oid: str,
        description: str = "",
    ) -> str:
        """Create a new feature (Epic with Type='Feature') under a parent.

        Args:
            name: Feature name
            parent_oid: Parent OID (Delivery Group or Business Epic)
            description: Optional description

        Returns:
            The created feature's OID
        """
        data: dict[str, Any] = {"Name": name, "Super": parent_oid}
        if description:
            data["Description"] = description
        # Note: Type may need to be set explicitly if not inherited
        return await self._create("Epic", data)

    async def create_story(
        self,
        name: str,
        project_oid: str,
        feature_oid: str | None = None,
        estimate: float | None = None,
        description: str = "",
    ) -> str:
        """Create a new story.

        Args:
            name: Story name
            project_oid: Project OID
            feature_oid: Optional parent feature OID
            estimate: Optional story points
            description: Optional description

        Returns:
            The created story's OID
        """
        data: dict[str, Any] = {"Name": name, "Scope": project_oid}
        if feature_oid:
            data["Super"] = feature_oid
        if estimate is not None:
            data["Estimate"] = estimate
        if description:
            data["Description"] = description
        return await self._create("Story", data)

    async def get_tasks(self, story_oid: str) -> list[Task]:
        """Get tasks for a story.

        Args:
            story_oid: The parent story OID

        Returns:
            List of tasks
        """
        results = await self._query(
            "Task",
            select=["Number", "Name", "Parent", "Parent.Number", "Status.Name", "Status", "Owners.Name", "ToDo", "Actuals"],
            filter_=[f"Parent='{story_oid}'"],
            sort=["Order"],
        )

        return self._parse_tasks(results)

    def _parse_tasks(self, results: list[dict[str, Any]]) -> list[Task]:
        """Parse task results into Task objects."""
        tasks = []
        for item in results:
            parent_data = item.get("Parent")
            parent_oid = ""
            if isinstance(parent_data, dict):
                parent_oid = parent_data.get("_oid", "")
            elif isinstance(parent_data, str):
                parent_oid = parent_data

            status_data = item.get("Status")
            status_oid = None
            if isinstance(status_data, dict):
                status_oid = status_data.get("_oid")

            owners = item.get("Owners.Name", [])
            if isinstance(owners, str):
                owners = [owners] if owners else []

            tasks.append(
                Task(
                    oid=item["_oid"],
                    number=item.get("Number", ""),
                    name=item.get("Name", ""),
                    parent_oid=parent_oid,
                    parent_number=item.get("Parent.Number", ""),
                    status=item.get("Status.Name"),
                    status_oid=status_oid,
                    owners=owners,
                    todo=item.get("ToDo"),
                    done=item.get("Actuals"),
                )
            )

        return tasks

    async def get_task_by_identifier(self, identifier: str) -> Task | None:
        """Get a task by its number (TK-nnnnn) or OID (Task:nnnnn)."""
        select = ["Number", "Name", "Parent", "Parent.Number", "Status.Name", "Status", "Owners.Name", "ToDo", "Actuals"]

        # Check if it's an OID token
        if ":" in identifier and identifier.split(":")[0].lower() == "task":
            results = await self._query(
                "Task",
                select=select,
                filter_=[f"ID='{identifier}'"],
            )
        else:
            # Normalize number format
            if not identifier.upper().startswith("TK-"):
                identifier = f"TK-{identifier}"
            results = await self._query(
                "Task",
                select=select,
                where={"Number": identifier},
            )

        if not results:
            return None

        tasks = self._parse_tasks(results)
        return tasks[0] if tasks else None

    async def create_task(
        self,
        name: str,
        story_oid: str,
        estimate: float | None = None,
    ) -> str:
        """Create a task for a story.

        Args:
            name: Task name
            story_oid: Parent story OID
            estimate: Optional hours estimate

        Returns:
            The created task's OID
        """
        data: dict[str, Any] = {"Name": name, "Parent": story_oid}
        if estimate is not None:
            data["ToDo"] = estimate
        return await self._create("Task", data)

    async def complete_task(self, task_oid: str) -> bool:
        """Mark a task as done.

        Args:
            task_oid: The task OID

        Returns:
            True if successful
        """
        # Move remaining ToDo to Actuals and set ToDo to 0
        return await self._update(task_oid, {"ToDo": 0})

    async def get_story_statuses(self) -> list[StatusInfo]:
        """Get all available story statuses."""
        results = await self._query(
            "StoryStatus",
            select=["Name"],
            sort=["Order"],
        )

        return [
            StatusInfo(oid=item["_oid"], name=item.get("Name", ""))
            for item in results
        ]

    async def get_feature_by_number(self, identifier: str) -> Feature | None:
        """Get a feature by its display number (e.g., E-100) or OID (e.g., Epic:100).

        Features are Epic assets under Delivery Groups or Business Epics.
        """
        select = ["Number", "Name", "Description", "Status.Name", "Status", "Scope.Name", "Scope", "Super.Name"]

        # Check if it's an OID token
        if ":" in identifier and identifier.split(":")[0].lower() == "epic":
            results = await self._query(
                "Epic",
                select=select,
                filter_=[f"ID='{identifier}'"],
            )
        else:
            if not identifier.upper().startswith("E-"):
                identifier = f"E-{identifier}"
            results = await self._query(
                "Epic",
                select=select,
                where={"Number": identifier},
            )

        if not results:
            return None

        item = results[0]
        status_data = item.get("Status")
        status_oid = None
        if isinstance(status_data, dict):
            status_oid = status_data.get("_oid")

        scope_data = item.get("Scope")
        scope_oid = ""
        if isinstance(scope_data, dict):
            scope_oid = scope_data.get("_oid", "")

        return Feature(
            oid=item["_oid"],
            number=item.get("Number", ""),
            name=item.get("Name", ""),
            description=item.get("Description"),
            scope_name=item.get("Scope.Name", ""),
            scope_oid=scope_oid,
            parent_name=item.get("Super.Name"),
            status=item.get("Status.Name"),
            status_oid=status_oid,
        )
