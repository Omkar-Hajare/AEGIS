import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL } from "../config.js";

export const options = {
  stages: [
    { duration: "10s", target: 10 },
    { duration: "5s", target: 100 },
    { duration: "30s", target: 100 },
    { duration: "5s", target: 10 },
    { duration: "10s", target: 0 },
  ],

  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const SLEEP_SECONDS =
  __ENV.SLEEP_SECONDS !== undefined
    ? parseFloat(__ENV.SLEEP_SECONDS)
    : 0.01;

export default function () {
  // Generate a unique product key for every iteration.
  // This creates cache misses and forces backend/origin work.
  const productId = `${__VU}-${__ITER}`;
  const path = `/data/product/${productId}`;

  const response = http.get(`${BASE_URL}${path}`, {
    tags: {
      name: "/data/product/{product_id}",
    },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  if (SLEEP_SECONDS > 0) {
    sleep(SLEEP_SECONDS);
  }
}