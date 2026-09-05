from collections.abc import Iterator, Iterable
from typing import Self, TextIO, BinaryIO
from pathlib import Path, PurePath
import filecmp

from srctools import StringPath, logger
from srctools.filesys import File, FileSystem, RootEscapeError, CACHE_KEY_INVALID

LOGGER = logger.get_logger(__name__)

class CasefoldPath(tuple[str, ...]):
    def __new__(cls, path: PurePath) -> Self:
        if path == PurePath('.'):
            iter = ()
        else:
            iter = map(str.casefold, path.parts)
        return super().__new__(cls, iter)

    def is_prefix_of(self, other: Self) -> bool:
        return len(self) <= len(other) and self == other[:len(self)]

    def __str__(self) -> str:
        if len(self) == 0:
            return "."
        else:
            return '/'.join(self)

class AmbiguousPathError(ValueError):
    path: CasefoldPath

    def __init__(self, path: CasefoldPath) -> None:
        self.path = path
        super().__init__(path)

    def __str__(self) -> str:
        return f'Casefolded path "{self.path}" is ambiguous'

class CaseInsensitiveFs(FileSystem[Path]):
    # note: assumes fs structure does not change
    _index: dict[CasefoldPath, Path]

    def __init__(self, path: StringPath) -> None:
        abs_path = Path(path).resolve()
        self._index = {}

        for dirpath, dirnames, filenames in abs_path.walk():
            reldir = dirpath.relative_to(abs_path)
            for file in filenames:
                true_path = dirpath / file
                case_path = CasefoldPath(reldir / file)
                if case_path in self._index:
                    existing_path = self._index[case_path]
                    LOGGER.warning('casefolded path ambiguity: "{}" vs "{}"! Checking if files identical...', existing_path, true_path)
                    
                    if not filecmp.cmp(existing_path, true_path):
                        raise AmbiguousPathError(case_path)
                else:
                    self._index[case_path] = true_path
        
        super().__init__(str(abs_path))

    def _resolve_path(self, path: str) -> CasefoldPath:
        abs_path = Path(self.path, path).resolve()

        try:
            return CasefoldPath(abs_path.relative_to(self.path))
        except ValueError:
            raise RootEscapeError(self.path, path) from None

    def _lookup(self, path: CasefoldPath) -> Path:
        try:
            return self._index[path]
        except KeyError:
            raise FileNotFoundError(path) from None
    
    def walk_folder(self, folder: str = '') -> Iterator[File[Self]]:
        case_folder = self._resolve_path(folder)

        for case_path, true_path in self._index.items():
            if case_folder.is_prefix_of(case_path):
                yield File(self, str(case_path), true_path)

    def open_str(self, name: str | File[Self], encoding: str = 'utf8') -> TextIO:
        if isinstance(name, File):
            path = self._get_data(name)
        else:
            path = self._lookup(self._resolve_path(name))

        return path.open(encoding=encoding)

    def open_bin(self, name: str | File[Self]) -> BinaryIO:
        if isinstance(name, File):
            path = self._get_data(name)
        else:
            path = self._lookup(self._resolve_path(name))

        return path.open(mode='rb')

    def _get_file(self, name: str) -> File[Self]:
        case_path = self._resolve_path(name)
        path = self._lookup(case_path)

        return File(self, str(case_path), path)

    def _get_cache_key(self, file: File[Self]) -> int:
        """Our cache key is the last modification time."""
        try:
            return self._get_data(file).stat().st_mtime_ns
        except FileNotFoundError:
            return CACHE_KEY_INVALID
        