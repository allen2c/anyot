from typing import List, Optional

import httpx
import yarl
from pydantic import BaseModel
from str_or_none import str_or_none


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
    version: str | None = None


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
    inspectedTraces: int | None = None
    inspectedBytes: str | None = None
    completedJobs: int
    totalJobs: int


class SearchResponse(BaseModel):
    traces: List[SearchTrace]
    metrics: Metrics


class TempoClient(httpx.Client):
    def __init__(
        self,
        base_url: str | httpx.URL | yarl.URL = "http://localhost:3200",
        *args,
        auth: httpx.Auth | None = None,
        **kwargs,
    ):
        __might_base_url = str_or_none(base_url)
        if __might_base_url is None:
            raise ValueError("base_url must be a string, httpx.URL, or yarl.URL")
        super().__init__(base_url=__might_base_url, auth=auth, *args, **kwargs)

    def health(self) -> bool:
        res = self.get("/api/echo")
        res.raise_for_status()
        return True

    def get_trace(self, trace_id: str) -> TraceV2Response:
        res = self.get(f"/api/v2/traces/{trace_id}")
        res.raise_for_status()
        return TraceV2Response.model_validate(res.json())

    def search_traces(
        self,
        service_name: str,
        *,
        q: Optional[str] = None,
        tags: Optional[str] = None,
        min_duration: Optional[str] = None,
        max_duration: Optional[str] = None,
        limit: Optional[int] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        spss: Optional[int] = None,
    ) -> SearchResponse:
        """
        Search for traces using either TraceQL queries or tag-based search.

        Args:
            service_name: Required service name to search for
            q: TraceQL query (URL encoded)
            tags: Additional logfmt encoding of span-level or process-level attributes
            min_duration: Find traces with at least this duration (e.g., "100ms", "30s")
            max_duration: Find traces with no greater than this duration
            limit: Limit the number of search results (default 20)
            start: Unix epoch seconds for time range start
            end: Unix epoch seconds for time range end
            spss: Limit the number of spans per span-set (default 3)

        Returns:
            SearchResponse containing traces and metrics
        """
        # Build tags parameter with service name
        service_tag = f"service.name={service_name}"
        if tags is not None:
            merged_tags = f"{service_tag} {tags}"
        else:
            merged_tags = service_tag

        params = {}
        if q is not None:
            params["q"] = q
        # Always include tags with service name
        params["tags"] = merged_tags
        if min_duration is not None:
            params["minDuration"] = min_duration
        if max_duration is not None:
            params["maxDuration"] = max_duration
        if limit is not None:
            params["limit"] = limit
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        if spss is not None:
            params["spss"] = spss

        res = self.get("/api/search", params=params)
        res.raise_for_status()
        return SearchResponse.model_validate(res.json())
