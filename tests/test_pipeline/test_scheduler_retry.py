"""Tests for run_pipeline_with_retry in scheduler.py.

Verifies that the retry wrapper:
- Calls run_pipeline once on success (no retry)
- Retries once on urllib HTTP 503 and succeeds on retry
- Retries once on urllib URLError (timeout) and succeeds on retry
- Retries once on socket.timeout and succeeds on retry
- Does NOT retry on 404 or other HTTP status codes
- Does NOT retry on non-urllib exceptions (e.g., ValueError)
- Propagates the exception if the retry also fails
- Sleeps 900 seconds between original call and retry
"""
import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.scheduler import run_pipeline_with_retry


@pytest.fixture
def fake_artifacts():
    return {"model": MagicMock()}


@pytest.fixture
def fake_pool():
    return MagicMock()


def make_http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://statsapi.mlb.com/",
        code=code,
        msg=f"HTTP Error {code}",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )


class TestRunPipelineWithRetry:
    def test_success_no_retry(self, fake_artifacts, fake_pool):
        """Happy path: run_pipeline succeeds, no retry, sleep never called."""
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.return_value = None
            run_pipeline_with_retry("pre_lineup", fake_artifacts, fake_pool)

        mock_run.assert_called_once_with("pre_lineup", fake_artifacts, fake_pool)
        mock_sleep.assert_not_called()

    def test_503_retries_once_and_succeeds(self, fake_artifacts, fake_pool):
        """503 HTTPError triggers sleep(900) then a single retry."""
        err = make_http_error(503)
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.side_effect = [err, None]
            run_pipeline_with_retry("post_lineup", fake_artifacts, fake_pool)

        assert mock_run.call_count == 2
        mock_sleep.assert_called_once_with(900)

    def test_url_error_retries_once_and_succeeds(self, fake_artifacts, fake_pool):
        """urllib URLError (e.g. connection timeout) triggers retry."""
        err = urllib.error.URLError(reason="timed out")
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.side_effect = [err, None]
            run_pipeline_with_retry("confirmation", fake_artifacts, fake_pool)

        assert mock_run.call_count == 2
        mock_sleep.assert_called_once_with(900)

    def test_socket_timeout_retries_once_and_succeeds(self, fake_artifacts, fake_pool):
        """socket.timeout triggers retry."""
        err = socket.timeout("timed out")
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.side_effect = [err, None]
            run_pipeline_with_retry("pre_lineup", fake_artifacts, fake_pool)

        assert mock_run.call_count == 2
        mock_sleep.assert_called_once_with(900)

    def test_503_retry_also_fails_propagates(self, fake_artifacts, fake_pool):
        """If retry also raises, the exception propagates out."""
        err = make_http_error(503)
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep"):
            mock_run.side_effect = [err, err]
            with pytest.raises(urllib.error.HTTPError):
                run_pipeline_with_retry("pre_lineup", fake_artifacts, fake_pool)

        assert mock_run.call_count == 2

    def test_404_does_not_retry(self, fake_artifacts, fake_pool):
        """Non-503 HTTP errors are NOT retried."""
        err = make_http_error(404)
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.side_effect = err
            with pytest.raises(urllib.error.HTTPError):
                run_pipeline_with_retry("pre_lineup", fake_artifacts, fake_pool)

        mock_run.assert_called_once()
        mock_sleep.assert_not_called()

    def test_value_error_does_not_retry(self, fake_artifacts, fake_pool):
        """Non-network exceptions are NOT retried."""
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep") as mock_sleep:
            mock_run.side_effect = ValueError("bad data")
            with pytest.raises(ValueError):
                run_pipeline_with_retry("pre_lineup", fake_artifacts, fake_pool)

        mock_run.assert_called_once()
        mock_sleep.assert_not_called()

    def test_url_error_retry_also_fails_propagates(self, fake_artifacts, fake_pool):
        """If URLError retry also fails, exception propagates."""
        err = urllib.error.URLError(reason="timed out")
        with patch("src.pipeline.scheduler.run_pipeline") as mock_run, \
             patch("src.pipeline.scheduler.time.sleep"):
            mock_run.side_effect = [err, err]
            with pytest.raises(urllib.error.URLError):
                run_pipeline_with_retry("post_lineup", fake_artifacts, fake_pool)

        assert mock_run.call_count == 2
