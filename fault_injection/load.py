#!/usr/bin/env python3
"""
Load Generator Script for LLM-Assisted Cloud Incident Response Demo

Generates load against Service A to:
1. Trigger resource exhaustion alarms (high Duration)
2. Test throttling scenario (reserved concurrency = 1)
3. Produce realistic metrics for the incident response pipeline

Usage:
    python fault_injection/load.py --url https://xxx.execute-api.ap-south-1.amazonaws.com/Prod/start \
        --rate 10 --duration 60 --concurrency 5
"""

import argparse
import json
import logging
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LoadGenerator:
    def __init__(self, url: str, rate: float, duration: int, concurrency: int, timeout: int = 10):
        self.url = url
        self.rate = rate  # requests per second
        self.duration = duration  # seconds
        self.concurrency = concurrency
        self.timeout = timeout
        self.results = []
        self.start_time = None
        self.stop_event = threading.Event()
        
    def _make_request(self, request_id: int) -> dict:
        """Make a single HTTP request and return result."""
        start = time.perf_counter()
        req = Request(self.url, method="GET")
        
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return {
                    "request_id": request_id,
                    "status": status,
                    "latency_ms": latency_ms,
                    "success": 200 <= status < 300,
                    "error": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except HTTPError as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "request_id": request_id,
                "status": e.code,
                "latency_ms": latency_ms,
                "success": False,
                "error": f"HTTP {e.code}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except (URLError, TimeoutError, OSError) as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "request_id": request_id,
                "status": 0,
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    
    def _worker(self, worker_id: int):
        """Worker that makes requests at the specified rate."""
        interval = 1.0 / (self.rate / self.concurrency) if self.rate > 0 else 0
        request_id = 0
        
        while not self.stop_event.is_set():
            if time.time() - self.start_time >= self.duration:
                break
                
            req_id = f"{worker_id}-{request_id}"
            result = self._make_request(req_id)
            self.results.append(result)
            request_id += 1
            
            # Log progress periodically
            if request_id % 10 == 0:
                logger.info(f"Worker {worker_id}: completed {request_id} requests")
            
            if interval > 0:
                time.sleep(interval)
    
    def run(self) -> dict:
        """Run the load test and return summary statistics."""
        logger.info(f"Starting load test: url={self.url}, rate={self.rate}/s, "
                   f"duration={self.duration}s, concurrency={self.concurrency}")
        
        self.start_time = time.time()
        self.stop_event.clear()
        
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = [executor.submit(self._worker, i) for i in range(self.concurrency)]
            for future in as_completed(futures):
                future.result()
        
        elapsed = time.time() - self.start_time
        
        # Calculate statistics
        total_requests = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        failed = total_requests - successful
        latencies = [r["latency_ms"] for r in self.results if r["latency_ms"] > 0]
        
        latencies.sort()
        p50 = latencies[len(latencies) // 2] if latencies else 0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        status_codes = {}
        for r in self.results:
            status_codes[r["status"]] = status_codes.get(r["status"], 0) + 1
        
        summary = {
            "url": self.url,
            "elapsed_seconds": round(elapsed, 2),
            "total_requests": total_requests,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total_requests * 100, 2) if total_requests > 0 else 0,
            "actual_rps": round(total_requests / elapsed, 2) if elapsed > 0 else 0,
            "latency_ms": {
                "avg": round(avg_latency, 2),
                "p50": round(p50, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
            },
            "status_codes": status_codes,
            "errors": [r["error"] for r in self.results if r["error"]],
        }
        
        logger.info(json.dumps(summary, indent=2))
        return summary


def main():
    parser = argparse.ArgumentParser(description="Load generator for Service A")
    parser.add_argument("--url", required=True, help="Service A URL (e.g., https://xxx.execute-api.region.amazonaws.com/Prod/start)")
    parser.add_argument("--rate", type=float, default=10, help="Requests per second (total across all workers)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    generator = LoadGenerator(
        url=args.url,
        rate=args.rate,
        duration=args.duration,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    
    try:
        summary = generator.run()
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump({
                    "summary": summary,
                    "results": generator.results,
                }, f, indent=2)
            logger.info(f"Results written to {args.output}")
        
        # Exit with error code if success rate is too low
        if summary["success_rate"] < 50:
            logger.warning("Success rate below 50%")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Load test interrupted")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Load test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()