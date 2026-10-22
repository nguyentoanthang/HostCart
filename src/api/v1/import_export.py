"""
Import/Export API endpoints for HostCart.
Provides collection data export in JSON and CSV formats and batch import.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlmodel import Session

from src.api.v1.auth import get_current_user
from src.core.import_export import (
    export_collection_csv,
    export_collection_json,
    import_collection_csv,
    import_collection_json,
)
from src.data.database import get_session
from src.data.models import MediaType, User

router = APIRouter(prefix="/import-export", tags=["import-export"])


@router.get("/export")
def export_collection(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    media_type: Optional[MediaType] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """
    Export the user's collection in JSON or CSV format.
    Optionally filter by media_type.
    """
    if format == "csv":
        csv_data = export_collection_csv(
            session=session,
            user_id=current_user.id,
            media_type=media_type,
        )
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="hostcart_export.csv"'},
        )

    # Default: json
    json_data = export_collection_json(
        session=session,
        user_id=current_user.id,
        media_type=media_type,
    )
    content = json.dumps(json_data, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="hostcart_export.json"'},
    )


@router.post("/import")
async def import_collection(
    request: Request,
    skip_duplicates: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, int]:
    """
    Import collection entries from a JSON body, CSV text, or uploaded file (.json / .csv).
    Handles catalog deduplication and user entry creation.
    """
    content_type = request.headers.get("content-type", "").lower()

    # 1. Handle multipart form file upload
    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if not uploaded_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded in form data",
            )

        filename = getattr(uploaded_file, "filename", "").lower()
        content_bytes = await uploaded_file.read()
        text_content = content_bytes.decode("utf-8", errors="replace")

        if filename.endswith(".csv"):
            return import_collection_csv(
                session=session,
                user_id=current_user.id,
                csv_text=text_content,
                skip_duplicates=skip_duplicates,
            )
        else:
            try:
                parsed_json = json.loads(text_content)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON file format: {e}",
                )
            items = (
                parsed_json.get("items", [])
                if isinstance(parsed_json, dict) and "items" in parsed_json
                else (parsed_json if isinstance(parsed_json, list) else [parsed_json])
            )
            return import_collection_json(
                session=session,
                user_id=current_user.id,
                items=items,
                skip_duplicates=skip_duplicates,
            )

    # 2. Handle raw CSV payload
    if "text/csv" in content_type:
        body_bytes = await request.body()
        csv_text = body_bytes.decode("utf-8", errors="replace")
        return import_collection_csv(
            session=session,
            user_id=current_user.id,
            csv_text=csv_text,
            skip_duplicates=skip_duplicates,
        )

    # 3. Handle JSON payload
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse JSON body: {e}",
        )

    if isinstance(body, list):
        items = body
    elif isinstance(body, dict) and "items" in body and isinstance(body["items"], list):
        items = body["items"]
    elif isinstance(body, dict):
        items = [body]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON body must be a list of items or an object with an 'items' array",
        )

    return import_collection_json(
        session=session,
        user_id=current_user.id,
        items=items,
        skip_duplicates=skip_duplicates,
    )
