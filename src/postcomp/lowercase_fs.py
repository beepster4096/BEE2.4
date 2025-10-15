"""hack added in fork for linux"""

from srctools.filesys import RawFileSystem

class ForceLowercaseRawFileSystem(RawFileSystem):
    def _resolve_path(self, path: str) -> str:
        return super()._resolve_path(path.lower())
