"""
Centralized file upload validation for all storage uploads.

Usage:
    from app.upload_utils import validate_and_upload

    url, error = validate_and_upload(
        db, file_obj, bucket='profile-images',
        prefix='avatar', owner_id=user_id,
        allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
        max_size=MAX_IMAGE_SIZE
    )
    if error:
        flash(error, 'error')
    else:
        # url contains the public URL
"""

import uuid

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_DOC_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf'}

MAX_IMAGE_SIZE = 5 * 1024 * 1024     # 5 MB
MAX_DOC_SIZE = 10 * 1024 * 1024      # 10 MB

# Maps extensions to their expected MIME type prefixes
_MIME_MAP = {
    'jpg':  'image/',
    'jpeg': 'image/',
    'png':  'image/',
    'gif':  'image/',
    'webp': 'image/',
    'pdf':  'application/pdf',
}


def validate_upload(file_obj, allowed_exts=None, max_size=None):
    """
    Validate a file upload for extension, MIME type, and size.

    Args:
        file_obj: Flask request.files[...] object
        allowed_exts: Set of allowed lowercase extensions (default: ALLOWED_IMAGE_EXTENSIONS)
        max_size: Maximum file size in bytes (default: MAX_IMAGE_SIZE)

    Returns:
        (safe_extension: str, error_message: str | None)
        If error_message is not None, the upload should be rejected.
    """
    if allowed_exts is None:
        allowed_exts = ALLOWED_IMAGE_EXTENSIONS
    if max_size is None:
        max_size = MAX_IMAGE_SIZE

    if not file_obj or not file_obj.filename:
        return None, "No file selected."

    # 1. Extract and validate extension
    filename = file_obj.filename
    if '.' not in filename:
        return None, "File must have an extension (e.g., .jpg, .png)."

    ext = filename.rsplit('.', 1)[-1].lower().strip()
    if ext not in allowed_exts:
        allowed_list = ', '.join(sorted(allowed_exts))
        return None, f"Invalid file type '.{ext}'. Allowed types: {allowed_list}."

    # 2. Validate MIME type matches extension
    content_type = (file_obj.content_type or '').lower()
    expected_mime = _MIME_MAP.get(ext)
    if expected_mime:
        if not content_type.startswith(expected_mime):
            return None, f"File content type '{content_type}' does not match extension '.{ext}'."

    # 3. Check file size
    file_obj.seek(0, 2)  # Seek to end
    file_size = file_obj.tell()
    file_obj.seek(0)     # Reset to beginning

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return None, f"File is too large ({file_size / (1024 * 1024):.1f} MB). Maximum allowed: {max_mb:.0f} MB."

    if file_size == 0:
        return None, "File is empty."

    return ext, None


def generate_safe_filename(prefix, owner_id, ext):
    """
    Generate a safe, unique filename that never uses client-provided names.

    Args:
        prefix: e.g., 'avatar', 'facility', 'court', 'kyc', 'receipt'
        owner_id: User or entity ID for namespacing
        ext: Validated file extension (e.g., 'jpg')

    Returns:
        Safe filename string like 'avatar_abc123_a1b2c3d4.jpg'
    """
    short_id = str(owner_id)[-12:] if owner_id else 'unknown'
    unique = uuid.uuid4().hex[:8]
    return f"{prefix}_{short_id}_{unique}.{ext}"


def validate_and_upload(db, file_obj, bucket, prefix, owner_id,
                        allowed_exts=None, max_size=None):
    """
    Validate and upload a file to Supabase Storage in one call.

    Args:
        db: Supabase client instance
        file_obj: Flask request.files[...] object
        bucket: Storage bucket name (e.g., 'profile-images')
        prefix: Filename prefix (e.g., 'avatar')
        owner_id: User/entity ID
        allowed_exts: Set of allowed extensions
        max_size: Max file size in bytes

    Returns:
        (public_url: str | None, error_message: str | None)
    """
    ext, error = validate_upload(file_obj, allowed_exts, max_size)
    if error:
        return None, error

    filename = generate_safe_filename(prefix, owner_id, ext)
    file_bytes = file_obj.read()

    try:
        db.storage.from_(bucket).upload(
            file=file_bytes,
            path=filename,
            file_options={"content-type": file_obj.content_type}
        )
        public_url = db.storage.from_(bucket).get_public_url(filename)
        return public_url, None
    except Exception as e:
        return None, f"Upload failed. Please try again."
