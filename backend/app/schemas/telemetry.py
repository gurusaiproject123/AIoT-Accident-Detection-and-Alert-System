from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    model_validator,
)


def normalize_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


UtcTimestamp = Annotated[AwareDatetime, AfterValidator(normalize_utc)]
SensorValue = Annotated[FiniteFloat, Field(ge=-3.4e38, le=3.4e38)]


class MotionSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_at: UtcTimestamp
    accel_x: SensorValue
    accel_y: SensorValue
    accel_z: SensorValue
    gyro_x: SensorValue
    gyro_y: SensorValue
    gyro_z: SensorValue


class GpsFix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_at: UtcTimestamp
    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    speed_kmh: FiniteFloat | None = Field(default=None, ge=0, le=3.4e38)


class TelemetryPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    vehicle_id: UUID
    boot_id: UUID
    sequence_number: int = Field(strict=True, ge=0, le=9223372036854775807)
    sample_count: int = Field(strict=True, ge=1, le=1600)
    sampling_hz: Literal[100] = 100
    acceleration_unit: Literal["m/s^2"] = "m/s^2"
    rotation_unit: Literal["deg/s"] = "deg/s"
    recorded_start: UtcTimestamp
    recorded_end: UtcTimestamp
    gps: GpsFix | None = None
    samples: list[MotionSample] = Field(min_length=1, max_length=1600)

    @model_validator(mode="after")
    def validate_recording(self):
        if self.sample_count != len(self.samples):
            raise ValueError("sample_count must match the samples list.")

        if self.recorded_start != self.samples[0].recorded_at:
            raise ValueError(
                "recorded_start must equal the first sample timestamp."
            )

        if self.recorded_end != self.samples[-1].recorded_at:
            raise ValueError(
                "recorded_end must equal the last sample timestamp."
            )

        previous_time = None

        for index, sample in enumerate(self.samples):
            if previous_time is not None and sample.recorded_at <= previous_time:
                raise ValueError("Sample timestamps must strictly increase.")

            actual_offset = (
                sample.recorded_at - self.recorded_start
            ).total_seconds()
            expected_offset = index / self.sampling_hz

            if abs(actual_offset - expected_offset) > 0.005:
                raise ValueError(
                    "Samples must follow 100 Hz timing within "
                    "5 milliseconds of their expected positions."
                )

            previous_time = sample.recorded_at

        return self


class TelemetryPrediction(BaseModel):
    crash_score: FiniteFloat = Field(ge=0, le=1)
    threshold: FiniteFloat = Field(ge=0, le=1)
    predicted_class: Literal[0, 1]
    label: str


class TelemetryResult(BaseModel):
    packet_id: UUID
    duplicate: bool
    sample_count: int
    samples_saved: int
    received_at: AwareDatetime
    detection_performed: bool = False
    prediction: TelemetryPrediction | None = None
    prediction_saved: bool = False
    incident_id: UUID | None = None