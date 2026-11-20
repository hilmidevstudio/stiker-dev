"""
StickerDrop Backend Application (FastAPI).
Provides TikTok URL link resolution, extraction provider orchestration,
and clean sticker extraction endpoints for clients.
"""

from typing import Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError

from .schemas import (
    ResolveAndExtractRequest,
    ResolveAndExtractResponse,
    ErrorDetail,
    MediaProxyRequest,
)
from .link_resolver import (
    TikTokLinkResolver,
    ResolvedTarget,
    LinkResolverException,
    MissingCommentIdException,
)
from .extractor_adapter import (
    get_extractor_adapter,
    get_extraction_provider_status,
    ExtractionException,
    CommentNotFoundException,
    StickerNotFoundException,
)
from .media_gateway import MediaGateway
from .comment_discovery import (
    CommentDiscoveryEngine,
    CommentSearchIncompleteException,
    DiscoveryLimits,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stickerdrop.backend")
# httpx INFO logs include complete request URLs. TikTok share redirects may contain
# user/share identifiers and signed query parameters, so log only our sanitized stages.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("StickerDrop FastAPI backend initializing...")
    yield
    logger.info("StickerDrop FastAPI backend shutting down...")


# Create FastAPI App
app = FastAPI(
    title="StickerDrop Backend API",
    description="TikTok comment sticker extraction and media normalization service",
    version="1.2.0",
    lifespan=lifespan
)

# Reuse one gateway per worker so its rate guard, concurrency cap, and bounded cache
# apply across requests instead of resetting for every media-proxy call.
media_gateway = MediaGateway()

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for mobile apps & web dashboards
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(LinkResolverException)
async def link_resolver_exception_handler(request: Request, exc: LinkResolverException):
    # Do not log exception text: malformed inputs and provider redirects can contain URLs.
    logger.warning("Link resolution error on %s (%s)", request.url.path, exc.error_code)
    error_payload = ErrorDetail(
        success=False,
        error_code=exc.error_code,
        message=exc.message,
        details={"path": request.url.path}
    )
    return JSONResponse(status_code=exc.status_code, content=error_payload.model_dump())


@app.exception_handler(ExtractionException)
async def extraction_exception_handler(request: Request, exc: ExtractionException):
    # Exception text can originate from an upstream service; log only a safe code.
    logger.warning("Extraction error on %s (%s)", request.url.path, exc.error_code)
    error_payload = ErrorDetail(
        success=False,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details or {"path": request.url.path}
    )
    response_headers = {}
    if exc.error_code == "MEDIA_RATE_LIMITED":
        response_headers["Retry-After"] = "60"
    elif exc.error_code == "MEDIA_GATEWAY_BUSY":
        response_headers["Retry-After"] = "1"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(),
        headers=response_headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Pydantic error details can contain submitted URLs; log only the route and error count.
    logger.warning("Validation error on %s (%d field error(s))", request.url.path, len(exc.errors()))
    safe_errors = [
        {
            "location": list(error.get("loc", ())),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    error_payload = ErrorDetail(
        success=False,
        error_code="VALIDATION_ERROR",
        message="Invalid request parameters or payload structure.",
        # Pydantic's raw errors can include the complete submitted URL in `input`.
        details={"errors": safe_errors}
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_payload.model_dump())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Avoid exception strings and tracebacks in normal logs/responses because they may
    # contain complete URLs, credentials, or raw upstream payloads.
    logger.error(
        "Unhandled server error on %s (%s)",
        request.url.path,
        type(exc).__name__,
    )
    error_payload = ErrorDetail(
        success=False,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please try again later.",
        details={"path": request.url.path}
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_payload.model_dump())


# ---------------------------------------------------------------------------
# Core Extraction Helper Logic
# ---------------------------------------------------------------------------
async def process_resolve_and_extract(
    url: str,
    max_comment_pages: Optional[int] = None,
) -> ResolveAndExtractResponse:
    """Resolve the link, discover the exact comment, then parse its sticker metadata.

    Discovery is provider-neutral. The currently configured adapter supplies pages;
    this orchestration layer owns cursor traversal, exact matching, and search limits.
    """
    resolver = TikTokLinkResolver()
    target: ResolvedTarget = await resolver.resolve(url)

    if not target.comment_id:
        raise MissingCommentIdException()

    # The factory is fail-closed by default. It will not infer a paid provider merely
    # because an API key happens to exist in the deployment environment.
    adapter = get_extractor_adapter()
    logger.info(
        "Processing extraction for post=%s comment=%s provider=%s",
        target.video_id,
        target.comment_id,
        adapter.provider_name,
    )

    limits = DiscoveryLimits.from_environment()
    if max_comment_pages is not None:
        limits = DiscoveryLimits(
            max_comment_pages=max_comment_pages,
            max_reply_parents=limits.max_reply_parents,
            max_reply_pages_per_parent=limits.max_reply_pages_per_parent,
        )

    discovery = await CommentDiscoveryEngine(limits).find_comment(
        adapter,
        video_url=target.canonical_url,
        target_comment_id=target.comment_id,
        target_author_id=target.author_id,
    )
    matched_comment = discovery.comment
    logger.info("Comment discovery completed: %s", discovery.stats.to_dict())

    if not matched_comment:
        if not discovery.stats.complete:
            raise CommentSearchIncompleteException(discovery.stats)
        raise CommentNotFoundException(target.comment_id)

    sticker = adapter.parse_sticker(matched_comment)
    if not sticker:
        raise StickerNotFoundException(target.comment_id)

    author = adapter.parse_author(matched_comment)

    return ResolveAndExtractResponse(
        success=True,
        message="Sticker metadata extracted successfully",
        video_id=target.video_id,
        comment_id=target.comment_id,
        canonical_url=target.canonical_url,
        comment_text=matched_comment.get("text", ""),
        create_time=int(matched_comment.get("create_time", 0)),
        digg_count=int(matched_comment.get("digg_count", 0)),
        author=author,
        sticker=sticker,
        provider_used=adapter.provider_name,
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "StickerDrop Backend API",
        "version": "1.2.0",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "POST /v1/resolve-link": "Resolve TikTok share URL without calling an extraction provider",
            "POST /v1/resolve-and-extract": "Resolve TikTok comment link and discover sticker metadata",
            "GET /v1/resolve-and-extract": "Resolve TikTok comment link via query parameter ?url=...",
            "GET /v1/extraction-status": "Report configured extraction adapter without making a provider request",
            "POST /v1/media-proxy": "Fetch and validate an approved TikTok CDN WebP through the backend",
            "GET /health": "Server health status"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "StickerDrop Backend",
        "cors_enabled": True
    }


@app.get("/v1/extraction-status", tags=["Diagnostics"])
async def extraction_status():
    """Expose provider selection only; never disclose secrets or make network calls."""
    return get_extraction_provider_status()




@app.post("/v1/media-proxy", tags=["Media"])
async def media_proxy(payload: MediaProxyRequest):
    """Fetch a CDN asset server-side after host, size, redirect, and WebP checks.

    The URL is accepted in a POST body so signed CDN query parameters do not appear
    in ordinary HTTP access-log request lines.
    """
    media_bytes = await media_gateway.fetch(payload.url)
    return Response(
        content=media_bytes,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline; filename=sticker.webp",
        },
    )


@app.post("/v1/resolve-link", tags=["Diagnostics"])
async def resolve_link_only(payload: ResolveAndExtractRequest):
    """Resolve a TikTok share URL without invoking any extraction provider or consuming provider credits."""
    resolver = TikTokLinkResolver()
    target = await resolver.resolve(payload.url)
    return {
        "success": True,
        "stage": "link_resolved_only",
        "provider_called": False,
        "video_id": target.video_id,  # retained for backward compatibility
        "post_id": target.video_id,
        "post_type": target.post_type,
        "comment_id": target.comment_id,
        "author_id": target.author_id,
        "canonical_url": target.canonical_url,
        "is_comment_link": target.is_comment_link,
    }


@app.post(
    "/v1/resolve-and-extract",
    response_model=ResolveAndExtractResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Invalid URL provided"},
        404: {"model": ErrorDetail, "description": "Comment or sticker not found"},
        422: {"model": ErrorDetail, "description": "Link missing comment ID"},
        500: {"model": ErrorDetail, "description": "Provider authentication error"},
        502: {"model": ErrorDetail, "description": "Upstream extraction provider error"},
    },
    tags=["Extraction"]
)
async def resolve_and_extract_post(payload: ResolveAndExtractRequest):
    """
    POST Endpoint: Accepts JSON payload with TikTok comment URL.
    Cleans and resolves link, queries extraction provider, and extracts clean sticker metadata.
    """
    return await process_resolve_and_extract(url=payload.url)


@app.get(
    "/v1/resolve-and-extract",
    response_model=ResolveAndExtractResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Invalid URL provided"},
        404: {"model": ErrorDetail, "description": "Comment or sticker not found"},
        422: {"model": ErrorDetail, "description": "Link missing comment ID"},
        500: {"model": ErrorDetail, "description": "Provider authentication error"},
        502: {"model": ErrorDetail, "description": "Upstream extraction provider error"},
    },
    tags=["Extraction"]
)
async def resolve_and_extract_get(
    url: str = Query(..., description="TikTok comment link (e.g. vt.tiktok.com or canonical URL)")
):
    """
    GET Endpoint: Accepts query parameter `?url=...`.
    Cleans and resolves link, queries extraction provider, and extracts clean sticker metadata.
    """
    return await process_resolve_and_extract(url=url)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
