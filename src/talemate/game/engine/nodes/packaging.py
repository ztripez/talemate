"""Discover, persist, initialize, and uninstall scene-level node packages.

Node packages declare graph modules that attach to a scene loop, expose configurable
properties, and track installed listener nodes in scene package metadata.
"""

import os
import tempfile
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import pydantic
import structlog

import talemate.emit.async_signals as async_signals

from .core import (
    TYPE_CHOICES,
    UNRESOLVED,
    Graph,
    Listen,
    Node,
    NodeStyle,
    PropertyField,
    register,
)
from .registry import get_node, get_nodes_by_base_type
from .scene import SceneLoop

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

__all__ = [
    "PromoteConfig",
    "initialize_scene_package_info",
    "get_scene_package_info",
    "apply_scene_package_info",
    "list_packages",
    "get_package_by_registry",
    "install_package",
    "update_package_properties",
    "uninstall_package",
    "initialize_package",
    "initialize_packages",
    "PackageInitializationError",
]


log = structlog.get_logger("talemate.game.engine.nodes.packaging")

TYPE_CHOICES.extend(
    [
        "node_module",
    ]
)

SCENE_PACKAGE_INFO_FILENAME = "modules.json"

# ------------------------------------------------------------------------------------------------
# MODELS
# ------------------------------------------------------------------------------------------------


class PackageProperty(pydantic.BaseModel):
    """Store one configurable property exposed by an installable node package.

    Attributes:
        module: Registry name of the node module receiving the property.
        name: Property name within the target node module.
        label: Human-readable configuration label.
        description: Human-readable explanation of the property.
        type: Node-system type identifier for the property value.
        default: Default property value.
        value: Scene-specific configured value, or ``None`` when unconfigured.
        required: Whether package initialization requires a configured value.
        choices: Allowed string values, or ``None`` when unrestricted.

    Unknown fields are rejected during validation.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    module: str
    name: str
    label: str
    description: str
    type: str
    default: pydantic.JsonValue
    value: pydantic.JsonValue | None = None
    required: bool = pydantic.Field(default=False)
    choices: list[str] | None = None


class PackageData(pydantic.BaseModel):
    """Describe an installable node package and its scene installation state.

    Attributes:
        name: Human-readable package name.
        author: Package author.
        description: Human-readable package purpose.
        installable: Whether users may install the package into scenes.
        registry: Unique package registry name.
        status: Whether the package is installed in the current scene.
        errors: Package-discovery or configuration errors.
        package_properties: Configurable properties keyed by exposed name.
        install_nodes: Registry names of node modules installed by the package.
        installed_nodes: Scene-loop identifiers of currently installed nodes.
        restart_scene_loop: Whether installation requires restarting the scene loop.

    Unknown fields are rejected except for the evidence-backed legacy
    ``configured`` computed field, which is discarded during migration.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    name: str
    author: str
    description: str
    installable: bool
    registry: str
    status: Literal["installed", "not_installed"] = "not_installed"

    errors: list[str] = pydantic.Field(default_factory=list)

    package_properties: dict[str, PackageProperty] = pydantic.Field(
        default_factory=dict
    )
    install_nodes: list[str] = pydantic.Field(default_factory=list)
    installed_nodes: list[str] = pydantic.Field(default_factory=list)
    restart_scene_loop: bool = pydantic.Field(default=False)

    @pydantic.model_validator(mode="before")
    @classmethod
    def discard_legacy_computed_configured(cls, value: Any) -> Any:
        """Discard the computed field written by the previous package serializer.

        Args:
            value: Raw persisted package payload.

        Returns:
            Payload without the formerly serialized ``configured`` computed field.
        """
        if isinstance(value, dict) and "configured" in value:
            value = dict(value)
            value.pop("configured")
        return value

    @pydantic.computed_field(description="Whether the package is configured")
    @property
    def configured(self) -> bool:
        """Return whether every required exposed property has a configured value."""
        return all(
            prop.value is not None
            for prop in self.package_properties.values()
            if prop.required
        )

    def properties_for_node(self, node_registry: str) -> dict[str, Any]:
        """Return configured property values targeting one node module.

        Args:
            node_registry: Registry name of the target node module.

        Returns:
            Mapping from target property names to configured values. The mapping is
            empty when the package exposes no properties for ``node_registry``.
        """

        return {
            prop.name: prop.value
            for prop in self.package_properties.values()
            if prop.module == node_registry
        }


