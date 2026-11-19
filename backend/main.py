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
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .schemas import (
    ResolveAndExtractRequest,
    ResolveAndExtractResponse,
    ErrorDetail,
)
from .link_resolver import (
    TikTokLinkResolver,
    ResolvedTarget,
    LinkResolverException,
    MissingCommentIdException,
)
from .extractor_adapter import (
    ExtractorAdapter,
    get_extractor_adapter,
    ExtractionException,
    CommentNotFoundException,
    StickerNotFoundException,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stickerdrop.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("StickerDrop FastAPI backend initializing...")
    yield
    logger.info("StickerDrop FastAPI backend shutting down...")


# Create FastAPI App
app = FastAPI(
    title="StickerDrop Backend API",
    description="TikTok comment sticker extraction and media normalization service",
    version="1.0.0",
    lifespan=lifespan
)

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
    logger.warning(f"Link resolution error on {request.url.path}: {exc.message}")
    error_payload = ErrorDetail(
        success=False,
        error_code=exc.error_code,
        message=exc.message,
        details={"path": request.url.path}
    )
    return JSONResponse(status_code=exc.status_code, content=error_payload.model_dump())


@app.exception_handler(ExtractionException)
async def extraction_exception_handler(request: Request, exc: ExtractionException):
    logger.warning(f"Extraction error on {request.url.path}: {exc.message}")
    error_payload = ErrorDetail(
        success=False,
        error_code=exc.error_code,
        message=exc.message,
        details={"path": request.url.path}
    )
    return JSONResponse(status_code=exc.status_code, content=error_payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    error_payload = ErrorDetail(
        success=False,
        error_code="VALIDATION_ERROR",
        message="Invalid request parameters or payload structure.",
        details={"errors": exc.errors()}
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_payload.model_dump())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url.path}: {str(exc)}", exc_info=True)
    error_payload = ErrorDetail(
        success=False,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please try again later.",
        details={"error": str(exc)}
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_payload.model_dump())


# ---------------------------------------------------------------------------
# Core Extraction Helper Logic
# ---------------------------------------------------------------------------
async def process_resolve_and_extract(
    url: str,
    max_comment_pages: int = 5
) -> ResolveAndExtractResponse:
    """
    Shared business logic for resolving a TikTok comment link and extracting its sticker.
    """
    resolver = TikTokLinkResolver()
    # The provider is selected by server configuration only. Never let a public
    # client request switch production traffic to a mock or alternate provider.
    adapter = get_extractor_adapter()
    target: ResolvedTarget = await resolver.resolve(url)

    # For resolved targets with no comment_id (e.g. canonical video link, no share_comment_id param),
    # always raise — even in MockProvider. The user must share the specific comment link.
    if not target.comment_id:
        raise MissingCommentIdException()
    logger.info(
        f"Processing extraction for Video: {target.video_id}, Comment: {target.comment_id} "
        f"using provider: {adapter.provider_name}"
    )

    matched_comment: Optional[Dict[str, Any]] = None
    cursor = 0
    pages_checked = 0

    # Phase 1: Search top-level comments & their reply_comment previews
    parent_cids_with_replies = []
    while pages_checked < max_comment_pages:
        data = await adapter.fetch_comments(
            video_url=target.canonical_url,
            cursor=cursor,
            count=50
        )
        comments = data.get("comments") or []
        for c in comments:
            cid = str(c.get("cid") or c.get("id") or "")
            if cid == target.comment_id:
                matched_comment = c
                break

            # Check inside reply_comment previews (TikTok attaches up to 3 previews in parent)
            replies_preview = c.get("reply_comment") or []
            for rep in replies_preview:
                rcid = str(rep.get("cid") or rep.get("id") or "")
                if rcid == target.comment_id:
                    matched_comment = rep
                    break
            if matched_comment:
                break

            if (c.get("reply_comment_total", 0) > 0 or len(replies_preview) > 0) and cid:
                if cid not in parent_cids_with_replies:
                    parent_cids_with_replies.append(cid)

        if matched_comment:
            break

        has_more = bool(data.get("has_more", False))
        next_cursor = data.get("cursor")
        if not has_more or next_cursor is None or next_cursor == cursor:
            break

        cursor = next_cursor
        pages_checked += 1

    # Phase 2: If not found in top-level or previews, search comment reply threads concurrently
    if not matched_comment:
        logger.info(f"Comment {target.comment_id} not found in top-level or previews. Checking reply threads...")
        
        # Search candidate parent threads sequentially. Each provider replies request may be billable,
        # so do not fire all candidate requests concurrently when the first successful response is enough.
        if not matched_comment and parent_cids_with_replies:
            for parent_cid in parent_cids_with_replies[:4]:
                try:
                    r_data = await adapter.fetch_replies(
                        comment_id=parent_cid,
                        video_url=target.canonical_url
                    )
                    for reply in r_data.get("comments") or []:
                        if str(reply.get("cid") or reply.get("id") or "") == target.comment_id:
                            matched_comment = reply
                            break
                    if matched_comment:
                        break
                except Exception as e:
                    logger.warning(f"Reply lookup for parent {parent_cid} failed: {str(e)}")

    # Never fabricate a comment or media URL. A miss must remain an explicit failure.
    if not matched_comment:
        raise CommentNotFoundException(target.comment_id)

    # Phase 3: Parse sticker metadata
    sticker = adapter.parse_sticker(matched_comment)
    if not sticker:
        raise StickerNotFoundException(target.comment_id)

    author = adapter.parse_author(matched_comment)

    return ResolveAndExtractResponse(
        success=True,
        message="Sticker extracted successfully",
        video_id=target.video_id,
        comment_id=target.comment_id,
        canonical_url=target.canonical_url,
        comment_text=matched_comment.get("text", ""),
        create_time=int(matched_comment.get("create_time", 0)),
        digg_count=int(matched_comment.get("digg_count", 0)),
        author=author,
        sticker=sticker,
        provider_used=adapter.provider_name
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "StickerDrop Backend API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "POST /v1/resolve-link": "Resolve TikTok share URL without calling an extraction provider",
            "POST /v1/resolve-and-extract": "Resolve TikTok comment link and extract sticker",
            "GET /v1/resolve-and-extract": "Resolve TikTok comment link via query parameter ?url=...",
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
