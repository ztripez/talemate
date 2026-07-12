"""Tests for loading-status cleanup on failures."""

import pytest

import talemate.status as status_module


@pytest.mark.asyncio
async def test_set_loading_clears_busy_status_after_error(monkeypatch):
    """A failed loading operation without an error status returns to idle."""
    emitted = []
    monkeypatch.setattr(
        status_module,
        "emit",
        lambda event, **payload: emitted.append((event, payload)),
    )

    @status_module.set_loading("Loading")
    async def fail():
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        await fail()

    assert emitted == [
        ("status", {"message": "Loading", "status": "busy", "data": {}}),
        ("status", {"message": "", "status": "idle"}),
    ]
