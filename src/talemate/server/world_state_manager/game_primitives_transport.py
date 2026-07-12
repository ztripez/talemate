"""Common strict transport and routing contracts for Game Primitives."""

from typing import Literal

import pydantic


class GamePrimitivesTransportModel(pydantic.BaseModel):
    """Apply strict validation to every Game Primitives transport model."""

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, allow_inf_nan=False, revalidate_instances="always"
    )


class GamePrimitivesRoutingEnvelope(GamePrimitivesTransportModel):
    """Carry fields needed for preliminary websocket request routing."""

    model_config = pydantic.ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    type: Literal["world_state_manager"]
    action: str = pydantic.Field(min_length=1)
    request_id: str = pydantic.Field(min_length=1)


class GamePrimitivesRoutingProbe(GamePrimitivesTransportModel):
    """Identify Game Primitives routing before complete request validation."""

    model_config = pydantic.ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    action: str = pydantic.Field(min_length=1)


class GamePrimitivesRequestModel(GamePrimitivesTransportModel):
    """Correlate one strictly validated action with its websocket response."""

    type: Literal["world_state_manager"]
    action: str
    request_id: str = pydantic.Field(min_length=1)
