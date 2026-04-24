"""Sanity tests for ``addon.xml``.

Task #255 bumped the addon version from 0.8.7 to 0.8.8.  A regression here
would mean Kodi installs would not pick up the fix on update.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
ADDON_XML = os.path.join(ROOT, "addon.xml")


def _parse_addon():
    return ET.parse(ADDON_XML).getroot()


def test_addon_id_is_stable():
    assert _parse_addon().get("id") == "plugin.video.watchorder"


def test_addon_version_bumped_for_task_255():
    assert _parse_addon().get("version") == "0.8.8"
