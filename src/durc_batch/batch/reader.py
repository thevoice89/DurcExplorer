"""Sorgenti dei codici fiscali (Strategy pattern)."""
import csv
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from durc_batch.core.logging_conf import get_logger

logger = get_logger(__name__)


class CodiceFiscaleReader(ABC):
    """Interfaccia per qualsiasi sorgente di codici fiscali."""

    @abstractmethod
    def read(self) -> Iterator[str]:
        """Itera i codici fiscali validati (uno per elemento)."""
        raise NotImplementedError


class CsvCodiceFiscaleReader(CodiceFiscaleReader):
    """Legge i codici fiscali da un file CSV."""

    def __init__(self, path: Path, column: str = "codice_fiscale") -> None:
        """Memorizza percorso file e nome della colonna contenente i CF."""
        self._path = Path(path)
        self._column = column

    def read(self) -> Iterator[str]:
        """Yield dei CF dal CSV, scartando righe vuote/duplicate."""
        seen: set[str] = set()
        # utf-8-sig per tollerare l'eventuale BOM dei file esportati da Excel.
        with self._path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or self._column not in reader.fieldnames:
                raise ValueError(
                    f"Colonna '{self._column}' assente in {self._path} "
                    f"(colonne trovate: {reader.fieldnames})")
            for row in reader:
                codice = (row.get(self._column) or "").strip()
                if not codice or codice in seen:
                    continue
                seen.add(codice)
                yield codice
        logger.info("Letti %d codici fiscali univoci da %s", len(seen), self._path)
