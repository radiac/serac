from .base import Storage


class Local(Storage):
    path: str

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        return {
            'path': config.get('path', ''),
        }

    def __init__(self, path: str) -> None:
        if not path:
            raise ValueError('Local storage requires a path')

        self.path = path
