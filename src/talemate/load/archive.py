"""Import complete scene ZIP archives."""

import json
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

import structlog

from talemate.path import SCENES_DIR
from talemate.status import set_loading
from talemate.load.project import to_project_name

log = structlog.get_logger("talemate.load.archive")


@set_loading("Importing scene archive...")
async def load_scene_from_zip(scene, zip_path, reset: bool = False):
    """Import a scene archive into a conflict-free project directory.

    The archive must contain a root-level ``scene.json``. Packaged assets, nodes,
    info, templates, and the referenced restore file are copied into the new
    project before the scene is loaded and saved.

    Args:
        scene: Scene instance to populate and persist.
        zip_path: Path to the scene ZIP archive.
        reset: Whether to reset the scene while loading its serialized data.

    Returns:
        The result returned by the serialized scene loader.

    Raises:
        ValueError: The path is not a ZIP archive or lacks ``scene.json``.
        OSError: An archive member or project file cannot be read or written.
        json.JSONDecodeError: ``scene.json`` is not valid JSON.

    Side Effects:
        Assigns a unique name to ``scene``, copies archive content into its
        project directory, loads it, creates a restore point when needed, and
        saves the scene. A missing referenced restore file is ignored and the
        scene receives a new ``initial.json`` restore point.

    """
    # Local import keeps archive IO dependent on orchestration in one direction.
    from talemate.load import load_scene_from_data

    log.info("Loading complete scene from ZIP", zip_path=zip_path, reset=reset)
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"File is not a valid ZIP archive: {zip_path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with zipfile.ZipFile(zip_path, "r") as archive:
            if "scene.json" not in archive.namelist():
                raise ValueError(
                    "ZIP archive does not contain required scene.json file"
                )
            archive.extractall(temp_path)
            log.debug("Extracted ZIP contents", files=len(archive.namelist()))

        with open(temp_path / "scene.json", encoding="utf-8") as scene_file:
            scene_data = json.load(scene_file)

        base_scene_name = scene_data.get("name", "imported-scene")
        scene_name = base_scene_name
        counter = 1
        potential_dir = os.path.join(str(SCENES_DIR), to_project_name(scene_name))
        while os.path.exists(potential_dir):
            scene_name = f"{base_scene_name}-{counter}"
            potential_dir = os.path.join(str(SCENES_DIR), to_project_name(scene_name))
            counter += 1
            if counter > 100:
                scene_name = f"{base_scene_name}-{uuid.uuid4().hex[:8]}"
                break

        scene.name = scene_name
        save_dir = Path(scene.save_dir)
        for directory in ("assets", "nodes", "info", "templates"):
            source = temp_path / directory
            if source.exists():
                shutil.copytree(source, save_dir / directory)
                log.debug(
                    "Loaded archive directory", directory=directory, source=source
                )

        restore_filename = scene_data.get("restore_from")
        if restore_filename:
            restore_source = temp_path / restore_filename
            if restore_source.exists():
                shutil.copy2(restore_source, save_dir / restore_filename)
            else:
                log.warning(
                    "Restore file referenced in scene data but not found in ZIP, "
                    "unsetting restore_from",
                    filename=restore_filename,
                )
                scene.restore_from = None

        scene_data = scene_data.copy()
        scene_data["name"] = scene.name
        zip_basename = os.path.basename(zip_path)
        clean_name = (
            zip_basename.replace(".zip", "")
            if zip_basename.endswith(".zip")
            else zip_basename
        )
        result = await load_scene_from_data(scene, scene_data, reset, name=clean_name)

        if not scene.restore_from:
            scene.restore_from = "initial.json"
            await scene.save_restore("initial.json")

        await scene.save(auto=False, force=True)
        return result
