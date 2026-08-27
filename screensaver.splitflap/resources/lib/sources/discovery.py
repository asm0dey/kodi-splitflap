"""Find sources supplied by other add-ons.

A contributor declares a normal xbmc.python.module extension with an id
under SOURCE_PREFIX and exposes create_source(). We discover it, import
it, and call it -- no dependency declaration needed, which is the part
that has to be right, because we cannot declare a dependency on add-ons
that do not exist yet.

Listing and importing are injected, so the whole policy is testable
without Kodi. One broken contributor is skipped and logged; it must never
hide the working ones.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

SOURCE_PREFIX = "script.splitflap.source."


class _SourceLike(Protocol):
    """Duck-typed source interface -- see rotator._SourceLike.

    Kept as a local copy rather than importing rotator's (private, and
    this module has no other reason to depend on rotator): both describe
    the same "any object with next()" contract a contributor fulfils
    without inheriting from anything of ours. `id` is also declared here
    (rotator's copy doesn't need it) because discover() guarantees every
    returned source has one -- defaulted to the addon id when the
    contributor didn't set its own -- and default.py matches on it.
    """

    id: str

    def next(self) -> Any:
        ...


def discover(
    list_addons: Callable[[], list[tuple[str, str]]],
    load_module: Callable[[str, str], object],
    log: Callable[[str], None],
) -> list[_SourceLike]:
    try:
        listed = list_addons()
    except Exception as exc:
        log(f"could not list add-ons: {exc!r}")
        return []

    found: list[_SourceLike] = []
    for addon_id, path in listed:
        if not addon_id.startswith(SOURCE_PREFIX):
            continue
        try:
            module = load_module(addon_id, path)
            factory = getattr(module, "create_source", None)
            if factory is None:
                raise AttributeError("no create_source()")
            source = factory()
            if not callable(getattr(source, "next", None)):
                raise TypeError(
                    f"create_source() returned {type(source).__name__!r}, "
                    "which has no next()"
                )
            if not getattr(source, "id", None):
                source.id = addon_id
            found.append(source)
        except Exception as exc:
            log(f"contributor {addon_id} skipped: {exc!r}")
    return found


def list_choices(
    listed: list[tuple[str, str]],
    name_of: Callable[[str], str],
) -> list[tuple[str, str]]:
    """(id, label) for every installed contributor, for the picker dialog.

    Labelled by add-on name, because an id is not something to make a user
    read off a remote. A name that cannot be read falls back to the id
    rather than dropping the contributor from the list -- an unpickable
    add-on is worse than an ugly label.
    """
    out: list[tuple[str, str]] = []
    for addon_id, _path in listed:
        if not addon_id.startswith(SOURCE_PREFIX):
            continue
        try:
            label = name_of(addon_id) or addon_id
        except Exception:
            label = addon_id
        out.append((addon_id, label))
    return sorted(out, key=lambda pair: pair[1].casefold())


def kodi_list_addons() -> list[tuple[str, str]]:
    """Enumerate installed python modules via JSON-RPC."""
    import json

    import xbmc
    import xbmcaddon

    request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons",
        "params": {"type": "xbmc.python.module", "enabled": True,
                   "properties": ["path"]},
    })
    reply = json.loads(xbmc.executeJSONRPC(request))
    out: list[tuple[str, str]] = []
    for entry in reply.get("result", {}).get("addons", []):
        addon_id = entry.get("addonid", "")
        if not addon_id.startswith(SOURCE_PREFIX):
            continue
        try:
            path = xbmcaddon.Addon(addon_id).getAddonInfo("path")
        except Exception:
            path = entry.get("path", "")
        out.append((addon_id, path))
    return out


def kodi_load_module(addon_id: str, path: str) -> object:
    import importlib.util
    import os

    import xbmcvfs

    entry = os.path.join(xbmcvfs.translatePath(path), "source.py")
    spec = importlib.util.spec_from_file_location(
        addon_id.replace(".", "_"), entry)
    if spec is None or spec.loader is None:
        raise ImportError(f"no loadable source.py at {entry}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
