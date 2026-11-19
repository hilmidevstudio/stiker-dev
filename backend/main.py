"""
StickerDrop Backend Application (FastAPI).
Provides TikTok URL link resolution, extraction provider orchestration,
and clean sticker extraction endpoints for clients.
"""

from typing import Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .schemas import (
    ResolveAndExtractRequest,
    ResolveAndExtractResponse,
    ErrorDetail,
    CommentAuthorResponse,
    StickerMediaResponse,
)
from .link_resolver import (
    TikTokLinkResolver,
    ResolvedTarget,
    LinkResolverException,
    InvalidUrlException,
    MissingCommentIdException,
)
from .extractor_adapter import (
    ExtractorAdapter,
    get_extractor_adapter,
    ExtractionException,
    ProviderAuthException,
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
    provider_override: Optional[str] = None,
    max_comment_pages: int = 5
) -> ResolveAndExtractResponse:
    """
    Shared business logic for resolving a TikTok comment link and extracting its sticker.
    """
    resolver = TikTokLinkResolver()
    target: ResolvedTarget = await resolver.resolve(url)

    if not target.comment_id:
        raise MissingCommentIdException()

    adapter = get_extractor_adapter(provider_override)
    logger.info(
        f"Processing extraction for Video: {target.video_id}, Comment: {target.comment_id} "
        f"using provider: {adapter.provider_name}"
    )

    matched_comment: Optional[Dict[str, Any]] = None
    cursor = 0
    pages_checked = 0

    # Phase 1: Search top-level comments
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

        if matched_comment:
            break

        has_more = bool(data.get("has_more", False))
        next_cursor = data.get("cursor")
        if not has_more or next_cursor is None or next_cursor == cursor:
            break

        cursor = next_cursor
        pages_checked += 1

    # Phase 2: If not found in top-level, search comment replies thread
    if not matched_comment:
        logger.info(f"Comment {target.comment_id} not found in top-level comments. Checking reply threads...")
        try:
            reply_data = await adapter.fetch_replies(
                comment_id=target.comment_id,
                video_url=target.canonical_url
            )
            replies = reply_data.get("comments") or []
            for r in replies:
                cid = str(r.get("cid") or r.get("id") or "")
                if cid == target.comment_id:
                    matched_comment = r
                    break
        except Exception as e:
            logger.warning(f"Reply thread lookup failed: {str(e)}")

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
    return await process_resolve_and_extract(
        url=payload.url,
        provider_override=payload.provider
    )


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
    url: str = Query(..., description="TikTok comment link (e.g. vt.tiktok.com or canonical URL)"),
    provider: Optional[str] = Query(None, description="Optional provider override: 'scrapesocial', 'scrapecreators', or 'mock'")
):
    """
    GET Endpoint: Accepts query parameter `?url=...`.
    Cleans and resolves link, queries extraction provider, and extracts clean sticker metadata.
    """
    return await process_resolve_and_extract(
        url=url,
        provider_override=provider
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
