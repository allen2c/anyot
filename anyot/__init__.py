import logging
import os
import pathlib
import typing
from typing import Dict, Optional

import logfire
import opentelemetry.sdk.resources
import opentelemetry.sdk.trace
import opentelemetry.trace
import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider
from pydantic import BaseModel, Field
from str_or_none import str_or_none

logger = logging.getLogger(__name__)


__version__ = pathlib.Path(__file__).parent.joinpath("VERSION").read_text().strip()


def get_otel_exporter_otlp_endpoint(
    otel_exporter_otlp_endpoint: typing.Optional[str] = None,
    *,
    raise_empty: bool = False,
) -> typing.Optional[str]:
    if otel_exporter_otlp_endpoint is None:
        otel_exporter_otlp_endpoint = str_or_none(
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        )

    if raise_empty and otel_exporter_otlp_endpoint is None:
        raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT is not set.")  # noqa: E501

    return otel_exporter_otlp_endpoint


def get_otel_exporter_otlp_traces_endpoint(
    otel_exporter_otlp_traces_endpoint: typing.Optional[str] = None,
    *,
    otel_exporter_otlp_endpoint: typing.Optional[str] = None,
    raise_empty: bool = False,
) -> typing.Optional[str]:
    if otel_exporter_otlp_traces_endpoint is None:
        otel_exporter_otlp_traces_endpoint = str_or_none(
            os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)
        )

    if otel_exporter_otlp_traces_endpoint is None:
        otel_exporter_otlp_endpoint = get_otel_exporter_otlp_endpoint(
            otel_exporter_otlp_endpoint, raise_empty=False
        )
        if otel_exporter_otlp_endpoint is not None:
            otel_exporter_otlp_traces_endpoint = (
                f"{otel_exporter_otlp_endpoint}/v1/traces"
            )
            logger.debug(
                "Set OTel exporter traces endpoint from OTel endpoint: "
                + f"{otel_exporter_otlp_traces_endpoint}"
            )
    else:
        logger.debug(
            "Set OTel exporter traces endpoint: "
            + f"{otel_exporter_otlp_traces_endpoint}"
        )

    if raise_empty and otel_exporter_otlp_traces_endpoint is None:
        raise ValueError("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is not set.")  # noqa: E501

    return otel_exporter_otlp_traces_endpoint


def get_resource(
    otel_resource_attributes: typing.Optional[str] = None,
    *,
    raise_empty: bool = False,
) -> opentelemetry.sdk.resources.Resource:
    # Use provided attributes or fall back to environment variable
    if otel_resource_attributes is None:
        otel_resource_attributes = str_or_none(
            os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        )

    # Parse attributes string into a dictionary
    attributes = {}
    if otel_resource_attributes:
        for item in otel_resource_attributes.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                attributes[key.strip()] = value.strip()

    if raise_empty and not attributes:
        raise ValueError("OTEL_RESOURCE_ATTRIBUTES is not set.")

    return Resource.create(attributes)


def get_tracer_provider(
    *,
    otel_exporter_otlp_endpoint: typing.Optional[str] = None,
    otel_exporter_otlp_traces_endpoint: typing.Optional[str] = None,
    otel_resource_attributes: typing.Optional[str] = None,
    ping_otel_exporter_healthy: bool = True,
    raise_empty: bool = False,
    use_noop_tracer_provider_if_unhealthy: bool = True,
) -> opentelemetry.trace.TracerProvider:
    otel_exporter_otlp_traces_endpoint = get_otel_exporter_otlp_traces_endpoint(
        otel_exporter_otlp_traces_endpoint,
        otel_exporter_otlp_endpoint=otel_exporter_otlp_endpoint,
        raise_empty=False,
    )
    if not otel_exporter_otlp_traces_endpoint and raise_empty:
        raise ValueError(
            "OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is not set."  # noqa: E501
        )

    resource = get_resource(
        otel_resource_attributes,
        raise_empty=raise_empty,
    )

    provider = opentelemetry.sdk.trace.TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(
        endpoint=otel_exporter_otlp_traces_endpoint,
    )

    if ping_otel_exporter_healthy:
        is_otlp_exporter_healthy = ping_otel_exporter_otlp_traces_endpoint(
            otlp_exporter._endpoint
        )
        if not is_otlp_exporter_healthy:
            if use_noop_tracer_provider_if_unhealthy:
                logger.warning(
                    "OTel exporter traces endpoint is not healthy: "
                    + f"{otel_exporter_otlp_traces_endpoint}, "
                    + "using NoOpTracerProvider instead."
                )
                return NoOpTracerProvider()
            raise ValueError(
                "OTel exporter traces endpoint is not healthy: "
                + f"{otel_exporter_otlp_traces_endpoint}"
            )

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    return provider


def ping_otel_exporter_otlp_traces_endpoint(
    otel_exporter_otlp_traces_endpoint: str,
) -> bool:
    try:
        res = requests.get(otel_exporter_otlp_traces_endpoint)
        res.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        res = e.response
        if res.status_code == 405:  # Method not allowed
            return True
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error pinging OTel exporter traces endpoint: {e}")
        return False
    except Exception as e:
        logger.exception(e)
        return False


