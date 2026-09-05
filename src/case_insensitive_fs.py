import os
from pathlib import Path

from srctools import StringPath
from srctools.filesys import RawFileSystem, RootEscapeError

type CasefoldPath = tuple[str, ...]

class AmbiguousPathError(ValueError):
    base: Path
    segment: str
    match_count: int

    def __init__(self, base: Path, segment: str, match_count: int) -> None:
        self.base = base
        self.segment = segment
        self.match_count = match_count
        super().__init__(base, segment, match_count)

    def __str__(self) -> str:
        return f'Path "{self.base}" contains {self.match_count} ambiguous casefolded matches for "{self.segment}"'

class CaseInsensitiveFs(RawFileSystem):
    _path_cache: dict[CasefoldPath, Path]

    def __init__(self, path: StringPath) -> None:
        self._path_cache = {}
        super().__init__(path, constrain_path = True)

    def _resolve_true_path_uncached(self, base: Path, segment: str) -> Path:
        matches = [child.name for child in base.iterdir() if child.name.casefold() == segment]

        match matches:
            case []:
                raise FileNotFoundError(base / segment)
            case [name]:
                return base / name
            case [*_]:
                raise AmbiguousPathError(base, segment, len(matches))

    def _resolve_true_path(self, path: CasefoldPath) -> Path:
        if len(path) == 0:
            return Path(self.path)

        try:
            return self._path_cache[path]
        except KeyError:
            base = self._resolve_true_path(path[:-1])
            true_path = self._resolve_true_path_uncached(base, path[-1])

            self._path_cache[path] = true_path
            return true_path

    def _resolve_path(self, path: str) -> str:
        abs_path = Path(os.path.abspath(os.path.join(self.path, path.casefold())))

        try:
            rel_path = abs_path.relative_to(self.path)
        except ValueError:
            raise RootEscapeError(self.path, path) from None

        case_path = tuple(rel_path.parts)
        true_path = self._resolve_true_path(case_path)
        return str(true_path)

    def _file_exists(self, name: str) -> bool:
        try:
            self._resolve_path(name)
            return True
        except FileNotFoundError:
            return False
        