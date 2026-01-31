from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PIL import Image
import imagehash
import shutil

from sqlalchemy.orm import Session
from models import Screenshot


def deduplicate_directory(
    input_dir: Path,
    output_dir: Path,
    distance_threshold: int = 5,
    db: Optional[Session] = None,
    to_rel=None,
) -> Dict[str, str]:
    """
    Deduplicate images in input_dir using pHash.
    Returns mapping of original file -> kept file.
    If db session provided, update Screenshot records.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping: Dict[str, str] = {}
    seen: List[Tuple[imagehash.ImageHash, Path]] = []

    for img_path in sorted(input_dir.glob("*.jpg")):
        try:
            h = imagehash.phash(Image.open(img_path))
        except Exception:
            continue

        duplicate_of: Path | None = None
        for shash, spath in seen:
            if h - shash <= distance_threshold:
                duplicate_of = spath
                break

        if duplicate_of:
            mapping[str(img_path)] = str(duplicate_of)
            if db:
                shot = db.query(Screenshot).filter_by(file_path=str(img_path)).first()
                if shot:
                    shot.hash_value = str(h)
                    shot.is_duplicate = True
                    shot.kept_path = to_rel(duplicate_of) if to_rel else str(duplicate_of)
            continue

        # keep this image
        target = output_dir / img_path.name
        shutil.copy2(img_path, target)
        seen.append((h, target))
        mapping[str(img_path)] = str(target)

        if db:
            shot = db.query(Screenshot).filter_by(file_path=str(img_path)).first()
            if shot:
                shot.hash_value = str(h)
                shot.is_duplicate = False
                shot.kept_path = to_rel(target) if to_rel else str(target)

    if db:
        db.commit()
    return mapping