class ScenePackageInfo(pydantic.BaseModel):
    """Store canonical package installation metadata for one scene.

    Attributes:
        packages: Packages currently persisted as installed in the scene.

    Unknown fields are rejected during validation.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    packages: list[PackageData]

    def has_package(self, package_registry: str) -> bool:
        """Return whether metadata contains the specified package registry name.

        Args:
            package_registry: Unique registry name to locate.

        Returns:
            ``True`` when the package is present; otherwise ``False``.
        """
        return any(p.registry == package_registry for p in self.packages)

    def get_package(self, package_registry: str) -> PackageData | None:
        """Return metadata for the specified package registry name.

        Args:
            package_registry: Unique registry name to locate.

        Returns:
            Matching package metadata, or ``None`` when no package matches.
        """
        return next((p for p in self.packages if p.registry == package_registry), None)


class PackageInitializationError(RuntimeError):
    """Raised when package metadata is invalid or nodes cannot be replaced safely."""


# ------------------------------------------------------------------------------------------------
# FUNCTIONS
# ------------------------------------------------------------------------------------------------


async def initialize_scene_package_info(scene: "Scene"):
    """Create empty package metadata when a scene has no metadata file.

    Existing package metadata is left unchanged.

    Args:
        scene: Scene whose information directory stores package metadata.

    Returns:
        None.

    Raises:
        OSError: If the information directory or metadata file cannot be created.
    """

    filepath = os.path.join(scene.info_dir, SCENE_PACKAGE_INFO_FILENAME)

    # if info dir does not exist, create it
    if not os.path.exists(scene.info_dir):
        os.makedirs(scene.info_dir)

    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write(
                ScenePackageInfo(packages=[]).model_dump_json(
                    indent=4, exclude_computed_fields=True
                )
            )


async def get_scene_package_info(scene: "Scene") -> ScenePackageInfo:
    """Load and validate package installation metadata for a scene.

    Missing metadata is represented by an empty package collection.

    Args:
        scene: Scene whose information directory contains package metadata.

    Returns:
        Validated scene package metadata.

    Raises:
        OSError: If existing metadata cannot be read.
        pydantic.ValidationError: If persisted metadata is invalid.
    """

    filepath = os.path.join(scene.info_dir, SCENE_PACKAGE_INFO_FILENAME)

    # if info dir does not exist, create it
    if not os.path.exists(scene.info_dir):
        os.makedirs(scene.info_dir)

    if not os.path.exists(filepath):
        return ScenePackageInfo(packages=[])

    with open(filepath, "r") as f:
        return ScenePackageInfo.model_validate_json(f.read())


async def apply_scene_package_info(scene: "Scene", package_datas: list[PackageData]):
    """Apply persisted installation status and property values to discovered packages.

    Args:
        scene: Scene containing persisted package metadata.
        package_datas: Discovered package definitions to update in place.

    Returns:
        None.

    Raises:
        OSError: If existing metadata cannot be read.
        pydantic.ValidationError: If persisted metadata is invalid.
    """

    scene_package_info = await get_scene_package_info(scene)

    for package_data in package_datas:
        if scene_package_info.has_package(package_data.registry):
            package_data.status = "installed"
            package = scene_package_info.get_package(package_data.registry)
            package_data.package_properties = package.package_properties
        else:
            package_data.status = "not_installed"


async def list_packages() -> list[PackageData]:
    """Discover and validate every installable node package.

    Returns:
        Installable package metadata, including promoted configuration properties.

    Raises:
        KeyError: If an installed module registry cannot be resolved.
        pydantic.ValidationError: If package declarations are invalid.
    """

    packages = get_nodes_by_base_type("util/packaging/Package")
    package_datas = []

    for package_module_cls in packages:
        package_module: "Package" = package_module_cls()

        # skip if not installable
        if not package_module.get_property("installable"):
            continue

        errors = []

        install_node_modules = await package_module.get_nodes(
            lambda node: node.registry == "util/packaging/InstallNodeModule"
        )
        promoted_properties = await package_module.get_nodes(
            lambda node: node.registry == "util/packaging/PromoteConfig"
        )
        install_nodes = []

        module_properties = {}
        for install_node_module in install_node_modules:
            node_registry = install_node_module.get_property("node_registry")
            node_module_cls = get_node(node_registry)
            node_module: "Graph" = node_module_cls()
            module_properties[node_module.registry] = node_module.module_properties
            install_nodes.append(node_module.registry)

        log.debug(
            "package_module",
            package_module=package_module,
            module_properties=module_properties,
            promoted_properties=promoted_properties,
        )
        package_properties = {}

        for promoted_property in promoted_properties:
            property_name = promoted_property.properties["property_name"]
            exposed_property_name = promoted_property.properties[
                "exposed_property_name"
            ]
            target_node_registry = promoted_property.properties["node_registry"]

            try:
                module_property = module_properties[target_node_registry][property_name]
            except KeyError:
                log.warning(
                    "module property not found",
                    target_node_registry=target_node_registry,
                    property_name=property_name,
                    module_properties=module_properties,
                )
                errors.append(
                    f"Module property {property_name} not found in {target_node_registry}"
                )
                continue

            package_property = PackageProperty(
                module=target_node_registry,
                name=property_name,
                label=promoted_property.properties.get("label", ""),
                type=module_property.type,
                default=module_property.default,
                description=module_property.description,
                choices=module_property.choices,
                required=promoted_property.properties.get("required", False),
            )
            package_properties[exposed_property_name] = package_property

        package_data = PackageData(
            name=package_module.properties["package_name"],
            author=package_module.properties["author"],
            description=package_module.properties["description"],
            installable=package_module.properties["installable"],
            registry=package_module.registry,
            package_properties=package_properties,
            install_nodes=install_nodes,
            restart_scene_loop=package_module.properties["restart_scene_loop"],
            errors=errors,
        )

        package_datas.append(package_data)

    return package_datas


async def get_package_by_registry(package_registry: str) -> PackageData | None:
    """Return one discovered installable package by registry name.

    Args:
        package_registry: Unique package registry name.

    Returns:
        Matching package metadata, or ``None`` when no package matches.
    """

    packages = await list_packages()

    return next((p for p in packages if p.registry == package_registry), None)


async def save_scene_package_info(scene: "Scene", scene_package_info: ScenePackageInfo):
    """Persist validated scene package metadata using atomic file replacement.

    Args:
        scene: Scene whose information directory receives the metadata file.
        scene_package_info: Validated package metadata to persist.

    Returns:
        None.

    Raises:
        OSError: If temporary-file creation, synchronization, or replacement fails.
    """

    # if info dir does not exist, create it
    if not os.path.exists(scene.info_dir):
        os.makedirs(scene.info_dir)

    filepath = os.path.join(scene.info_dir, SCENE_PACKAGE_INFO_FILENAME)
    serialized = scene_package_info.model_dump_json(
        indent=4, exclude_computed_fields=True
    )
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=scene.info_dir, delete=False, encoding="utf-8"
        ) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, filepath)
    except Exception:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


async def install_package(scene: "Scene", package_data: PackageData) -> PackageData:
    """Persist a package as installed without attaching runtime nodes.

    Args:
        scene: Scene receiving package installation metadata.
        package_data: Discovered package definition to install.

    Returns:
        Installed package metadata. Existing installations are unchanged.

    Raises:
        OSError: If package metadata cannot be read or persisted.
        pydantic.ValidationError: If persisted metadata is invalid.
    """

    scene_package_info = await get_scene_package_info(scene)

    if scene_package_info.has_package(package_data.registry):
        # already installed
        return package_data

    package_data.status = "installed"

    scene_package_info.packages.append(package_data)

    await save_scene_package_info(scene, scene_package_info)

    return package_data


async def update_package_properties(
    scene: "Scene",
    package_registry: str,
    package_properties: dict[str, PackageProperty],
) -> PackageData | None:
    """Persist configured values for an installed package's exposed properties.

    Args:
        scene: Scene containing the installed package.
        package_registry: Unique package registry name.
        package_properties: Exposed properties containing replacement values.

    Returns:
        Updated package metadata, or ``None`` when the package is not installed.

    Raises:
        KeyError: If an unknown exposed property is supplied.
        OSError: If package metadata cannot be read or persisted.
        pydantic.ValidationError: If persisted metadata is invalid.
    """

    scene_package_info = await get_scene_package_info(scene)

    package_data = scene_package_info.get_package(package_registry)

    if not package_data:
        return

    for property_name, property_data in package_properties.items():
        package_data.package_properties[property_name].value = property_data.value

    await save_scene_package_info(scene, scene_package_info)

    return package_data


async def uninstall_package(scene: "Scene", package_registry: str):
    """Remove a package and disconnect its installed scene-loop listeners.

    The operation removes persisted package metadata and every tracked installed
    node. No changes are made when the package is not installed.

    Args:
        scene: Scene from which the package is removed.
        package_registry: Unique registry name of the package to remove.

    Returns:
        None.

    Raises:
        OSError: If updated package metadata cannot be persisted.
        pydantic.ValidationError: If persisted package metadata is invalid.
    """

    scene_package_info = await get_scene_package_info(scene)

    if not scene_package_info.has_package(package_registry):
        # not installed
        return

    package_data = scene_package_info.get_package(package_registry)

    scene_package_info.packages = [
        p for p in scene_package_info.packages if p.registry != package_registry
    ]

    scene_loop: SceneLoop | None = scene.active_node_graph
    if scene_loop:
        for node_id in package_data.installed_nodes:
            node = scene_loop.nodes.get(node_id)
            if node is not None:
                _disconnect_package_node(node)
                scene_loop.remove_node(node_id)

    package_data.installed_nodes = []

    await save_scene_package_info(scene, scene_package_info)


async def initialize_packages(scene: "Scene", scene_loop: SceneLoop):
    """Attach every valid installed package to a scene loop.

    Args:
        scene: Scene containing authoritative persisted package metadata.
        scene_loop: Scene loop receiving installed package nodes.

    Returns:
        None.

    Raises:
        PackageInitializationError: If any installed package is unconfigured,
            contains discovery errors, or cannot be attached transactionally.
        OSError: If package metadata cannot be read or persisted.
        pydantic.ValidationError: If persisted package metadata is invalid.
    """
    scene_package_info = await get_scene_package_info(scene)
    invalid_packages = []
    for package_data in scene_package_info.packages:
        if not package_data.configured:
            missing = sorted(
                name
                for name, prop in package_data.package_properties.items()
                if prop.required and prop.value is None
            )
            invalid_packages.append(
                f"{package_data.registry}: missing required properties {missing}"
            )
        elif package_data.errors:
            invalid_packages.append(
                f"{package_data.registry}: {'; '.join(package_data.errors)}"
            )
    if invalid_packages:
        raise PackageInitializationError(
            "Installed package configuration is invalid: "
            + " | ".join(invalid_packages)
        )

    for package_data in scene_package_info.packages:
        await initialize_package(scene, scene_loop, package_data)


async def initialize_package(
    scene: "Scene",
    scene_loop: SceneLoop,
    package_data: PackageData,
) -> PackageData:
    """Replace installed package nodes transactionally and persist their identifiers.

    Previously installed nodes remain active until every replacement node has been
    created, configured, attached, and persisted. Any failure removes replacement
    nodes and raises ``PackageInitializationError`` without removing prior nodes.

    Args:
        scene: Scene whose persisted package metadata is authoritative.
        scene_loop: Scene loop receiving the package's listener/module nodes.
        package_data: Package identity used to locate canonical persisted metadata.

    Returns:
        Canonical persisted package metadata with current installed node identifiers.

    Raises:
        PackageInitializationError: If the package is not installed or replacement
            nodes cannot be created, configured, attached, or persisted.
        OSError: If package metadata cannot be read before replacement begins.
        pydantic.ValidationError: If persisted package metadata is invalid.
    """
    scene_package_info = await get_scene_package_info(scene)
    persisted_package = scene_package_info.get_package(package_data.registry)
    if persisted_package is None:
        raise PackageInitializationError(
            f"Package is not installed: {package_data.registry}"
        )

    previous_node_ids = list(persisted_package.installed_nodes)
    previous_nodes = {
        node_id: scene_loop.nodes[node_id]
        for node_id in previous_node_ids
        if node_id in scene_loop.nodes
    }
    new_nodes: list[Node] = []
    attached_nodes: list[Node] = []
    try:
        for registry in persisted_package.install_nodes:
            install_node_cls = get_node(registry)
            node: Node = install_node_cls()
            existing = scene_loop.nodes.get(node.id)
            if existing is not None and node.id not in previous_node_ids:
                raise PackageInitializationError(
                    f"Package node id collision for {node.id}: "
                    f"{persisted_package.registry} does not own the existing node"
                )
            for property_name, property_value in persisted_package.properties_for_node(
                registry
            ).items():
                field = node.get_property_field(property_name)
                field.default = property_value
                node.properties[property_name] = property_value
            new_nodes.append(node)

        for node in new_nodes:
            scene_loop.add_node(node)
            attached_nodes.append(node)
            log.debug(
                "installed node",
                registry=node.registry,
                properties=persisted_package.properties_for_node(node.registry),
            )
        persisted_package.installed_nodes = [node.id for node in new_nodes]
        await save_scene_package_info(scene, scene_package_info)
    except Exception as exc:
        rollback_errors = []
        for node in reversed(attached_nodes):
            _disconnect_package_node(node)
            if scene_loop.nodes.get(node.id) is node:
                try:
                    scene_loop.remove_node(node.id)
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            previous = previous_nodes.get(node.id)
            if previous is not None:
                scene_loop.add_node(previous)
        rollback_suffix = (
            f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        )
        raise PackageInitializationError(
            f"Failed to initialize package {package_data.registry}: {exc}"
            + rollback_suffix
        ) from exc

    for node_id, previous in previous_nodes.items():
        _disconnect_package_node(previous)
        if scene_loop.nodes.get(node_id) is previous:
            scene_loop.remove_node(node_id)
    return persisted_package


def _disconnect_package_node(node: Node) -> None:
    """Disconnect a package listener node from its registered async signal."""
    if not isinstance(node, Listen):
        return
    event_name = node.get_property("event_name")
    signal = async_signals.get(event_name)
    if signal is not None:
        signal.disconnect(node.execute_from_event)


# ------------------------------------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------------------------------------


@register("util/packaging/Package", as_base_type=True)
class Package(Graph):
    """Describe an installable collection of node modules and configuration."""

    _export_definition: ClassVar[bool] = False

    class Fields:
        package_name = PropertyField(
            name="package_name",
            description="The name of the node module",
            type="str",
            default="",
        )

        author = PropertyField(
            name="author",
            description="The author of the node module",
            type="str",
            default="",
        )

        description = PropertyField(
            name="description",
            description="The description of the node module",
            type="str",
            default="",
        )

        installable = PropertyField(
            name="installable",
            description="Whether the node module is installable to the scene",
            type="bool",
            default=True,
        )

        restart_scene_loop = PropertyField(
            name="restart_scene_loop",
            description="Whether the scene loop should be restarted after the package is installed",
            type="bool",
            default=False,
        )

    def __init__(self, title="Package", **kwargs):
        """Create a package declaration graph.

        Args:
            title: Node-editor display title.
            **kwargs: Additional graph model fields forwarded to ``Graph``.
        """
        super().__init__(title=title, **kwargs)

    def setup(self):
        """Initialize package metadata properties to their declared defaults.

        Returns:
            None.
        """
        self.set_property("package_name", "")
        self.set_property("author", "")
        self.set_property("description", "")
        self.set_property("installable", True)
        self.set_property("restart_scene_loop", False)


@register("util/packaging/InstallNodeModule")
class InstallNodeModule(Node):
    """Declare a node module that a package attaches to a scene loop."""

    class Fields:
        node_registry = PropertyField(
            name="node_registry",
            description="The registry path of the node module to package",
            type="str",
            default=UNRESOLVED,
        )

    @pydantic.computed_field(description="Node style")
    @property
    def style(self) -> NodeStyle:
        """Return the package installer node's editor style.

        Returns:
            Node style containing package-specific colors and icon.
        """
        return NodeStyle(
            node_color="#2c3339",
            title_color="#2e4657",
            icon="F01A6",
        )

    def __init__(self, title="Install Node Module", **kwargs):
        """Create a node-module installation declaration.

        Args:
            title: Node-editor display title.
            **kwargs: Additional node model fields forwarded to ``Node``.
        """
        super().__init__(title=title, **kwargs)

    def setup(self):
        """Initialize the target registry as unresolved until configured.

        Returns:
            None.
        """
        self.set_property("node_registry", UNRESOLVED)


@register("util/packaging/PromoteConfig")
class PromoteConfig(Node):
    """Expose one installed module property as scene package configuration."""

    class Fields:
        node_registry = PropertyField(
            name="node_registry",
            description="The registry path of the node module to package",
            type="str",
            default=UNRESOLVED,
        )

        property_name = PropertyField(
            name="property_name",
            description="Property Name",
            type="str",
            default=UNRESOLVED,
        )

        exposed_property_name = PropertyField(
            name="exposed_property_name",
            description="Exposed Property Name",
            type="str",
            default=UNRESOLVED,
        )

        label = PropertyField(
            name="label",
            description="Label",
            type="str",
            default="",
        )

        required = PropertyField(
            name="required",
            description="Whether the property is required",
            type="bool",
            default=False,
        )

    @pydantic.computed_field(description="Node style")
    @property
    def style(self) -> NodeStyle:
        """Return the promoted-configuration node's editor style.

        Returns:
            Node style containing the promoted-configuration icon.
        """
        return NodeStyle(
            icon="F168A",
        )

    def __init__(self, title="Promote Config", **kwargs):
        """Create a promoted package-configuration declaration.

        Args:
            title: Node-editor display title.
            **kwargs: Additional node model fields forwarded to ``Node``.
        """
        super().__init__(title=title, **kwargs)

    def setup(self):
        """Initialize promoted configuration properties to declared defaults.

        Returns:
            None.
        """
        self.set_property("node_registry", UNRESOLVED)
        self.set_property("property_name", UNRESOLVED)
        self.set_property("exposed_property_name", UNRESOLVED)
        self.set_property("required", False)
        self.set_property("label", "")
