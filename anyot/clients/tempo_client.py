from typing import List, Optional

from pydantic import BaseModel


class StringValue(BaseModel):
    stringValue: str


class IntValue(BaseModel):
    intValue: str | int


class AttributeValue(BaseModel):
    stringValue: Optional[str] = None
    intValue: Optional[str | int] = None


class Attribute(BaseModel):
    key: str
    value: AttributeValue


class Resource(BaseModel):
    attributes: List[Attribute]


class Scope(BaseModel):
    name: str
    version: str


class Status(BaseModel):
    pass


class Span(BaseModel):
    traceId: str
    spanId: str
    parentSpanId: Optional[str] = None
    name: str
    kind: str
    startTimeUnixNano: str
    endTimeUnixNano: str
    attributes: List[Attribute]
    status: Status


class ScopeSpan(BaseModel):
    scope: Scope
    spans: List[Span]


class ResourceSpan(BaseModel):
    resource: Resource
    scopeSpans: List[ScopeSpan]


class Trace(BaseModel):
    resourceSpans: List[ResourceSpan]


class TraceV2Response(BaseModel):
    trace: Trace


class Batch(BaseModel):
    """
    Represents a batch of trace data, including a resource and its scope spans.
    This corresponds to each element in the 'batches' list.
    """

    resource: Resource
    scopeSpans: List[ScopeSpan]


class TraceV1Response(BaseModel):
    """
    Represents the root structure of the trace data, containing a list of batches.
    """

    batches: List[Batch]


class SearchTrace(BaseModel):
    traceID: str
    rootServiceName: str
    rootTraceName: Optional[str] = None
    startTimeUnixNano: str
    durationMs: Optional[int] = None


class Metrics(BaseModel):
    inspectedTraces: int
    inspectedBytes: str
    completedJobs: int
    totalJobs: int


class SearchResponse(BaseModel):
    traces: List[SearchTrace]
    metrics: Metrics
