"""HTTP client for the smk-executor service."""

import logging
from collections.abc import Iterator
from http import HTTPStatus

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class SmkExecutorClient:
    """Talks to smk-executor over HTTP using httpx."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, json=json, timeout=timeout)
        except httpx.ConnectError as e:
            raise HTTPException(503, "smk-executor service is unreachable") from e
        except httpx.TimeoutException as e:
            raise HTTPException(504, "smk-executor request timed out") from e

        if response.status_code == HTTPStatus.NOT_FOUND:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Job not found on smk-executor")
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            detail = response.text[:500]
            raise HTTPException(502, f"smk-executor error: {detail}")

        return response.json()

    def health_check(self) -> dict:
        return self._request("GET", "/health")

    def list_jobs(self) -> list[dict]:
        """Fetch all jobs."""
        result = self._request("GET", "/jobs")
        return result.get("jobs", [])

    def submit_job(self, payload: dict) -> dict:
        return self._request("POST", "/jobs", json=payload)

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}")

    def get_job_outputs(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}/outputs")

    def cancel_job(self, job_id: str) -> dict:
        return self._request("POST", f"/jobs/{job_id}/cancel")

    def delete_job(self, job_id: str) -> dict:
        return self._request("DELETE", f"/jobs/{job_id}")

    def _proxy_stream(self, path: str) -> Iterator[bytes]:
        """Forward a streaming response without buffering.

        Status is checked eagerly before yielding so that HTTP errors
        propagate as exceptions before StreamingResponse starts writing.
        """
        url = f"{self.base_url}{path}"
        try:
            client = httpx.Client(timeout=None)  # noqa: S113
            response = client.send(client.build_request("GET", url), stream=True)
        except httpx.ConnectError as e:
            raise HTTPException(503, "smk-executor service is unreachable") from e

        if response.status_code == HTTPStatus.NOT_FOUND:
            response.close()
            client.close()
            raise HTTPException(HTTPStatus.NOT_FOUND, "Not found on smk-executor")
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            response.close()
            client.close()
            raise HTTPException(502, "smk-executor streaming error")

        def generate() -> Iterator[bytes]:
            try:
                yield from response.iter_bytes()
            finally:
                response.close()
                client.close()

        return generate()

    def subscribe_job_logs(self, job_id: str) -> Iterator[bytes]:
        """Subscribe to live SSE log stream (open connection)."""
        return self._proxy_stream(f"/jobs/{job_id}/logs")

    def download_job_output(self, job_id: str, path: str) -> Iterator[bytes]:
        """Download an output file without buffering into memory."""
        return self._proxy_stream(f"/jobs/{job_id}/outputs/{path}")
