"""Tool implementation over the TrioWorkspace SSH client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trioworkspace_client import SAFE_ID, TrioClient, TrioRemoteError
from trioworkspace_contracts import multipart, task_form


SUBMISSION_TOOLS = frozenset(
    {
        "trio_submit_mol2",
        "trio_submit_peptide",
        "trio_submit_protac",
        "trio_submit_ires",
        "trio_submit_dna",
    }
)

CAPABILITIES = {
    "engines": {
        "triomol2": {
            "contract": "triomol2.v1",
            "input": "receptor PDB, target name, exact pocket center/size, 1-10 candidates",
            "search_budgets": [100, 200, 500],
        },
        "triopep": {
            "contract": "triopep.v1",
            "input": "receptor PDB, distinct receptor/peptide chains, peptide length 4-20",
            "search_budgets": [4, 8, 16],
        },
        "trioprotac": {
            "contract": "trioprotac.v1",
            "input": "accepted target system brd4-8g46",
            "search_budgets": [8, 16, 32],
        },
        "trioires": {
            "contract": "trioires.v1",
            "input": "CrPV or PSIV family",
            "search_budgets": [1, 2, 4],
        },
        "triodna": {
            "contract": "triodna.v1",
            "input": "200-base reference, 1-indexed editable interval, accepted cell context",
            "cell_contexts": ["HepG2", "K562", "SK-N-SH"],
        },
    },
    "execution": {
        "asynchronous": True,
        "owner_isolated": True,
        "default_wall_clock_timeout": None,
        "remote_runtime": "doomx_3nd:/work/doomx/TrioWorkspace",
    },
}


class TrioTools:
    def __init__(self, client: TrioClient, project_root: Path):
        self.client = client
        self.project_root = project_root

    def call(self, name: str, arguments: Any) -> Any:
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if name == "trio_capabilities":
            _empty(arguments)
            return CAPABILITIES
        if name == "trio_health":
            _empty(arguments)
            return self.client.json("GET", "/healthz")
        if name == "trio_list_tasks":
            _empty(arguments)
            result = self.client.json("GET", "/v1/tasks")
            if not isinstance(result, dict) or not isinstance(result.get("tasks"), list):
                raise TrioRemoteError("TrioWorkspace task list is malformed")
            return result
        if name == "trio_get_task":
            task_id = _only_id(arguments, "task_id")
            return self._task(task_id)
        if name == "trio_download_artifact":
            if set(arguments) != {"task_id", "artifact_id"}:
                raise ValueError("download requires exactly task_id and artifact_id")
            task_id = _id(arguments["task_id"], "task_id")
            artifact_id = _id(arguments["artifact_id"], "artifact_id")
            task = self._task(task_id)
            artifacts = task.get("artifacts")
            if not isinstance(artifacts, list):
                raise TrioRemoteError("TrioWorkspace task artifacts are malformed")
            matches = [item for item in artifacts if isinstance(item, dict) and item.get("id") == artifact_id]
            if len(matches) != 1:
                raise TrioRemoteError("artifact is not present on the owned task")
            return self.client.download(task_id, matches[0])
        if name in SUBMISSION_TOOLS:
            fields, files = task_form(name, arguments, self.project_root)
            content_type, body = multipart(fields, files)
            task = self.client.json("POST", "/v1/tasks", body=body, content_type=content_type)
            if not isinstance(task, dict) or task.get("engine") != fields["engine"]:
                raise TrioRemoteError("TrioWorkspace submission response is malformed")
            return task
        raise ValueError(f"unknown TrioWorkspace tool: {name}")

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.client.json("GET", f"/v1/tasks/{task_id}")
        if not isinstance(task, dict) or task.get("id") != task_id:
            raise TrioRemoteError("TrioWorkspace task response is malformed")
        return task


def _empty(arguments: dict[str, Any]) -> None:
    if arguments:
        raise ValueError("this tool accepts no arguments")


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


def _only_id(arguments: dict[str, Any], name: str) -> str:
    if set(arguments) != {name}:
        raise ValueError(f"tool requires exactly {name}")
    return _id(arguments[name], name)


def text_result(value: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            }
        ],
        "isError": False,
    }
