import http from "k6/http";
import { check, sleep } from "k6";
import exec from "k6/execution";
import { BASE_URL } from "../config.js";

export const options = {
  stages: [
    { duration: "10s", target: 50 },
    { duration: "30s", target: 50 },
    { duration: "30s", target: 100 },
    { duration: "10s", target: 20 },
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

function randomProduct(start, end) {
  return Math.floor(Math.random() * (end - start + 1)) + start;
}

export default function () {
  const startTime = Number(exec.scenario.startTime);
  const elapsed = (Date.now() - startTime) / 1000;

  let productId;
  const random = Math.random();

  if (elapsed < 40) {
    // First phase: Group A is popular
    if (random < 0.70) {
      productId = randomProduct(1, 10);
    } else if (random < 0.90) {
      productId = randomProduct(11, 20);
    } else {
      productId = randomProduct(21, 50);
    }
  } else {
    // Second phase: Group B becomes popular
    if (random < 0.20) {
      productId = randomProduct(1, 10);
    } else if (random < 0.90) {
      productId = randomProduct(11, 20);
    } else {
      productId = randomProduct(21, 50);
    }
  }

  const path = `/data/product/${productId}`;

  const response = http.get(`${BASE_URL}${path}`, {
    tags: {
      name: "/data/product/{product_id}",
    },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  sleep(SLEEP_SECONDS);
}