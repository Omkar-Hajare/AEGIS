import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL } from "../config.js";

export const options = {
  stages: [
    { duration: "10s", target: 10 },
    { duration: "40s", target: 10 },
    { duration: "10s", target: 20 },
    { duration: "40s", target: 20 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function selectProduct() {
  const r = Math.random();

  // Hot: 60% of requests, only 100 objects
  if (r < 0.60) {
    return randomInt(1, 100);
  }

  // Warm: 25%, 900 objects
  if (r < 0.85) {
    return randomInt(101, 1000);
  }

  // Cold: 10%, 4000 objects
  if (r < 0.95) {
    return randomInt(1001, 5000);
  }

  // Very cold: 5%
  return randomInt(5001, 10000);
}

export default function () {
  const productId = selectProduct();
  const path = `/data/product/${productId}`;

  const response = http.get(`${BASE_URL}${path}`, {
    tags: {
      name: "/data/product/{product_id}",
    },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  // Small think time between requests
  sleep(0.05);
}