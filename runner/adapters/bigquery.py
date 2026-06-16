"""
BigQuery-backed evidence adapter.

google-cloud-bigquery is an optional dependency. The adapter only
imports it at construction time so the runner can be installed without
it for sqlite-only deployments.

Authentication uses Application Default Credentials (gcloud auth
application-default login, or a service-account JSON via
GOOGLE_APPLICATION_CREDENTIALS).
"""
from __future__ import annotations

from typing import Any

from .base import EvidenceAdapter


def _named_to_at(sql: str) -> str:
    """
    Translate ":name" placeholders (the runner's convention) to BigQuery's
    "@name" parameter syntax. Inside string literals we don't translate.
    """
    out = []
    i = 0
    n = len(sql)
    in_str = None
    while i < n:
        ch = sql[i]
        if in_str:
            out.append(ch)
            if ch == in_str and sql[i - 1] != "\\":
                in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == ":" and i + 1 < n and (sql[i + 1].isalpha() or sql[i + 1] == "_"):
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            name = sql[i + 1:j]
            out.append("@" + name)
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class BigQueryAdapter(EvidenceAdapter):
    """
    BigQuery adapter. Constructed from a config block of the form:

        evidence_store:
          type: bigquery
          project: my-gcp-project
          dataset: gate_evidence
          location: EU                # optional
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        location: str | None = None,
    ) -> None:
        try:
            from google.cloud import bigquery  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "BigQueryAdapter requires google-cloud-bigquery. "
                "Install it with: pip install google-cloud-bigquery"
            ) from exc
        self._bigquery = bigquery
        self._client = bigquery.Client(project=project, location=location)
        self._project = project
        self._dataset = dataset
        self._location = location

    @classmethod
    def from_config(cls, evidence_store: dict[str, Any]) -> "BigQueryAdapter":
        try:
            project = evidence_store["project"]
            dataset = evidence_store["dataset"]
        except KeyError as exc:
            raise ValueError(
                "BigQuery evidence_store requires 'project' and 'dataset'"
            ) from exc
        return cls(
            project=project,
            dataset=dataset,
            location=evidence_store.get("location"),
        )

    def _scoped_sql(self, sql: str) -> str:
        """
        Replace bare table references like `gate_tool_requests` with the
        fully-qualified `project.dataset.gate_tool_requests` form expected
        by BigQuery. We do this for any identifier prefixed with `gate_`
        so the same SQL works against the runner's logical schema regardless
        of project/dataset.
        """
        import re
        pattern = re.compile(r"(?<![\w.])gate_[A-Za-z0-9_]+")
        return pattern.sub(
            lambda m: f"`{self._project}.{self._dataset}.{m.group(0)}`",
            sql,
        )

    def _build_params(self, params: dict[str, Any] | None):
        if not params:
            return []
        out = []
        for name, value in params.items():
            # Best-effort type inference; BigQuery is strict so we keep this
            # simple and explicit for the runner's known parameter set.
            if isinstance(value, bool):
                param_type = "BOOL"
            elif isinstance(value, int):
                param_type = "INT64"
            elif isinstance(value, float):
                param_type = "FLOAT64"
            else:
                param_type = "STRING"
                value = str(value)
            out.append(self._bigquery.ScalarQueryParameter(name, param_type, value))
        return out

    def _execute(self, sql: str, params: dict[str, Any] | None):
        translated = _named_to_at(self._scoped_sql(sql))
        job_config = self._bigquery.QueryJobConfig(
            query_parameters=self._build_params(params),
        )
        return list(self._client.query(translated, job_config=job_config).result())

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self._execute(sql, params)
        return [dict(r.items()) for r in rows]

    def scalar(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        rows = self._execute(sql, params)
        if not rows:
            return None
        first = rows[0]
        return list(first.values())[0]