def configure(
    *,
    tracer_provider: typing.Optional[opentelemetry.trace.TracerProvider] = None,
    otel_exporter_otlp_endpoint: typing.Optional[str] = None,
    otel_resource_attributes: typing.Optional[
        typing.Union["OtelResourceAttributes", str]
    ] = None,
    ping_otel_exporter_healthy: bool = True,
    raise_empty: bool = False,
    use_logfire: bool = True,
    send_to_logfire: bool = False,
    use_noop_tracer_provider_if_unhealthy: bool = True,
    distributed_tracing: bool = False,
):
    otel_resource_attributes = (
        OtelResourceAttributes.from_string(otel_resource_attributes)
        if not isinstance(otel_resource_attributes, OtelResourceAttributes)
        else otel_resource_attributes
    )

    if tracer_provider is None:
        tracer_provider = get_tracer_provider(
            otel_exporter_otlp_endpoint=otel_exporter_otlp_endpoint,
            otel_resource_attributes=otel_resource_attributes.to_string(),
            ping_otel_exporter_healthy=ping_otel_exporter_healthy,
            raise_empty=raise_empty,
            use_noop_tracer_provider_if_unhealthy=use_noop_tracer_provider_if_unhealthy,
        )

    # If the tracer provider is a NoOpTracerProvider, we don't need to use logfire
    if use_logfire and isinstance(tracer_provider, NoOpTracerProvider):
        logger.warning(
            "OTel exporter traces endpoint is not healthy, "
            + "using NoOpTracerProvider instead, "
            + "set `use_logfire=False` to disable logfire."
        )
        use_logfire = False

    if use_logfire:
        logfire.configure(
            send_to_logfire=send_to_logfire,
            service_name=otel_resource_attributes.service_name,
            service_version=otel_resource_attributes.service_version,
            environment=otel_resource_attributes.deployment_environment,
            distributed_tracing=distributed_tracing,
        )
    else:
        opentelemetry.trace.set_tracer_provider(tracer_provider)

    return None


class OtelResourceAttributes(BaseModel):
    # Service attributes
    service_name: Optional[str] = Field(
        default=None,
        description="Logical name of the service",
    )
    service_namespace: Optional[str] = Field(
        default=None,
        description="A namespace for service.name",
    )
    service_instance_id: Optional[str] = Field(
        default=None,
        description="The string ID of the service instance",
    )
    service_version: Optional[str] = Field(
        default=None,
        description="The version string of the service API or implementation",
    )

    # Telemetry SDK attributes
    telemetry_sdk_name: Optional[str] = Field(
        default=None,
        description="The name of the telemetry SDK (default: 'opentelemetry')",
    )
    telemetry_sdk_language: Optional[str] = Field(
        default=None,
        description="The language of the telemetry SDK",
    )
    telemetry_sdk_version: Optional[str] = Field(
        default=None,
        description="The version string of the telemetry SDK",
    )

    # Telemetry distro attributes
    telemetry_distro_name: Optional[str] = Field(
        default=None,
        description="The name of the auto instrumentation agent or distribution",
    )
    telemetry_distro_version: Optional[str] = Field(
        default=None,
        description="The version string of the auto instrumentation agent or distribution",  # noqa: E501
    )

    # Deployment attributes
    deployment_environment: Optional[str] = Field(
        default=None,
        description="The deployment environment (e.g., 'production', 'staging', 'test')",  # noqa: E501
    )

    # Host attributes
    host_name: Optional[str] = Field(
        default=None,
        description="Name of the host",
    )
    host_type: Optional[str] = Field(
        default=None,
        description="Type of host",
    )

    # OS attributes
    os_name: Optional[str] = Field(
        default=None,
        description="Operating system name",
    )
    os_version: Optional[str] = Field(
        default=None,
        description="Operating system version",
    )

    # Container attributes
    container_id: Optional[str] = Field(
        default=None,
        description="Container ID",
    )
    container_name: Optional[str] = Field(
        default=None,
        description="Container name",
    )
    container_image_name: Optional[str] = Field(
        default=None,
        description="Name of the container image",
    )
    container_image_tag: Optional[str] = Field(
        default=None,
        description="Tag of the container image",
    )

    # Process attributes
    process_pid: Optional[int] = Field(
        default=None,
        description="Process identifier (PID)",
    )
    process_executable_name: Optional[str] = Field(
        default=None,
        description="The name of the process executable",
    )
    process_executable_path: Optional[str] = Field(
        default=None,
        description="The full path to the process executable",
    )
    process_command: Optional[str] = Field(
        default=None,
        description="The command used to launch the process",
    )
    process_command_line: Optional[str] = Field(
        default=None,
        description="The full command line used to launch the process",
    )
    process_runtime_name: Optional[str] = Field(
        default=None,
        description="The name of the runtime of this process",
    )
    process_runtime_version: Optional[str] = Field(
        default=None,
        description="The version of the runtime of this process",
    )
    process_runtime_description: Optional[str] = Field(
        default=None,
        description="An additional description about the runtime of the process",
    )

    # Custom attributes (can be any key-value pair)
    custom_attributes: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom resource attributes",
    )

    @classmethod
    def from_string(cls, attr_string: Optional[str]) -> "OtelResourceAttributes":
        if not attr_string:
            return cls()  # type: ignore

        attributes = {}
        custom_attributes = {}

        # Get all field names from the model
        model_fields = cls.model_fields.keys() if hasattr(cls, "model_fields") else {}

        for item in attr_string.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Map to the pydantic model field names (convert dots to underscores)
                mapped_key = key.replace(".", "_")

                # Check if this is a field in our model
                if mapped_key in model_fields:
                    attributes[mapped_key] = value
                else:
                    # Custom attribute
                    custom_attributes[key] = value

        if custom_attributes:
            attributes["custom_attributes"] = custom_attributes

        return cls(**attributes)

    def to_string(self) -> str:
        result = []

        # Add model attributes (converting underscores back to dots)
        for key, value in self.model_dump(
            exclude={"custom_attributes"}, exclude_none=True
        ).items():
            otel_key = key.replace("_", ".")
            result.append(f"{otel_key}={value}")

        # Add custom attributes
        if self.custom_attributes:
            for key, value in self.custom_attributes.items():
                result.append(f"{key}={value}")

        return ",".join(result)
