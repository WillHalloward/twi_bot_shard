"""HTTP client utility module.

This module provides a shared HTTP client for making HTTP requests,
with connection pooling and other optimizations.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

import aiohttp
from aiohttp import ClientResponse, ClientSession, ClientTimeout, TraceConfig


class RateLimiter:
    """Rate limiter for HTTP requests.

    This class implements a token bucket rate limiter to prevent overwhelming
    external services with too many requests in a short period of time.
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        per_domain_limits: dict[str, tuple[float, int]] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_second: Default number of requests allowed per second.
            burst_size: Default maximum burst size (token bucket capacity).
            per_domain_limits: Dictionary mapping domains to (requests_per_second, burst_size) tuples.
            logger: Logger instance to use for logging.
        """
        self.default_rate = requests_per_second
        self.default_burst = burst_size
        self.per_domain_limits = per_domain_limits or {}
        self.logger = logger or logging.getLogger("rate_limiter")

        # Token buckets for each domain: {domain: (tokens, last_refill_time)}
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

        # Queues for waiting requests when rate limited
        self._waiting_requests: defaultdict[str, list[asyncio.Future]] = defaultdict(
            list
        )

    async def acquire(self, domain: str) -> None:
        """Acquire a token for a request to the specified domain.

        This method will block until a token is available.

        Args:
            domain: The domain to acquire a token for.
        """
        async with self._lock:
            # Get rate limits for this domain
            rate, burst = self.per_domain_limits.get(
                domain, (self.default_rate, self.default_burst)
            )

            # Initialize bucket if not exists
            if domain not in self._buckets:
                self._buckets[domain] = (burst, time.time())

            # Refill the bucket
            tokens, last_refill = self._buckets[domain]
            now = time.time()
            elapsed = now - last_refill
            tokens = min(burst, tokens + elapsed * rate)

            # If we have a token, consume it and return immediately
            if tokens >= 1:
                self._buckets[domain] = (tokens - 1, now)
                return

            # Calculate wait time until next token
            wait_time = (1 - tokens) / rate
            self._buckets[domain] = (0, now)

            # Create a future to wait on
            future = asyncio.Future()
            self._waiting_requests[domain].append(future)

            self.logger.debug(f"Rate limited for {domain}, waiting {wait_time:.2f}s")

        # Schedule token release
        asyncio.create_task(self._release_token(domain, wait_time))

        # Wait for our turn
        await future

    async def _release_token(self, domain: str, wait_time: float) -> None:
        """Release a token after the specified wait time.

        Args:
            domain: The domain to release a token for.
            wait_time: Time to wait before releasing the token.
        """
        await asyncio.sleep(wait_time)

        async with self._lock:
            # Update the bucket
            tokens, last_refill = self._buckets[domain]
            now = time.time()
            elapsed = now - last_refill
            rate, burst = self.per_domain_limits.get(
                domain, (self.default_rate, self.default_burst)
            )
            tokens = min(burst, tokens + elapsed * rate)

            # If we have waiting requests and tokens, release one
            if self._waiting_requests[domain] and tokens >= 1:
                future = self._waiting_requests[domain].pop(0)
                if not future.done():
                    future.set_result(None)

                # Update bucket
                self._buckets[domain] = (tokens - 1, now)

                self.logger.debug(f"Released token for {domain}")


class CircuitBreaker:
    """Circuit breaker implementation for HTTP requests.

    This class implements the circuit breaker pattern to prevent repeated calls
    to failing endpoints, allowing them time to recover.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening the circuit.
            recovery_timeout: Time in seconds to wait before trying again.
            logger: Logger instance to use for logging.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.logger = logger or logging.getLogger("circuit_breaker")
        self._failures: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._open_circuits: dict[str, bool] = {}

    def is_open(self, endpoint: str) -> bool:
        """Check if the circuit is open for an endpoint.

        Args:
            endpoint: The endpoint to check.

        Returns:
            True if the circuit is open, False otherwise.
        """
        if endpoint not in self._open_circuits or not self._open_circuits[endpoint]:
            return False

        # Check if recovery timeout has passed
        if (
            time.time() - self._last_failure_time.get(endpoint, 0)
            > self.recovery_timeout
        ):
            self.logger.info(
                f"Circuit for {endpoint} is half-open, allowing a test request"
            )
            self._open_circuits[endpoint] = False
            return False

        return True

    def record_success(self, endpoint: str) -> None:
        """Record a successful request to an endpoint.

        Args:
            endpoint: The endpoint that was successfully called.
        """
        self._failures[endpoint] = 0
        self._open_circuits[endpoint] = False

    def record_failure(self, endpoint: str) -> None:
        """Record a failed request to an endpoint.

        Args:
            endpoint: The endpoint that failed.
        """
        self._failures[endpoint] = self._failures.get(endpoint, 0) + 1
        self._last_failure_time[endpoint] = time.time()

        if self._failures[endpoint] >= self.failure_threshold:
            if not self._open_circuits.get(endpoint, False):
                self.logger.warning(
                    f"Circuit opened for {endpoint} after {self._failures[endpoint]} failures"
                )
                self._open_circuits[endpoint] = True


