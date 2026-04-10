"""
Celery tasks for the stadiums app.

Tasks:
  generate_slots_for_all_stadiums — daily Beat task; idempotent slot generation
  process_stadium_photo           — generates thumbnail + medium variants after upload
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, time, timedelta

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

SLOT_GENERATION_HORIZON_DAYS = 60


# ---------------------------------------------------------------------------
# Slot generation
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_slots_for_all_stadiums(self):
    """
    Celery Beat daily task.

    For every active stadium with at least one operating hour record, generate
    slots for today through today + SLOT_GENERATION_HORIZON_DAYS.
    Already-existing slots are skipped (idempotent via get_or_create).
    """
    from apps.stadiums.models import OperatingHour, Slot, Stadium, StadiumStatus

    try:
        active_stadiums = Stadium.objects.filter(
            status=StadiumStatus.ACTIVE
        ).prefetch_related("operating_hours")

        today = date.today()
        horizon = today + timedelta(days=SLOT_GENERATION_HORIZON_DAYS)

        total_created = 0
        for stadium in active_stadiums:
            created = _generate_slots_for_stadium(stadium, today, horizon)
            total_created += created

        logger.info(
            "Slot generation complete. Created %d new slots across %d stadiums.",
            total_created,
            active_stadiums.count(),
        )
        return {"created": total_created}

    except Exception as exc:
        logger.exception("Slot generation failed: %s", exc)
        raise self.retry(exc=exc)


def _generate_slots_for_stadium(stadium, start_date: date, end_date: date) -> int:
    """Generate slots for a single stadium between start_date and end_date (exclusive)."""
    from apps.stadiums.models import OperatingHour, Slot

    hours_by_day = {
        oh.day_of_week: oh
        for oh in stadium.operating_hours.all()
    }

    created_count = 0
    current = start_date
    while current < end_date:
        day_of_week = current.weekday()  # 0=Monday … 6=Sunday
        oh: OperatingHour | None = hours_by_day.get(day_of_week)

        if oh and not oh.is_closed and oh.open_time and oh.close_time:
            created_count += _create_slots_for_day(stadium, current, oh)

        current += timedelta(days=1)

    return created_count


def _create_slots_for_day(stadium, slot_date: date, oh) -> int:
    """Create all slots for a single (stadium, date) combination."""
    from apps.stadiums.models import Slot, SlotStatus

    duration = timedelta(minutes=stadium.slot_duration_minutes)
    open_dt = datetime.combine(slot_date, oh.open_time)
    close_dt = datetime.combine(slot_date, oh.close_time)

    created_count = 0
    current = open_dt
    while current + duration <= close_dt:
        slot_start = current.time()
        slot_end = (current + duration).time()
        _, created = Slot.objects.get_or_create(
            stadium=stadium,
            date=slot_date,
            start_time=slot_start,
            defaults={"end_time": slot_end, "status": SlotStatus.AVAILABLE},
        )
        if created:
            created_count += 1
        current += duration

    return created_count


# ---------------------------------------------------------------------------
# Photo processing
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_stadium_photo(self, photo_id: int):
    """
    Generate thumbnail (400×300) and medium (800×600) variants for a stadium photo.
    Stores variants using the configured file storage backend and writes the
    absolute URLs back to StadiumPhoto.thumbnail_url / medium_url.
    """
    try:
        from PIL import Image

        from apps.stadiums.models import StadiumPhoto

        photo = StadiumPhoto.objects.select_related("stadium").get(pk=photo_id)

        with photo.image.open("rb") as f:
            original = Image.open(f)
            original.load()

        thumbnail_url = _save_variant(original, photo, "thumbnail", (400, 300))
        medium_url = _save_variant(original, photo, "medium", (800, 600))

        StadiumPhoto.objects.filter(pk=photo_id).update(
            thumbnail_url=thumbnail_url,
            medium_url=medium_url,
        )
        logger.info("Processed photo %d — thumbnail and medium variants saved.", photo_id)
        return {"photo_id": photo_id, "thumbnail_url": thumbnail_url, "medium_url": medium_url}

    except StadiumPhoto.DoesNotExist:
        logger.warning("StadiumPhoto %d not found — skipping processing.", photo_id)
        return None
    except Exception as exc:
        logger.exception("Photo processing failed for photo %d: %s", photo_id, exc)
        raise self.retry(exc=exc)


def _save_variant(original_image, photo, variant_name: str, size: tuple[int, int]) -> str:
    """Resize image to ``size``, save via default_storage, return absolute URL."""
    from PIL import Image

    img = original_image.copy()
    img.thumbnail(size, Image.LANCZOS)

    # Pad to exact size with black bars if aspect ratio differs
    canvas = Image.new("RGB", size, (0, 0, 0))
    offset_x = (size[0] - img.width) // 2
    offset_y = (size[1] - img.height) // 2
    canvas.paste(img, (offset_x, offset_y))

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=85, optimize=True)
    buffer.seek(0)

    original_name = photo.image.name.replace("original/", "")
    stem = original_name.rsplit(".", 1)[0]
    variant_path = f"stadiums/photos/{variant_name}/{stem}.jpg"

    saved_path = default_storage.save(variant_path, ContentFile(buffer.read()))
    return default_storage.url(saved_path)
