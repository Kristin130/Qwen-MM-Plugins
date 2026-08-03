"""Smoke test for the video-edit capability's generation MCP server.

conftest auto-discovers qwen_mm_plugins_video_edit (it scans src/capabilities/*/ for the server
package), so it imports like any other server. Handlers hit remote DashScope APIs, so we only
exercise discovery + the advertised schema/handler surface here (no live calls).
"""

import qwen_mm_plugins_video_edit as ve

GENERATION_TOOLS = {"qwen_image", "qwen_tts", "wan_s2v", "wan_t2v", "happyhorse"}


def test_lists_the_generation_tools():
    names = {t["name"] for t in ve.list_tools()}
    assert names == GENERATION_TOOLS


def test_every_tool_has_schema_and_handler():
    for tool in ve.list_tools():
        assert tool["inputSchema"]["type"] == "object"
        assert callable(ve.get_handler(tool["name"]))


def test_unknown_tool_has_no_handler():
    assert ve.get_handler("does_not_exist") is None