class HTTPClient:
    """HTTP client utility class with connection pooling.

    This class provides a shared aiohttp ClientSession that can be reused
    across the application, improving performance by reusing connections.
    Features include:
    - Connection pooling
    - Request retries with exponential backoff
    - Circuit breaker pattern for failing endpoints
    - Detailed request metrics
    """

    def __init__(
        self,
        timeout: int = 30,
        max_connections: int = 100,
        max_keepalive_connections: int = 30,
        keepalive_timeout: int = 60,
        retry_attempts: int = 3,
        retry_start_timeout: float = 0.1,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
        max_concurrent_requests: int = 100,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            timeout: Default timeout for requests in seconds.
            max_connections: Maximum number of connections to keep in the pool.
            max_keepalive_connections: Maximum number of connections to keep alive.
            keepalive_timeout: Time in seconds to keep connections alive.
            retry_attempts: Maximum number of retry attempts for failed requests.
            retry_start_timeout: Initial timeout in seconds for retry backoff.
            circuit_breaker: Circuit breaker instance to use.
            rate_limiter: Rate limiter instance to use.
            max_concurrent_requests: Maximum number of concurrent requests allowed.
            logger: Logger instance to use for logging.
        """
        self.timeout = timeout
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_timeout = keepalive_timeout
        self.retry_attempts = retry_attempts
        self.retry_start_timeout = retry_start_timeout
        self.circuit_breaker = circuit_breaker or CircuitBreaker(logger=logger)
        self.rate_limiter = rate_limiter or RateLimiter(logger=logger)
        self.max_concurrent_requests = max_concurrent_requests
        self.logger = logger or logging.getLogger("http_client")
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._stats = {
            "requests": 0,
            "errors": 0,
            "timeouts": 0,
            "retries": 0,
            "circuit_breaks": 0,
            "rate_limited": 0,
            "backpressure_applied": 0,
            "request_times": [],  # List of request times in seconds
            "status_codes": {},  # Count of responses by status code
            "endpoints": {},  # Stats by endpoint
        }

    async def get_session(self) -> ClientSession:
        """Get the shared ClientSession, creating it if it doesn't exist.

        Returns:
            The shared aiohttp ClientSession.
        """
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    # Create trace config for request timing
                    trace_config = TraceConfig()

                    async def on_request_start(
                        session, trace_config_ctx, params
                    ) -> None:
                        trace_config_ctx.start = time.time()

                    async def on_request_end(session, trace_config_ctx, params) -> None:
                        if hasattr(trace_config_ctx, "start"):
                            duration = time.time() - trace_config_ctx.start
                            self._stats["request_times"].append(duration)
                            # Keep only the last 1000 request times
                            if len(self._stats["request_times"]) > 1000:
                                self._stats["request_times"] = self._stats[
                                    "request_times"
                                ][-1000:]

                    trace_config.on_request_start.append(on_request_start)
                    trace_config.on_request_end.append(on_request_end)

                    connector = aiohttp.TCPConnector(
                        limit=self.max_connections,
                        limit_per_host=self.max_keepalive_connections,
                        ttl_dns_cache=300,  # Cache DNS results for 5 minutes
                        enable_cleanup_closed=True,
                        keepalive_timeout=self.keepalive_timeout,
                    )
                    timeout = ClientTimeout(total=self.timeout)
                    self._session = ClientSession(
                        connector=connector,
                        timeout=timeout,
                        raise_for_status=False,
                        trace_configs=[trace_config],
                    )
                    self.logger.debug(
                        f"Created new HTTP client session with max_connections={self.max_connections}, "
                        f"max_keepalive_connections={self.max_keepalive_connections}, "
                        f"keepalive_timeout={self.keepalive_timeout}s"
                    )
        return self._session

    async def get_fresh_session(self) -> ClientSession:
        """Get a fresh ClientSession for operations that need guaranteed availability.
        This creates a new session each time to avoid race conditions with cleanup.

        Returns:
            A new aiohttp ClientSession that the caller is responsible for closing.
        """
        # Create trace config for request timing
        trace_config = TraceConfig()

        async def on_request_start(session, trace_config_ctx, params) -> None:
            trace_config_ctx.start = time.time()

        async def on_request_end(session, trace_config_ctx, params) -> None:
            if hasattr(trace_config_ctx, "start"):
                duration = time.time() - trace_config_ctx.start
                self._stats["request_times"].append(duration)
                if len(self._stats["request_times"]) > 1000:
                    self._stats["request_times"] = self._stats["request_times"][-1000:]

        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)

        connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=self.max_keepalive_connections,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            keepalive_timeout=self.keepalive_timeout,
        )
        timeout = ClientTimeout(total=self.timeout)

        return ClientSession(
            connector=connector,
            timeout=timeout,
            raise_for_status=False,
            trace_configs=[trace_config],
        )

    async def get_session_with_retry(self, max_retries: int = 1) -> ClientSession:
        """Get session with automatic retry on session closed errors.

        This method provides a simple interface for other parts of the codebase
        that need resilience against session closure issues without the full
        complexity of the webhook manager.

        Args:
            max_retries: Maximum number of retries on session errors

        Returns:
            A ClientSession that should work properly

        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(max_retries + 1):
            try:
                session = await self.get_session()
                # Test that the session is usable
                if session and not session.closed:
                    return session
                else:
                    raise aiohttp.ClientError("Session is closed or None")
            except Exception as e:
                error_msg = str(e).lower()
                if (
                    "session is closed" in error_msg or "cannot reuse" in error_msg
                ) and attempt < max_retries:
                    self.logger.warning(
                        f"Session error on attempt {attempt + 1}/{max_retries + 1}: {e}, retrying..."
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))  # Brief backoff
                    continue
                else:
                    # Either not a session error, or we've exhausted retries
                    raise

    async def close(self) -> None:
        """Close the shared ClientSession."""
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.debug("Closed HTTP client session")

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        retry_for_statuses: list[int] = None,
        no_circuit_breaker: bool = False,
        no_rate_limit: bool = False,
        **kwargs,
    ) -> ClientResponse:
        """Make a GET request with retry, circuit breaker, and rate limiting support.

        Args:
            url: URL to request.
            params: Query parameters.
            headers: HTTP headers.
            timeout: Request timeout in seconds.
            retry_for_statuses: HTTP status codes to retry for (default: 5xx).
            no_circuit_breaker: If True, bypass the circuit breaker.
            no_rate_limit: If True, bypass the rate limiter.
            **kwargs: Additional arguments to pass to the request.

        Returns:
            The response from the server.
        """
        # Extract domain for circuit breaker and rate limiter
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Apply backpressure using semaphore
        try:
            # Try to acquire semaphore without waiting if we're at capacity
            if not self._request_semaphore.locked():
                await asyncio.wait_for(self._request_semaphore.acquire(), 0.01)
            else:
                self._stats["backpressure_applied"] += 1
                self.logger.debug(
                    f"Backpressure applied for GET {url}, waiting for semaphore"
                )
                await self._request_semaphore.acquire()
        except TimeoutError:
            # If we can't acquire immediately, count it and wait
            self._stats["backpressure_applied"] += 1
            self.logger.debug(
                f"Backpressure applied for GET {url}, waiting for semaphore"
            )
            await self._request_semaphore.acquire()

        try:
            # Check circuit breaker
            if not no_circuit_breaker and self.circuit_breaker.is_open(domain):
                self._stats["circuit_breaks"] += 1
                self.logger.warning(
                    f"Circuit breaker open for {domain}, request blocked"
                )
                raise aiohttp.ClientError(f"Circuit breaker open for {domain}")

            # Apply rate limiting
            if not no_rate_limit:
                try:
                    # Acquire rate limiting token
                    await self.rate_limiter.acquire(domain)
                except Exception as e:
                    self._stats["rate_limited"] += 1
                    self.logger.warning(f"Rate limiting error for {domain}: {str(e)}")
                    raise

            # Set default retry status codes if not provided
            if retry_for_statuses is None:
                retry_for_statuses = [500, 502, 503, 504]

            session = await self.get_session()
            request_timeout = ClientTimeout(total=timeout or self.timeout)

            # Update endpoint stats
            if domain not in self._stats["endpoints"]:
                self._stats["endpoints"][domain] = {
                    "requests": 0,
                    "errors": 0,
                    "timeouts": 0,
                    "retries": 0,
                    "rate_limited": 0,
                    "backpressure_applied": 0,
                }
            self._stats["endpoints"][domain]["requests"] += 1
            self._stats["requests"] += 1

            # Retry logic with exponential backoff
            retry_count = 0
            retry_timeout = self.retry_start_timeout

            while True:
                try:
                    response = await session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=request_timeout,
                        **kwargs,
                    )

                    # Update status code stats
                    status = str(response.status)
                    self._stats["status_codes"][status] = (
                        self._stats["status_codes"].get(status, 0) + 1
                    )

                    # Check if we should retry based on status code
                    if (
                        response.status in retry_for_statuses
                        and retry_count < self.retry_attempts
                    ):
                        retry_count += 1
                        self._stats["retries"] += 1
                        self._stats["endpoints"][domain]["retries"] = (
                            self._stats["endpoints"][domain].get("retries", 0) + 1
                        )
                        self.logger.warning(
                            f"Retrying GET {url} due to status {response.status} "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    # Record success for circuit breaker if status is good
                    if response.status < 500:
                        self.circuit_breaker.record_success(domain)
                    else:
                        self.circuit_breaker.record_failure(domain)

                    return response

                except TimeoutError:
                    self._stats["timeouts"] += 1
                    self._stats["endpoints"][domain]["timeouts"] = (
                        self._stats["endpoints"][domain].get("timeouts", 0) + 1
                    )
                    self.logger.warning(f"Request timed out: GET {url}")

                    # Retry on timeout if attempts remain
                    if retry_count < self.retry_attempts:
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying GET {url} after timeout "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    raise

                except Exception as e:
                    self._stats["errors"] += 1
                    self._stats["endpoints"][domain]["errors"] = (
                        self._stats["endpoints"][domain].get("errors", 0) + 1
                    )
                    self.logger.error(f"Error making request: GET {url} - {str(e)}")

                    # Retry on certain exceptions if attempts remain
                    if retry_count < self.retry_attempts and isinstance(
                        e,
                        aiohttp.ClientConnectorError
                        | aiohttp.ServerDisconnectedError
                        | aiohttp.ClientOSError,
                    ):
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying GET {url} after error: {str(e)} "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    raise
        finally:
            # Always release the semaphore
            self._request_semaphore.release()

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        retry_for_statuses: list[int] = None,
        no_circuit_breaker: bool = False,
        no_rate_limit: bool = False,
        **kwargs,
    ) -> ClientResponse:
        """Make a POST request with retry, circuit breaker, and rate limiting support.

        Args:
            url: URL to request.
            data: Form data to send.
            json: JSON data to send.
            headers: HTTP headers.
            timeout: Request timeout in seconds.
            retry_for_statuses: HTTP status codes to retry for (default: 5xx).
            no_circuit_breaker: If True, bypass the circuit breaker.
            no_rate_limit: If True, bypass the rate limiter.
            **kwargs: Additional arguments to pass to the request.

        Returns:
            The response from the server.
        """
        # Extract domain for circuit breaker and rate limiter
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Apply backpressure using semaphore
        try:
            # Try to acquire semaphore without waiting if we're at capacity
            if not self._request_semaphore.locked():
                await asyncio.wait_for(self._request_semaphore.acquire(), 0.01)
            else:
                self._stats["backpressure_applied"] += 1
                self.logger.debug(
                    f"Backpressure applied for POST {url}, waiting for semaphore"
                )
                await self._request_semaphore.acquire()
        except TimeoutError:
            # If we can't acquire immediately, count it and wait
            self._stats["backpressure_applied"] += 1
            self.logger.debug(
                f"Backpressure applied for POST {url}, waiting for semaphore"
            )
            await self._request_semaphore.acquire()

        try:
            # Check circuit breaker
            if not no_circuit_breaker and self.circuit_breaker.is_open(domain):
                self._stats["circuit_breaks"] += 1
                self.logger.warning(
                    f"Circuit breaker open for {domain}, request blocked"
                )
                raise aiohttp.ClientError(f"Circuit breaker open for {domain}")

            # Apply rate limiting
            if not no_rate_limit:
                try:
                    # Acquire rate limiting token
                    await self.rate_limiter.acquire(domain)
                except Exception as e:
                    self._stats["rate_limited"] += 1
                    self.logger.warning(f"Rate limiting error for {domain}: {str(e)}")
                    raise

            # Set default retry status codes if not provided
            if retry_for_statuses is None:
                retry_for_statuses = [500, 502, 503, 504]

            session = await self.get_session()
            request_timeout = ClientTimeout(total=timeout or self.timeout)

            # Update endpoint stats
            if domain not in self._stats["endpoints"]:
                self._stats["endpoints"][domain] = {
                    "requests": 0,
                    "errors": 0,
                    "timeouts": 0,
                    "retries": 0,
                    "rate_limited": 0,
                    "backpressure_applied": 0,
                }
            self._stats["endpoints"][domain]["requests"] += 1
            self._stats["requests"] += 1

            # Retry logic with exponential backoff
            retry_count = 0
            retry_timeout = self.retry_start_timeout

            while True:
                try:
                    response = await session.post(
                        url,
                        data=data,
                        json=json,
                        headers=headers,
                        timeout=request_timeout,
                        **kwargs,
                    )

                    # Update status code stats
                    status = str(response.status)
                    self._stats["status_codes"][status] = (
                        self._stats["status_codes"].get(status, 0) + 1
                    )

                    # Check if we should retry based on status code
                    if (
                        response.status in retry_for_statuses
                        and retry_count < self.retry_attempts
                    ):
                        retry_count += 1
                        self._stats["retries"] += 1
                        self._stats["endpoints"][domain]["retries"] = (
                            self._stats["endpoints"][domain].get("retries", 0) + 1
                        )
                        self.logger.warning(
                            f"Retrying POST {url} due to status {response.status} "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    # Record success for circuit breaker if status is good
                    if response.status < 500:
                        self.circuit_breaker.record_success(domain)
                    else:
                        self.circuit_breaker.record_failure(domain)

                    return response

                except TimeoutError:
                    self._stats["timeouts"] += 1
                    self._stats["endpoints"][domain]["timeouts"] = (
                        self._stats["endpoints"][domain].get("timeouts", 0) + 1
                    )
                    self.logger.warning(f"Request timed out: POST {url}")

                    # Retry on timeout if attempts remain
                    if retry_count < self.retry_attempts:
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying POST {url} after timeout "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    raise

                except Exception as e:
                    self._stats["errors"] += 1
                    self._stats["endpoints"][domain]["errors"] = (
                        self._stats["endpoints"][domain].get("errors", 0) + 1
                    )
                    self.logger.error(f"Error making request: POST {url} - {str(e)}")

                    # Retry on certain exceptions if attempts remain
                    if retry_count < self.retry_attempts and isinstance(
                        e,
                        aiohttp.ClientConnectorError
                        | aiohttp.ServerDisconnectedError
                        | aiohttp.ClientOSError,
                    ):
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying POST {url} after error: {str(e)} "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    raise
        finally:
            # Always release the semaphore
            self._request_semaphore.release()

    async def download_file(
        self,
        url: str,
        file_path: str,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        chunk_size: int = 8192,
        retry_for_statuses: list[int] = None,
        no_circuit_breaker: bool = False,
        no_rate_limit: bool = False,
    ) -> bool:
        """Download a file from a URL with retry, circuit breaker, and rate limiting support.

        Args:
            url: URL to download from.
            file_path: Path to save the file to.
            headers: HTTP headers.
            timeout: Request timeout in seconds.
            chunk_size: Size of chunks to download.
            retry_for_statuses: HTTP status codes to retry for (default: 5xx).
            no_circuit_breaker: If True, bypass the circuit breaker.
            no_rate_limit: If True, bypass the rate limiter.

        Returns:
            True if the download was successful, False otherwise.
        """
        # Extract domain for circuit breaker and rate limiter
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Apply backpressure using semaphore
        try:
            # Try to acquire semaphore without waiting if we're at capacity
            if not self._request_semaphore.locked():
                await asyncio.wait_for(self._request_semaphore.acquire(), 0.01)
            else:
                self._stats["backpressure_applied"] += 1
                self.logger.debug(
                    f"Backpressure applied for download {url}, waiting for semaphore"
                )
                await self._request_semaphore.acquire()
        except TimeoutError:
            # If we can't acquire immediately, count it and wait
            self._stats["backpressure_applied"] += 1
            self.logger.debug(
                f"Backpressure applied for download {url}, waiting for semaphore"
            )
            await self._request_semaphore.acquire()

        try:
            # Check circuit breaker
            if not no_circuit_breaker and self.circuit_breaker.is_open(domain):
                self._stats["circuit_breaks"] += 1
                self.logger.warning(
                    f"Circuit breaker open for {domain}, download blocked"
                )
                return False

            # Apply rate limiting
            if not no_rate_limit:
                try:
                    # Acquire rate limiting token
                    await self.rate_limiter.acquire(domain)
                except Exception as e:
                    self._stats["rate_limited"] += 1
                    self.logger.warning(f"Rate limiting error for {domain}: {str(e)}")
                    return False

            # Set default retry status codes if not provided
            if retry_for_statuses is None:
                retry_for_statuses = [500, 502, 503, 504]

            session = await self.get_session()
            request_timeout = ClientTimeout(total=timeout or self.timeout)

            # Update endpoint stats
            if domain not in self._stats["endpoints"]:
                self._stats["endpoints"][domain] = {
                    "requests": 0,
                    "errors": 0,
                    "timeouts": 0,
                    "retries": 0,
                    "rate_limited": 0,
                    "backpressure_applied": 0,
                }
            self._stats["endpoints"][domain]["requests"] += 1
            self._stats["requests"] += 1

            # Retry logic with exponential backoff
            retry_count = 0
            retry_timeout = self.retry_start_timeout

            while True:
                try:
                    async with session.get(
                        url, headers=headers, timeout=request_timeout
                    ) as response:
                        # Update status code stats
                        status = str(response.status)
                        self._stats["status_codes"][status] = (
                            self._stats["status_codes"].get(status, 0) + 1
                        )

                        # Check if we should retry based on status code
                        if (
                            response.status in retry_for_statuses
                            and retry_count < self.retry_attempts
                        ):
                            retry_count += 1
                            self._stats["retries"] += 1
                            self._stats["endpoints"][domain]["retries"] = (
                                self._stats["endpoints"][domain].get("retries", 0) + 1
                            )
                            self.logger.warning(
                                f"Retrying download {url} due to status {response.status} "
                                f"(attempt {retry_count}/{self.retry_attempts})"
                            )
                            await asyncio.sleep(retry_timeout)
                            retry_timeout *= 2  # Exponential backoff
                            continue

                        if response.status != 200:
                            self.logger.warning(
                                f"Failed to download file: {url} - Status: {response.status}"
                            )
                            self.circuit_breaker.record_failure(domain)
                            return False

                        # Download the file
                        with open(file_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(
                                chunk_size
                            ):
                                f.write(chunk)

                        self.circuit_breaker.record_success(domain)
                        return True

                except TimeoutError:
                    self._stats["timeouts"] += 1
                    self._stats["endpoints"][domain]["timeouts"] = (
                        self._stats["endpoints"][domain].get("timeouts", 0) + 1
                    )
                    self.logger.warning(f"Download timed out: {url}")

                    # Retry on timeout if attempts remain
                    if retry_count < self.retry_attempts:
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying download {url} after timeout "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    return False

                except Exception as e:
                    self._stats["errors"] += 1
                    self._stats["endpoints"][domain]["errors"] = (
                        self._stats["endpoints"][domain].get("errors", 0) + 1
                    )
                    self.logger.error(f"Error downloading file: {url} - {str(e)}")

                    # Retry on certain exceptions if attempts remain
                    if retry_count < self.retry_attempts and isinstance(
                        e,
                        aiohttp.ClientConnectorError
                        | aiohttp.ServerDisconnectedError
                        | aiohttp.ClientOSError,
                    ):
                        retry_count += 1
                        self._stats["retries"] += 1
                        self.logger.warning(
                            f"Retrying download {url} after error: {str(e)} "
                            f"(attempt {retry_count}/{self.retry_attempts})"
                        )
                        await asyncio.sleep(retry_timeout)
                        retry_timeout *= 2  # Exponential backoff
                        continue

                    self.circuit_breaker.record_failure(domain)
                    return False
        finally:
            # Always release the semaphore
            self._request_semaphore.release()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the HTTP client.

        Returns:
            A dictionary with statistics.
        """
        stats = self._stats.copy()

        # Calculate some additional metrics if we have request times
        if stats.get("request_times"):
            times = stats["request_times"]
            stats["avg_request_time"] = sum(times) / len(times)
            stats["min_request_time"] = min(times)
            stats["max_request_time"] = max(times)
            # Calculate 95th percentile
            sorted_times = sorted(times)
            idx = int(len(sorted_times) * 0.95)
            stats["p95_request_time"] = sorted_times[idx]

        return stats

    def get_endpoint_stats(self, endpoint: str | None = None) -> dict[str, Any]:
        """Get statistics for a specific endpoint or all endpoints.

        Args:
            endpoint: The endpoint to get statistics for, or None for all endpoints.

        Returns:
            A dictionary with endpoint statistics.
        """
        if endpoint:
            return self._stats.get("endpoints", {}).get(endpoint, {}).copy()
        return self._stats.get("endpoints", {}).copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "requests": 0,
            "errors": 0,
            "timeouts": 0,
            "retries": 0,
            "circuit_breaks": 0,
            "rate_limited": 0,
            "backpressure_applied": 0,
            "request_times": [],
            "status_codes": {},
            "endpoints": {},
        }
