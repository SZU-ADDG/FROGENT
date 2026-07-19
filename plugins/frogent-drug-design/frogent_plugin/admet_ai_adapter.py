"""Lazy in-process adapter for the optional ADMET-AI v2 package."""

import importlib
import importlib.metadata
from collections.abc import Mapping

from .admet_execution import ADMETBatchPrediction


class ADMETAIAdapter:
    provider_id = "admet-ai"
    model_name = "ADMETModel"

    def __init__(self, model_factory=None, *, model_version: str = "") -> None:
        self._factory = model_factory
        self._model = None
        self._version = model_version

    @property
    def model_version(self) -> str:
        return self._version or "unavailable-until-load"

    def predict(self, smiles: tuple[str, ...]) -> ADMETBatchPrediction:
        if not isinstance(smiles, tuple) or not smiles or any(
                not isinstance(value, str) or not value.strip() for value in smiles):
            raise ValueError("ADMET-AI inputs must be non-empty SMILES")
        model = self._load()
        output = model.predict(smiles=list(smiles))
        return ADMETBatchPrediction(smiles, _rows(output, smiles))

    def _load(self):
        if self._model is not None:
            return self._model
        if self._factory is None:
            module = importlib.import_module("admet_ai")
            self._factory = getattr(module, "ADMETModel")
            self._version = _package_version(module)
        self._model = self._factory()
        if not self._version:
            self._version = "injected"
        return self._model


def _rows(output, inputs):
    if isinstance(output, Mapping):
        if len(inputs) != 1:
            raise ValueError("ADMET-AI mapping output cannot represent a batch")
        return (output,)
    index = getattr(output, "index", None)
    converter = getattr(output, "to_dict", None)
    if index is None or not callable(converter) or tuple(index) != inputs:
        raise ValueError("ADMET-AI output index does not match requested SMILES order")
    rows = converter(orient="records")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise TypeError("ADMET-AI output rows are malformed")
    return tuple(rows)


def _package_version(module):
    try:
        return importlib.metadata.version("admet-ai")
    except importlib.metadata.PackageNotFoundError:
        value = getattr(module, "__version__", "unknown")
        return value if isinstance(value, str) and value.strip() else "unknown"
